"""Ammo without a material has a plain name (card ammoname 01), Doom side, no bridge.

usage: ammoname.py assemble | doom
assemble: makes the review folder: this worktree's engine build, this worktree's doomerfall.pk3 and doomerfall-drla.pk3,
          and the same mod as it was at git HEAD (before this change) in run/old/ for the old save.
doom:     for stock DOOM.WAD and with the DRLA set: E1M1 with the old mod saves a game holding a Regular and a Silver
          clip; E1M1 with the new mod prints every tiered pickup's tag (the look label), the HUD name and the pickup
          message; then the old save loads with the new mod and prints the saved pickups' names.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\ammoname")
ENGINE = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-quiet\Release")  # Built from this worktree after its last engine change.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map", "Script error")
SRC = "mods/doomerfall/src"


def build(out, at_head):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((REPO / SRC).rglob("*")):
            if p.is_file():
                rel = p.relative_to(REPO / SRC).as_posix()
                data = subprocess.check_output(["git", "-C", str(REPO), "show", f"HEAD:{SRC}/{rel}"]) if at_head else p.read_bytes()
                z.writestr(rel, data)


def harness(path, new):
    text = (HERE / "harness.zs").read_text()
    if not new:  # The old mod has no AmmoName.
        a, b = text.index("/*NEW*/"), text.rindex("/*NEW*/") + len("/*NEW*/")
        text = text[:a] + '"-"' + text[b:]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ANHarness" }\n')


def assemble():
    if (REVIEW / "uzdoom").exists():
        shutil.rmtree(REVIEW / "uzdoom")
    shutil.copytree(ENGINE, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    (REVIEW / "run" / "old").mkdir(parents=True, exist_ok=True)
    build(REVIEW / "doomerfall.pk3", False)
    build(REVIEW / "run" / "old" / "doomerfall.pk3", True)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    print("assembled", REVIEW)


def launch(runs, name, mods, extra):
    log = runs / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate",
               "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"{name}.ini"), "-savedir", str(runs / "saves"), "-nosound",
               "-noautoload", "-skill", "3", "-file", *mods, "+logfile", name, "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
               "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", *extra]
    code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    fatal = [l for l in body.splitlines() if any(k in l for k in FATAL)]
    print(f"{name}: exit {code}, {len(body.splitlines())} lines, fatal/script errors {len(fatal)}")
    for l in fatal[:5]:
        print("   ", l[:200])
    return body


def doom():
    runs = REVIEW / "run"
    (runs / "saves").mkdir(parents=True, exist_ok=True)
    old_h, new_h = runs / "harness-old.pk3", runs / "harness-new.pk3"
    harness(old_h, False)
    harness(new_h, True)
    ok = True
    for label, base in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        drla = [str(REVIEW / "doomerfall-drla.pk3")] if base else []
        save = runs / "saves" / f"old-{label}.zds"
        save.unlink(missing_ok=True)
        launch(runs, f"old-{label}", base + [str(runs / "old" / "doomerfall.pk3")] + drla + [str(old_h)],
               ["+map", "E1M1", f"+wait 70;save {save.name};wait 35;quit"])
        body = launch(runs, f"new-{label}", base + [str(REVIEW / "doomerfall.pk3")] + drla + [str(new_h)], ["+map", "E1M1", "+wait 70;quit"])
        tags = [l for l in body.splitlines() if l.startswith("ANTAG")]
        spawns = [l for l in body.splitlines() if l.startswith("ANSPAWN")]
        for l in tags[:12] + tags[20:22] + tags[30:32] + spawns:
            print("   ", l)
        regular = [l for l in tags if " tier=0 " in l]
        plain = all("Regular" not in l for l in tags) and [l.split("tag=")[1].split(" hud=")[0] for l in regular] == ["Bullets", "Shells", "Rockets", "Energy Cells"]
        tiered = "type=0 tier=2 tag=Silver Bullets hud=Silver Bullets" in body and "type=3 tier=9 tag=Daedric Energy Cells" in body
        same = all(l.split("tag=")[1].split(" hud=")[0] == l.split(" hud=")[1] for l in tags) and len(tags) == 40
        messages = "message=Picked up 10 Bullets." in body and "message=Picked up 10 Silver Bullets." in body
        if not save.exists():
            print(f"   no old save written ({save})")
            loaded = ""
        else:
            loaded = launch(runs, f"load-{label}", base + [str(REVIEW / "doomerfall.pk3")] + drla + [str(new_h)], ["-loadgame", save.name, "+wait 70;quit"])  # Relative to -savedir.
            for l in loaded.splitlines():
                if l.startswith("ANLOAD"):
                    print("   ", l)
        old = "ANLOAD class=DFAmmo_Clip_0 tag=Bullets message=Picked up 10 Bullets." in loaded and "ANLOAD class=DFAmmo_Clip_2 tag=Silver Bullets" in loaded
        result = plain and tiered and same and messages and old
        ok &= result
        print(f"{label}: Regular plain {plain}, tiered keeps material {tiered}, HUD = tag {same}, pickup messages {messages},"
              f" old save shows new names {old}: {'PASS' if result else 'FAIL'}")
    print("doom:", "PASS" if ok else "FAIL")


{"assemble": assemble, "doom": doom}[sys.argv[1]]()
