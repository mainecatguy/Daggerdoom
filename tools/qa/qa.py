"""QA bot CLI prototype: lets a text agent drive a paired Doomerfall session. Claude-run QA only (UZDoom -ddqa).

  qa.py assemble                 Build the session folder from a play folder and this branch's uzdoom build.
  qa.py start [--dungeon]        Start both games through the launcher, minimized, at Gothway Garden's Privateer's Hold
                                 door; --dungeon also presses Use on the door and waits until inside.
  qa.py start --solo <file>...   Start Doom alone (no Daggerfall) on MAP01 of the given converted dungeon files, for
                                 movement checks. Set DDQA_POINTS to that conversion's points.txt.
  qa.py <command> [args...]      Send one command to Doom and print its JSON reply. See work/notes/*-qa-bot.md.
                                 pos | actors [radius] [limit] [kind] | move_to x y [tolerance] [seconds] |
                                 fly_to x y z [tolerance] [seconds] | stop | use | god [on|off] |
                                 teleport x y [z|nan] [angle] | kill <ref or Daggerfall id> | con <console command>
  qa.py goto x y z [seconds]     Plan with nav.py over the dungeon's walk graph and walk there honestly, one move_to per
                                 waypoint, in this one call. Prints the plan and the outcome. Only when no walking
                                 route exists, it plans again with levitation links (fewest flights first) and flies
                                 those links with fly_to: the QA bot's own flight, standing in for Levitate until
                                 Doomerfall has it. Every flight is listed in the reply and in the run summary.
  qa.py summary                  Print the run summary (setup commands used, and every place the bot flew) and write it
                                 to the session's qa/summary.txt.
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
POINTS = Path(os.environ.get("DDQA_POINTS", r"D:\dev\DoomDaggerfall-loop\review\encounter-placer\wad\privateershold.points.txt"))
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


def start_solo(files):
    """Doom alone on MAP01 of a converted dungeon: no launcher, no Daggerfall (Doom keeps running without it)."""
    run = SESSION / "run"
    # DDQA_VISIBLE=1 is for a person watching a demo (review play.bat): the window opens on their desktop.
    quiet = [] if os.environ.get("DDQA_VISIBLE") == "1" else [sys.executable, QUIET, "--timeout", str(SESSION_SECONDS), "--cwd", str(run), "--"]
    cmd = [*quiet, str(BUILD / "uzdoom.exe"),
           "-iwad", str(GAME / "wads" / "DOOM2.WAD"), "-file", *files, "-ddqa", str(QA), "-config", str(run / "qa.ini"),
           "-noautoload", "-skill", "3", "+logfile", "uz-console.txt", "+vid_fullscreen", "0", "+wipetype", "0",
           "+screenshot_dir", str(QA / "shots"), "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
           "+vid_lowerinbackground", "0", "+map", "MAP01"]
    proc = subprocess.Popen(cmd, cwd=str(run), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    (QA / "pid").write_text(str(proc.pid))
    t0 = time.time()
    if not await_line(lambda o: o.get("event") == "level", 60):
        return say({"ok": False, "error": "no level event in 60 s", "fatal": fatal()})
    say({"ok": True, "solo": True, "seconds": round(time.time() - t0, 1), "pos": command(["pos"])})


def start(dungeon, solo=None):
    run = SESSION / "run"
    (run / "saves").mkdir(parents=True, exist_ok=True)
    QA.mkdir(exist_ok=True)
    for old in QA.iterdir():  # Empty the folder rather than remove it: a shell may be sitting in it.
        shutil.rmtree(old) if old.is_dir() else old.unlink()
    INBOX.write_text("")
    for name in ("uz.log", "df.log", "uz-console.txt", "launcher.log"):
        (run / name).unlink(missing_ok=True)
    if solo:
        return start_solo(solo)
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


def goto(x, y, z, seconds):
    sys.path.insert(0, str(HERE))
    import nav
    graph = nav.Graph(POINTS)
    here = command(["pos"])
    if not here.get("ok"):
        return say(here)
    plan = graph.plan(here["x"], here["y"], here["z"], x, y, z)
    if not plan["ok"] and "no walking route" in plan.get("error", ""):
        # Only a spot that walking cannot reach may use the bot's flight in place of Levitate.
        graph.add_levitation()
        plan = graph.plan(here["x"], here["y"], here["z"], x, y, z)
        if plan["ok"]:
            plan["needs_levitation"] = True
    if not plan["ok"]:
        return say(plan)
    out = {k: v for k, v in plan.items() if k not in ("waypoints", "segments")}
    out["waypoint_count"] = len(plan["waypoints"])
    out["flights"] = []
    end, tics, travelled, i, takeoff = time.time() + seconds, 0, 0.0, -1, None
    for segment in plan["segments"]:
        for (wx, wy, wz) in segment["waypoints"]:
            i += 1
            last = i == len(plan["waypoints"]) - 1
            left = str(max(1, int(end - time.time())))
            if segment["fly"]:
                done = fly(wx, wy, wz, end, out, takeoff)
            takeoff = (wx, wy, wz)
            for attempt in range(0 if segment["fly"] else 2):  # Stuck once: press Use (a closed door on the route), retry.
                # The walk up to a flight ends close beside the ledge.
                job = command(["move_to", str(wx), str(wy), "12" if plan.get("needs_levitation") else ("24" if last else "20"), left])
                done = await_line(lambda o: o.get("id") == job.get("id") and o.get("done"), max(1, end - time.time()) + 2) if job.get("ok") else job
                if attempt or not done or done.get("result") != "stuck":
                    break
                command(["use"])
                out["uses"] = out.get("uses", 0) + 1
                time.sleep(1.0)  # Doors take about a second to open.
            if segment["fly"]:
                out["flights"].append({"from": (done or {}).get("fly_from"), "to": [wx, wy, wz], "result": (done or {}).get("result"),
                                       "landed": [(done or {}).get(k) for k in ("x", "y", "z")]})
            if not done or done.get("result") != "arrived":
                out.update(ok=False, failed_at=i, at=[wx, wy, wz], flying=segment["fly"], last=done)
                return say(out)
            tics += done["tics"]
            travelled += done["travelled"]
    out.update(ok=True, result="arrived", honest=True, tics=tics, seconds_game=round(tics / 35, 1), travelled=round(travelled),
               final=command(["pos"]))
    say(out)


def settle():
    """Waits (up to 1.5 s) until the player stops sliding: Doom keeps about 85 units of momentum after a walk."""
    last = command(["pos"])
    for _ in range(60):
        time.sleep(0.06)
        p = command(["pos"])
        if p.get("tic") == last.get("tic"):  # Two replies in one tic say nothing about movement.
            continue
        if (p.get("x"), p.get("y"), p.get("z")) == (last.get("x"), last.get("y"), last.get("z")):
            break
        last = p
    return last


def walk_to_spot(x, y):
    """Walks to (x, y) and stays: repeats while the slide after arriving carries the player more than 8 units off."""
    for _ in range(4):
        p = settle()
        if ((p["x"] - x) ** 2 + (p["y"] - y) ** 2) ** 0.5 <= 8:
            return p
        job = command(["move_to", f"{x:.1f}", f"{y:.1f}", "4", "5"])
        await_line(lambda o: o.get("id") == job.get("id") and o.get("done"), 8)
    return settle()


def fly(wx, wy, wz, end, out, takeoff=None):
    """One levitation link by flight, from the take-off node (the walk's last waypoint, which the walk graph says is
    clear overhead). The graph is a 24-unit lattice and the body is 32 wide, so rising right beside a ledge can bump its
    underside: when a flight stops below the ledge, take off again 16 and then 32 units further back, on the line from
    the ledge through the take-off node."""
    here = command(["pos"])
    takeoff = takeoff or (here["x"], here["y"], here["z"])
    dx, dy = takeoff[0] - wx, takeoff[1] - wy
    n = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    done = None
    for back in (0, 16, 32):
        p = walk_to_spot(takeoff[0] + dx / n * back, takeoff[1] + dy / n * back)
        if abs(p["z"] - takeoff[2]) > 24:  # Never fly from anywhere but the planned floor: it could reach unchecked places.
            return {"done": True, "result": "wrong_floor", "flew": False, "takeoff": list(takeoff), "x": p["x"], "y": p["y"], "z": p["z"]}
        if back:
            out["flight_retries"] = out.get("flight_retries", 0) + 1
        job = command(["fly_to", str(wx), str(wy), str(wz), "12", str(max(1, int(end - time.time())))])
        done = await_line(lambda o: o.get("id") == job.get("id") and o.get("done"), max(1, end - time.time()) + 2) if job.get("ok") else job
        if not done or done.get("result") != "stuck" or done.get("z", 0) >= wz:
            break
    return done


def summary():
    """Setup commands used and every flight, from the session's own logs (inbox and outbox)."""
    setup = [l.split(" ", 1)[1] for l in INBOX.read_text().splitlines() if len(l.split()) > 1 and l.split()[1] in ("teleport", "god", "kill", "con")] \
        if INBOX.exists() else []
    flights = [{k: o.get(k) for k in ("tic", "result", "from", "to")} for o in lines() if o.get("event") == "flew"]
    text = ["QA run summary", f"setup commands: {len(setup)}"] + [f"  {s}" for s in setup]
    text.append(f"flights (QA bot flight in place of Levitate): {len(flights)}")
    text += [f"  tic {f['tic']}: {f['result']}, from {f['from']} to {f['to']}" for f in flights]
    (QA / "summary.txt").write_text("\n".join(text) + "\n")
    say({"ok": True, "setup": setup, "flights": flights, "file": str(QA / "summary.txt")})


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
        start("--dungeon" in args, args[args.index("--solo") + 1:] if "--solo" in args else None)
    elif verb == "wait":
        wait(args[1], float(args[2]) if len(args) > 2 else 30)
    elif verb == "goto":
        goto(float(args[1]), float(args[2]), float(args[3]), float(args[4]) if len(args) > 4 else 60)
    elif verb == "events":
        say([o for o in lines() if "event" in o])
    elif verb == "summary":
        summary()
    elif verb == "quit":
        quit_session()
    else:
        say(command(args))


if __name__ == "__main__":
    main()
