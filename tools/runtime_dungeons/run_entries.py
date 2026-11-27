"""Enters dungeons through their real town doors with both real games, minimized, and walks back out.

Usage: run_entries.py --uzdoom EXE --kit DIR --data DIR --converter EXE --out DIR GROUP[:runtime] ...
GROUP is a location group (ddruntime.groups.tsv) whose map has a dungeon door. ":runtime" leaves the dungeon out of the
cache, so the running game converts it on the door press; otherwise it is converted ahead of time, as a cached dungeon.
--kit is an installed play folder (launcher, dfu, doomerfall.pk3, dfitems.pk3, data/overworld.pk3). --data holds this
checkout's ddruntime.pk3 and privateershold.wad, _mesh.pk3, _doors.pk3. Logs stay under --out, outside the repository.
Passes when every run reaches the dungeon in both games, comes back out, and no "not available yet" message appears.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
HARNESS = Path(__file__).resolve().parents[1] / "overworld" / "door_harness.zs"
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")
DUNGEON_GROUP = 30000000


def ddt_lumps(path):
    data = path.read_bytes()
    count, at, heads, lumps = struct.unpack("<i", data[4:8])[0], 8, [], {}
    for _ in range(count):
        heads.append((data[at:at + 8].rstrip(b"\0").decode(), *struct.unpack("<II", data[at + 8:at + 16])))
        at += 16
    for name, raw, packed in heads:
        lumps[name] = zlib.decompress(data[at:at + packed]) if packed else b""
        at += packed
    return lumps


def convert(exe, group, ddt, work, winter=False):
    r = subprocess.run([str(exe), "--group", str(group), "--ddt", str(ddt), "--out", str(work), "--arena2", str(GAME / "DAGGER" / "ARENA2")] + (["--winter"] * winter),
                       capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not ddt.exists():
        sys.exit(f"conversion of group {group} failed: {(r.stdout + r.stderr)[-400:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uzdoom", required=True)
    ap.add_argument("--kit", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--converter", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=75)
    ap.add_argument("--dfu-flag", action="append", default=[], help="one more Daggerfall argument (repeatable), such as -dfarealevel")
    ap.add_argument("--uz-flag", action="append", default=[], help="one more UZDoom argument (repeatable), such as -ddloadingtest")
    ap.add_argument("targets", nargs="+")
    args = ap.parse_args()
    cache = args.out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    results = []
    for target in args.targets:
        group, _, mode = target.partition(":")
        group = int(group)
        # The test character's date is in winter, so the game reads the town's winter file (dd_towncache.cpp FileFor).
        town = cache / f"T{group:05d}W.ddt"
        if not town.exists():
            convert(args.converter, group, town, args.out / "work" / f"T{group}", winter=True)
        doors = [l.split() for l in ddt_lumps(town)["DDDOORS"].decode().splitlines() if l.strip()]
        dungeon_doors = [d for d in doors if d[0] == "1"]
        if not dungeon_doors:
            sys.exit(f"group {group} has no dungeon door")
        door = min(dungeon_doors, key=lambda d: float(d[5]))  # the lowest: some ruins also have door planes on upper floors
        map_id = int(door[1])
        dgroup = DUNGEON_GROUP + (map_id & 0xFFFFF)
        dddt = cache / f"T{dgroup:05d}.ddt"
        scratch = args.out / "work" / f"T{dgroup}.ddt"
        prebuilt = group == 7154  # Privateer's Hold comes from its packages, as in the play build
        if not prebuilt and not scratch.exists():
            convert(args.converter, dgroup, scratch, args.out / "work" / f"T{dgroup}")
        if not prebuilt and mode != "runtime":
            shutil.copy2(scratch, dddt)
        elif dddt.exists():
            dddt.unlink()  # the game converts it on the door press
        if prebuilt:
            import zipfile
            with zipfile.ZipFile(args.data / "privateershold_doors.pk3") as z:
                info = z.read("DDDUNGN").decode()
        else:
            info = ddt_lumps(scratch)["DDDUNGN"].decode()
        exits = [l.split()[1:] for l in info.splitlines() if l.startswith("exit ")][:1]

        run = args.out / f"run-{group}{'-runtime' if mode == 'runtime' else ''}"
        shutil.rmtree(run, ignore_errors=True)
        (run / "saves").mkdir(parents=True)
        text = HARNESS.read_text()
        text = text.replace("@DOORS@", ", ".join(door[3:8])).replace("@EXITS@", ", ".join(v for e in exits for v in e) or "0, 0, 0, 0, 0")
        text = text.replace("@MODE@", "route").replace("const LIMIT = 35 * 14;", "const LIMIT = 35 * 90;")  # a runtime conversion took 7-47 s, depending on machine load
        text = text.replace("if (inside || level.maptime < 4) break;", 'if (inside || level.maptime < 4 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;')
        import zipfile
        with zipfile.ZipFile(run / "harness.pk3", "w") as z:
            z.writestr("zscript.txt", text)
            z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DTHarness" }\n')
        console, df_log = run / "log-console.txt", run / "df.log"
        uz = ["-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(run / "uz.log"), "-ddtowncache", str(cache),
              "-ddconverter", str(args.converter), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3",
              "+logfile", "console", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
              "+vid_lowerinbackground", "0", "+map", f"DDT{group:05d}"]
        uz += args.uz_flag
        df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
        df += args.dfu_flag
        command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--", str(args.kit / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", args.uzdoom, "--dfu", str(args.kit / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
        for mod in (args.data / "ddruntime.pk3", args.kit / "data" / "overworld.pk3", args.data / "privateershold.wad", args.data / "privateershold_mesh.pk3",
                    args.data / "privateershold_doors.pk3", run / "harness.pk3"):
            command += ["--mod", str(mod)]
        for a in uz:
            command += ["--uzdoom-arg", a]
        for a in df:
            command += ["--dfu-arg", a]
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        reason, end = "timeout", time.time() + args.timeout + 3
        while time.time() < end:
            if proc.poll() is not None:
                reason = "exited"
                break
            time.sleep(0.25)
            log = console.read_text(errors="replace") if console.exists() else ""
            if any(k in log for k in FATAL):
                reason = "fatal"
                break
            if "DTDONE" in log:
                reason = "finished"
                time.sleep(2.5)
                break
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
        log = console.read_text(errors="replace") if console.exists() else ""
        dft = df_log.read_text(errors="replace") if df_log.exists() else ""
        arrive = [l for l in log.splitlines() if l.startswith("DTARRIVE")]
        df_in = [l for l in dft.splitlines() if "Daggerfall is in dungeon" in l]
        df_out = [l for l in dft.splitlines() if "Daggerfall is in exterior" in l]
        refused = "not available yet" in log
        returned = "DTRETURN" in log or "DTDONE done" in log
        ok = bool(reason == "finished" and arrive and df_in and returned and not refused and "DTFAIL" not in log)
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} group {group} dungeon {map_id} ({'prebuilt' if prebuilt else mode or 'cached'}): stopped {reason}, refused {refused}")
        for l in arrive[:1] + df_in[:1] + df_out[-1:] + [l for l in log.splitlines() if l.startswith(("DTFAIL", "DTDONE", "DTRETURN")) or any(k in l for k in FATAL)][:4]:
            print("   ", l[:200])
    print(f"{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
