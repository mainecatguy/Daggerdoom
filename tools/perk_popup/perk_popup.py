"""Perk popup, Daggerfall and Doom together.

usage: perk_popup.py <play folder> assemble <base play folder>
       perk_popup.py <play folder> run [skill]

  assemble  makes <play folder> from a play folder of the same bridge version (scripts/play/install.py layout): its
            UZDoom, launcher and pk3s are copied, its data folder is linked, and dfu is this repo's Unity build.
  run       the test start in Daggerfall city with -dfperktest <skill> (default Jumping). Daggerfall raises the skill
            from 20 to 26 and opens the perk window by itself; Doom must open it as menu 7 and stop its clock. The
            script clicks the window, which must close it, and Doom's clock must run again.
Wrap the whole script in quiet_run.py: it starts the launcher itself, so its window driver shares the games' desktop.
Config and logs go to <play folder>/../perk-popup.
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
sys.path.insert(0, str(HERE.parent / "new_game"))
import run_new_game as ng  # noqa: E402  (window-message driver)

DRLA = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
TIMEOUT = 150
FATAL = ("DIED WITH FATAL", "VM execution aborted")

# Prints Doom's level time once a second, so the log shows when Doom's game clock stops and runs again.
HARNESS = """version "4.10"
class PPHarness : EventHandler
{
    override void WorldTick()
    {
        if (level.maptime % 35 == 0)
            Console.Printf("PPTICK %d", level.maptime);
    }
}
"""


def assemble(play, base):
    sys.path.insert(0, str(REPO / "scripts" / "play"))
    import install  # noqa: E402
    play.mkdir(parents=True, exist_ok=True)
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(base / name, play / name)
    install.replace_tree(base / "uzdoom", play / "uzdoom")
    if not (play / "data").exists():
        subprocess.check_call(["cmd", "/c", "mklink", "/J", str(play / "data"), str(base / "data")])
    dfu = install.replace_tree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", play / "dfu")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    print("assembled", play)


def ticks(text):
    return [int(t) for t in re.findall(r"^PPTICK (\d+)", text, re.M)]


def run(play, out, skill):
    harness = out / "perk-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", HARNESS)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PPHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-perk.txt", out / "launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / "perk.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "perk", "+vid_fullscreen", "0", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-skill", "3", "+map", "DDOVER01"]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
          "-dfsynctest", ng.DAGGER, "-dfperktest", skill]
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
    deadline, hwnd, facts = time.time() + TIMEOUT, None, {}
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.2)
            text, uzt, dft = ng.read(console), ng.read(uz_log), ng.read(df_log)
            if any(k in text for k in FATAL) or re.search(r"Script error.*perk-harness", text):  # DRLA always logs a "translation" one.
                facts["fatal"] = True
                break
            hwnd = hwnd or ng.doom_window(launcher)
            if not hwnd or "ui: menu 7 opened" not in dft:
                continue
            # The perk window is up. Watch Doom's clock for 3 seconds, then close the window with a click.
            if "open_ticks" not in facts:
                time.sleep(1.0)
                facts["open_ticks"] = ticks(ng.read(console))
                time.sleep(3.0)
                facts["open_ticks_later"] = ticks(ng.read(console))
                size = re.findall(r"opened menu 7 at (\d+)x(\d+)", ng.read(uz_log))
                if size:
                    ng.SURFACE[:] = [int(size[-1][0]), int(size[-1][1])]
                ng.click(hwnd, 160, 100)
                facts["clicked_at"] = time.time()
                continue
            if "ui: menu 7 closed" in dft:
                time.sleep(3.0)
                facts["after_ticks"] = ticks(ng.read(console))
                break
            if time.time() - facts["clicked_at"] > 5 and "escaped" not in facts:
                facts["escaped"] = True  # The click did not close it: Esc, and the run fails.
                ng.key(hwnd, 0x1B)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)

    dft, uzt = ng.read(df_log), ng.read(uz_log)
    lines = [l for l in dft.splitlines() if re.search(r"perks?test|perks:|ui: (menu 7|top window|Daggerfall opened)", l)]
    lines += ["uz " + l for l in uzt.splitlines() if re.search(r"ui: (Daggerfall asked|asked Daggerfall to open menu 7|Daggerfall opened menu 7|closed)", l)]
    checks = {
        "no fatal error": not facts.get("fatal"),
        "Daggerfall showed the perk": "perks: showing 1 perk(s)" in dft and f"perk at 25" in dft,
        "the perk window is Daggerfall's message box": "ui: top window is DaggerfallMessageBox" in dft,
        "Doom opened it as menu 7": "ui: menu 7 opened" in dft and "asked Daggerfall to open menu 7" in uzt,
        "Doom's clock stopped while it was open": bool(facts.get("open_ticks")) and facts.get("open_ticks") == facts.get("open_ticks_later"),
        "a click closed it": "ui: menu 7 closed" in dft and not facts.get("escaped"),
        "Doom's clock ran again": bool(facts.get("after_ticks")) and max(facts["after_ticks"]) > max(facts.get("open_ticks_later") or [0]),
    }
    report = [f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()]
    report += ["", f"ticks while open: {facts.get('open_ticks', [])[-3:]} then {facts.get('open_ticks_later', [])[-3:]}",
               f"ticks after close: {facts.get('after_ticks', [])[-4:]}", ""] + lines
    result = "PERK POPUP " + ("PASS" if all(checks.values()) else "FAIL")
    (out / "result.txt").write_text(result + "\n" + "\n".join(report) + "\n")
    print(result)
    print("\n".join(report))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "perk-popup"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "assemble":
        assemble(play, Path(sys.argv[3]).resolve())
    else:
        run(play, out, sys.argv[3] if len(sys.argv) > 3 else "Jumping")
