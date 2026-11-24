# Area level replaces player level

**Waiting on:** owner design. The owner is researching which level ranges Daggerfall works best with.

Owner decisions (2026-11-23):

- Daggerfall no longer looks at player level. It uses area level instead.
- Items that land in Daedric on the material roll are rolled again among any category, biased against rarer tiers. Daedric stays the best category, and this is the only way to get it.
- Every category gets monotonically better with level. The proposal is in `work/notes/20261123-material-tier-proposal.md`.
- Lower tier items are always more common. At best, a lower tier can be only slightly less common than the tier above it.

Player level currently feeds loot and gold amounts, material rolls, random encounter tables, class enemy level and health, guild costs, and quest offers and rewards. Start from `LootTables.cs`, `DaggerfallLoot.cs`, `FormulaHelper.RandomMaterial`, `RandomEncounters.cs`, `RDBLayout.cs`, `EnemyEntity.cs`, `Guild.cs`, and `DaggerfallQuestOfferWindow.cs`.

## Open questions for the owner

1. How is an area's level defined?
2. Does area level replace player level everywhere, or only for loot and encounters?
3. Approve or change the material tier proposal, including how rare early high tiers and Daedric should be.
