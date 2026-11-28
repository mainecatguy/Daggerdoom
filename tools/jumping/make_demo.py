"""Turns a play folder made by scripts/play/install.py into the jumping demo: adds jump_demo.pk3 (demo_skill.zs) and
replaces play.bat's what-to-try notes with the jumping ones. usage: make_demo.py <play folder>"""
import os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
play = os.path.abspath(sys.argv[1])
with zipfile.ZipFile(os.path.join(play, "jump_demo.pk3"), "w") as z:
    z.write(os.path.join(HERE, "demo_skill.zs"), "zscript/demo.zs")
    z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/demo.zs"\n')
    z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "DoomerfallJumpDemo" }\n')

NOTES = [
    "Jumping demo. Choose New Game in Doom's menu and make any character. A fall up to 1.5x your jump height is free, then 5 HP per metre.",
    " 1. Climb onto a roof (hold forward against a store wall) and walk off: falls over about 2 m hurt at Jumping 0. A jump that lands where it started never hurts.",
    " 2. Open the console (~) and type: netevent jumpskill:25  (or 0, 50, 75, 100; -1 goes back to your real Jumping). This does not change Daggerfall's sheet.",
    " 3. At 25 jumps are 1.5x as high (+25% spike), at 100 2.25x. At 50 press Jump again in mid-air (double jump), at 100 twice (triple jump).",
    " 4. The higher you jump, the farther you can fall: the same roof hurts less at 100 (free fall 3.9 m) than at 0 (1.8 m). No level makes falls harmless any more.",
    " 5. Walk off the roof at 50 or more and press Jump on the way down: the double jump still works.",
    " 6. Every jump, ground or mid-air, trains Jumping: watch the Jumping skill climb on Daggerfall's character sheet after a while.",
    " 7. Load a save made before this change: your jump height follows your Jumping skill, not the saved number.",
]
bat = open(os.path.join(play, "play.bat")).read().splitlines()
start = [l for l in bat if l.startswith("start ")][0]
start = start.replace('--mod "%HERE%doomerfall.pk3"', '--mod "%HERE%doomerfall.pk3" --mod "%HERE%jump_demo.pk3"')
body = [l for l in bat if not l.startswith("rem ") and not l.startswith("start ") and l != "@echo off"]
out = ["@echo off"] + ["rem " + n for n in NOTES] + body + [start]
open(os.path.join(play, "play.bat"), "w", newline="\r\n").write("\n".join(out) + "\n")
print("demo ready:", os.path.join(play, "play.bat"))
