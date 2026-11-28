"""List DRLA's Scout (Sharpshooter) pistol damage multipliers: the fast/slow scale the Pistols fire-rate perks use.

DRLA states each gun's Scout multiplier in a comment above its Fire state ("// 8x damage with Scout") and builds it as a
second A_FireBullets, taken with RLSharpshooterPerk, with a fixed damage of that multiple. The Scout's description
(language.classes) says pistols do 8x down to 3x "based on their firerate, faster weapons dealing less".
Usage: python -I tools/pistols/scout_scale.py <DoomRL_Arsenal folder>
"""
import os
import re
import sys

root = sys.argv[1]
mult_re = re.compile(r"//\s*(\d+)x (max )?damage with Scout(.*)", re.I)
actor_re = re.compile(r'^\s*actor\s+"?(\w+)"?', re.I | re.M)

for dirpath, _, files in os.walk(os.path.join(root, "actors", "weapons")):
    for f in sorted(files):
        text = open(os.path.join(dirpath, f), encoding="latin-1").read()
        m = mult_re.search(text)
        if not m:
            continue
        actor = actor_re.search(text)
        name = actor.group(1) if actor else f
        print(f"{name}\t{m.group(1)}x{' max' if m.group(2) else ''}\t{m.group(3).strip(' ,')}")
