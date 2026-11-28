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

TAG = re.compile(r"shots: tag (\S+) gun (\S+) skill (-?\d+) gen (-?\d+) tic (\d+) by (\S+)( carrier)?")
HIT = re.compile(r"GUNSRC hit inf=(\S+) found=(\d) gen=(-?\d+) gun=(\S+) held=(\S+) tic=(\d+)")
SPAWN = re.compile(r"GUNSRC spawned (\S+) gun=(\S+) gen=(-?\d+) carrier=(\d) missile=(\d) puff=(\d) root=(\S+)")
# Real (non-carrier) tags per harness family in one case: bomb, 3 blasts, 2 fragments, 3 sparks, 3 embers; gun C's
# bullet makes one puff (a carrier) whose fragment gives fragment, blast, spark, ember.
FAMILY_TAGS = {"A": 12, "B": 12, "C": 4, "D": 12}
CARRIERS = {"GunSrcPuffC", "GunSrcHelperD"}


def analyse(name, lines, check):
    check(name, "no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check(name, "finished", any("AUTOTEST done" in l for l in lines))
    check(name, "no stuck case", not any("GUNSRC stuck" in l or "GUNSRC noshot" in l or "GUNSRC nogun" in l for l in lines),
          [l for l in lines if "GUNSRC stuck" in l or "noshot" in l or "nogun" in l][:3])
    cases, cur = {}, None
    for l in lines:
        if m := re.search(r"GUNSRC case (\S+) (\S+)", l):
            cur = (m.group(1), m.group(2))
            cases[cur] = {"tags": [], "hits": [], "spawned": [], "held": 0}
        elif cur and "GUNSRC end" in l:
            cur = None
        elif cur and (m := re.search(r"GUNSRC held (\d+)", l)):
            cases[cur]["held"] = int(m.group(1))
        elif cur and (m := TAG.search(l)):
            cases[cur]["tags"].append(m)
        elif cur and (m := HIT.search(l)):
            cases[cur]["hits"].append(m)
        elif cur and (m := SPAWN.search(l)):
            cases[cur]["spawned"].append(m)
    check(name, "cases ran", len(cases) >= 2, list(cases))
    for (a, b), d in cases.items():
        c = f"{a}+{b}"
        tags, hits, spawned = d["tags"], d["hits"], d["spawned"]
        real = [t for t in tags if not t.group(7)]
        guns = {t.group(2) for t in tags}
        check(name, f"{c}: both guns' shots were tagged", {a, b} <= guns, guns)
        # The nearest rule may still tag spawns that no gun's chain reaches (a barrel's napalm aimed at the player: the
        # old behaviour), never a class the guns' chains spawn.
        chain_classes = {x.group(1) for x in spawned if x.group(7) != "other"}
        near = [t.group(0) for t in tags if t.group(6) not in ("fired", "child", "carried") and t.group(1) in chain_classes]
        check(name, f"{c}: {len(tags)} tags; none of the guns' chains uses the nearest rule", tags and not near, near[:3])
        old = sorted({t.group(1) for t in tags if t.group(6) == "near"})
        if old:
            print(f"  {name} {c}: nearest-rule tags outside the guns' chains (unchanged old behaviour): {old}")
        # Done-when: every actor whose spawn chain (engine ground truth, logged by the harness) reaches a gun firing
        # in this case carries a tag naming that gun. Actors the chain does not tie to the player (DRLA's own world
        # helpers) are listed, not judged.
        shot = [s for s in spawned if s.group(7) != "other"]
        wrong = [s.group(0) for s in shot if s.group(2) != s.group(7)]
        check(name, f"{c}: all {len(shot)} actors the two guns' shots spawned carry their own gun's tag", shot and not wrong, wrong[:5])
        check(name, f"{c}: both guns are roots", {a, b} <= {s.group(7) for s in shot}, {s.group(7) for s in shot})
        other = sorted({s.group(1) for s in spawned if s.group(7) == "other"})
        if other:
            print(f"  {name} {c}: not from the guns (not judged): {other}")
        nearonly = {t.group(1) for t in tags if t.group(6) == "near"} - {t.group(1) for t in tags if t.group(6) != "near"}
        extra = [x.group(0) for x in spawned if x.group(7) == "other" and x.group(2) != "None" and x.group(1) not in nearonly]
        check(name, f"{c}: nothing outside the guns' spawn chains was tagged by the exact path", not extra, extra[:3])
        # Blood from the hits and an effect a damage handler spawns during a hit (like Energy's splash and burn burst)
        # appear and are nobody's shots.
        for kind in ("GunSrcBlood", "GunSrcSideFx"):
            k = [x for x in spawned if x.group(1) == kind]
            check(name, f"{c}: {len(k)} {kind} spawned during hits, none tagged or chained to a gun",
                  (k or kind == "GunSrcBlood") and all(x.group(2) == "None" and x.group(7) == "other" for x in k), [x.group(0) for x in k if x.group(2) != "None" or x.group(7) != "other"][:3])
        by_class = {}
        for s in shot:
            by_class.setdefault(s.group(1), set()).add(s.group(2))
        print(f"  {name} {c}: " + ", ".join(f"{k}->{'/'.join(sorted(v))}" for k, v in sorted(by_class.items())))
        if a.startswith("GunSrc"):
            fam = {"A": "GunSrcGunA", "B": "GunSrcGunB", "C": "GunSrcGunC", "D": "GunSrcGunD"}
            wrong = [s.group(0) for s in shot if fam.get(s.group(1)[-1]) != s.group(2)]
            check(name, f"{c}: every spawned actor carries its own family's gun", spawned and not wrong, wrong[:3])
            badcarrier = [s.group(0) for s in spawned if (s.group(4) == "1") != (s.group(1) in CARRIERS)]
            check(name, f"{c}: only the puff and the helper are carriers", not badcarrier, badcarrier[:3])
            for g in (a[-1], b[-1]):
                n = sum(1 for t in real if t.group(1)[-1] == g and t.group(2) == fam[g])
                check(name, f"{c}: gun {g}: {FAMILY_TAGS[g]} real tags expected, got {n}", n == FAMILY_TAGS[g], n)
                for kind in ("Spark", "Ember"):
                    k = [s for s in spawned if s.group(1) == f"GunSrc{kind}{g}"]
                    check(name, f"{c}: gun {g}: every {kind.lower()} (spawned without SXF_TRANSFERPOINTERS) carries gun {g}",
                          k and all(s.group(2) == fam[g] for s in k), [s.group(0) for s in k][:3])
            if a == "GunSrcGunA":
                check(name, f"{c}: gun A's shot held in the pack", d["held"] > 0, d["held"])
                fragsB = [t for t in real if t.group(1) == "GunSrcFragB"]
                check(name, f"{c}: B's fragments, born beside A's held bomb, carry gun B", len(fragsB) == 2 and all(t.group(2) == b for t in fragsB),
                      [t.group(0) for t in fragsB])
            gens = {(t.group(1)[-1], int(t.group(4))) for t in real}
            want = {"A": {0, 1, 2, 3}, "B": {0, 1, 2, 3}, "C": {1, 2, 3, 4}, "D": {0, 1, 2, 3}}
            check(name, f"{c}: generations", all(want[g] <= {x for f, x in gens if f == g} for g in (a[-1], b[-1])), sorted(gens))
            badhit = [h.group(0) for h in hits if h.group(1).startswith("GunSrc") and not h.group(1).startswith("GunSrcPuff")
                      and (h.group(2) != "1" or fam.get(h.group(1)[-1]) != h.group(4))]
            check(name, f"{c}: {len(hits)} hits, each credited to its own gun", hits and not badhit, badhit[:3])
        else:
            check(name, f"{c}: gun A's shot held in the pack", d["held"] > 0, d["held"])
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
