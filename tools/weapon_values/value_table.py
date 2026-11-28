"""Print a Markdown table of Doom gun values (before and after the file's scale) and weights by material.

usage: python -I tools/weapon_values/value_table.py [--set DRLA] [--all]

Reads Resources/Doomerfall/WeaponValues.txt and df_weapon_prices.json and repeats the game's rules
(DoomerfallWeaponValues.cs): value = role's Daggerfall base price x 3 x material multiplier x tier x share x scale (at
least 1); weight = the file's Iron weight through Daggerfall's weapon material rule. Without --all it lists one weapon
per (role, tier) pair of the set, plus a summary of the largest values.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE.parents[1] / "daggerfall-unity-master" / "Assets" / "Resources" / "Doomerfall" / "WeaponValues.txt"
MATS = ["Iron", "Steel", "Silver", "Elven", "Dwarven", "Mithril", "Adamantium", "Ebony", "Orcish", "Daedric"]
VALUE_X = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]  # ItemBuilder.valueMultipliersByMaterial
WEIGHT_Q = [4, 5, 4, 4, 3, 4, 4, 2, 4, 5]  # ItemBuilder.weightMultipliersByMaterial


def weight(kg, m):
    return round(int(kg * 4) * WEIGHT_Q[m] / 4) / 4  # CalculateWeightForMaterial; halves to even like Mathf.Round


def main():
    prices = json.loads((HERE / "df_weapon_prices.json").read_text())
    roles, tiers, weapons, scale = {}, {}, [], 1.0
    for line in FILE.read_text().splitlines():
        f = line.split()
        if not f or f[0].startswith("#"):
            continue
        if f[0] == "scale":
            scale = float(f[1])
        elif f[0] == "role":
            roles[f[1]] = f[2]
        elif f[0] == "tier":
            tiers[f[1]] = int(f[2])
        elif f[0] == "weapon":
            weapons.append(dict(cls=f[1], set=f[2], role=f[4], tier=f[5], kg=float(f[6]), share=float(f[7])))
    only = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "DRLA"
    rows = [w for w in weapons if w["set"] == only and w["role"] != "unarmed"]
    if "--all" not in sys.argv:
        seen, picked = set(), []
        for w in rows:
            if (w["role"], w["tier"]) not in seen:
                seen.add((w["role"], w["tier"]))
                picked.append(w)
        rows = sorted(picked, key=lambda w: (w["role"], tiers[w["tier"]]))

    def value(w, m, s):
        return max(1, round(prices[roles[w["role"]]] * 3 * VALUE_X[m] * tiers[w["tier"]] * w["share"] * s))

    print(f"scale {scale:g}; tiers {tiers}\n")
    print("| Weapon | Role (base) | Tier | Old Iron | New Iron | Old Daedric | New Daedric | Base weapon Daedric | kg Iron | Steel | Dwarven | Ebony | Daedric |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for w in rows:
        base_d = prices[roles[w["role"]]] * 3 * 512
        print("| {} | {} ({}) | {} | {:,} | {:,} | {:,} | {:,} | {:,} | {:g} | {:g} | {:g} | {:g} | {:g} |".format(
            w["cls"], w["role"], roles[w["role"]].replace("_", " "), w["tier"], value(w, 0, 1), value(w, 0, scale),
            value(w, 9, 1), value(w, 9, scale), base_d, w["kg"], weight(w["kg"], 1), weight(w["kg"], 4), weight(w["kg"], 7), weight(w["kg"], 9)))
    allw = [w for w in weapons if w["role"] != "unarmed"]
    top = max(allw, key=lambda w: value(w, 9, 1))
    print("\nLargest value, all sets: {} Daedric, old {:,}, new {:,} (its base weapon {} Daedric: {:,}).".format(
        top["cls"], value(top, 9, 1), value(top, 9, scale), roles[top["role"]], prices[roles[top["role"]]] * 3 * 512))
    ratios = {w["tier"]: value(w, 9, scale) / (prices[roles[w["role"]]] * 3 * 512) for w in allw if w["share"] == 1}
    print("New Daedric value / base Daggerfall weapon's Daedric value, by tier:", {k: round(v, 3) for k, v in ratios.items()})


main()
