The basic design goal of this project is simple: "daggerfall, but oops we replaced all the monsters with slaughter map sized packs from doom, and that ebony mace that dropped got converted to an energy machinegun from the doom roguelike arsenal extended mod, and when NPCs get angry at you they behave like Doom NPCs."


Short-Term Game Design Goals

## Vertical Slice Target
Play through one Daggerfall dungeon (e.g., Privateer's Hold) and one town, fast-traveling between them: fight Doom slaughter-map packs, loot and fire a converted DRLX weapon, talk to and provoke an NPC, complete one Daggerfall kill quest, save and reload mid-fight, and leave/re-enter the dungeon with dead enemies and dropped gear intact.



## Long-term Game Deisgn Goals

| Domain | Prevailing System | Game Design Rule |
|---|---|---|
| **World, Time & Weather** | **Daggerfall** | The calendar, seasons, regions, day/night cycle, weather, and fast travel govern the world. |
| **Aesthetics & Tone** | **Daggerfall (world) + Doom (combat)** | Environments, architecture, skies, and props look like Daggerfall; weapons, monsters, gore, and combat effects look like Doom/DRLX. |
| **World Persistence** | **Strict Full Persistence** | Every killed monster, corpse, dropped item, unlocked door, and world change stays permanent across revisits (except permitting vanilla Daggerfall's dungeon resets). |
| **Combat & Weapons** | **Doom / DRLX** | Pure real-time FPS gunplay, projectiles, hitscans, ammo economy, and Doom Roguelike Extended Arsenal weapon modding. No Daggerfall dice-roll-to-hit combat. |
| **Monsters & Encounters** | **Doom / DRLX** | All monsters are replaced by slaughter-map-sized Doom/DRLX packs that spill through available space and infight, scaled by Daggerfall's location difficulty and encounter tables. |
| **NPCs, Dialogue & Quests** | **Daggerfall (peaceful) + Doom (hostile)** | Townsfolk, guilds, dialogue, and quests follow Daggerfall's rules. Once attacked or flagged hostile, NPCs fight as aggressive Doom bots, usually with powerful non-hitscan weapons. |
| **Crime, Bounties & Guards** | **Daggerfall (rules) + Doom (enforcement)** | Daggerfall governs reputation, bounties, surrender, and court/jail; hostile guards pursue and fight like Doom bots. |
| **Player Vitals & Death** | **Daggerfall** | Daggerfall's HP, attributes, armor, resistances, fatigue, magicka, and death rules govern survival. DRLX passes base damage and damage type entities want to deal to daggerfall, and daggerfall applies its damage rules and is the final arbitrator of how much damage was dealt to an entity. All DRLX weapons have damage types. |
| **Status Effects & Transformations** | **Daggerfall** | Poison, disease, paralysis, buffs, vampirism, and lycanthropy follow Daggerfall's rules and directly alter movement, vision, and survivability in Doom combat. |
| **Movement & Traversal** | **Doom (feel) + Daggerfall (abilities)** | Doom's fast, responsive FPS movement is the baseline, modified by Daggerfall's encumbrance, swimming, climbing, levitation, and horses. |
| **Magic & Spellcasting** | **Daggerfall (rules) + Doom (execution)** | Daggerfall's spellbooks, spellmaker, and magicka costs prevail, for spells that hit Daggerfall can spawn a projectile and specify a radius which it will ask  Doom to spawn, Doom will then report what the projectile hit. |
| **Loot & Economy** | **Daggerfall (economy) + DRLX (gear)** | Daggerfall rolls loot tiers and runs the gold economy, shops, banks, wagons, and houses; combat drops translate into DRLX weapons, ammo, armor, and mod packs. |
| **Interactive World & Locks** | **Daggerfall** | Lock ratings, lockpicking, door bashing, traps, and secret triggers follow Daggerfall's RPG checks. |
| **Stealth & Detection** | **Doom (spatial) + Daggerfall (stats)** | Real line-of-sight, lighting, and gunfire noise alert monsters; Daggerfall's stealth skill adjusts detection thresholds and backstab damage. |
| **Resting & Loitering** | **Daggerfall** | Resting advances time and restores vitals, blocked when Doom monsters are nearby and interrupted by Doom ambush packs. |
| **Progression & Skill XP** | **Daggerfall** | Combat, spellcasting, and traversal drive Daggerfall's use-based skill leveling; DRLX progression remains gear-centric. |
| **Audio & Music** | **Daggerfall (music/UI/NPCs) + Doom (combat)** | Daggerfall supplies music, UI sounds, and NPC barks; Doom supplies combat SFX. |

## The world does not scale to the player (design principle)

Unlike Daggerfall, the world never changes around the player to accommodate them. Doomerfall is totally indifferent to player level for scaling purposes and only cares about area level. Never use level scaling or any other artificial scaling of the game world that breaks the illusion that facts about the world are independent of facts about the player. This is a major feature of the mod and a major change from original Daggerfall.

## Material tiers (design principles)

- Every category gets monotonically better with area level: the chance of getting a given tier or better never falls.
- Lower tier items are always more common. At best, a lower tier can be only slightly less common than the tier above it.
- Daedric is the best tier, and its own check is the only way to get it. It reaches 1 in 40 at area level 20 and 1 in 20 at area level 30.
- Ammo uses the same tiers, with Tin added below Iron.

The approved odds are in `work/notes/20261123-material-tier-proposal.md`.

Handling multiple enemies:
Enemy placements in Daggerfall are now encounters.
Encounters produce multiple doom enemies, which we will call "mooks" because they don't receive the same attention as normal daggerfall entities by daggerfall engine in some ways.
Mooks are generated from deterministic seeds so we always get the same set of mooks from the same entity data whenever we reconstruct it. Use perhaps the static part of their definitions as a fixed seed. 
Then, we only need to track which mooks are dead for save/load in daggerfall (this is an expansion) and then tell doom on load "these are dead bodies".
Doom then for all mooks places Doom enemies using a point buy system the user will define. Points are allocated based on encounter difficulty calculations.
Death events for an NPC trigger when most of the mooks are dead. For consistency's sake, if the user kills all but 1-2 entities, we may have to flag the NPC is dead and allow that to not make those stragglers respawn.

Mook HP and resistances: Daggerfall does not understand Doom monster tables and must not be made to. It never sets a mook's HP or resistances directly. Doom's WAD and mod definitions decide them, and Daggerfall can at most apply a multiplier. Daggerfall can set HP for its own non-Doom entities, such as NPCs.

Damage and resistances for the initial release (not final, to be revisited after release):
DRLA keeps its resistance system, and Daggerfall's rules are applied on top of it as much as is reasonable.
Daggerfall controls damage, so Daggerfall armor is the armor that matters.

## Ammunition (design pillar)

Ammunition will eventually be an inventory object.

- Ammunition has different qualities.
- A system will let the player change the type of ammo loaded in a gun.
- Daggerfall can tell Doom that the player has more than Doom's max ammo, and Doom accepts it.
- There may be limits on how much ammo the player can carry. That is a future system.

Other todos:
DFU loot should persist no matter where it is dropped if possible.
DFU area respawns should be delayed or made indefinite.
We want maximal state persistence / "object permanence" in-engine.
