"""Runs both real games with the class card test and checks the class lists, levels and gun skills.

usage: class_card_test.py [demo folder]   (default D:\\dev\\DoomDaggerfall-loop\\review\\classcards)
Daggerfall uses the demo's portable, registry-isolated copy. One launch, minimized.

Expected cards are rebuilt here, independently of the game's C# tables: the classic lists from CLASS00-17.CFG
(skill bytes 16-27), then the replacements written in work/notes/20261126-class-skill-remap-proposal.md
(no-guns table, then the guns-mode table's "Daggerfall skill > Doom skill" cells).
"""
import json, re, subprocess, sys
from pathlib import Path

DEMO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\dev\DoomDaggerfall-loop\review\classcards")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
SECONDS = 120

NAMES = ("Medical Etiquette Streetwise Jumping Orcish Harpy Giantish Dragonish Nymph Daedric Spriggan Centaurian Impish "
         "Lockpicking Mercantile Pickpocket Stealth Swimming Climbing Backstabbing Dodging Running Destruction Restoration "
         "Illusion Alteration Thaumaturgy Mysticism ShortBlade LongBlade HandToHand Axe BluntWeapon Archery CriticalStrike").split()
CLASSES = "Mage Spellsword Battlemage Sorcerer Healer Nightblade Bard Burglar Rogue Acrobat Thief Assassin Monk Archer Ranger Barbarian Warrior Knight".split()
GUNS = ["shotguns", "automatics", "explosives", "pistols", "rifles", "energyweapons", "melee"]
DF_WEAPONS = ["shortblade", "longblade", "axe", "bluntweapon", "archery"]

# Proposal, no-guns table (class: old > new).
NO_GUNS = {
    "Mage": {"Dragonish": "Etiquette", "Daedric": "Mercantile"}, "Sorcerer": {"Dragonish": "Etiquette", "Daedric": "Mercantile"},
    "Nightblade": {"Critical Strike": "Archery"}, "Burglar": {"Critical Strike": "Hand-to-Hand"},
    "Rogue": {"Critical Strike": "Short Blade"}, "Acrobat": {"Critical Strike": "Long Blade"}, "Thief": {"Critical Strike": "Blunt Weapon"},
    "Assassin": {"Critical Strike": "Running"}, "Monk": {"Critical Strike": "Running"}, "Archer": {"Critical Strike": "Backstabbing"},
    "Ranger": {"Critical Strike": "Stealth", "Spriggan": "Medical"},
    "Barbarian": {"Critical Strike": "Hand-to-Hand", "Giantish": "Streetwise"},
}
# Proposal, guns-mode table cells per class (all tiers together).
GUNS_CARDS = {
    "Mage": "Short Blade > Pistols, Blunt Weapon > Energy Weapons",
    "Spellsword": "Axe > Shotguns, Long Blade > Melee, Blunt Weapon > Automatics, Short Blade > Energy Weapons, Archery > Rifles",
    "Battlemage": "Long Blade > Explosives, Axe > Energy Weapons, Archery > Rifles, Short Blade > Melee, Blunt Weapon > Shotguns",
    "Sorcerer": "Short Blade > Explosives, Blunt Weapon > Energy Weapons",
    "Healer": "Short Blade > Pistols, Blunt Weapon > Energy Weapons",
    "Nightblade": "Short Blade > Pistols, Archery > Rifles",
    "Bard": "Short Blade > Pistols, Archery > Automatics",
    "Burglar": "Short Blade > Pistols",
    "Rogue": "Long Blade > Shotguns, Short Blade > Pistols, Blunt Weapon > Energy Weapons",
    "Acrobat": "Long Blade > Automatics, Short Blade > Pistols, Archery > Melee",
    "Thief": "Short Blade > Pistols, Blunt Weapon > Explosives",
    "Assassin": "Short Blade > Pistols, Long Blade > Rifles, Blunt Weapon > Melee, Axe > Explosives, Archery > Energy Weapons",
    "Monk": "Blunt Weapon > Melee, Axe > Shotguns, Long Blade > Energy Weapons, Archery > Rifles, Short Blade > Pistols",
    "Archer": "Archery > Rifles, Axe > Explosives, Blunt Weapon > Melee, Long Blade > Automatics, Short Blade > Energy Weapons",
    "Ranger": "Long Blade > Rifles, Axe > Shotguns, Archery > Melee, Blunt Weapon > Explosives, Short Blade > Automatics",
    "Barbarian": "Blunt Weapon > Melee, Long Blade > Automatics, Axe > Shotguns, Archery > Explosives",
    "Warrior": "Axe > Shotguns, Long Blade > Automatics, Blunt Weapon > Melee, Archery > Rifles, Short Blade > Explosives",
    "Knight": "Long Blade > Melee, Blunt Weapon > Energy Weapons, Axe > Shotguns, Archery > Rifles, Short Blade > Automatics",
}


def norm(name):
    n = re.sub(r"[^a-z]", "", name.lower())
    return "pickpocket" if n == "pickpocketing" else n  # the sheet's name for the Pickpocket skill


def expected_cards():
    cards = []
    for i, cls in enumerate(CLASSES):
        data = (Path(DAGGER) / "ARENA2" / f"CLASS{i:02d}.CFG").read_bytes()
        card = [norm(NAMES[b]) for b in data[16:28]]
        for old, new in NO_GUNS.get(cls, {}).items():
            card[card.index(norm(old))] = norm(new)
        for cell in GUNS_CARDS[cls].split(","):
            old, new = (norm(x) for x in cell.split(">"))
            card[card.index(old)] = new
        cards.append(card)
    return cards


def custom_rule(lists, first_language=11):
    """The proposal's custom-class rule, written separately from the C#."""
    out = list(lists)
    # monster-language numbers still read as languages; the sheet shows unused slots 11-12 with no name
    removed = {norm(NAMES[i]) for i in range(first_language, 13)} | {""}
    usable = [norm(n) for n in NAMES if norm(n) not in ("criticalstrike", "centaurian", "impish") and norm(n) not in DF_WEAPONS]
    usable = [n if n not in ("orcish", "harpy", "giantish", "dragonish", "nymph", "daedric", "spriggan") else
              GUNS[["orcish", "harpy", "giantish", "dragonish", "nymph", "daedric", "spriggan"].index(n)] for n in usable]

    def free(cands):
        for c in cands + usable:
            if c not in out:
                return c
    for p, s in enumerate(out):
        if s in removed:
            out[p] = free(["etiquette", "streetwise", "mercantile", "medical"])
        elif s == "criticalstrike":
            out[p] = free(["shortblade", "longblade", "axe", "bluntweapon", "archery", "running"])
    default = dict(zip(DF_WEAPONS, ["pistols", "automatics", "shotguns", "melee", "rifles"]))
    for p, s in enumerate(out):
        if s in default:
            out[p] = default[s] if default[s] not in out else free(["pistols", "shotguns", "automatics", "rifles", "explosives", "energyweapons", "melee"])
    return out


CARD_LINE = re.compile(r"class card test: (.+?) \| class (.*?) \| primary \[(.*?)\] major \[(.*?)\] minor \[(.*?)\] \| level (-?\d+) start (-?\d+) "
                       r"current (-?\d+) calculated (-?\d+) \| guns (.*)")
SHEET = re.compile(r"sheet: (published|read) v(\d+) .*? sum ([0-9a-f]{8}) shotguns (-?\d+)/-?\d+ automatics (-?\d+)/-?\d+ explosives (-?\d+)/-?\d+ "
                   r"pistols (-?\d+)/-?\d+ rifles (-?\d+)/-?\d+ energy (-?\d+)/-?\d+ melee (-?\d+)/-?\d+")


def main():
    run = DEMO / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log = run / "classcard-uz.log", run / "classcard-df.log"
    uz =["-noactivate", "-config", str(run / "classcard.ini"), "-dfbridgelog", str(uz_log), "-nosound", "-skill", "3", "+map", "E1M1",
          "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfclasscardtest", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(SECONDS), "--", str(DEMO / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(DEMO / "uzdoom" / "uzdoom.exe"), "--dfu", str(DEMO / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(run / "classcard-launcher.log")]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    if "--check-only" not in sys.argv:
        for path in (uz_log, df_log):
            path.unlink(missing_ok=True)
        print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)

    df_lines = df_log.read_text(encoding="utf-8", errors="replace").splitlines() if df_log.exists() else []
    uz_lines = uz_log.read_text(encoding="utf-8", errors="replace").splitlines() if uz_log.exists() else []
    read = {}
    for l in uz_lines:
        m = SHEET.search(l)
        if m and m.group(1) == "read":
            read[int(m.group(2))] = (m.group(3), [int(x) for x in m.groups()[3:]])
    failures = []

    def check(ok, what):
        print(("ok    " if ok else "FAIL  ") + what)
        if not ok:
            failures.append(what)

    cards = expected_cards()
    entries = {}
    published_before = {}
    pending = []
    for l in df_lines:
        if "error" in l.lower():
            print(l[:220])
        m = SHEET.search(l)
        if m and m.group(1) == "published":
            pending.append((int(m.group(2)), m.group(3), [int(x) for x in m.groups()[3:]]))
        if "class maker offers" in l:
            entries["maker"] = l.split("[", 1)[1].rstrip("]")
        m = CARD_LINE.search(l)
        if m:
            label = m.group(1)
            lists = [norm(x) for g in (3, 4, 5) for x in m.group(g).split(",")]
            guns = {norm(kv.split("=")[0]): int(kv.split("=")[1]) for kv in m.group(10).split(",")}
            entries[label] = dict(cls=m.group(2), lists=lists, level=int(m.group(6)), calc=int(m.group(9)), guns=guns,
                                  start=int(m.group(7)), current=int(m.group(8)))
            published_before[label] = pending
            pending = []
            print(l.split("class card test: ", 1)[1][:240])

    offered = [norm(x) for x in entries.get("maker", "").split(",")]
    check(bool(offered) and all(g in offered for g in GUNS), "class maker offers all seven Doom skills")
    check(bool(offered) and not any(w in offered for w in DF_WEAPONS + ["criticalstrike"]),
          "class maker offers no Daggerfall weapon skill and no Critical Strike")

    def reached_doom(label):
        """The gun values logged for this step were published and Doom read that version with the same values."""
        e = entries[label]
        want = [e["guns"][g] for g in GUNS]
        for version, summ, vals in reversed(published_before[label]):
            if vals == want:
                return version in read and read[version] == (summ, vals)
        return False

    for i, cls in enumerate(CLASSES):
        label = f"preset {i}"
        e = entries.get(label)
        check(e is not None and e["lists"] == cards[i], f"{cls}: new character's sheet lists its guns card")
        if e:
            if e["lists"] != cards[i]:
                print("      got     ", e["lists"], "\n      expected", cards[i])
            on_card = [g for g in GUNS if g in cards[i]]
            check(all(e["guns"][g] >= 10 for g in on_card), f"{cls}: card gun skills rolled as class skills {[(g, e['guns'][g]) for g in on_card]}")
            check(reached_doom(label), f"{cls}: gun skills reached Doom")

    # Old saves: the level and the progress through it (current - starting level-up sum) must be what the save stored.
    # (The sheet test that made them raised the level by hand, so their calculated level can be below their level.)
    stored = {}
    for info in (DEMO / "dfu" / "PortableAppdata" / "Saves").glob("SAVE*/SaveInfo.txt"):
        name = json.loads(info.read_text(encoding="utf-8-sig")).get("saveName")
        pe = json.loads((info.parent / "SaveData.txt").read_text(encoding="utf-8-sig"))["playerData"]["playerEntity"]
        stored[name] = (pe["level"], pe["currentLevelUpSkillSum"] - pe["startingLevelUpSkillSum"], pe["currentLevelUpSkillSum"])
    for label, e in entries.items():
        if label.startswith("old save"):
            level, progress, current = stored.get(label.split()[2], (None, None, None))
            same = e["level"] == level and (current == 0 or e["current"] - e["start"] == progress)
            check(same and e["cls"] in CLASSES and e["lists"] == cards[CLASSES.index(e["cls"])],
                  f"{label}: level {e['level']} and progress {e['current'] - e['start']} as saved ({level}, {progress}); class card {e['cls']}")

    b, a = entries.get("pre-card warrior before save"), entries.get("pre-card warrior loaded")
    check(b is not None and b["level"] == 5 and b["calc"] == 5, "pre-card warrior: level 5 before save")
    check(a is not None and a["level"] == 5 and a["calc"] == 5 and a["current"] - a["start"] == b["current"] - b["start"],
          "pre-card warrior: loads at level 5, same progress through the level")
    check(a is not None and a["lists"] == cards[16], "pre-card warrior: loads with the Warrior guns card")

    b, a = entries.get("old custom before save"), entries.get("old custom loaded")
    want = custom_rule(b["lists"]) if b else None
    check(a is not None and a["lists"] == want, f"old custom class converts by the default map: {want}")
    check(a is not None and a["calc"] == a["level"], "old custom class keeps its level")
    if a:
        check(reached_doom("old custom loaded"), "old custom class: gun skills reached Doom")
    b, a = entries.get("guns custom before save"), entries.get("guns custom loaded")
    check(a is not None and b is not None and a["lists"] == b["lists"], "guns-mode custom class keeps its own picks")
    b, a = entries.get("lookalike custom before save"), entries.get("lookalike custom loaded")
    check(a is not None and b is not None and a["lists"] == b["lists"],
          "custom class with Mage's other skills but its own gun picks keeps them (not the Mage card)")
    for name, preset in (("language lookalike custom", 0), ("barbarian lookalike custom", 15)):
        b, a = entries.get(name + " before save"), entries.get(name + " loaded")
        check(a is not None and b is not None and a["lists"] == b["lists"] and a["lists"] != cards[preset],
              f"{name}: Doom skills in {CLASSES[preset]}'s former language slots are kept (not the {CLASSES[preset]} card)")
    b, a = entries.get("old lookalike custom before save"), entries.get("old lookalike custom loaded")
    want = custom_rule(b["lists"]) if b else None
    check(a is not None and a["lists"] == want and a["lists"] != cards[0],
          f"older custom class with Mage's other skills converts by the default map: {want}")
    m = next((re.search(r"start (-?\d+) current (-?\d+)", l) for l in df_lines if "classic import warrior before" in l), None)
    e = entries.get("classic import warrior")
    check(m is not None and e is not None and e["level"] == 5 and e["calc"] == 5
          and e["current"] - e["start"] == int(m.group(2)) - int(m.group(1)) and e["lists"] == cards[16],
          "classic import (Warrior, level 5, trained weapons): Warrior card, level 5, same progress through the level")
    e = entries.get("new game knight")
    check(e is not None and e["lists"] == cards[17], "full new game (Knight): guns card on the sheet")
    if e:
        check(reached_doom("new game knight"), "full new game (Knight): gun skills reached Doom")
    check(any("class card test: done" in l for l in df_lines), "test ran to the end")
    print("RESULT", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
