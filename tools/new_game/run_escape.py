"""Escape at every step of New Game, in a real paired session with the play mods.

  run_escape.py assemble   Copy this checkout's builds and fresh play data into review/newgameesc/play, with play.bat.
  run_escape.py run        The test, on a private desktop: make a character, pressing Escape once on each creation
                           screen the first time it shows and checking where Daggerfall went; at the difficulty prompt
                           Escape (asks), Escape again (No, the prompt comes back), Escape then Y (back to the title).
                           New Game is chosen again each time Doom is back at the title, and the second character must
                           reach Privateer's Hold with both games running.
"""
import importlib.util
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run_new_game as ng  # noqa: E402  (window, key, click and wizard helpers)

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\newgameesc")
PLAY = REVIEW / "play"
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
DATA_FROM = Path(r"D:\dev\DoomDaggerfall-loop\review\hidden-world")  # install.py data made today from integration's converter.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
TIMEOUT = 300
FATAL = ng.FATAL

# Where Daggerfall's own wizard goes when Escape cancels each screen (DaggerfallStartNewGameWizard.cs).
EXPECT = {
    "CreateCharRaceSelect": "backed out",          # the first screen: creation closes, Doom is at its title
    # Message boxes with buttons ignore Escape (DaggerfallMessageBox.AddButton sets AllowCancel = false).
    "DaggerfallMessageBox after CreateCharRaceSelect": "ignored",  # "Is this your race?" Yes/No
    "CreateCharGenderSelect": "ignored",          # Male/Female buttons
    "CreateCharChooseClassGen": "CreateCharClassSelect",  # Daggerfall's own quirk: cancelling this popup means "from a list"
    "CreateCharClassSelect": "CreateCharRaceSelect",
    "CreateCharChooseBio": "CreateCharClassSelect",
    "DaggerfallMessageBox after CreateCharChooseBio": "CreateCharNameSelect",  # the reputation box closes on any key
    "CreateCharNameSelect": "CreateCharChooseBio",
    "CreateCharFaceSelect": "CreateCharNameSelect",
    "CreateCharAddBonusStats": "CreateCharFaceSelect",
    "CreateCharAddBonusSkills": "CreateCharAddBonusStats",
    "CreateCharSummary": "CreateCharAddBonusSkills",
}


def assemble():
    spec = importlib.util.spec_from_file_location("install", REPO / "scripts" / "play" / "install.py")
    install = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(install)
    PLAY.mkdir(parents=True, exist_ok=True)
    uz = install.replace_tree(BUILD / "uzdoom-newgameesc" / "Release", PLAY / "uzdoom")
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(install.SOUND_DLLS / dll, uz / dll)
    dfu = install.replace_tree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", PLAY / "dfu")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge-newgameesc" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    if not (PLAY / "data").exists():
        shutil.copytree(DATA_FROM / "data", PLAY / "data")
    shutil.copy2(DATA_FROM / "dfitems.pk3", PLAY / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(PLAY / "doomerfall.pk3")])
    shutil.copy2(BUILD / "launcher-newgameesc" / "Release" / "doomerfall-launcher.exe", PLAY / "doomerfall-launcher.exe")
    try_lines = [
        "Escape during New Game (this build):",
        " 1. Choose New Game. On each character creation screen, Escape steps back as in Daggerfall; on the race screen it",
        "    closes creation and you are at Doom's title, where New Game works again.",
        " 2. After the cinematics, Escape at the difficulty prompt asks whether to abandon the character. N or Escape brings",
        "    the prompt back; Y returns to the title. Doom's main menu never opens over Daggerfall's screens.",
    ]
    bat = install.PLAY.replace("@DAGGER@", str(GAME / "DAGGER")).replace("@IWAD@", str(GAME / "wads" / "DOOM2.WAD"))
    bat = bat.replace("@MODS@", str(MODS)).replace("@TRY@", "\nrem ".join(try_lines))
    (PLAY / "play.bat").write_text(bat, newline="\r\n")
    print("assembled", PLAY)


def launcher_command(run):
    uz_log, df_log = run / "uz.log", run / "df.log"
    command = [str(PLAY / "doomerfall-launcher.exe"), "--minimized", "--nodraw", "--uzdoom", str(PLAY / "uzdoom" / "uzdoom.exe"),
               "--dfu", str(PLAY / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
    mods = [MODS / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    mods += [PLAY / "data" / n for n in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    mods += [PLAY / "dfitems.pk3", PLAY / "doomerfall.pk3"]
    for mod in mods:
        command += ["--mod", str(mod)]
    uz_args = ["-noactivate", "-nosound", "-config", str(run / "test.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log),
               "-dfflow", "-dfnewgametest", "escape", "-dfuitest", "0", "-ddtowncache", str(PLAY / "data" / "cache"),
               "-ddconverter", str(PLAY / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
               "+logfile", "console.txt", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in ["-dfbridgelog", str(df_log), "-dfflow", str(GAME / "DAGGER"), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]:
        command += ["--dfu-arg", arg]
    return command


def prompt_state(log):
    """What the difficulty step shows, from Doom's last New Game line about it."""
    marks = {"asking whether to return": "question", "asking for a difficulty": "prompt", "prompt opened, showing it again": "prompt",
             "returned to the title from the difficulty prompt": "title"}
    best, state = -1, ""
    for text, name in marks.items():
        at = log.rfind(text)
        if at > best:
            best, state = at, name
    return state


def wait_for(check, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.05)
    return False


def inner():
    """Runs on quiet_run's private desktop, so Doom's window can be found and sent keys."""
    run = REVIEW / "run"
    shutil.rmtree(run, ignore_errors=True)
    (run / "saves").mkdir(parents=True)
    uz_log, df_log, console = run / "uz.log", run / "df.log", run / "console.txt"
    proc = subprocess.Popen(launcher_command(run), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results, seen, hwnd = [], set(), None
    difficulty_round, last, previous, tries = 0, "", "", 0
    outcome = "timeout"
    deadline = time.time() + TIMEOUT - 10

    def uz():
        return ng.read(uz_log)

    def note(step, ok, detail):
        results.append((step, ok, detail))
        line = f"{'ok  ' if ok else 'FAIL'} {step}: {detail}"
        print(line, flush=True)
        with open(run / "result.txt", "a") as out:
            out.write(line + "\n")

    try:
        while time.time() < deadline and proc.poll() is None:
            log = uz()
            if any(k in ng.read(console) for k in FATAL):
                outcome = "fatal"
                break
            if "both games running" in log:
                outcome = "reached"
                time.sleep(2)
                break
            hwnd = hwnd or ng.doom_window(run / "launcher.log")
            if not hwnd:
                time.sleep(0.1)
                continue

            asks = len(re.findall(r"new game: asking for a difficulty\r?\n", log))
            if asks > difficulty_round:
                difficulty_round = asks
                time.sleep(2.0)  # A late cinematic-skip Escape may already have opened the question.
                if difficulty_round == 1:
                    if prompt_state(uz()) == "question":
                        note("Escape while skipping the last cinematic", True, "opened the abandon question; Escape closes it")
                        ng.key(hwnd, 0x1B)
                        wait_for(lambda: prompt_state(uz()) == "prompt", 4)
                    for step, vk, want in (("difficulty Escape", 0x1B, "question"), ("question Escape (No)", 0x1B, "prompt"),
                                           ("difficulty Escape again", 0x1B, "question"), ("question Y", 0x59, "title")):
                        time.sleep(0.8)
                        ng.key(hwnd, vk)
                        ok = wait_for(lambda: prompt_state(uz()) == want, 4)
                        note(step, ok, f"now {prompt_state(uz())}, want {want}")
                    note("Daggerfall dropped the character", wait_for(lambda: "held character was dropped" in ng.read(df_log), 4), "df.log")
                else:
                    if prompt_state(uz()) == "question":
                        ng.key(hwnd, 0x1B)
                        wait_for(lambda: prompt_state(uz()) == "prompt", 4)
                    for step, vk, want in (("difficulty Escape", 0x1B, "question"), ("question Enter (No is highlighted)", 0x0D, "prompt")):
                        time.sleep(0.8)
                        ng.key(hwnd, vk)
                        ok = wait_for(lambda: prompt_state(uz()) == want, 4)
                        note(step, ok, f"now {prompt_state(uz())}, want {want}")
                    time.sleep(0.8)
                    ng.key(hwnd, 0x0D)  # The highlighted difficulty.
                    note("difficulty chosen", wait_for(lambda: "difficulty chosen" in uz(), 4), "Enter on the prompt")
                continue

            size = re.search(r"opened menu 4 at (\d+)x(\d+)", log[log.rfind("asked Daggerfall to open menu 4"):]) if "asked Daggerfall to open menu 4" in log else None
            if not size or "ui: closed" in log[log.rfind("opened menu 4"):]:
                time.sleep(0.05)
                continue
            ng.SURFACE[:] = [int(size.group(1)), int(size.group(2))]
            top = ng.top_window(df_log)
            tries = tries + 1 if top == last else 0
            if top != last:
                previous, last = last, top
            screen = f"{top} after {previous}" if top == "DaggerfallMessageBox" else top
            if screen in EXPECT and screen not in seen:
                seen.add(screen)
                time.sleep(0.8)
                backed = uz().count("backed out of character creation")
                closes = uz().count("ui: closed")
                ng.key(hwnd, 0x1B)
                want = EXPECT[screen]
                if want == "ignored":
                    time.sleep(2.0)
                    got = ng.top_window(df_log)
                    note(f"{screen} Escape", got == top and uz().count("ui: closed") == closes, f"still {got}; Daggerfall ignores Escape here")
                elif want == "backed out":
                    ok = wait_for(lambda: uz().count("backed out of character creation") > backed, 4)
                    note(f"{top} Escape", ok, "creation closed, Doom at its title" if ok else "creation did not close")
                    reopened = wait_for(lambda: uz().count("ui: asked Daggerfall to open menu 4") >= 2, 6)
                    note("New Game after backing out", reopened, "Daggerfall's creation opened again" if reopened else "did not reopen")
                else:
                    ok = wait_for(lambda: ng.top_window(df_log) not in (top, ""), 4)
                    got = ng.top_window(df_log)
                    note(f"{screen} Escape", ok and got == want, f"went to {got}, Daggerfall's wizard goes to {want}")
                continue
            ng.act(hwnd, top, tries)
            time.sleep(0.15)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)

    log, dflog = uz(), ng.read(df_log)
    note("late cinematic Escape", True, f"{log.count('showing it again')} time(s) the prompt was shown again without asking")
    blocked = log.count("kept Doom's main menu closed")
    note("Doom's main menu", True, f"{blocked} attempt(s) kept closed during New Game")
    held = re.findall(r"new game: (.*) held at pixel .*?, (dungeon [^,]+|outdoors)", dflog)
    note("second character arrival", outcome == "reached" and bool(held) and "Privateer" in held[-1][1],
         f"outcome {outcome}, last held: {held[-1] if held else 'none'}")
    missing = [s for s in EXPECT if s not in seen]
    note("every creation screen tried", not missing, "missing: " + ", ".join(missing) if missing else f"{len(seen)} screens")
    failed = [r for r in results if not r[1]]
    note("result", not failed, "PASS" if not failed else f"FAIL ({len(failed)})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "assemble":
        assemble()
    elif mode == "inner":
        inner()
    else:
        sys.exit(subprocess.call([sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", sys.executable, "-u", __file__, "inner"]))


if __name__ == "__main__":
    main()
