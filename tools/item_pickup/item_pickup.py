"""Builds and assembles the Doomerfall item pickup demo in a private review folder.

usage: item_pickup.py build | unity | sprites | assemble | playcheck | check | registry save|compare
It reuses the inventory demo's build steps with its own folder. Game data stays out of the repo.
"""
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "inventory_menu"))
import inventory_menu as base  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\item-pickup")
base.PREVIOUS = Path(r"D:\dev\DoomDaggerfall-loop\review\inventory-menu")
base.REVIEW, base.BUILD, base.RUN = REVIEW, REVIEW / "build", REVIEW / "run"
SPRITES = REVIEW / "dfitems.pk3"

DATA = Path(r"D:\dev\DoomDaggerfall-loop\review\combined-bridge\data")
GROUP = 7154  # The location whose dungeon door leads to the packaged Privateer's Hold.
BINDS = [("e", "netevent df_interact"), ("i", "netevent df_inventory"), ("k", "netevent df_fast_travel")]
START = """version "4.14"
// Demo only: starts the player facing the Privateer's Hold door.
class ItemDemoStart : StaticEventHandler
{
	bool done;
	override void WorldLoaded(WorldEvent e) { if (e.IsSaveGame) done = true; }
	override void WorldTick()
	{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		let p = players[0].mo;
		p.SetOrigin((@X@ + @NX@ * 64, @Y@ + @NY@ * 64, @Z@), false);
		p.angle = atan2(-(@NY@), -(@NX@));
		Console.Printf("ITEMDEMO at the dungeon door");
	}
}
"""


def launch_args(here, extra_uz=(), extra_df=(), minimized=False):
    """The demo's launcher arguments, shared by play.bat and its automated check."""
    args = ["--nodraw"] + (["--minimized"] if minimized else [])
    args += ["--uzdoom", here + r"uzdoom\uzdoom.exe", "--dfu", here + r"dfu\DaggerfallUnity.exe", "--iwad", base.IWAD2]
    for mod in (r"data\ddruntime.pk3", r"data\overworld.pk3", r"data\privateershold.wad", r"data\privateershold_mesh.pk3",
                r"data\privateershold_doors.pk3", "dfitems.pk3", "doomerfall", "demo_start.pk3"):
        args += ["--mod", here + mod]
    args += ["--uzdoom-cwd", here + "play", "--log", here + r"play\launcher.log"]
    uz = ["-config", here + r"play\uzdoom.ini", "-savedir", here + r"play\saves", "-dfbridgelog", here + r"play\uz.log",
          "-ddtowncache", here + r"data\cache", "-ddconverter", here + r"data\converter\DungeonConverter.exe", "-ddarena2", base.DAGGER + r"\ARENA2",
          "-skill", "3", "+map", f"DDT{GROUP:05d}", "+vid_fullscreen", "0", "+i_pauseinbackground", "0"] + list(extra_uz)
    df = ["-dfbridgelog", here + r"play\df.log", "-dfsynctest", base.DAGGER, "-dfinventorytest", "-screen-fullscreen", "0",
          "-screen-width", "1280", "-screen-height", "800"] + list(extra_df)
    for arg in uz:
        args += ["--uzdoom-arg", arg]
    for arg in df:
        args += ["--dfu-arg", arg]
    return args


def quoted(args):
    return " ".join(f'"{a}"' if " " in a or "%" in a or "\\" in a else a for a in args)


bind_args = [a for key, command in BINDS for a in ("--uzdoom-arg", "+bind", "--uzdoom-arg", key, "--uzdoom-arg", command)]
base.PLAY = (
    "@echo off\n"
    "rem Starts at the Privateer's Hold door. Press Use to go in, look at a loot pile, and press E to take it.\n"
    "rem I opens Daggerfall's inventory. Rebind both in Options, Customize Controls, Doomerfall Controls.\n"
    "set \"HERE=%~dp0\"\n"
    "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\n"
    "set BINDS=\n"
    f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={quoted(bind_args)}\n"
    f"start \"\" \"%HERE%doomerfall-launcher.exe\" {quoted(launch_args('%HERE%'))} %BINDS%\n"
)


def demo_data():
    base.copy_tree(DATA, REVIEW / "data")
    with open(DATA / "cache" / f"T{GROUP:05d}.ddt", "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        lumps = {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}
    door = next(l.split() for l in lumps["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    text = START
    for name, value in zip(("@X@", "@Y@", "@Z@", "@NX@", "@NY@"), door[3:8]):
        text = text.replace(name, value)
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ItemDemoStart" }\n')


def play_check():
    """Launches play.bat's exact setup, minimized and without focus, in a throwaway play folder."""
    here = str(REVIEW) + "\\"
    play = REVIEW / "play"
    keep = play.with_name("play-owner")
    if play.exists() and not keep.exists():
        play.rename(keep)
    play.mkdir(exist_ok=True)
    command = [sys.executable, base.QUIET, "--timeout", "25", "--", here + "doomerfall-launcher.exe"]
    command += launch_args(here, ["-noactivate", "-nosound", "+logfile", "demo", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"], minimized=True)
    subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # quiet_run stops only the launcher at its timeout, so end this folder's games before reading and cleaning up.
    subprocess.call(["powershell", "-NoProfile", "-Command",
                     f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -like '{REVIEW}\\*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    log = base.read(play / "log-demo.txt")
    df = base.read(play / "df.log")
    print(f"play setup: door start {'ITEMDEMO at the dungeon door' in log}, town {'DDTOWN active DDT07154' in log}, fatal {any(k in log for k in base.FATAL)}, Daggerfall in world {'entered the world' in df}")
    shutil.rmtree(play)
    if keep.exists():
        keep.rename(play)


def sprites():
    project = base.WORKTREE / "tools" / "item_gallery" / "ItemGallery.csproj"
    templates = base.WORKTREE / "daggerfall-unity-master" / "Assets" / "StreamingAssets" / "ItemTemplates.txt"
    if not templates.exists():
        found = list((base.WORKTREE / "daggerfall-unity-master" / "Assets").rglob("ItemTemplates.txt"))
        if not found:
            sys.exit("ItemTemplates.txt not found")
        templates = found[0]
    REVIEW.mkdir(parents=True, exist_ok=True)
    code = subprocess.call(["dotnet", "run", "-c", "Release", "--project", str(project), "--", base.DAGGER + r"\ARENA2", str(templates),
                            str(base.WORKTREE / "mods" / "daggerfall_items"), str(SPRITES), str(REVIEW / "dfitems-manifest.tsv")], stdin=subprocess.DEVNULL)
    if code:
        sys.exit(f"sprite package failed ({code})")


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "build":
        base.build()
    elif command == "unity":
        base.unity()
    elif command == "sprites":
        sprites()
    elif command == "assemble":
        base.assemble()
        for name in ("sndfile.dll", "soft_oal.dll"):
            shutil.copy2(base.SOUND / name, REVIEW / "uzdoom")
        demo_data()
    elif command == "playcheck":
        play_check()
    elif command == "check":
        base.check()
    elif command == "registry":
        base.registry(sys.argv[2])
    else:
        sys.exit(__doc__)
