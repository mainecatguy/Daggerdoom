"""Builds, assembles, and tests the stationary NPC demo in a private review folder.

usage: stationary_npcs.py build | unity | data | assemble | run NAME [--drla] | check | registry save|compare
Game data and generated maps stay outside the repo.
"""
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "monster_deaths"))
import monster_deaths as md  # noqa: E402

base, pickup = md.base, md.pickup
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\stationary-npcs")
PREVIOUS = Path(r"D:\dev\DoomDaggerfall-loop\review\monster-deaths")
base.REVIEW, base.BUILD, base.RUN, base.PREVIOUS = REVIEW, REVIEW / "build", REVIEW / "run", PREVIOUS
pickup.REVIEW = md.REVIEW = REVIEW
CONVERTER = REVIEW / "data" / "converter" / "DungeonConverter.exe"
PROJECT = base.WORKTREE / "tools" / "dungeon_converter" / "DungeonConverter.csproj"


def data():
    """Publishes the converter, then rebuilds the shared package and the dungeon package with NPCs."""
    out = REVIEW / "data"
    out.mkdir(parents=True, exist_ok=True)
    base.copy_tree(PREVIOUS / "data", out)
    shutil.rmtree(out / "cache", ignore_errors=True)
    shutil.rmtree(out / "converter", ignore_errors=True)
    subprocess.check_call(["dotnet", "build", str(PROJECT), "-c", "Release", "-v", "q", "-o", str(out / "converter"),
                           f"-p:BaseIntermediateOutputPath={REVIEW / 'converter-obj'}\\"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    arena2 = base.DAGGER + r"\ARENA2"
    subprocess.check_call([str(CONVERTER), "--runtime-assets", "--out", str(out / "ddruntime.pk3"), "--arena2", arena2], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    work = REVIEW / "dungeon"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    text = subprocess.run([str(CONVERTER), "Privateer's Hold", "--export-mesh", "--runtime-dungeon", "--out", str(work)], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace")
    print(text.returncode, *[l[:240] for l in text.stdout.splitlines() if l.startswith("flats:")])
    with zipfile.ZipFile(work / "privateershold_doors.pk3") as z:
        rows = z.read("DFDFLATS").decode().splitlines()
    print("dungeon NPC rows:", sum(len(r.split()) > 6 for r in rows), "of", len(rows))
    shutil.copy2(work / "privateershold_doors.pk3", out / "privateershold_doors.pk3")


def lumps(path):
    return dict(md.pickup_lumps(path))


def doors(group):
    """Converts the location if needed. Returns its door rows and each interior's Daggerfall building type."""
    cache = REVIEW / "data" / "cache"
    cache.mkdir(exist_ok=True)
    path = cache / f"T{group:05d}.ddt"
    arena2 = base.DAGGER + r"\ARENA2"
    if not path.exists():
        subprocess.check_call([str(CONVERTER), "--group", str(group), "--ddt", str(path), "--out", str(REVIEW / "work"), "--arena2", arena2], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    listed = subprocess.run([str(CONVERTER), "--group", str(group), "--list-buildings", "--arena2", arena2], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    return [l.split() for l in lumps(path)["DDDOORS"].decode().splitlines() if l.startswith("0 ")], types, path


def assemble():
    base.assemble()
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(base.SOUND / name, REVIEW / "uzdoom")
    shutil.copy2(md.SOURCE_SPRITES, REVIEW / "dfitems.pk3")
    pickup.DATA = REVIEW / "data"
    rows, types, _ = doors(pickup.GROUP)
    door = next(r for r in rows if types.get(int(r[1])) == "Tavern")
    text = pickup.START
    for key, value in zip(("@X@", "@Y@", "@Z@", "@NX@", "@NY@"), door[3:8]):
        text = text.replace(key, value)
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", text.replace("Privateer's Hold door", "tavern door").replace("the dungeon door", "the tavern door"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ItemDemoStart" }\n')
    args = pickup.launch_args("%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Starts in town facing a tavern door. Look for NPCs outside, then press Use to go in.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={pickup.quoted(pickup.bind_args)}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" {pickup.quoted(args)} %BINDS%\r\n", newline="")
    print("assembled", REVIEW, "tavern", door[1])


def run(name, kind, night=False, drla=False):
    data, runs = REVIEW / "data", REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    saves = runs / "saves"
    saves.mkdir(exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    rows, types, path = doors(pickup.GROUP)
    dungeon_mods = [data / n for n in (md.WAD, "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    if kind.startswith("dungeon:"):  # A converted dungeon replaces the packaged one for this run.
        out = REVIEW / "scan" / "route-dungeon"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        subprocess.check_call([str(CONVERTER), kind[8:], "--out", str(out)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        subprocess.check_call([str(CONVERTER), kind[8:], "--export-mesh", "--runtime-dungeon", "--out", str(out)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        dungeon_mods = [next(out.glob("*.wad")), next(out.glob("*_mesh.pk3")), next(out.glob("*_doors.pk3"))]
        door = next(l.split() for l in lumps(path)["DDDOORS"].decode().splitlines() if l.startswith("1 "))
    elif kind == "dungeon":
        door = next(l.split() for l in lumps(path)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    else:
        if kind == "outdoors":  # Stand beside the first outdoor NPC. A zero normal ends the route there.
            npc = next(l.split() for l in lumps(path)["DFFLATS"].decode().splitlines() if len(l.split()) > 6)
            door = ["", "", "", str(float(npc[1]) + 64), npc[2], npc[3], "0", "0"]
        else:
            door = next(r for r in rows if types.get(int(r[1])) == kind)
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "NPHarness" }\n')
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(CONVERTER), "-ddarena2", base.DAGGER + r"\ARENA2",
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{pickup.GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", base.DAGGER, "-dfnpcreport", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"] + (["-dfnpcnight"] if night else [])
    command = [sys.executable, base.QUIET, "--timeout", "60", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", base.IWAD2, "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in ([base.MODS / n for n in base.DRLA] if drla else []) + [data / n for n in ("ddruntime.pk3", "overworld.pk3")] + dungeon_mods + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    fatal = tuple(k for k in md.FATAL if k != "Script error") if drla else md.FATAL
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + 62
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = base.read(console)
        if "NPDONE" in body:
            reason = "route finished"
            time.sleep(1)
            break
        if any(k in body for k in fatal):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    text = base.read(console)
    for line in text.splitlines():
        if line.startswith(("NPCOUNT", "NPDONE", "DDNPC", "DDTOWN contents")) or any(k in line for k in fatal):
            print(line[:150])
    compare(text, base.read(df_log))
    exceptions = sorted({l[:150] for l in base.read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(exceptions), *exceptions[:4], sep="\n  ")


def scan(names):
    """Counts exterior NPC rows in the named locations, and dungeon NPC rows in the named dungeons (prefix dungeon:)."""
    table = [l.split("\t") for l in (REVIEW / "data" / "ddruntime.groups.tsv").read_text(errors="replace").splitlines()]
    work = REVIEW / "scan"
    work.mkdir(exist_ok=True)
    for name in names:
        if name.startswith("dungeon:"):
            out = work / "dungeon"
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir()
            subprocess.run([str(CONVERTER), name[8:], "--export-mesh", "--runtime-dungeon", "--out", str(out)], stdin=subprocess.DEVNULL, capture_output=True)
            for pk3 in out.glob("*_doors.pk3"):
                with zipfile.ZipFile(pk3) as z:
                    rows = z.read("DFDFLATS").decode().splitlines() if "DFDFLATS" in z.namelist() else []
                print(name, "NPC rows", sum(len(r.split()) > 6 for r in rows), "of", len(rows))
            continue
        for row in [r for r in table if "/" + name + " " in r[3]][:1]:
            path = work / f"T{int(row[0]):05d}.ddt"
            subprocess.run([str(CONVERTER), "--group", row[0], "--ddt", str(path), "--out", str(work / "w"), "--arena2", base.DAGGER + r"\ARENA2"], stdin=subprocess.DEVNULL, capture_output=True)
            rows = lumps(path)["DFFLATS"].decode().splitlines() if path.exists() else []
            print(name, "group", row[0], "exterior NPC rows", sum(len(r.split()) > 6 for r in rows), "of", len(rows))


def compare(doom, daggerfall):
    """Every NPC Doom shows must be the same NPC, in the same place, as a live one in Daggerfall."""
    reports, current = [], None
    for line in daggerfall.splitlines():
        if "npcs: report" in line:
            current = {}
            reports.append((line.split("npcs: report ")[1], current))
        elif "npcrow " in line and current is not None:
            f = line.split("npcrow ")[1].split()
            current[f[0]] = (float(f[1]), float(f[2]), float(f[3]), f[4])
    for tag in ("town", "inside"):
        rows = {f[2]: f for f in (l.split() for l in doom.splitlines() if l.startswith("NPROW " + tag))}
        if not rows:
            continue
        best = max(reports, key=lambda r: len(rows.keys() & r[1].keys()), default=(None, {}))
        live = best[1]
        both = rows.keys() & live.keys()
        offsets = [tuple(float(rows[k][3 + a]) - live[k][a] for a in range(3)) for k in both]
        spread = [max(o[a] for o in offsets) - min(o[a] for o in offsets) for a in range(3)] if offsets else []
        blocking = sum(f[7] == "1" for f in rows.values())
        print(f"{tag}: Doom {len(rows)}, Daggerfall {len(live)} ({best[0]}), matched {len(both)}, Doom only {len(rows.keys() - live.keys())}, "
              f"position spread x/y/z {[round(s, 2) for s in spread]}, first offset {[round(v, 2) for v in offsets[0]] if offsets else None}, solid or shootable {blocking}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        base.build()
    elif command == "unity":
        base.unity()
    elif command == "data":
        data()
    elif command == "assemble":
        assemble()
    elif command == "run":
        if "--group" in sys.argv:
            pickup.GROUP = int(sys.argv[sys.argv.index("--group") + 1])
        run(sys.argv[2], sys.argv[3], "--night" in sys.argv, "--drla" in sys.argv)
    elif command == "scan":
        scan(sys.argv[2:])
    elif command == "check":
        base.check()
    elif command == "registry":
        base.registry(sys.argv[2])
    else:
        sys.exit(__doc__)
