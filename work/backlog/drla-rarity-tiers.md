# DRLA rarity tiers for Doom weapon loot

**Waiting on:** owner approval of the tier mapping and odds below. Needed by *Doom items replace most weapon loot*.

Owner direction (2026-11-24): DRLA weapons get at least five rarity tiers, each progressively rarer, independent of
area level for now. Starting numbers: common 70%, uncommon (+1 / upgraded) 15%, rare 8%, very rare 4.5%, legendary the
rest (2.5%). This is DRLA only. Other mods and stock Doom use default rates unless specified, but can reuse the system.

## DRLA's own tiers (counted from `GameMods/ExtractedData/DoomRL_Arsenal_1.1.5/actors/weapons`)

| DRLA tier | Weapons (fist excluded) |
|---|---:|
| Standard | 12 |
| Exotic | 18 |
| Superior | 7 |
| Unique | 31 |
| Demonic | 4 |
| Legendary | 9 |

DRLAX adds no weapon tiers in its extracted files (only a fist).

## Pool size matters

The chance of one particular weapon is the tier's share divided by the number of weapons in it. With the starting
numbers and the mapping common = Standard, uncommon = Exotic, rare = Superior, very rare = Unique, legendary = Demonic
plus Legendary:

| Tier | Share | Weapons | Each weapon |
|---|---:|---:|---:|
| Common | 70% | 12 | 5.8% |
| Uncommon | 15% | 18 | 0.83% |
| Rare | 8% | 7 | **1.14%** |
| Very rare | 4.5% | 31 | 0.15% |
| Legendary | 2.5% | 13 | **0.19%** |

Two inversions: a particular rare weapon is more common than a particular uncommon one, and a particular legendary is
more common than a particular very rare one.

## Proposal (needs the owner's yes)

Keep the tier shares close to the owner's, adjusted so each weapon in a rarer tier is always rarer than each weapon in
the tier below:

| Tier | Share | Each weapon |
|---|---:|---:|
| Common (Standard) | 70% | 5.8% |
| Uncommon (Exotic) | 19% | 1.06% |
| Rare (Superior) | 5.5% | 0.79% |
| Very rare (Unique) | 4% | 0.13% |
| Legendary (Demonic, Legendary) | 1.5% | 0.115% |

These shares apply to the 74% of weapon rolls that become a Doom weapon. A per-weapon weight table is simpler to keep
correct if pools change: give each weapon a weight by tier, and recompute shares from the loaded pool.

The owner's "+1 upgraded" could instead mean a common weapon that drops with one mod already applied. That would be a
separate roll on any weapon, not a tier. Confirm which is meant.
