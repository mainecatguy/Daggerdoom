# Area level replaces player level

**Waiting on:** owner design for how an area's level is defined.

Owner decisions (2026-11-23):

- Doomerfall is totally indifferent to player level for scaling purposes. It only cares about area level. See "The world does not scale to the player" in `gamedesign.md`.
- Material tiers follow the approved design in `work/notes/20261123-material-tier-proposal.md`.

Player level currently feeds loot and gold amounts, material rolls, random encounter tables, class enemy level and health, guild costs, and quest offers and rewards. Start from `LootTables.cs`, `DaggerfallLoot.cs`, `FormulaHelper.RandomMaterial`, `RandomEncounters.cs`, `RDBLayout.cs`, `EnemyEntity.cs`, `Guild.cs`, and `DaggerfallQuestOfferWindow.cs`.

DRLA Monsters also scales with player progress. Its `RLDangerLevelIncreaser` script raises `RLDangerLevel` on map entry, and `RLAdaptiveSpawnPicker` reads it. Doomerfall encounters must not depend on that value.

## Open question for the owner

How is an area's level defined?
