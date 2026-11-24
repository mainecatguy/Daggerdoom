"""QA bot CLI prototype: lets a text agent drive a paired Doomerfall session. Claude-run QA only (UZDoom -ddqa).

  qa.py assemble                 Build the session folder from a play folder and this branch's uzdoom build.
  qa.py start [--dungeon]        Start both games through the launcher, minimized, at Gothway Garden's Privateer's Hold
                                 door; --dungeon also presses Use on the door and waits until inside.
  qa.py <command> [args...]      Send one command to Doom and print its JSON reply. See work/notes/*-qa-bot.md.
                                 pos | actors [radius] [limit] [kind] | move_to x y [tolerance] [seconds] | stop |
                                 use | god [on|off] | teleport x y [z|nan] [angle] | kill <ref or Daggerfall id> |
                                 con <console command>
  qa.py wait <job> [seconds]     Block until a job (the id move_to returned) finishes; prints its result.
  qa.py events                   Print the events written since the session started.
  qa.py quit                     End the session.

Every command and reply is kept in the session's inbox.txt and outbox.jsonl, so a run can be replayed.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SESSION = Path(os.environ.get("DDQA_SESSION", r"D:\dev\DoomDaggerfall-loop\review\qabot"))
PLAY = Path(os.environ.get("DDQA_PLAY", r"D:\dev\DoomDaggerfall-loop\review\newstart3"))  # uzdoom, dfu, data, pk3s, launcher
BUILD = Path(os.environ.get("DDQA_BUILD", r"D:\dev\DoomDaggerfall-build\uzdoom-qabot\Release"))
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
DRLA = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
GROUP = 7154
SESSION_SECONDS = int(os.environ.get("DDQA_SECONDS", "240"))  # quiet_run's hard limit on one session; overnight runs raise it
QA = SESSION / "qa"
INBOX, OUTBOX = QA / "inbox.txt", QA / "outbox.jsonl"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def say(obj):
    print(json.dumps(obj, separators=(",", ":")))


def lines():
    if not OUTBOX.exists():
        return []
    out = []
    for raw in OUTBOX.read_text(errors="replace").splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            out.append({"unparsed": raw})
    return out


def fatal():
    log = SESSION / "run" / "uz-console.txt"
    body = log.read_text(errors="replace") if log.exists() else ""
    return next((k for k in FATAL if k in body), None)


def send(text):
    """Appends one command and returns its id."""
    seq = SESSION / "qa" / "seq"
    n = int(seq.read_text()) + 1 if seq.exists() else 1
    seq.write_text(str(n))
    cid = f"c{n}"
    with open(INBOX, "a", newline="\n") as f:
        f.write(f"{cid} {text}\n")
    return cid


def await_line(match, seconds):
    end = time.time() + seconds
    while time.time() < end:
        for obj in lines():
            if match(obj):
                return obj
        if fatal():
            return {"ok": False, "error": "fatal: " + fatal()}
        time.sleep(0.05)
    return None


def command(words, seconds=10):
    cid = send(" ".join(words))
    got = await_line(lambda o: o.get("id") == cid and "done" not in o, seconds)
    if got is None:
        paused = [o for o in lines() if o.get("event") in ("paused", "resumed")]
        got = {"id": cid, "ok": False, "error": "no reply (game paused or not in a level?)",
               "paused": bool(paused) and paused[-1]["event"] == "paused"}
    return got


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def assemble():
    SESSION.mkdir(parents=True, exist_ok=True)
    for name in ("dfu", "data"):  # Junctions to the play folder: no copy.
        if not (SESSION / name).exists():
            subprocess.check_call(["cmd", "/c", "mklink", "/J", str(SESSION / name), str(PLAY / name)], stdout=subprocess.DEVNULL)
    if (SESSION / "uzdoom").exists():
        shutil.rmtree(SESSION / "uzdoom")
    shutil.copytree(PLAY / "uzdoom", SESSION / "uzdoom")
    for name in ("uzdoom.exe", "uzdoom.pk3"):
        shutil.copy2(BUILD / name, SESSION / "uzdoom" / name)
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(PLAY / name, SESSION / name)
    say({"ok": True, "assembled": str(SESSION)})


def start(dungeon):
    run = SESSION / "run"
    (run / "saves").mkdir(parents=True, exist_ok=True)
    if QA.exists():
        shutil.rmtree(QA)
    QA.mkdir()
    INBOX.write_text("")
    for name in ("uz.log", "df.log", "uz-console.txt", "launcher.log"):
        (run / name).unlink(missing_ok=True)
    data = SESSION / "data"
    uz = ["-noactivate", "-ddqa", str(QA), "-config", str(run / "qa.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(run / "uz.log"),
          "-nosound", "-noautoload", "-skill", "3", "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+logfile", "uz-console.txt", "+vid_fullscreen", "0", "+wipetype", "0",
          "+screenshot_dir", str(QA / "shots"), "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(run / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    cmd = [sys.executable, QUIET, "--timeout", str(SESSION_SECONDS), "--", str(SESSION / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", str(SESSION / "uzdoom" / "uzdoom.exe"), "--dfu", str(SESSION / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
           "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
    for mod in DRLA + [data / n for n in DUNGEON] + [SESSION / "dfitems.pk3", SESSION / "doomerfall.pk3"]:
        cmd += ["--mod", str(mod)]
    for a in uz:
        cmd += ["--uzdoom-arg", a]
    for a in df:
        cmd += ["--dfu-arg", a]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    (QA / "pid").write_text(str(proc.pid))
    t0 = time.time()
    if not await_line(lambda o: o.get("event") == "level", 60):
        return say({"ok": False, "error": "no level event in 60 s", "fatal": fatal()})
    # Wait for Daggerfall's sync phase 3 (both games in the same place), as the scripted harnesses do.
    while time.time() - t0 < 90:
        p = command(["pos"])
        if p.get("df_phase") == 3:
            break
        time.sleep(0.5)
    else:
        return say({"ok": False, "error": "Daggerfall never reached sync phase 3", "last": p})
    door = next(r for r in (l.split() for l in lumps(SESSION / "data" / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()) if r[0] == "1")
    x, y, z, nx, ny = map(float, door[3:8])
    import math
    face = math.degrees(math.atan2(-ny, -nx))
    out = {"ok": True, "seconds": round(time.time() - t0, 1), "door": [x, y, z], "teleport": command(["teleport", f"{x + nx * 48:.1f}", f"{y + ny * 48:.1f}", "nan", f"{face:.1f}"])}
    if dungeon:
        command(["con", "dd_tm_use", "1"])
        inside = None
        for _ in range(60):
            time.sleep(0.5)
            p = command(["pos"])
            if p.get("map") and not str(p["map"]).upper().startswith("DDT"):  # Left the town map: a dungeon or building.
                inside = p
                break
        out["inside"] = inside
        out["ok"] = inside is not None
    say(out)


def wait(job, seconds):
    got = await_line(lambda o: o.get("id") == job and o.get("done"), seconds)
    say(got or {"id": job, "done": False, "error": f"still running after {seconds} s"})


def quit_session():
    pid = (QA / "pid").read_text() if (QA / "pid").exists() else ""
    if pid:
        subprocess.call(["taskkill", "/F", "/T", "/PID", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say({"ok": True, "quit": pid})


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    verb = args[0]
    if verb == "assemble":
        assemble()
    elif verb == "start":
        start("--dungeon" in args)
    elif verb == "wait":
        wait(args[1], float(args[2]) if len(args) > 2 else 30)
    elif verb == "events":
        say([o for o in lines() if "event" in o])
    elif verb == "quit":
        quit_session()
    else:
        say(command(args))


if __name__ == "__main__":
    main()
