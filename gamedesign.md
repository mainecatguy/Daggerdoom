The basic design goal of this project is simple: "daggerfall, but oops we replaced all the monsters with slaughter map sized packs from doom, and that ebony mace that dropped got converted to an energy machinegun from the doom roguelike arsenal extended mod, and when NPCs get angry at you they behave like Doom NPCs."


Short-Term Game Design Goals

## Vertical Slice Target
Play through one Daggerfall dungeon (e.g., Privateer's Hold) and one town, fast-traveling between them: fight Doom monster packs, loot and fire a converted DRLX weapon, talk to and provoke an NPC, complete one Daggerfall kill quest, save and reload mid-fight, and leave/re-enter the dungeon with dead enemies and dropped gear intact.



## Long-term Game Deisgn Goals

| Domain | Prevailing System | Game Design Rule |
|---|---|---|
| **World, Time & Weather** | **Daggerfall** | The calendar, seasons, regions, day/night cycle, weather, and fast travel govern the world. |
| **Aesthetics & Tone** | **Daggerfall (world) + Doom (combat)** | Environments, architecture, skies, and props look like Daggerfall; weapons, monsters, gore, and combat effects look like Doom/DRLX. |
| **World Persistence** | **Total Persistence** | Every killed monster, corpse, dropped item, unlocked door, and world change stays permanent across revisits. Persistence is total and uncompromising: there are no dungeon resets, respawns, or area refreshes. |
| **Combat & Weapons** | **Doom / DRLX** | Pure real-time FPS gunplay, projectiles, hitscans, ammo economy, and Doom Roguelike Extended Arsenal weapon modding. No Daggerfall dice-roll-to-hit combat. |
| **Monsters & Encounters** | **Doom / DRLX** | Daggerfall's monsters are replaced by packs of Doom/DRLX monsters that spill through available space and infight. Pack size is unpredictable and depends on the dungeon, from small packs up to slaughter-map scale. Difficulty follows area level. |
| **NPCs, Dialogue & Quests** | **Daggerfall (peaceful) + Doom (hostile)** | Townsfolk, guilds, dialogue, and quests follow Daggerfall's rules. Once attacked or flagged hostile, NPCs fight as aggressive Doom bots, usually with powerful non-hitscan weapons. |
| **Crime, Bounties & Guards** | **Daggerfall (rules) + Doom (enforcement)** | Daggerfall governs reputation, bounties, surrender, and court/jail; hostile guards pursue and fight like Doom bots. |
| **Player Vitals & Death** | **Daggerfall** | Daggerfall's HP, attributes, armor, resistances, fatigue, magicka, and death rules govern survival. DRLX passes base damage and damage type entities want to deal to daggerfall, and daggerfall applies its damage rules and is the final arbitrator of how much damage was dealt to an entity. All DRLX weapons have damage types. |
| **Status Effects & Transformations** | **Daggerfall** | Poison, disease, paralysis, buffs, vampirism, and lycanthropy follow Daggerfall's rules and directly alter movement, vision, and survivability in Doom combat. |
| **Movement & Traversal** | **Doom (feel) + Daggerfall (abilities)** | Doom's fast, responsive FPS movement is the baseline, modified by Daggerfall's encumbrance, swimming, climbing, levitation, and horses. |
| **Magic & Spellcasting** | **Daggerfall (rules) + Doom (execution)** | Daggerfall's spellbooks, spellmaker, magicka costs, and spell effects prevail. Spells are cast and fly in real time like Doom attacks. |
| **Loot & Economy** | **Daggerfall (economy) + DRLX (gear)** | Daggerfall rolls loot from its own loot tables with fixed seeds, and runs the gold economy, shops, banks, wagons, and houses. It decides how much drops and in which category. The material tier comes from the approved odds for the area level. Drops then translate into DRLX weapons, ammo, armor, mod packs, and consumables. Each area can have a fixed loot identity that leans which kinds of gear drop there, such as weapon families or ammo types, and loosely echoes the army that guarded it. That identity never changes tier odds or amounts, and every kind of item stays possible everywhere. The loot identity is a proposal: see `work/notes/20261123-215220-area-loot-variety.md`. |
| **Interactive World & Locks** | **Daggerfall** | Lock ratings, lockpicking, door bashing, traps, and secret triggers follow Daggerfall's RPG checks. |
| **Stealth & Detection** | **Detection bar (similar to Blood West)** | The player has a detection bar. Doom monsters are forced to stay idle until the bar fills or the player fires a gun. Enemies facing the player with line of sight, and sounds, make the bar fill faster. A high Stealth skill makes it fill much slower. |
| **Resting & Loitering** | **Daggerfall** | Resting advances time and restores vitals, blocked when Doom monsters are nearby and interrupted by Doom ambush packs. |
| **Progression & Skill XP** | **Daggerfall** | Combat, spellcasting, and traversal drive Daggerfall's use-based skill leveling; DRLX progression remains gear-centric. |
| **Audio & Music** | **Daggerfall (music/UI/NPCs) + Doom (combat)** | Daggerfall supplies music, UI sounds, and NPC barks; Doom supplies combat SFX. |

## The world does not scale to the player (design principle)

Unlike Daggerfall, the world never changes around the player to accommodate them. Doomerfall is totally indifferent to player level for scaling purposes and only cares about area level. Never use level scaling or any other artificial scaling of the game world that breaks the illusion that facts about the world are independent of facts about the player. This is a major feature of the mod and a major change from original Daggerfall.

## Randomness (design principles)

### Fixed seeds, not per-save randomness

In general, events are fixed and not randomized per save. The world is generated from fixed seeds, so the same place is the same kind of place in every game. If two players visit the same dungeon, they get the same encounter theme and the same loot customization. Unless they pick a custom option, they even get the same loot drops. This gives the Morrowind experience of players comparing notes: "Oh yeah, that cave was full of dangerous enemies, but it had the BFG in it."

- Loot and encounter theming use separate seed definitions.
- The overworld follows the same rule. Its encounter variety and surprise come from fixed seeds based on the region.
- Optional settings to make loot or encounter theming random per save are planned. Deterministic is the default.

### Surprise: learn the pattern, then break it

Random events aim for Bayesian surprise: outcomes that meaningfully change what the player expected. Pure noise does not do this, because after a while every room is different in the same way. Surprise comes from fixed structure that the player can learn, which then breaks its own pattern. Apply this within reason, without compromising the core structure of the game.

- **Places have a fixed identity.** Each dungeon gets a fixed "genome" from its identity. It makes the place mostly coherent but varied: its armies, their sizes, and possibly what kinds of loot it gives. The encounter genome is accepted. The loot genome is proposed.
- **Exceptions break the pattern.** A shotgun dungeon holds one plasma rifle cache, or an elites-only dungeon has one room of grunts. An exception means something because of where it is.
- **Favor extremes.** Use a U-shaped distribution where a middle value would be dull: many weak enemies or a few strong ones, and places that are either strongly themed or barely themed.
- **Recurring types with new ones trickling in.** Rooms reuse squad types and loot piles reuse a few combinations, more often the more common they are, while new kinds keep appearing now and then (Pitman-Yor style reuse).
- **Leans, not bans.** A place may make something common or rare, but should not make it impossible where that could starve the player, such as ammo for their gun.
- **Randomness never bends approved rules.** For example, a genome may change what kind of item drops, never the material tier odds.
- **Never adapt to the player.** Randomness uses only fixed facts about the place and its area level. There is no "smart loot" tuned to the player's guns, no pity timers based on the player's history, and no live tuning to how the player plays. See "The world does not scale to the player."

## Material tiers (design principles)

- Every category gets monotonically better with area level: the chance of getting a given tier or better never falls.
- Lower tier items are always more common. At best, a lower tier can be only slightly less common than the tier above it.
- Daedric is the best tier, and its own check is the only way to get it. It reaches 1 in 40 at area level 20 and 1 in 20 at area level 30.
- Ammo uses the same tiers. Iron ammo is called Regular ammo. The working ammo table is in the change ammo key item in `work/todo.md`.

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

Ammunition will eventually be an inventory object. Damage rules, including material bonuses and ammo tags, are in `gamedesign/damage.md`.

- Ammunition has different qualities.
- A system will let the player change the type of ammo loaded in a gun.
- Daggerfall can tell Doom that the player has more than Doom's max ammo, and Doom accepts it.
- There may be limits on how much ammo the player can carry. That is a future system.

Other todos:
DFU loot should persist no matter where it is dropped if possible.
DFU area respawns and dungeon resets are removed entirely (owner, 2026-11-23).
We want maximal state persistence / "object permanence" in-engine.
