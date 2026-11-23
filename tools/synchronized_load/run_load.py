"""Proves synchronized loading and the death screen with both real games, minimized.

Usage: run_load.py [case ...]   With no case, runs everything. Results go to test/results.txt.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import winreg
import zipfile
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\synchronized-loading")
DATA = REVIEW.parent / "combined-bridge" / "data"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
REAL_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
TEST = REVIEW / "test"
FATAL = ("VM execution aborted", "DIED WITH FATAL", "Execution could not continue")
TIMEOUT = 35


def registry_hash():
    """A hash of the owner's real Daggerfall key. The values are never printed."""
    digest = hashlib.sha256()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REAL_KEY) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                digest.update(repr(winreg.EnumValue(key, index)).encode())
    except OSError:
        return "absent"
    return digest.hexdigest()[:16]


def stop(proc):
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    subprocess.call(["taskkill", "/F", "/IM", "DaggerfallUnity.exe", "/FI", "MODULES eq doomerfall_bridge.dll"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def play(name, mode, save, keep=False):
    run = TEST / name
    if not keep:
        shutil.rmtree(run, ignore_errors=True)
    (run / "saves").mkdir(parents=True, exist_ok=True)
    uz_log, df_log = run / "uz.log", run / "df.log"
    for path in (uz_log, df_log, run / "log-console.txt"):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-nosound",
          "-ddtowncache", str(DATA / "cache"), "-ddconverter", str(DATA / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3", "-dfloadtest", f"{mode}:{save}",
          "+logfile", "console", "+map", "DDT09183", "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(run),
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
    for mod in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        command += ["--mod", str(DATA / mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end, reason = time.time() + TIMEOUT + 3, "timeout"
    while time.time() < end:
        if proc.poll() is not None:
            reason = "exited"
            break
        time.sleep(0.25)
        text = uz_log.read_text(errors="replace") if uz_log.exists() else ""
        console = (run / "log-console.txt").read_text(errors="replace") if (run / "log-console.txt").exists() else ""
        if any(k in console for k in FATAL):
            reason = "fatal"
            break
        if "load test: PASS" in text or "load test: FAIL" in text:
            reason = "finished"
            time.sleep(0.5)
            break
    stop(proc)
    uz_text = uz_log.read_text(errors="replace") if uz_log.exists() else ""
    df_text = df_log.read_text(errors="replace") if df_log.exists() else ""
    return reason, uz_text, df_text


def lines(text, *keys):
    return [l[:240] for l in text.splitlines() if any(k in l for k in keys) and "hp: " not in l]


class Report:
    def __init__(self):
        TEST.mkdir(parents=True, exist_ok=True)
        self.out = open(TEST / "results.txt", "a", encoding="utf-8")
        self.failed = 0

    def check(self, name, ok, detail=""):
        self.failed += not ok
        line = f"{'PASS' if ok else 'FAIL'} {name} {detail}"
        print(line, flush=True)
        self.out.write(line + "\n")
        self.out.flush()

    def detail(self, *items):
        for item in items:
            self.out.write(f"    {item}\n")
        self.out.flush()


def rewrite(source, target, change):
    """Copies a zip, passing each entry through change(name, data). Returning None drops the entry."""
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as new:
        for name in old.namelist():
            data = change(name, old.read(name))
            if data is not None:
                new.writestr(name, data)


def flip_stored_byte(path, entry):
    """Damages one compressed byte inside an entry, leaving the zip's stored checksum as it was."""
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(entry)
    raw = bytearray(path.read_bytes())
    name_len = int.from_bytes(raw[info.header_offset + 26:info.header_offset + 28], "little")
    extra_len = int.from_bytes(raw[info.header_offset + 28:info.header_offset + 30], "little")
    start = info.header_offset + 30 + name_len + extra_len
    raw[start + info.compress_size // 2] ^= 0xFF
    path.write_bytes(raw)


def make_bad(base, kind, target):
    if kind == "flipped":
        shutil.copy2(base, target)
        flip_stored_byte(target, "doomerfall/daggerfall/SaveData.txt")
    elif kind == "flipped-doom":
        shutil.copy2(base, target)
        flip_stored_byte(target, "globals.json")
    elif kind == "truncated":
        target.write_bytes(base.read_bytes()[:base.stat().st_size // 2])
    elif kind == "missing-file":
        rewrite(base, target, lambda n, d: None if n.endswith("FactionData.txt") else d)
    elif kind == "doom-only":
        rewrite(base, target, lambda n, d: None if n.startswith("doomerfall/") else d)
    elif kind == "wrong-hp":
        def change(name, data):
            if name != "doomerfall/manifest.json":
                return data
            manifest = json.loads(data)
            manifest["hp"] += 7
            return json.dumps(manifest, separators=(",", ":")).encode()
        rewrite(base, target, change)
    elif kind == "wrong-map":
        def change(name, data):
            if name != "doomerfall/manifest.json":
                return data
            manifest = json.loads(data)
            manifest["map"] = "MAP01"
            return json.dumps(manifest, separators=(",", ":")).encode()
        rewrite(base, target, change)
    elif kind == "new-format":
        def change(name, data):
            if name != "doomerfall/manifest.json":
                return data
            manifest = json.loads(data)
            manifest["format"] = 99
            return json.dumps(manifest, separators=(",", ":")).encode()
        rewrite(base, target, change)


STOCK_SCRIPT = '''version "4.10"
class StockLoadControl : StaticEventHandler
{
	int loads;
	int deadTics;
	ui int ticks;
	ui bool saved, asked;
	override void WorldLoaded(WorldEvent e)
	{
		if (!e.IsSaveGame) return;
		loads++;
		Console.Printf(loads == 1 ? "STOCKLOADED" : "STOCKREBORN");
	}
	override void UiTick()
	{
		if (gamestate != GS_LEVEL) return;
		ticks++;
		let saves = SavegameManager.GetManager();
		if (!saved && ticks > 70)
		{
			saved = true;
			saves.ReadSaveStrings();
			saves.InsertNewSaveNode();
			saves.DoSave(0, "control");
			saves.RemoveNewSaveNode();
		}
		else if (saved && !asked && ticks > 140)
		{
			asked = true;
			saves.ReadSaveStrings();
			saves.LoadSavegame(0);
		}
	}
	override void WorldTick()
	{
		if (loads != 1) return;
		let p = players[consoleplayer];
		if (p.playerstate == PST_LIVE && level.maptime > 35) p.mo.DamageMobj(null, null, 1000000, 'None', DMG_FORCED);
		else if (p.playerstate == PST_DEAD && ++deadTics > 35) p.playerstate = PST_REBORN;
	}
}
'''


def stock(report, name, mods):
    run = TEST / f"stock-{name}"
    shutil.rmtree(run, ignore_errors=True)
    (run / "saves").mkdir(parents=True)
    control = run / "control.pk3"
    with zipfile.ZipFile(control, "w") as z:
        z.writestr("zscript.txt", STOCK_SCRIPT)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "StockLoadControl" }\n')
    files = [str(m) for m in mods] + [str(control)]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--cwd", str(run), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate",
               "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-file", *files, "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-nosound",
               "-noautoload", "-skill", "3", "+logfile", "console", "+map", "E1M1", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log, end, result = run / "log-console.txt", time.time() + TIMEOUT + 3, "timeout"
    text = ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.3)
        text = log.read_text(errors="replace") if log.exists() else ""
        if "STOCKREBORN" in text:
            result = "finished"
            break
        if any(k in text for k in FATAL):
            result = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    text = log.read_text(errors="replace") if log.exists() else ""
    report.check(f"stock {name}: load, death, automatic reload", result == "finished" and "STOCKLOADED" in text and "[bridge]" not in text, result)


def main():
    wanted = set(sys.argv[1:])
    want = lambda name: not wanted or name in wanted
    report = Report()
    registry = registry_hash()
    report.out.write(f"\n=== run {time.ctime()}\n")
    base = TEST / "cycle" / "saves" / "bundle.zds"

    for mode in ("cycle", "death", "menu"):
        if not want(mode):
            continue
        run = TEST / mode
        reason, uz, df = play(mode, mode, run / "saves" / "bundle.zds")
        report.check(f"{mode}: both games restored and resumed", reason == "finished" and "load test: PASS" in uz and "both games ready, resuming" in df, reason)
        report.detail(*lines(uz, "load test", "load ", "death:", "title:"), *lines(df, "load ", "hold:", "error"))
        if mode != "cycle":
            report.check(f"{mode}: Daggerfall did not restart itself", "still dead after Daggerfall's restart time | doom hp" in uz and "Daggerfall hp 0 dead 1" in next((l for l in uz.splitlines() if "still dead" in l), ""))
        if mode == "menu":
            report.check("menu: a new game is refused at the title", "title: refused a new game" in uz)

    if want("skip") and base.exists():
        run = TEST / "skip"
        shutil.rmtree(run, ignore_errors=True)
        (run / "saves").mkdir(parents=True)
        damaged = run / "saves" / "zz-damaged.zds"
        make_bad(base, "flipped", damaged)
        future = time.time() + 3600
        os.utime(damaged, (future, future))
        reason, uz, df = play("skip", "death", run / "saves" / "bundle.zds", keep=True)
        report.check("skip: Load Last Save passes over a damaged newer save", reason == "finished" and "load test: PASS" in uz and "skipping" in uz, reason)
        report.detail(*lines(uz, "skipping", "loading the newest", "load test: PASS", "load test: FAIL"))

    for kind in ("flipped", "flipped-doom", "truncated", "missing-file", "doom-only", "wrong-hp", "wrong-map", "new-format"):
        if not want(kind) and not want("bad") or not base.exists():
            continue
        run = TEST / f"bad-{kind}"
        shutil.rmtree(run, ignore_errors=True)
        (run / "saves").mkdir(parents=True)
        target = run / "saves" / "bad.zds"
        make_bad(base, kind, target)
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        reason, uz, df = play(f"bad-{kind}", "bad", target, keep=True)
        unchanged = hashlib.sha256(target.read_bytes()).hexdigest() == before
        leftovers = [p.name for p in (run / "saves").iterdir() if p.name != "bad.zds"]
        restored = "restoring Daggerfall" in df
        report.check(f"bad {kind}: refused, game continues", reason == "finished" and "load test: PASS" in uz and "refused" in uz and not restored and unchanged and not leftovers,
                     f"{reason}, file unchanged {unchanged}, leftovers {leftovers}, Daggerfall touched {restored}")
        report.detail(*lines(uz, "load: refused", "load test: PASS", "load test: FAIL"), *lines(df, "refused"))

    if want("stock"):
        stock(report, "doom", [])
    if want("drla"):
        stock(report, "drla", [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3"])

    report.check("owner registry key unchanged", registry == registry_hash())
    print("failed:", report.failed)
    sys.exit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
