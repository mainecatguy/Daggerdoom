"""The loaded ammo's tinted HUD icon, and the top notice on an ammo change (card ammoicon). Both real games, minimized.

usage: ammoicon.py assemble | paired [screenblocks] | check
assemble: makes the review folder: the batch7 stage's engine, launcher, data and bridge (no engine change here), this
          worktree's Daggerfall Unity build, and this worktree's doomerfall.pk3 and doomerfall-drla.pk3, plus play.bat.
paired:   enters the test town, touches a Silver and a Daedric pickup of the starting gun's ammo type, and presses the
          change ammo key three times (Regular -> Silver -> Daedric -> Regular). Each press must change the reserve item's
          status bar icon to that tier's DFAI icon and put "Loading <ammo>." in Doom's top messages. Screenshots: each
          notice as it arrives (run/paired/notice-*.png) and each report (shot-*.png). With a screen size (11 is
          DRLA's fullscreen HUD, which draws the reserve item's icon) the run goes to run/paired-<size>/.
check:    DOOM.WAD E1M1 with no bridge, stock and with the DRLA set: loads clean, and the reserve icons stay stock.
"""
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-icon")
STAGE = Path(r"D:\dev\DoomDaggerfall-loop\review\batch7-stage")  # Engine, launcher, bridge and data this branch is based on.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
# Not "Script error": DRLAX's TRNSLATE and DRLA Monsters' MENUDEF log one in every run. ZScript compile errors are
# caught by their own "N errors while compiling" (or "while parsing scripts") line.
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
TIER_NAMES = {0: "Regular", 2: "Silver", 9: "Daedric"}
RESERVES = ("Clip", "Shell", "RocketAmmo", "Cell")
LETTERS = ("C", "S", "R", "E")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble():
    if REVIEW.exists():
        shutil.rmtree(REVIEW)
    REVIEW.mkdir(parents=True)
    shutil.copytree(STAGE / "uzdoom", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    shutil.copytree(STAGE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    # The stage's own Daggerfall Unity build and bridge (the change is Doom-side only; Daggerfall already sends the notice).
    shutil.copytree(STAGE / "dfu", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini", "Saves", "*.log"))
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    for name in ("doomerfall-launcher.exe", "dfitems.pk3"):
        shutil.copy2(STAGE / name, REVIEW / name)
    for flag, name in (([], "doomerfall.pk3"), (["--drla"], "doomerfall-drla.pk3")):
        subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), *flag, str(REVIEW / name)])
    with zipfile.ZipFile(REVIEW / "demo.pk3", "w") as z:  # Demo only: a Silver and a Daedric pickup to try the control.
        z.writestr("zscript.txt", (HERE / "demo.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AIDemo" }\n')
    write_play()
    print("assembled", REVIEW)


NOTES = """@echo off
rem Doomerfall demo: the loaded ammo's coloured icon, and a notice when you change ammo (card ammoicon).
rem Choose New Game in Doom's menu. Once you are in town, a Silver and a Daedric pickup of your gun's ammo lie just in
rem front of you (demo.pk3 puts them there; the game does not). Walk over both.
rem What to try:
rem  1. Look at the ammo box at the bottom right: where it said AMMO it now shows your loaded ammo's icon, grey for
rem     Regular bullets.
rem  2. Bind Change Ammo (Options, Customize Controls, Doomerfall Controls) if it has no key, and press it: the gun
rem     reloads, "Loading Silver Bullets." shows at the top of the screen, and the icon turns pale silver.
rem  3. Press it again: "Loading Daedric Bullets." and a red-orange icon. Again: "Loading Bullets." and grey.
rem  4. Press + or - to change the screen size: on the fullscreen HUD the icon beside the reserve count is the tinted one.
rem  5. Switch to fists: the icon goes back to the plain one (nothing is loaded).
"""


def write_play():
    stage = (STAGE / "play.bat").read_text()
    launch = stage[stage.index('set "HERE=%~dp0"'):]
    launch = launch.replace('--mod "%HERE%doomerfall-drla.pk3"', '--mod "%HERE%doomerfall-drla.pk3" --mod "%HERE%demo.pk3"')
    assert "demo.pk3" in launch
    (REVIEW / "play.bat").write_text(NOTES.replace("\n", "\r\n") + launch, newline="")


def launch(runs, harness_pk3, timeout, on_line, extra=()):
    """Runs both games through the launcher on the private desktop; on_line(body) returns a stop reason or None."""
    console, uz_log, df_log = runs / "log-console.txt", runs / "uz.log", runs / "df.log"
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddqa", str(runs / "qa"), "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+logfile", "console", "+wipetype", "0", "+i_pauseinbackground", "0",
          "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          # Not minimized and with a set window size, as tools/hud_messages does: a minimized window renders at 320x200.
          "-width", "1280", "-height", "800", "+vid_fullscreen", "0", "+win_w", "1280", "+win_h", "800", "+vid_scalemode", "0", "+vid_scalefactor", "1",
          *extra, "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", harness_pk3]:
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
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?(, \d+ warnings?)? while (compiling|parsing)", body):
            reason = "fatal"
            break
        stop = on_line(body)
        if stop:
            reason = stop
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    return read(console), read(df_log)


def paired(blocks=None):
    runs = REVIEW / "run" / ("paired" if blocks is None else f"paired-{blocks}")
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    harness_pk3 = runs / "harness.pk3"
    with zipfile.ZipFile(harness_pk3, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AIHarness" }\n')
    state = {"shots": 0, "notes": 0, "done_at": None}

    def watch(body):
        presses = re.findall(r"^Loading .*\.$", body, re.M)  # The top notice reached Doom: photograph it while it shows.
        while state["notes"] < len(presses):
            state["notes"] += 1
            with open(inbox, "a") as f:
                f.write(f"n{state['notes']} con screenshot \"{(runs / ('notice-%d.png' % state['notes'])).as_posix()}\"\n")
        reports = re.findall(r"^AIREPORT (\S+(?: \d+)?) ", body, re.M)
        while state["shots"] < len(reports):  # A screenshot of each report's moment (the notice has gone by then).
            with open(inbox, "a") as f:
                f.write(f"s{state['shots']} con screenshot \"{(runs / ('shot-%d.png' % state['shots'])).as_posix()}\"\n")
            state["shots"] += 1
        if "AIDONE" in body and state["done_at"] is None:
            state["done_at"] = time.time()
        return "harness finished" if state["done_at"] and time.time() - state["done_at"] > 3 else None

    console, df_body = launch(runs, harness_pk3, 150, watch, ("+screenblocks", blocks) if blocks else ())
    for line in console.splitlines():
        if line.startswith(("AI", "DFAMMO")) or "Loading " in line or "loaded ammo" in line or any(k in line for k in FATAL):
            print("uz", line[:260])
    for line in df_body.splitlines():
        if "ammo: change" in line or "loaded ammo shown" in line or "hud: top" in line or "guns now load" in line:
            print("df", line[:260])
    # The checks: after press n the loaded tier is Silver, Daedric, Regular in turn, the reserve item of the loaded
    # type carries that tier's DFAI icon, every other reserve item its stock icon, and "Loading <name>." reached Doom.
    ok = True
    reports = {m.group(1): m for m in re.finditer(r'^AIREPORT (start|press \d) loaded="([^"]*)" tier=(-?\d+) type=(-?\d+) weapon=\S+ icons:(.*)$', console, re.M)}
    start = reports.get("start")
    if not start:
        print("FAIL: no start report")
        return False
    type_ = int(start.group(4))
    print(f"start: {start.group(2)} (tier {start.group(3)}) icons:{start.group(5)}")
    for n, tier in ((1, 2), (2, 9), (3, 0)):
        r = reports.get(f"press {n}")
        if not r:
            print(f"FAIL: press {n}: no report")
            ok = False
            continue
        icons = dict(re.findall(r"(\w+)=(\w+)/", r.group(5)))
        want_icon = f"DFAI{LETTERS[type_]}{tier}"
        others = all(icons.get(c) in (None, "none") or not icons[c].startswith("DFAI") for i, c in enumerate(RESERVES) if i != type_)
        name = r.group(2)
        notice = f"Loading {name}." in console
        good = int(r.group(3)) == tier and icons.get(RESERVES[type_]) == want_icon and others and notice
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}: press {n}: loaded {name} (tier {r.group(3)}, want {TIER_NAMES[tier]}), "
              f"{RESERVES[type_]} icon {icons.get(RESERVES[type_])} (want {want_icon}), other icons stock: {others}, top notice \"Loading {name}.\": {notice}")
    print("screenshots:", ", ".join(p.name for p in sorted(runs.glob("*.png"))) or "none")
    print("RESULT:", "PASS" if ok else "FAIL")
    return ok


CHECK_ZS = """version "4.14"
class AICheck : EventHandler
{
	override void WorldTick()
	{
		if (level.maptime != 70 || !players[0].mo) return;
		let p = players[0].mo;
		String s = "";
		static const String R[] = { "Clip", "Shell", "RocketAmmo", "Cell" };
		for (int i = 0; i < 4; i++) { let inv = p.FindInventory(R[i]); s = s .. " " .. R[i] .. "=" .. (inv ? TexMan.GetName(inv.Icon) : "none"); }
		Console.Printf("AICHECK%s", s);
	}
}
"""


def check():
    runs = REVIEW / "run" / "check"
    runs.mkdir(parents=True, exist_ok=True)
    pk3 = runs / "check.pk3"
    with zipfile.ZipFile(pk3, "w") as z:
        z.writestr("zscript.txt", CHECK_ZS)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AICheck" }\n')
    ok = True
    for label, mods in (("stock", [REVIEW / "doomerfall.pk3"]), ("drla", [MODS / n for n in DRLA] + [REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"])):
        log = runs / f"log-{label}.txt"  # UZDoom writes +logfile NAME to log-NAME.txt.
        log.unlink(missing_ok=True)
        cmd = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
               "-config", str(runs / f"{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *map(str, mods), str(pk3), "+logfile", label,
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        line = next((l for l in body.splitlines() if l.startswith("AICHECK")), "")
        fatal = [l for l in body.splitlines() if any(k in l for k in FATAL) or re.search(r"[1-9]\d* errors?(, \d+ warnings?)? while (compiling|parsing)", l)]
        good = bool(line) and "DFAI" not in line and not fatal
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}: {label} E1M1: {line or 'no report'}{' | ' + fatal[0] if fatal else ''}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "assemble":
        assemble()
    elif cmd == "paired":
        sys.exit(0 if paired(sys.argv[2] if len(sys.argv) > 2 else None) else 1)
    elif cmd == "check":
        sys.exit(0 if check() else 1)
    else:
        sys.exit(__doc__)
