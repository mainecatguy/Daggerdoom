"""Reserve ammo in Daggerfall's inventory, with both real games, minimized. Based on tools/gun_icons/gun_icons.py.

usage: ammo.py assemble | uzdoom | take | load | equip | equipload | check
assemble: builds the review folder from this worktree's builds (UZDoom, bridge, launcher, Daggerfall Unity).
uzdoom:   copies only a fresh UZDoom build into the review folder.
take:     touch-picks a box of bullets, spends 5, lets Daggerfall's -dfammotest hook drop 7 bullets and add 20 shells,
          then autosaves. Compares Doom's and Daggerfall's counts at the end.
load:     loads that autosave in fresh copies of both games and compares the counts again.
equip:    with stand-in ammo bonuses (-dfequiptest: bullets +50%, shells +25%), hurts a monster for 10 with the starting
          gun, fists, the starting gun raised by hotkey 2, and a shotgun equipped from Daggerfall by hotkey 3, spends 3
          shells, autosaves, and checks the damage and the counts.
equipload: loads that autosave and checks the damage and the counts again.
change:   (-dfchangeammotest) draws a DRLA pistol with 10 in its magazine, presses the change ammo key (magazine back to
          Daggerfall, Steel loads), spends every loaded round (Silver loads by itself), and autosaves.
changeload: loads that autosave and checks that Silver is still loaded.
check:    DOOM.WAD E1M1 with no bridge, stock and with the DRLA set.
"""
import argparse
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-change")  # Was review\ammo, ammo-pickup, ammo-equip, then ammo-tiers, for earlier ammo runs.
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # Data, sprite package, and demo items.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-doomitems" / "Release"  # Built from this worktree.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-doomitems" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-doomitems" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
CLASSES = ("Clip", "Shell", "RocketAmmo", "Cell")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def harness(load, equip=False, tiers=False, change=False):
    cache = REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt"
    for other in cache.parent.glob("T*.ddt"):
        other.unlink()
    shutil.copy(SOURCE / "data" / "cache" / cache.name, cache)
    door = next(l.split() for l in lumps(cache)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    text = (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@LOADRUN@", "1" if load else "0").replace("@EQUIPRUN@", "1" if equip else "0").replace("@TIERRUN@", "1" if tiers else "0").replace("@CHANGERUN@", "1" if change else "0")
    path = REVIEW / "run" / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AMHarness" }\n')
    return path


def copy_uzdoom():
    if (REVIEW / "uzdoom").exists():
        shutil.rmtree(REVIEW / "uzdoom")
    shutil.copytree(UZ_BUILD, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    copy_uzdoom()
    if (REVIEW / "dfu").exists():
        shutil.rmtree(REVIEW / "dfu")
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if (REVIEW / "data").exists():
        shutil.rmtree(REVIEW / "data")
    shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    # The tiers run needs the converter's placed pickups, which the doom-items dungeon predates.
    pickups = REVIEW.parent / "pickups" / "data"
    for name in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        if (pickups / name).exists():
            shutil.copy2(pickups / name, REVIEW / "data" / name)
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    print("assembled", REVIEW)


def counts_doom(body):
    last = [l for l in body.splitlines() if l.startswith("AMCOUNT final")]
    return dict(re.findall(r"(\w+)=(\d+)", last[-1])) if last else {}


def counts_df(body):
    # Daggerfall's latest loaded total per class: the full totals lines, and the later equip lines for one class.
    counts = {}
    for l in body.splitlines():
        if "holds Clip" in l and "stacks" in l:
            counts.update(re.findall(r"(Clip|Shell|RocketAmmo|Cell) (\d+);", l))
        m = re.search(r"equip: the ready gun loads (Clip|Shell|RocketAmmo|Cell); Daggerfall holds (\d+),", l)
        if m:
            counts[m.group(1)] = m.group(2)
    return counts


def run(name):
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    saves = runs / "saves"
    saves.mkdir(exist_ok=True)
    load, equip, tiers = name in ("load", "equipload", "tierload", "changeload"), name in ("equip", "equipload"), name in ("tiers", "tierload")
    change = name in ("change", "changeload")
    if name in ("take", "equip", "tiers", "change"):
        for old in saves.glob("*.zds"):
            old.unlink()
    autosaves = sorted(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime)
    if load and not autosaves:
        sys.exit("no autosave from the take run")
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    if load:
        uz += ["-dfloadtest", f"resume:{autosaves[-1]}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), *(["-dfequiptest"] if equip else ["-dfshoptest"] if tiers else ["-dfchangeammotest"] if change else ["-dfammotest"]), "-dfarealevel", "20", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 180 if change and not load else 120  # The reload checks add about 35 s.
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness(load, equip, tiers, change)]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if "AMDONE" in body:
            reason = "harness finished"
            time.sleep(2)
            break
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?, \d+ warnings? while compiling", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if re.match(r"AM[A-Z]+ ", line) or "loaded ammo" in line or "ammo unload" in line or "change ammo" in line or "DFAMMO jackpot" in line or "DFAMMO reload" in line or "DFAMMO redraw" in line or "ammo add" in line or "ready weapon" in line or "damage bonus" in line or "Script error" in line or any(k in line for k in FATAL):
            print("uz", line[:220])
    for line in read(uz_log).splitlines():
        if re.search(r"save|load test", line, re.I):
            print("uz-bridge", line[:200])
    df_body = read(df_log)
    for line in df_body.splitlines():
        if ("ammo" in line and "area level" not in line) or "damage bonus" in line or "equiptest" in line or re.search(r"\bsave\b|load", line):
            print("df", line[:300])
    doom, dagger = counts_doom(read(console)), counts_df(df_body)
    print("final Doom:", doom)
    print("final Daggerfall:", dagger)
    if equip or change:
        # The bridge logs what Daggerfall's bonus made of each hit ("10 -> 15 (5000 bp)"), or nothing with no bonus.
        # Health lost is shown too, but DRLA X starting perks can multiply it further after the bonus.
        want = {"Clip": "10 -> 15 (5000 bp)", "Shell": "10 -> 12 (2500 bp)"}
        if change:  # By hit label: Regular +0%, Steel +20%, Silver +10% (the automatic change, the pistol again, after the load).
            want = {"regular": None, "steel": "10 -> 12 (2000 bp)", "automatic": "10 -> 11 (1000 bp)", "other gun": None, "pistol again": "10 -> 11 (1000 bp)", "loaded": "10 -> 11 (1000 bp)"}
        scaled, hits = None, 0
        for line in read(console).splitlines():
            m = re.search(r"damage bonus: .* hit by the player, (.+)$", line)
            if m:
                scaled = m.group(1).strip()
            m = re.match(r"AMHIT (.+?) weapon=(\S+) ammo=(\S+) lost=(\d+)", line)
            if m:
                label, weapon, ammo, lost = m.groups()
                hits += 1
                expect = want.get(label) if change else want.get(ammo)
                ok = scaled == expect
                print("hit", label, weapon, ammo, "bridge", scaled or "unscaled", "expected", expect or "unscaled", "lost", lost, "PASS" if ok else "FAIL")
                scaled = None
        print("hits", hits)
    if change and not load:
        reload_checks(read(console))
    print("MATCH" if doom and all(doom.get(c) == dagger.get(c) for c in CLASSES) else "MISMATCH")


def reload_checks(body):
    """The change ammo key is a reload: after it, the gun reloads (DRLA) or is lowered and raised (no magazine), cannot
    fire until that ends, and ends ready to fire with its magazine filled."""
    for k, what in enumerate(("DRLA shotgun", "DRLA chaingun", "stock shotgun")):
        rows = []
        for m in re.finditer(rf"AMRELOAD change{k} gun=(\S+) state=(\S+) fire=(\d) mag=(-?\d+) reserve=(\S+) tic=(\d+)", body):
            gun, state, fire, mag, reserve, tic = m.groups()
            rows.append((gun, state, int(fire), int(mag), reserve, int(tic)))
        before = re.search(rf"AMRELOAD change{k} before (.*)", body)
        print(f"change{k} {what} before:", before.group(1) if before else "missing")
        for r in rows:
            print("  ", *r)
        # The change arrives when the magazine or reserve first differs from the first row. From then on the gun must
        # not be able to fire a round (an empty DRLA magazine only starts DRLA's own reload) until the reload ends.
        arrival = next((i for i, r in enumerate(rows) if i and (r[3], r[4]) != (rows[0][3], rows[0][4])), None)
        start = next((i for i in range(arrival, len(rows)) if not rows[i][2]), None) if arrival is not None else None
        early = [r[5] for r in rows[arrival:start] if r[2] and r[3] != 0] if start is not None else []
        last = rows[-1] if rows else None
        held = start is not None and all(not r[2] for r in rows[start:-1])
        filled = last is not None and last[2] == 1 and last[3] != 0
        ok = start is not None and held and filled and not early
        print(f"change{k} {what}:", "reload seen" if start is not None else "NO RELOAD", "| no fire during it" if held else "| FIRED DURING IT",
              "| ends ready, magazine filled" if filled else "| NOT READY OR EMPTY AT END", f"| could fire before the reload at tics {early}" if early else "", "PASS" if ok else "FAIL")
    for line in body.splitlines():
        if "change ammo reload of" in line or "DFAMMO reload" in line or "DFAMMO redraw" in line:
            print("  ", line[:160])


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"  # UZDoom writes +logfile NAME to log-NAME.txt.
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3"), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()), "| E1M1 entered", "E1M1" in body)
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "uzdoom", "take", "load", "equip", "equipload", "tiers", "tierload", "change", "changeload", "check"))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "uzdoom":
    copy_uzdoom()
elif args.command == "check":
    check()
else:
    run(args.command)
