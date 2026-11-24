# Area level replaces player level

**Waiting on:** "Compute area levels in Daggerfall" in the todo, and owner approval to move to todo. The owner approved the area level proposal on 2026-11-23 (`work/notes/20261123-225515-area-level-proposal.md`).

Owner decisions (2026-11-23):

- Doomerfall is totally indifferent to player level for scaling purposes. It only cares about area level. See "The world does not scale to the player" in `gamedesign.md`.
- Material tiers follow the approved design in `work/notes/20261123-material-tier-proposal.md`.

Player level currently feeds loot and gold amounts, material rolls, random encounter tables, class enemy level and health, guild costs, and quest offers and rewards. Start from `LootTables.cs`, `DaggerfallLoot.cs`, `FormulaHelper.RandomMaterial`, `RandomEncounters.cs`, `RDBLayout.cs`, `EnemyEntity.cs`, `Guild.cs`, and `DaggerfallQuestOfferWindow.cs`.

DRLA Monsters also scales with player progress. Its `RLDangerLevelIncreaser` script raises `RLDangerLevel` on map entry, and `RLAdaptiveSpawnPicker` reads it. Doomerfall encounters must not depend on that value.

## Owner direction for the proposal (2026-11-23)

Levels 1 to 30, all about equally common. Level 1 is the minimum because Daggerfall's player level starts at 1.

Clarification (owner, 2026-11-23): player agency does not come from guessing difficulty from a place's region or type. That would mean, for example, no hard crypts. Every kind of place should exist at every difficulty. Agency comes from showing the player each place's difficulty, as a hint in the travel menu (see the todo item "Show area difficulty in the travel menu"). Inputs are region (early-game regions lower, late-game higher, with variety), encounter type, a per-location random part, and geographic clustering, all from fixed seeds. The goals are player agency over region and difficulty, and many kinds of themed content at many levels.
