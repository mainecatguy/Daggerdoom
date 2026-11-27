"""Shared parts of the visual parity scripts (scenes.py, menus.py). See README.md."""
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [MODS / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
# An assembled play folder (uzdoom, dfu, data, dfitems.pk3, doomerfall-launcher.exe), as scripts/play/install.py makes.
PLAY = Path(os.environ.get("VP_PLAY", r"D:\dev\DoomDaggerfall-loop\review\visualparity\play"))
OUT = Path(os.environ.get("VP_OUT", r"D:\dev\DoomDaggerfall-loop\review\visualparity"))
CAPTURE_EXE = REPO / "daggerfall-unity-master" / "Builds" / "Capture" / "DFCapture.exe"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map", "errors while parsing")  # DRLAX prints a harmless "Script error" (a warning)

WIDTH, HEIGHT = 960, 720
WORLD_SCALE = 0.75  # the converter's default: Doom units = Daggerfall units * 0.75
# Daggerfall Unity's standing eye: PlayerHeightChanger, capsule 1.8 m with the eye 0.09 m below its top.
DF_EYE_METERS = 1.8 - 0.09
DF_EYE = DF_EYE_METERS / 0.025  # 68.4 Daggerfall units (MeshReader.GlobalScale 0.025 m per unit)
DOOM_EYE = DF_EYE * WORLD_SCALE  # 51.3 Doom units
DF_VFOV = 65.0  # Daggerfall Unity's default FieldOfView (defaults.ini), vertical in Unity
# Doom's fov is horizontal for a 4:3 view, so the same vertical angle at 960x720 is:
DOOM_FOV = math.degrees(2 * math.atan(math.tan(math.radians(DF_VFOV / 2)) * WIDTH / HEIGHT))  # 80.68


def ensure_outside_repo(path):
    p = os.path.normcase(str(Path(path).resolve())) + os.sep
    if p.startswith(os.path.normcase(str(REPO)) + os.sep):
        sys.exit("output must be outside the repository: screenshots are derived from game data")


def read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def prepare(work):
    """Builds this checkout's doomerfall.pk3 and doomerfall-drla.pk3 into <work>."""
    work.mkdir(parents=True, exist_ok=True)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(work / "doomerfall.pk3")], stdout=subprocess.DEVNULL)
    subprocess.check_call([sys.executable, str(build), "--drla", str(work / "doomerfall-drla.pk3")], stdout=subprocess.DEVNULL)


def paired_command(work, run, timeout, uz_extra=(), df_extra=(), qa=None, minimized=True):
    """The real game's launch (scripts/play/install.py's play.bat), minimized on a private desktop, with the test town
    start (-dfsynctest), a private config, and the visual parity harness, which removes monsters and NPCs."""
    data = PLAY / "data"
    uz = ["-noactivate", "-config", str(run / "vp.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(run / "uz.log"),
          "-nosound", "-noautoload", "-skill", "3", "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+logfile", "vpcon", "+vid_fullscreen", "0", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          # A minimized UZDoom renders only its tiny window unless the scene has a custom size (tools/lights/light_shots.py).
          "+vid_scalemode", "5", "+vid_scale_customwidth", str(WIDTH), "+vid_scale_customheight", str(HEIGHT),
          "+screenshot_type", "png", "+con_notifylines", "0", "+crosshair", "0", "+cl_bob", "0", "+movebob", "0"]
    if qa:
        uz += ["-ddqa", str(qa)]
    uz += list(uz_extra) + ["+map", "DDT07154"]
    df = ["-dfbridgelog", str(run / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-dfmute", "-screen-fullscreen", "0",
          "-screen-width", str(WIDTH), "-screen-height", str(HEIGHT)] + list(df_extra)
    cmd = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(PLAY / "doomerfall-launcher.exe"), *(["--minimized"] if minimized else []), "--nodraw",
           "--uzdoom", str(PLAY / "uzdoom" / "uzdoom.exe"), "--dfu", str(PLAY / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
           "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
    mods = DRLA + [data / n for n in DUNGEON] + [PLAY / "dfitems.pk3", work / "doomerfall.pk3", work / "doomerfall-drla.pk3", HERE / "doom"]
    for m in mods:
        cmd += ["--mod", str(m)]
    for a in uz:
        cmd += ["--uzdoom-arg", a]
    for a in df:
        cmd += ["--dfu-arg", a]
    return cmd


def fresh_run_folder(run):
    (run / "saves").mkdir(parents=True, exist_ok=True)
    for name in ("uz.log", "df.log", "log-vpcon.txt", "launcher.log"):
        (run / name).unlink(missing_ok=True)


def fatal(run):
    body = read(run / "log-vpcon.txt")
    return next((k for k in FATAL if k in body), None)


def kill(proc):
    if proc and proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()


def capture_daggerfall(job_lines, out, timeout, log_name):
    """Runs the Daggerfall Unity capture player (DungeonCaptureTest) on a job and returns its result lines."""
    job = out / (log_name + "_job.txt")
    job.write_text("\n".join(job_lines) + "\n", encoding="utf-8", newline="\n")
    result = out / "df_probes.txt"
    result.unlink(missing_ok=True)
    code = subprocess.run([sys.executable, QUIET, "--timeout", str(timeout), "--", str(CAPTURE_EXE), "-dfcapture", str(job),
                           "-screen-fullscreen", "0", "-screen-width", str(WIDTH), "-screen-height", str(HEIGHT),
                           "-logFile", str(out / (log_name + "_player.log"))]).returncode
    lines = read(result).splitlines()
    if result.exists():
        result.replace(out / (log_name + "_result.txt"))
    print("Daggerfall Unity capture exit code:", code, "last line:", lines[-1] if lines else "none")
    return lines


def pair(left, right, side, label_left="Daggerfall Unity", label_right="Doomerfall"):
    """Writes a side-by-side image and returns a rough difference score (mean absolute difference, 0-255, on a
    downscaled grey copy), or None if either image is missing."""
    if not (Path(left).exists() and Path(right).exists()):
        return None
    a, b = Image.open(left).convert("RGB"), Image.open(right).convert("RGB")
    if b.size != a.size:
        b = b.resize(a.size, Image.BILINEAR)
    canvas = Image.new("RGB", (a.width * 2 + 6, a.height), (255, 255, 0))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width + 6, 0))
    canvas.save(side)
    small = (160, 120)
    diff = ImageChops.difference(a.convert("L").resize(small), b.convert("L").resize(small))
    return round(ImageStat.Stat(diff).mean[0], 1)


def mean_brightness(path):
    return round(ImageStat.Stat(Image.open(path).convert("L")).mean[0], 1)


def write_index(path, title, cards):
    import html
    body = []
    for c in cards:
        img = f'<img src="{html.escape(c["side"])}" loading="lazy">' if c.get("side") else "<p>missing image</p>"
        body.append(f'<h2>{html.escape(c["title"])}</h2><p>{html.escape(c.get("note", ""))}</p>{img}')
    Path(path).write_text("<!doctype html><meta charset=utf-8><title>" + html.escape(title) + "</title>"
                          "<style>body{background:#222;color:#eee;font:15px sans-serif}img{max-width:100%}</style>"
                          f"<h1>{html.escape(title)}</h1><p>Daggerfall Unity on the left, Doomerfall on the right.</p>" + "".join(body),
                          encoding="utf-8")


def wait_until(predicate, seconds, run=None, step=0.1):
    end = time.time() + seconds
    while time.time() < end:
        if predicate():
            return True
        if run and fatal(run):
            return False
        time.sleep(step)
    return False


def copy_tree_files(src, dst):
    for f in Path(src).rglob("*"):
        if f.is_file():
            t = Path(dst) / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
