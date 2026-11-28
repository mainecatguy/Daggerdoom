"""Exact "which gun fired this" (UZDoom/src/dd_shotsource.cpp + DoomerfallShots.zs) with two guns firing into one pack.

usage: python quiet_run.py --timeout 900 -- python tools/gunsource/gunsource_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The harness (gunsource_test.zs) holds gun A's bomb still inside a pack, right where gun B's bomb throws its fragments,
fires gun B into the pack, then lets A's bomb go while B's fragments fly. Runs DOOM.WAD E1M1 against a fake Daggerfall
peer:
  stock     doomerfall.pk3: two harness guns, each with its own family (bomb -> blast + fragments -> blasts).
  drla      play_drlax.bat's DRLA set: the harness pair again, then RLClusterBombLauncher (A) and RLRocketLauncher (B).
  nobridge  no Daggerfall character: nothing is tagged.
Every tag must name its own gun, and must come from the exact spawner (by fired/child), never the nearest-thing guess.
"""
import re, subprocess, sys, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "shottag"))
sys.path.insert(0, str(REPO / "tools" / "automatics"))
from automatics_test import Peer, MODS, DRLA, BAD  # noqa: E402
from shottag_test import launch  # noqa: E402

TAG = re.compile(r"shots: tag (\S+) gun (\S+) skill (-?\d+) gen (\d+) tic (\d+) by (\S+)")
HIT = re.compile(r"GUNSRC hit inf=(\S+) found=(\d) gen=(-?\d+) gun=(\S+) held=(\S+) tic=(\d+)")


def analyse(name, lines, check):
    check(name, "no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check(name, "finished", any("AUTOTEST done" in l for l in lines))
    check(name, "no stuck case", not any("GUNSRC stuck" in l or "GUNSRC noshot" in l or "GUNSRC nogun" in l for l in lines),
          [l for l in lines if "GUNSRC stuck" in l or "noshot" in l or "nogun" in l][:3])
    cases, cur = {}, None
    for l in lines:
        if m := re.search(r"GUNSRC case (\S+) (\S+)", l):
            cur = (m.group(1), m.group(2))
            cases[cur] = {"tags": [], "hits": [], "held": 0}
        elif cur and "GUNSRC end" in l:
            cur = None
        elif cur and (m := re.search(r"GUNSRC held (\d+)", l)):
            cases[cur]["held"] = int(m.group(1))
        elif cur and (m := TAG.search(l)):
            cases[cur]["tags"].append(m)
        elif cur and (m := HIT.search(l)):
            cases[cur]["hits"].append(m)
    check(name, "cases ran", bool(cases), list(cases))
    for (a, b), d in cases.items():
        c = f"{a}+{b}"
        tags, hits = d["tags"], d["hits"]
        check(name, f"{c}: gun A's shot held in the pack", d["held"] > 0, d["held"])
        guns = {t.group(2) for t in tags}
        check(name, f"{c}: both guns' shots were tagged", {a, b} <= guns, guns)
        near = [t.group(0) for t in tags if t.group(6) not in ("fired", "child")]
        check(name, f"{c}: {len(tags)} tags, all from the exact spawner", tags and not near, near[:3])
        by_class = {}
        for t in tags:
            by_class.setdefault(t.group(1), set()).add(t.group(2))
        both = {k: v for k, v in by_class.items() if len(v) > 1}
        check(name, f"{c}: no class tagged under both guns", not both, both)
        print(f"  {name} {c}: " + ", ".join(f"{k}->{'/'.join(sorted(v))}" for k, v in sorted(by_class.items())))
        if a == "GunSrcGunA":
            wrong = [t.group(0) for t in tags if {"A": a, "B": b}.get(t.group(1)[-1]) != t.group(2)]
            check(name, f"{c}: every tag names its own family's gun", tags and not wrong, wrong[:3])
            fragsB = [t for t in tags if t.group(1) == "GunSrcFragB"]
            check(name, f"{c}: B's fragments, born beside A's held bomb, carry gun B", len(fragsB) == 2 and all(t.group(2) == b for t in fragsB),
                  [t.group(0) for t in fragsB])
            gens = {(t.group(1)[-1], int(t.group(4))) for t in tags}
            check(name, f"{c}: generations 0, 1 and 2 for both guns", {(x, g) for x in "AB" for g in (0, 1, 2)} <= gens, sorted(gens))
            badhit = [h.group(0) for h in hits if h.group(2) != "1" or {"A": a, "B": b}.get(h.group(1)[-1]) != h.group(4)]
            infl = {h.group(1) for h in hits}
            check(name, f"{c}: {len(hits)} hits, each credited to its own gun", hits and not badhit, badhit[:3])
            check(name, f"{c}: both guns' fragments' blasts hit the pack", {"GunSrcBlastA", "GunSrcBlastB"} <= infl, infl)
        else:
            badhit = [h.group(0) for h in hits if h.group(2) != "1" or h.group(4) not in (a, b)]
            check(name, f"{c}: {len(hits)} hits, all found and credited to one of the two guns", hits and not badhit, badhit[:3])
            hitguns = {}
            for h in hits:
                hitguns.setdefault(h.group(1), set()).add(h.group(4))
            print(f"  {name} {c} hits: " + ", ".join(f"{k}->{'/'.join(sorted(v))}" for k, v in sorted(hitguns.items())))
            check(name, f"{c}: no inflictor class credited to both guns", not any(len(v) > 1 for v in hitguns.values()), hitguns)
    return cases


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    only = sys.argv[4:]
    work.mkdir(parents=True, exist_ok=True)
    (work / "saves").mkdir(exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "autotest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("gunsource_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "GunSourceTest" }\n')
    results = []

    def check(name, label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {detail if not ok else ''}", flush=True)

    stock = [mod, harness]
    drla = [MODS / n for n in DRLA] + stock
    for name, files in (("stock", stock), ("drla", drla)):
        if only and name not in only:
            continue
        peer = Peer(dll)
        try:
            lines = launch(exe, work, files, peer, name, 90 if name == "stock" else 240, ["+map", "E1M1"])
        finally:
            peer.close()
        analyse(name, lines, check)
    if not only or "nobridge" in only:
        nb = launch(exe, work, stock, None, "nobridge", 60, ["+map", "E1M1"])
        check("nobridge", "no tags without a Daggerfall character", not any("shots: tag" in l for l in nb) and any("nosheet" in l for l in nb))
    failed = results.count(False)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
