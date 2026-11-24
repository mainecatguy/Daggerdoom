# Doom items replace most weapon loot

**Waiting on:** owner approval to move to todo, and *DRLA rarity tiers* (which Doom weapon is picked). Related: *Inventory translation*.

Owner decisions (2026-11-24):

- When Daggerfall rolls a weapon as loot, it is replaced **80%** of the time, because Daggerfall weapons are not usable
  yet. **Revisit this rate** once Daggerfall weapons work in Doom (the long-term idea was 50%).
- Of all weapon rolls: about **5% become a DRLA modpack** and **1% a DRLA recipe** (only when DRLA is loaded; see
  *DRLA recipes as Daggerfall rewards*). Both are inside the 80%. The other 74% become a Doom weapon.
- Every source that rolls weapons: treasure piles, enemy loot, shop shelves, house containers, enemy starting
  equipment, and quest rewards.
- The roll uses the loot's fixed seed, so the same place gives the same result in every game.
- The replacement keeps the rolled material (*Doom weapons have a Daggerfall material*).

Where weapons are rolled today: `LootTables.GenerateRandomLoot`, `DaggerfallLoot` shop shelves and house containers,
`ItemHelper.AssignEnemyStartingEquipment`, and `Questing/Item.cs`. Doom items in Daggerfall's inventory are
`DoomerfallDoomItem` (`DoomerfallDoomItems.cs`).

Open: should Doom weapons dropped by Doom monsters also get a material?
