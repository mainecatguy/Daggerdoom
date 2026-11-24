"""Encounter card 6: Civil War factions, run in UZDoom alone (no Daggerfall).

usage: civilwar_test.py war STANCES NAME            100 against 100 on an open test map (zscript/CivilWarTest.zs)
       civilwar_test.py save STANCES NAME           the same, saved at tic 245 (7 s, mid-war), then loaded and run to the end
       civilwar_test.py check NAME...               prints the DDWARTEST lines and the pass/fail checks

STANCES is army A's Thing_Hate stance then army B's (3 hunt, 1 untilshot, 5 ignore), e.g. 31.
The test map is generated into the review folder; game data stays out of the repo.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
sys.path.insert(0, str(WORKTREE / "tools" / "monster_deaths"))
import monster_deaths as md  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\civilwar")
UZ = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-encounters\Release\uzdoom.exe")
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
FATAL = ("Script error", "VM execution aborted", "Unhandled exception", "Execution could not continue", "FATAL")
STANCE = {3: "hunt", 1: "untilshot", 5: "ignore"}


def make_map():
    """One open 4096 x 4096 room with a player start at the south."""
    REVIEW.mkdir(parents=True, exist_ok=True)
    s = 2048
    text = 'namespace = "zdoom";\n'
    for x, y in ((-s, -s), (-s, s), (s, s), (s, -s)):
        text += f"vertex {{ x = {x}.0; y = {y}.0; }}\n"
    for i in range(4):
        text += f"linedef {{ v1 = {i}; v2 = {(i + 1) % 4}; sidefront = {i}; blocking = true; }}\n"
        text += 'sidedef { sector = 0; texturemiddle = "STONE2"; }\n'
    text += 'sector { heightfloor = 0; heightceiling = 512; texturefloor = "FLAT5"; textureceiling = "F_SKY1"; lightlevel = 224; }\n'
    text += "thing { x = 0.0; y = -1000.0; angle = 90; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }\n"
    path = REVIEW / "civilwar_map.wad"
    md.write_wad(path, [("MAP01", b""), ("TEXTMAP", text.encode()), ("ENDMAP", b"")])
    return path


def launch(name, stances, extra, timeout=45):
    REVIEW.mkdir(parents=True, exist_ok=True)
    log = REVIEW / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    wad = make_map()
    args = [str(UZ), "-iwad", IWAD, "-file", str(wad), str(WORKTREE / "mods" / "doomerfall" / "src"), "-noactivate", "-nosound", "-noautoload",
            "-config", str(REVIEW / "civilwar.ini"), "-skill", "3", "+logfile", name, "+vid_fullscreen", "0", "+i_pauseinbackground", "0",
            "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+set", "dd_civilwar_test", str(stances), *extra]
    code = subprocess.call([sys.executable, QUIET, "--timeout", str(timeout), "--cwd", str(REVIEW), "--", *args],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    fatal = [k for k in FATAL if k in body]
    print(f"{name}: exit {code}, log {len(body)} bytes, fatal {fatal or 'none'}, done {'DDWARTEST done' in body}")
    return body


def war(stances, name):
    launch(name, stances, ["-ddtestquit", "1000", "+map", "MAP01"])


def save(stances, name):
    zds = REVIEW / "doom.id.doom2.commercial" / f"{name}.zds"   # save_dir gets a per-game subfolder
    zds.unlink(missing_ok=True)
    # The save command refuses a full Windows path, so save by name into save_dir.
    launch(name + "-save", stances, ["+set", "save_dir", REVIEW.as_posix(), "-ddtestsave", "245", name, "-ddtestquit", "270", "+map", "MAP01"])
    print(f"  save file {zds.name} exists {zds.exists()}")
    launch(name, stances, ["+set", "save_dir", REVIEW.as_posix(), "-ddtestquit", "1000", "-loadgame", zds.name])   # relative to save_dir


def lines(name, key):
    p = REVIEW / f"log-{name}.txt"
    body = p.read_text(errors="replace") if p.exists() else ""
    return [ln for ln in body.splitlines() if ln.startswith(key)]


def check(name):
    for ln in lines(name, "DDWAR"):
        print(" ", ln)
    body = "\n".join(lines(name, "DDWAR"))
    armies = {a: dict(zip(("stance", "killed", "before", "retaliated", "sametarget", "samedamage", "cross", "toplayer"), map(int, g)))
              for a, *g in re.findall(r"DDWARTEST army (\w) stance (\d) killed (\d+) targeted-player-before-shot (\d+) shot-retaliated (\d) same-army-target (\d+) "
                                      r"same-army-damage (\d+) cross-damage (\d+) damage-to-player (\d+)", body)}
    if not armies:
        print(f"  {name}: no summary")
        return
    ok = True
    for a, r in armies.items():
        st = r["stance"]
        verdict = []
        if r["cross"] <= 0:
            verdict.append("FAIL no cross-army damage")
        if r["sametarget"] or r["samedamage"]:
            verdict.append(f"note same-army target {r['sametarget']} damage {r['samedamage']}")
        if st == 1 and r["before"]:
            verdict.append("FAIL untilshot targeted the player before being shot")
        if st == 1 and not r["retaliated"]:
            verdict.append("FAIL untilshot did not answer the shot")
        if st == 5 and (r["before"] or r["retaliated"]):
            verdict.append("FAIL ignore targeted the player")
        if st == 3 and not (r["before"] or r["toplayer"]):
            verdict.append("note hunt never targeted the player before the shot")
        ok &= not any(v.startswith("FAIL") for v in verdict)
        print(f"  army {a} ({STANCE.get(st, st)}): {'; '.join(verdict) or 'ok'}")
    bad = [ln for ln in lines(name, "DDWARTEST state") if re.search(r"bad-(species|hate|flags) [1-9]", ln)]
    if bad:
        ok = False
        print("  FAIL rig state:", *bad, sep="\n    ")
    end = "\n".join(lines(name, "DDWARTEST state end"))
    if "ended 1 winner 0" not in end:
        ok = False
        print("  FAIL the watcher did not end the war with army A the winner")
    if not re.search(r"survivors-targeted-player-after-wipe [1-9]", body):
        print("  note no survivor targeted the player after the wipe")
    print(f"  {name}: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "war":
        war(sys.argv[2], sys.argv[3])
        check(sys.argv[3])
    elif cmd == "save":
        save(sys.argv[2], sys.argv[3])
        for ln in lines(sys.argv[3] + "-save", "DDWARTEST state"):
            print("  (before save)", ln)
        check(sys.argv[3])
    elif cmd == "check":
        for n in sys.argv[2:]:
            check(n)
    else:
        sys.exit(__doc__)
