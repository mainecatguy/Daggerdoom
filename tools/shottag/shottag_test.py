"""Shot tags (mods/doomerfall/src/zscript/DoomerfallShots.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/shottag/shottag_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [runs]

The harness (shottag_test.zs) fires one shot per gun at a target, holds the shot's projectiles still until the player
holds the fist, then lets them fly; every hit logs the tag behind it. Runs DOOM.WAD E1M1:
  stock     doomerfall.pk3: the stock Rocket Launcher's rocket and splash, and a harness rocket whose death spawns an
            explosion actor and fragments that explode in turn (generations 0, 1 and 2).
  drla      play_drlax.bat's DRLA set: RLRocketLauncher, RLClusterBombLauncher (bomb -> exploders -> explosions),
            RLShrapnelCannon (a spray of ripping shrapnel).
  save/load stock and DRLA: a rocket frozen in flight after the switch to the fist is autosaved; a fresh Doom loads
            the save, the rocket keeps its tag, flies and hits with the launcher's tag.
  nobridge  no Daggerfall character: nothing is tagged.
Every hit must name the gun that fired the shot, never the fist held when it lands.
"""
import re, subprocess, sys, time, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "automatics"))
from automatics_test import Peer, IWAD, MODS, DRLA, BAD  # noqa: E402

HIT = re.compile(r"SHOTTEST hit inf=(\S+) found=(\d) gen=(-?\d+) gun=(\S+) skill=(-?\d+) held=(\S+) dmg=(\d+)")
SKILL = {"RocketLauncher": 6, "RLRocketLauncher": 6, "RLClusterBombLauncher": 6, "RLShrapnelCannon": 6}  # rocket ammo: Explosive (DoomerfallWeaponCategory)


def launch(exe, work, files, peer, name, timeout, extra):
    out = work / f"{name}.out"
    args = [str(exe), "-iwad", str(IWAD), "-file", *map(str, files), "-config", str(work / f"{name}.ini"), "-savedir",
            str(work / "saves"), "-nosound", "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0",
            "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height",
            "200", "-skill", "3", "+set", "dd_perklog", "1", *extra]
    if peer:
        args += ["-dfbridge", peer.id, "-dfbridgelog", str(work / f"{name}-bridge.log")]
    with open(out, "wb") as f:
        p = subprocess.Popen(args, cwd=work, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while p.poll() is None and time.monotonic() < deadline:
                if peer:
                    peer.pump()
                time.sleep(0.004)
                text = out.read_text(errors="replace")
                if "AUTOTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def analyse(name, lines, check):
    check(name, "no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check(name, "finished", any("AUTOTEST done" in l for l in lines))
    cases, cur = {}, None
    for l in lines:
        if m := re.search(r"SHOTTEST case (\S+) ?(\S*)", l):
            cur = (m.group(1) + (" " + m.group(2) if m.group(2) else "")).strip()
            cases[cur] = {"gun": m.group(1), "hits": [], "release": None}
        elif cur and (m := re.search(r"SHOTTEST release n=(\d+) held=(\S+)", l)):
            cases[cur]["release"] = (int(m.group(1)), m.group(2))
        elif cur and (h := HIT.search(l)):
            cases[cur]["hits"].append(h)
    for c, d in cases.items():
        gun, hits = d["gun"], d["hits"]
        check(name, f"{c}: shot held until the fist was up", d["release"] is not None and d["release"][0] > 0 and d["release"][1].endswith("Fist"), d["release"])
        bad = [h.group(0) for h in hits if h.group(2) != "1" or h.group(4) != gun or int(h.group(5)) != SKILL[gun] or not h.group(6).endswith("Fist")]
        check(name, f"{c}: {len(hits)} hits, all name {gun} (skill {SKILL[gun]}) while the fist is held", hits and not bad, bad[:3])
        infl = {h.group(1) for h in hits}
        gens = {int(h.group(3)) for h in hits}
        print(f"  {name} {c}: inflictors {sorted(infl)} generations {sorted(gens)}")
        if c == "RocketLauncher ShotTestBomb":
            check(name, f"{c}: bomb (gen 0), its blast and fragments (gen 1) and the fragments' blasts (gen 2) all hit",
                  {"ShotTestBomb", "ShotTestBlast", "ShotTestFrag"} <= infl and {0, 1, 2} <= gens, (infl, gens))
        if gun == "RLClusterBombLauncher":
            check(name, f"{c}: the bomb's exploders' explosions (generation 2) hit with the tag",
                  any(i.startswith("RLClusterBombExplosion") for i in infl) and 2 in gens, (infl, gens))
        if gun == "RLShrapnelCannon":
            check(name, f"{c}: several ripping shrapnel hits", len(hits) >= 3 and all(i.startswith("RLShrapnelCannonShrapnel") for i in infl), infl)
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
        z.write(Path(__file__).with_name("shottag_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ShotTagTest" }\n')
        z.writestr("cvarinfo.txt", 'server noarchive string shottest_mode = "";\n')
    results = []

    def check(name, label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {detail if not ok else ''}", flush=True)

    drla = [MODS / n for n in DRLA] + [mod, harness]
    stock = [mod, harness]
    for name, files in (("stock", stock), ("drla", drla)):
        if only and name not in only:
            continue
        peer = Peer(dll)
        try:
            lines = launch(exe, work, files, peer, name, 90 if name == "stock" else 240, ["+map", "E1M1"])
        finally:
            peer.close()
        analyse(name, lines, check)
    for name, files in (("stocksave", stock), ("drlasave", drla)):
        if only and name not in only:
            continue
        saves = work / "saves"
        for old in saves.glob("*.zds"):
            old.unlink()
        peer = Peer(dll)
        try:
            lines = launch(exe, work, files, peer, name, 90 if name == "stocksave" else 240, ["+map", "E1M1", "+set", "shottest_mode", "save"])
        finally:
            peer.close()
        check(name, "no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
        check(name, "rocket frozen in flight and saved", any("SHOTTEST saved" in l for l in lines) and any(re.search(r"saving frozen=[1-9]", l) for l in lines))
        found = sorted(saves.glob("*.zds"), key=lambda p: p.stat().st_mtime)
        check(name, "an autosave was written", bool(found), list(saves.iterdir()))
        if not found:
            continue
        peer = Peer(dll)
        try:
            lines = launch(exe, work, files, peer, name + "-load", 90 if name == "stocksave" else 240, ["+load", found[-1].name])
        finally:
            peer.close()
        gun = "RLRocketLauncher" if name == "drlasave" else "RocketLauncher"
        inflight = [l for l in lines if "SHOTTEST inflight" in l]
        check(name, f"loaded: the rocket in flight keeps its {gun} tag", inflight and all(f"tag={gun} " in l + " " for l in inflight), inflight[:3])
        lines_case = ["SHOTTEST case " + gun] + lines  # the case line was printed before the save
        cases = analyse(name + "-load", lines_case, check)
    nb = [] if only and "nobridge" not in only else launch(exe, work, stock, None, "nobridge", 60, ["+map", "E1M1"])
    if nb:
        check("nobridge", "no tags without a Daggerfall character", not any("shots: tag" in l for l in nb) and any("nosheet" in l for l in nb))
    failed = results.count(False)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
