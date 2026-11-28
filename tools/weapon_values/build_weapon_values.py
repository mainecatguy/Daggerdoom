"""Build Doomerfall's weapon value and weight file from scan_weapons.py's scan.

Usage: python -I tools/weapon_values/build_weapon_values.py [--table notes.md]

Writes daggerfall-unity-master/Assets/Resources/Doomerfall/WeaponValues.txt (read by DoomerfallWeaponValues.cs) and,
with --table, appends a Markdown table of every weapon's value and weight to the given notes file.

Rules (goal card, owner 2026-11-24 and 2026-11-26):
  value  = the Daggerfall weapon closest in role (its base price) x Daggerfall's material rule x rarity multiplier.
           The material part is applied in game by Daggerfall's own ItemBuilder; this file holds role and tier.
  weight = by what the weapon is (its kind), scaled within the kind by the non-black area of its pickup sprite
           against the kind's median area, clamped to 0.6x..1.6x.
"""
import json
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "daggerfall-unity-master", "Assets", "Resources", "Doomerfall", "WeaponValues.txt")

# Role -> the Daggerfall weapon closest in role (Weapons enum name). Its base price sets the value.
ROLES = {
    "unarmed": "Dagger", "pistol": "Dagger", "melee": "Tanto", "smg": "Shortsword", "shotgun": "Broadsword",
    "rifle": "Longsword", "heavy": "Warhammer", "chainsaw": "Battle_Axe", "energy": "Katana",
    "launcher": "Claymore", "greatsword": "Claymore", "superweapon": "Dai_Katana", "staff": "Staff", "mace": "Mace",
    "axe": "Battle_Axe", "hammer": "Warhammer", "bow": "Short_Bow", "thrown": "Dagger",
}
# Kind -> base weight in kg for a typical one (Daggerfall scale: dagger 0.5, longsword 4.5, claymore 7.5).
KINDS = {
    "fist": 0.5, "knife": 0.5, "gauntlets": 1.5, "wand": 0.5, "pistol": 1.25, "smg": 3.0, "shotgun": 3.5,
    "rifle": 4.5, "heavy": 10.0, "launcher": 8.0, "energy": 5.0, "superweapon": 15.0, "chainsaw": 6.0,
    "sword": 4.5, "greatsword": 7.5, "axe": 6.0, "hammer": 7.0, "mace": 4.5, "staff": 2.0, "crossbow": 3.0,
    "spell": 0.5, "grenade": 1.0, "flamethrower": 9.0,
}
TIERS = {"common": 1, "uncommon": 2, "rare": 3, "veryrare": 6, "legendary": 10}
# Every value x SCALE (owner 2026-11-27, Q&A item 37): a legendary costs 2x its base Daggerfall weapon; proportions stay.
SCALE = 2 / TIERS["legendary"]
# Daggerfall's weapon weight by material (ItemBuilder.weightMultipliersByMaterial, quarters), Iron..Daedric.
WEIGHT_QUARTERS = [4, 5, 4, 4, 3, 4, 4, 2, 4, 5]


def material_weight(kg, material):
    """ItemBuilder.CalculateWeightForMaterial, for the notes table (the game calls Daggerfall's own)."""
    q = int(kg * 4) * WEIGHT_QUARTERS[material] / 4
    return round(q) / 4  # Python and Mathf.Round both round halves to even
DRLA_TIERS = {"standard": "common", "exotic": "uncommon", "superior": "rare", "unique": "veryrare",
              "demonic": "legendary", "legendary": "legendary",
              # Assemblies (made from mod packs, not DRLA rarity tiers): Constrained call, see notes.
              "basic": "uncommon", "advanced": "rare", "master": "veryrare"}

# Stock weapons: class -> (kind, role, tier). Role follows the Doom slot the weapon fills; tier is inferred from
# role and power (owner: "infer a tier from the weapon's role and power").
STOCK = {
    "Fist": ("fist", "unarmed", "common"), "Chainsaw": ("chainsaw", "chainsaw", "common"),
    "Pistol": ("pistol", "pistol", "common"), "Shotgun": ("shotgun", "shotgun", "common"),
    "SuperShotgun": ("shotgun", "shotgun", "uncommon"), "Chaingun": ("heavy", "heavy", "common"),
    "RocketLauncher": ("launcher", "launcher", "uncommon"), "PlasmaRifle": ("energy", "energy", "rare"),
    "BFG9000": ("superweapon", "superweapon", "veryrare"),
    "Staff": ("staff", "staff", "common"), "Gauntlets": ("gauntlets", "melee", "common"),
    "GoldWand": ("wand", "pistol", "common"), "Crossbow": ("crossbow", "shotgun", "common"),
    "Blaster": ("gauntlets", "heavy", "uncommon"), "SkullRod": ("staff", "energy", "uncommon"),
    "PhoenixRod": ("staff", "launcher", "rare"), "Mace": ("mace", "superweapon", "rare"),
    "FWeapFist": ("fist", "unarmed", "common"), "FWeapAxe": ("axe", "shotgun", "uncommon"),
    "FWeapHammer": ("hammer", "launcher", "rare"), "FWeapQuietus": ("greatsword", "superweapon", "veryrare"),
    "CWeapMace": ("mace", "mace", "common"), "CWeapStaff": ("staff", "shotgun", "uncommon"),
    "CWeapFlame": ("staff", "launcher", "rare"), "CWeapWraithverge": ("staff", "superweapon", "veryrare"),
    "MWeapWand": ("wand", "pistol", "common"), "MWeapFrost": ("spell", "shotgun", "uncommon"),
    "MWeapLightning": ("staff", "launcher", "rare"), "MWeapBloodscourge": ("staff", "superweapon", "veryrare"),
}
PIECES = {"FWeaponPiece": "FWeapQuietus", "CWeaponPiece": "CWeapWraithverge", "MWeaponPiece": "MWeapBloodscourge"}

# Schism (DECORATE classes): class -> (kind, role, tier). Base classes, monster shields and the fists are left out
# (SCHISM_SKIP). Tiers follow the Doom weapon each one replaces in Schism's spawners and its power.
SCHISM = {
    "AdvancedMissileLauncher": ("launcher", "launcher", "rare"), "Arrancadora": ("chainsaw", "chainsaw", "uncommon"),
    "BattleAxe": ("axe", "axe", "common"), "BoltRifle": ("rifle", "rifle", "rare"), "BrutalAxe": ("axe", "axe", "common"),
    "BrutalDragonClaw": ("gauntlets", "heavy", "uncommon"), "BrutalFireMace": ("mace", "superweapon", "rare"),
    "BrutalHellStaff": ("staff", "energy", "uncommon"), "BrutalPhoenixRod": ("staff", "launcher", "rare"),
    "Chain_saw": ("chainsaw", "chainsaw", "common"), "DualBattleAxe": ("axe", "axe", "uncommon"),
    "DualMP40": ("smg", "smg", "uncommon"), "DualPistols": ("pistol", "pistol", "uncommon"),
    "DualRifles": ("rifle", "rifle", "rare"), "DV_Crossbow": ("crossbow", "bow", "uncommon"),
    "DV_DangerousCrossbow": ("crossbow", "bow", "rare"), "FlameCannon": ("flamethrower", "heavy", "rare"),
    "Flamethrower2": ("flamethrower", "heavy", "uncommon"), "Freezenades": ("grenade", "thrown", "uncommon"),
    "Frostmancy": ("spell", "heavy", "uncommon"), "GrenadeLauncher": ("launcher", "launcher", "uncommon"),
    "HandFreezebot": ("grenade", "thrown", "rare"), "HandGrenades": ("grenade", "thrown", "common"),
    "HellishMissileLauncher": ("launcher", "launcher", "veryrare"), "HitlersBuzzsaw": ("heavy", "heavy", "veryrare"),
    "Machinegun": ("heavy", "heavy", "uncommon"), "MageDagger": ("knife", "melee", "common"),
    "MageMeleeStaff": ("staff", "staff", "common"), "MiniGun": ("heavy", "heavy", "uncommon"),
    "MP40": ("smg", "smg", "common"), "NukeLauncher": ("launcher", "superweapon", "legendary"),
    "Piromancy": ("spell", "pistol", "common"), "RailGun": ("energy", "energy", "veryrare"),
    "Revolver": ("pistol", "pistol", "common"), "Revolver2": ("pistol", "pistol", "uncommon"),
    "Runecraft": ("spell", "launcher", "rare"), "Schism_AssaultShotgun": ("shotgun", "shotgun", "rare"),
    "Schism_BFG10k": ("superweapon", "superweapon", "legendary"), "Schism_BFG9k": ("superweapon", "superweapon", "veryrare"),
    "Schism_Crossbow": ("crossbow", "shotgun", "common"), "Schism_CryoShotgun": ("shotgun", "shotgun", "uncommon"),
    "Schism_Deagle": ("pistol", "pistol", "uncommon"), "Schism_DualPlasmaRifles": ("energy", "energy", "veryrare"),
    "Schism_DualSMG": ("smg", "smg", "uncommon"), "Schism_ElectroRifle": ("energy", "energy", "uncommon"),
    "Schism_Freezethrower": ("flamethrower", "energy", "rare"), "Schism_GoldenWand": ("wand", "pistol", "common"),
    "Schism_HeavyRifle": ("rifle", "rifle", "uncommon"), "Schism_NecroGauntlets": ("gauntlets", "melee", "common"),
    "Schism_Pistol": ("pistol", "pistol", "common"), "Schism_PlasmaRifle": ("energy", "energy", "rare"),
    "Schism_PoweredCrossbow": ("crossbow", "shotgun", "uncommon"), "Schism_QuadShotgun": ("shotgun", "shotgun", "rare"),
    "Schism_Rifle": ("rifle", "rifle", "common"), "Schism_RocketLauncher": ("launcher", "launcher", "uncommon"),
    "Schism_Shotgun": ("shotgun", "shotgun", "common"), "Schism_Sickle": ("knife", "melee", "uncommon"),
    "Schism_SMG": ("smg", "smg", "common"), "Schism_SniperRifle": ("rifle", "rifle", "rare"),
    "Schism_SSG": ("shotgun", "shotgun", "uncommon"), "Schism_Tesla": ("energy", "energy", "rare"),
    "Shield_SMG": ("smg", "smg", "uncommon"), "ShieldRifle": ("rifle", "rifle", "uncommon"),
    "Stormcast": ("spell", "shotgun", "uncommon"), "TheQuietus": ("greatsword", "superweapon", "veryrare"),
    "Unmaker": ("energy", "superweapon", "legendary"), "VorpalBlade": ("sword", "greatsword", "veryrare"),
}
SCHISM_SKIP = {"AmmoDroper", "Berserker_Melee_Attacks", "BrutalWeapon", "Melee_Attacks", "Schism_BaseWeapon",
               "Schism_Weapon", "Schism_WS1S", "ShieldPlus", "CguyShield", "EvilMarineShield", "ImpShield",
               "NaziShield", "SguyShield", "ZMANShield", "ZombieCivilianShield"}

HEAVY = re.compile(r"(?i)minigun|chaingun|onslaught|autocannon|machinegun|armamentgenerator|gatling|sussgun")
SMG = re.compile(r"(?i)smg|uzi|thompson|rcp90|stealth")


def drla_kind(r):
    name, tokens, slot, ammo = r["class"], r["tokens"], r["slot"], (r["ammo"] + " " + r["ammo1"]).lower()
    t = lambda s: ("RL" + s + "TypeWeapon") in tokens
    if "fist" in name.lower():
        return "fist", "unarmed"
    if t("Melee") or slot == "1":
        return ("greatsword", "greatsword") if "dragonslayer" in name.lower() else ("chainsaw", "chainsaw")
    if "dragonslayer" in name.lower():
        return "greatsword", "greatsword"
    if (t("Pistol") and t("Rapidfire")) or "uzi" in name.lower():
        return "smg", "smg"  # the Uzis (owner, 2026-11-27: Automatics)
    if t("Pistol"):
        return "pistol", "pistol"
    if slot == "7":
        return "superweapon", "superweapon"
    if t("Shotgun"):
        return "shotgun", "shotgun"
    if HEAVY.search(name):
        return "heavy", "heavy"
    if slot == "5" or "rocket" in ammo:
        return "launcher", "launcher"
    if slot == "6" or "cell" in ammo:
        return "energy", "energy"
    if SMG.search(name):
        return "smg", "smg"
    if slot == "3":
        return "shotgun", "shotgun"
    if slot == "2":
        return "pistol", "pistol"
    return "rifle", "rifle"


def usable_area(r):
    # A "pickup" sprite as big as the screen (Schism's Deagle and Stormcast reuse a HUD frame) says nothing about size.
    return r["area"] if r["area"] > 0 and r["w"] <= 128 else 0


def main():
    scan_path = os.path.join(os.environ.get("TEMP", "."), "doomerfall_weapon_scan.json")
    subprocess.check_call([sys.executable, "-I", os.path.join(HERE, "scan_weapons.py"), "--json", scan_path],
                          stdout=subprocess.DEVNULL)
    rows = json.load(open(scan_path))
    out = []
    for r in rows:
        cls = r["class"]
        if r["set"] in ("DRLA", "DRLAX"):
            kind, role = drla_kind(r)
            tier = DRLA_TIERS[r["tier"]] if r["set"] == "DRLA" else "common"
            pickups = [r["pickup"], r["pickup"] + "Modded"]
        elif r["set"] == "Schism":
            if cls in SCHISM_SKIP:
                continue
            kind, role, tier = SCHISM[cls]
            pickups = r.get("pickups") or [cls]
        else:
            base = next((w for p, w in PIECES.items() if cls.startswith(p)), None)
            kind, role, tier = STOCK[base or cls]
            pickups = [cls]
        out.append(dict(r, kind=kind, role=role, tierName=tier, pickups=pickups, piece=bool(r["set"] == "Hexen" and "Piece" in cls)))

    medians = {}
    for k in KINDS:
        areas = [usable_area(e) for e in out if e["kind"] == k and usable_area(e) > 0 and not e["piece"]]
        medians[k] = statistics.median(areas) if areas else 0
    for e in out:
        a, m = usable_area(e), medians[e["kind"]]
        factor = min(1.6, max(0.6, a / m)) if a and m else 1.0
        e["factor"] = factor
        e["weight"] = max(0.25, round(KINDS[e["kind"]] * factor * 4) / 4)
        e["share"] = 1.0
    # Hexen's fourth weapons come in three pieces: each piece carries its share of the weapon's weight (by sprite
    # area) and a third of its value; the assembled weapon keeps the full numbers.
    for p, whole in PIECES.items():
        parts = [e for e in out if e["class"].startswith(p)]
        total = sum(usable_area(e) for e in parts) or len(parts)
        wweight = next(e["weight"] for e in out if e["class"] == whole)
        for e in parts:
            e["weight"] = max(0.25, round(wweight * (usable_area(e) or 1) / total * 4) / 4)
            e["share"] = round(1.0 / len(parts), 4)
            e["factor"] = 0

    lines = [
        "# Doomerfall weapon values and weights. Generated by tools/weapon_values/build_weapon_values.py; edit that",
        "# script's tables (or this file by hand) and rebuild Daggerfall Unity. Read by DoomerfallWeaponValues.cs.",
        "#",
        "# value = base price of the role's Daggerfall weapon x Daggerfall's material rule (x3 x 1..512, Iron..Daedric)",
        "#         x the tier multiplier x share x scale, at least 1. A Doom item without a material (not a gun) counts as Iron.",
        "# weight is the Iron weight in kilograms. A gun of another material changes it by Daggerfall's weapon material rule.",
        "#",
        "# scale <factor>: every value x this. Owner (2026-11-27): a legendary (x10) costs 2x its base Daggerfall weapon of the",
        "# same material, so 2 / 10 = 0.2; the tiers keep their proportions.",
        "scale {:g}".format(SCALE),
        "#",
        "# cap <gold>: largest value any Doom weapon may have before shop pricing (0 = no cap). Daggerfall shops pay",
        "# with letters of credit and have no gold limit, so no cap is set.",
        "cap 0",
        "#",
        "# role <name> <Daggerfall Weapons enum name>",
    ]
    lines += ["role {} {}".format(k, v) for k, v in ROLES.items()]
    lines += ["#", "# tier <name> <multiplier> (owner: common x1, uncommon x2, rare x3, very rare x6, legendary x10)"]
    lines += ["tier {} {}".format(k, v) for k, v in TIERS.items()]
    lines += ["#", "# weapon <class> <set> <kind> <role> <tier> <weightKg> <share> <pickup classes, comma separated>",
              "# The game finds a Doom item by any of its pickup classes or by the weapon class."]
    for e in out:
        lines.append("weapon {} {} {} {} {} {:g} {:g} {}".format(e["class"], e["set"], e["kind"], e["role"], e["tierName"],
                                                             e["weight"], e["share"], ",".join(e["pickups"])))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", OUT, len(out), "weapons")

    if "--table" in sys.argv:
        prices = json.load(open(os.path.join(HERE, "df_weapon_prices.json")))
        mats = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
        t = ["", "| Set | Weapon | Kind | Role (Daggerfall base) | Tier | Weight kg | Sprite px x scale | Iron | Steel | Ebony | Daedric |",
             "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
        for e in out:
            base = prices[ROLES[e["role"]]] * TIERS[e["tierName"]] * e["share"] * SCALE
            v = lambda m: "{:,}".format(max(1, int(round(base * 3 * m))))
            t.append("| {} | {} | {} | {} ({}) | {} | {:g} | {} | {} | {} | {} | {} |".format(
                e["set"], e["class"], e["kind"], e["role"], ROLES[e["role"]].replace("_", " "), e["tierName"], e["weight"],
                int(usable_area(e)) or "-", v(mats[0]), v(mats[1]), v(mats[7]), v(mats[9])))
        with open(sys.argv[sys.argv.index("--table") + 1], "a", encoding="utf-8") as f:
            f.write("\n".join(t) + "\n")
        print("table appended")
    for k in KINDS:
        print("kind {:12} base {:5} kg median area {}".format(k, KINDS[k], medians[k]))


if __name__ == "__main__":
    main()
