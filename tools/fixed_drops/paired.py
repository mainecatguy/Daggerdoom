"""Fixed drops with Daggerfall and Doom together, against an installed play folder (scripts/play/install.py).

usage: paired.py <play folder> assemble|fresh|save|load|compare [--area N] [--out <results folder name>]
  assemble  builds this lane's UZDoom, bridge and launcher and puts a play folder together (Unity must be built).
  fresh  a real New Game, arrive in Privateer's Hold, kill the monsters near the start, list the drops, take one gun.
  save   the same, but makes a bundled autosave just before the kill.
  load   loads the save run's autosave in fresh copies of both games and does the kill again.
  compare  checks that all three runs killed the same monsters, got the same drops, and took the same gun with the
           same Daggerfall material and floor id.
Wrap the whole script in quiet_run.py: it starts the launcher itself, so its window driver shares the games' desktop.
Config, saves and logs go to <play folder>/../fixed-drops-paired.
"""
import re
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "new_game"))
import run_new_game as ng  # noqa: E402  (its window-message driver for Daggerfall's creation screens)

DRLA = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
TIMEOUT = 240
TRY = [
    "Fixed drops (branch agent/fixeddrops). Saves and settings go to this folder's run folder.",
    " 1. New Game, clear the gunners at the Privateer's Hold start, note the guns and ammo they drop, take a gun (E), check its material in the inventory (I).",
    " 2. Quit, New Game with another character, do the same: the same drops, and the same gun has the same material.",
    " 3. Save before the fight, fight, note the drops, load, fight again: the same.",
    " 4. Drops still land where each monster dies; only what drops is fixed.",
]
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error")


def door_spot(play):
    """Privateer's Hold's dungeon door on DDT07154 (x y z nx ny), from the town cache's DDDOORS lump, as tools/dungeon_reentry."""
    path = play / "data" / "cache" / "T07154.ddt"
    if not path.exists():
        return "0, 0, 0, 1, 0"
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        lumps = {n: zlib.decompress(f.read(packed)) if raw else b"" for n, raw, packed in heads}
    door = next(l.split() for l in lumps["DDDOORS"].decode().splitlines() if l.split()[:1] == ["1"])
    return ", ".join(door[3:8])


def make_harness(out, name, play=None):
    harness = out / f"paired-{name}.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        text = (HERE / "paired.zs").read_text().replace("@MODE@", str({"fresh": 0, "save": 1, "load": 2, "travel": 3}[name.rstrip("0123456789")]))
        z.writestr("zscript.txt", text.replace("@DOOR@", door_spot(play) if play else "0, 0, 0, 1, 0"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PDHarness" }\n')
    return harness


def compile_check(play, out):
    """UZDoom alone with the play mods and the harness, -norun: 1337 means everything compiled."""
    data = play / "data"
    files = DRLA + [data / n for n in DATA] + [play / "dfitems.pk3", play / "doomerfall.pk3", make_harness(out, "load")]
    result = subprocess.run([str(play / "uzdoom" / "uzdoom.exe"), "-iwad", ng.IWAD, "-norun", "-nosound", "-noactivate", "-config", str(out / "check.ini"),
                             "-file", *map(str, files), "+logfile", "check"], cwd=out, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    print("exit", result.returncode)


def run(play, out, name, area):
    saves = out / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    if name.startswith("fresh"):
        saves = out / f"saves-{name}"
        saves.mkdir(exist_ok=True)
    if name == "save":
        for old in saves.glob("*.zds"):
            old.unlink()
    autosaves = sorted(saves.glob("*auto*.zds"), key=lambda p: p.stat().st_mtime)  # <character>-autoNN.zds
    if name == "load" and not autosaves:
        sys.exit("no autosave from the save run")
    harness = make_harness(out, name, play) if name.startswith("travel") else make_harness(out, name)  # civilwar.py swaps in its own two-argument one.
    uz_log, df_log, console, launcher = out / f"{name}-uz.log", out / f"{name}-df.log", out / f"log-{name}.txt", out / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-dfarealevel", str(area), "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    if name == "load":
        uz += ["-skill", "3", "+map", "DDT07154", "-dfloadtest", f"resume:{autosaves[-1]}"]
        df += ["-dfsynctest", ng.DAGGER]
    elif name.startswith("travel"):  # The test start: a character in Daggerfall city, who has never been to Privateer's Hold.
        uz += ["-skill", "3", "+map", "DDOVER01"]
        df += ["-dfsynctest", ng.DAGGER]
    else:
        uz += ["-dfflow", "-dfnewgametest", "once", "-dfuitest", "0"]
        df += ["-dfflow", ng.DAGGER]
    command = [str(play / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD,
               "--uzdoom-cwd", str(out), "--log", str(launcher)]
    for mod in DRLA + [data / n for n in DATA] + [play / "dfitems.pk3", play / "doomerfall.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline, result, hwnd, tries, last, answered, escaped = time.time() + TIMEOUT, "timeout", None, 0, "", 0, 0
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.1)
            text, uzt, dft = ng.read(console), ng.read(uz_log), ng.read(df_log)
            if any(k in text for k in FATAL[:2]) or re.search(r"Script error.*paired", text):
                result = "fatal"
                break
            if "PDDONE" in text:
                result = re.search(r"PDDONE (.*)", text).group(1).strip()
                time.sleep(2)
                break
            hwnd = hwnd or ng.doom_window(launcher)
            if not hwnd:
                continue
            # A Daggerfall window opened by the take's Use press (a loot pile took it) is closed, so the harness fails visibly.
            if "PDTAKE" in text and dft.count("opened, surface") > dft.count("closed, reason") and escaped < 6:
                time.sleep(1.5)
                ng.key(hwnd, 0x1B)
                escaped += 1
                continue
            if name == "load":
                continue
            if "both games running" not in uzt:  # Character creation.
                size = re.search(r"opened menu 4 at (\d+)x(\d+)", uzt)
                if not size or "ui: closed" in uzt[uzt.rfind("opened menu 4"):]:
                    continue
                ng.SURFACE[:] = [int(size.group(1)), int(size.group(2))]
                top = ng.top_window(df_log)
                tries = tries + 1 if top == last else 0
                last = top
                ng.act(hwnd, top, tries)
                time.sleep(0.15)
                continue
            # A window Daggerfall opened by itself, such as the tutorial question: answer No, then Esc if it stays.
            own = dft.count("ui: menu 7 opened") - dft.count("ui: menu 7 closed")
            if own > 0 and answered < 12:
                time.sleep(1.5)
                ng.key(hwnd, 0x4E if answered % 2 == 0 else 0x1B)
                answered += 1
                time.sleep(0.5)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    lines = [l for l in ng.read(console).splitlines() if l.startswith("PD") or any(k in l for k in FATAL) and "DoomRL" not in l and "translation" not in l]
    lines += ["df " + l for l in ng.read(df_log).splitlines() if re.search(r"doomitems: take|save|load", l)]
    (out / f"result-{name}.txt").write_text(f"result: {result}\n" + "\n".join(lines) + "\n")
    print(f"{name} result:", result)
    for line in lines:
        if not re.match(r"PD(DROP|KILL|CORPSE) |df .*ammo:", line):
            print(line[:220])


def assemble(play):
    """scripts/play/install.py's layout, built in this lane's native build trees instead of the shared ones."""
    import shutil
    sys.path.insert(0, str(HERE.parents[1] / "scripts" / "play"))
    import install  # noqa: E402
    trees = Path(r"D:\dev\DoomDaggerfall-build")
    bridge = install.build("bridge", trees / "bridge-items", "doomerfall_bridge")
    launcher = install.build("launcher", trees / "launcher-items", "doomerfall-launcher")
    play.mkdir(parents=True, exist_ok=True)
    uzdoom = install.replace_tree(install.build("UZDoom", trees / "uzdoom-items", "zdoom"), play / "uzdoom")
    (uzdoom / "check.ini").unlink(missing_ok=True)
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(install.SOUND_DLLS / dll, uzdoom / dll)
    dfu = install.replace_tree(install.REPO / "daggerfall-unity-master" / "Builds" / "Windows64", play / "dfu")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bridge / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    if not (play / "data").exists():
        install.make_data(trees / "fixeddrops-play", play)
    subprocess.check_call([sys.executable, str(install.REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(play / "doomerfall.pk3")])
    shutil.copy2(launcher / "doomerfall-launcher.exe", play / "doomerfall-launcher.exe")
    write_play_bat(play)
    print("assembled", play)


def write_play_bat(play):
    """install.py's play.bat, with this branch's what-to-try lines."""
    sys.path.insert(0, str(HERE.parents[1] / "scripts" / "play"))
    import install  # noqa: E402
    text = install.PLAY.replace("@DAGGER@", str(install.GAME / "DAGGER")).replace("@IWAD@", str(install.GAME / "wads" / "DOOM2.WAD"))
    text = text.replace("@MODS@", str(install.GAME.parent / "GameMods")).replace("@TRY@", "\nrem ".join(TRY))
    (play / "play.bat").write_text(text, newline="\r\n")


def summary(out, name):
    text = (out / f"result-{name}.txt").read_text()
    kills = Counter(re.findall(r"^PDKILL (.*)$", text, re.M))
    drops = Counter(re.findall(r"^PDDROP (.*?)(?: @ .*)?$", text, re.M))  # Where a drop lands is physics, not compared.
    take = re.findall(r"^PDTAKE (.*)$", text, re.M)
    material = re.findall(r'doomitems: take \d+ ("[^"]+") .*?(stored as .*)$', text, re.M)
    # Anything not fixed by a seed: a victim the blow did not kill, a monster that died without a seed (no Daggerfall
    # id) anywhere on the level, a corpse or floor item without one, a plain ammo drop without one.
    unseeded = re.findall(r"^(PDALIVE .*|PDNOID .*|PDUNSEEDED .*|PDAMMOUNSEEDED .*|PDCORPSE .* seed 00000000)$", text, re.M)
    plain = re.findall(r"^PDAMMOPLAIN (\d+)$", text, re.M)
    # Phase 6: summoned monsters (no Daggerfall id) drop nothing, whoever kills them. Any loose item after their deaths
    # fails, and so does a run where no Lost Soul or no drone died by the player's hand and by a placed monster's.
    summoned = re.search(r"^PDSUMMONED died (\d+), souls by player (\d+) by monster (\d+), drones by player (\d+) by monster (\d+), drops (\d+)$", text, re.M)
    covered = bool(summoned) and all(int(summoned.group(i)) > 0 for i in range(2, 6))
    unseeded += re.findall(r"^(PDSUMMONDROP .*|PDSUMMONALIVE .*)$", text, re.M)
    if not covered:
        unseeded.append("PDSUMMONED missing or incomplete: " + (summoned.group(0) if summoned else "no line"))
    return {"result": text.splitlines()[0], "kills": kills, "drops": drops, "take": take, "material": material,
            "unseeded": unseeded, "plain": plain}


def compare(out, names):
    runs = {n: summary(out, n) for n in names}
    ok = True
    for n, s in runs.items():
        print(f"{n:6} {s['result']}, {sum(s['kills'].values())} killed, {sum(s['drops'].values())} drops, take {s['take']}, Daggerfall {s['material']}")
        print(f"       {len(s['unseeded'])} unseeded, plain ammo drops checked {s['plain']}")
        for line in s["unseeded"][:20]:
            print("       ", line)
        ok &= s["result"] == "result: passed" and bool(s["material"]) and sum(s["drops"].values()) > 0 and not s["unseeded"]
    base = runs[names[0]]
    for n in names[1:]:
        for key in ("kills", "drops", "take", "material"):
            if runs[n][key] != base[key]:
                ok = False
                print(f"DIFF fresh vs {n} in {key}:")
                if isinstance(base[key], Counter):
                    for label, diff in ((names[0], base[key] - runs[n][key]), (n, runs[n][key] - base[key])):
                        print(f"  only {label} ({sum(diff.values())}):", list(diff.items())[:15])
                else:
                    print("  fresh:", base[key], f"\n  {n}:", runs[n][key])
    print("PAIRED FIXED DROPS", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    if "--out" in sys.argv:  # Results folder beside the play folder; the value is not a run name.
        i = sys.argv.index("--out")
        out = play.parent / sys.argv[i + 1]
        del sys.argv[i:i + 2]
    else:
        out = play.parent / "fixed-drops-paired"
    out.mkdir(exist_ok=True)
    area = int(sys.argv[sys.argv.index("--area") + 1]) if "--area" in sys.argv else 10
    if sys.argv[2] == "assemble":
        assemble(play)
    elif sys.argv[2] == "playbat":
        write_play_bat(play)
    elif sys.argv[2] == "compile":
        compile_check(play, out)
    elif sys.argv[2] == "series":  # Several runs in turn, then compare them.
        names = [a for a in sys.argv[3:] if not a.startswith("--") and not a.isdigit()]
        for name in names:
            run(play, out, name, area)
        compare(out, names)
    elif sys.argv[2] == "compare":
        compare(out, [a for a in sys.argv[3:] if not a.startswith("--") and not a.isdigit()] or ["fresh", "save", "load"])
    else:
        run(play, out, sys.argv[2], area)
