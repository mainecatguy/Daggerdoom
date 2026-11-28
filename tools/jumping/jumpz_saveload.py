"""Save/load check for the Jumping skill's jump height (DoomerfallJump.zs): a real Doom save made at one Jumping value,
then loaded in new launches at other values, must give the default JumpZ scaled once for the new value.
Doom only, with DRLA, on DOOM2 MAP01; jumpz_saveload.zs turns the handler on as a Daggerfall map would.

usage: jumpz_saveload.py <uzdoom.exe> <run dir>      (the run folder is deleted and recreated)"""
import glob, math, os, re, shutil, subprocess, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GAME = r"D:\dev\DoomDaggerfall\GameResources"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"


def factor(s):
    return 1.0 + s / 100.0 + (0.25 if s >= 25 else 0.0)


def launch(uz, run, name, mode, skill, extra):
    pk3 = os.path.join(run, name + ".pk3")
    text = open(os.path.join(HERE, "jumpz_saveload.zs")).read().replace("@MODE@", mode).replace("@SKILL@", str(skill)).replace("@OLDFACTOR@", "1.7")
    with zipfile.ZipFile(pk3, "w") as z:
        z.writestr("zscript/probe.zs", text)
        z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
        z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "DoomerfallJumpZSaveLoad" }\n')
    files = [os.path.join(MODS, m) for m in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    files += [os.path.join(run, "doomerfall.pk3"), pk3]
    log = os.path.join(run, f"log-{name}.txt")  # UZDoom names +logfile <name> this way, in its working folder
    cmd = [sys.executable, QUIET, "--timeout", "40", "--cwd", run, "--", uz, "-iwad", os.path.join(GAME, "wads", "DOOM2.WAD"),
           "-noautoload", "-nomonsters", "-skill", "3", "-config", os.path.join(run, "uzdoom.ini"), "-savedir", os.path.join(run, "saves"),
           "+logfile", name, "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-file"] + files + extra
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + 45
    body = ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
        body = open(log, errors="replace").read() if os.path.exists(log) else ""
        if "JZDONE" in body or "FATAL" in body or "VM execution aborted" in body:
            time.sleep(1)
            break
    subprocess.run(["taskkill", "/f", "/t", "/pid", str(proc.pid)], capture_output=True)
    proc.wait()
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    m = re.search(r"JZTEST mode=(\w+) skill=(-?\d+) jumpz=([\d.]+) default=([\d.]+) class=(\S+)", body)
    if not m:
        print(name, ": no JZTEST line;", "\n".join(l for l in body.splitlines() if re.search("doomerfall.pk3.*error|probe.*error|FATAL|aborted", l, re.I))[:2000])
        return None
    print(name, ":", m.group(0))
    return float(m.group(3)), float(m.group(4))


def main():
    uz, run = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    if os.path.isdir(run):
        shutil.rmtree(run)
    os.makedirs(os.path.join(run, "saves"))
    subprocess.check_call([sys.executable, os.path.join(REPO, "scripts", "doomerfall", "build_pk3.py"), os.path.join(run, "doomerfall.pk3")])
    ok = True

    def check(name, got, skill):
        nonlocal ok
        if got is None:
            ok = False
            return
        jumpz, default = got
        want = default * math.sqrt(factor(skill))
        good = abs(jumpz - want) < 1e-3
        ok &= good
        print(f"  {name}: Jumping {skill}: JumpZ {jumpz:.4f}, want {want:.4f} (default {default:.4f}): {'ok' if good else 'WRONG'}")

    check("save", launch(uz, run, "save", "save", 50, ["+map", "MAP01"]), 50)
    saves = glob.glob(os.path.join(run, "saves", "*.zds"))
    if not saves:
        print("no save written")
        ok = False
    else:
        save = os.path.basename(max(saves, key=os.path.getmtime))
        for skill in (100, 0, 50, 75):
            check(f"load{skill}", launch(uz, run, f"load{skill}", "load", skill, ["-loadgame", save]), skill)
    for old in glob.glob(os.path.join(run, "saves", "*.zds")):
        os.remove(old)
    launch(uz, run, "oldsave", "oldsave", 50, ["+map", "MAP01"])
    saves = glob.glob(os.path.join(run, "saves", "*.zds"))
    if not saves:
        print("no old-formula save written")
        ok = False
    else:
        save = os.path.basename(max(saves, key=os.path.getmtime))
        for skill in (0, 50, 100):
            check(f"oldload{skill}", launch(uz, run, f"oldload{skill}", "load", skill, ["-loadgame", save]), skill)
    print("JUMPZ SAVELOAD PASS" if ok else "JUMPZ SAVELOAD FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
