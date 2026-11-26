# Magic: Soul Bound

**Waiting on:** owner (2026-11-25: backlog it so it is done right), "Magic: effects on enemies" (Soul Trap filling traps from Doom kills).

Daggerfall facts (`Effects/Enchanting/SoulBound.cs`): the item maker lists one Soul Bound option per filled soul trap (or a filled Azura's Star), by Daggerfall creature. Making the item uses up that trap and adds the creature's forced enchantments (`MobileForcedEnchantmentSets`). When the item breaks, Daggerfall spawns the bound creature as a hostile (`GameObjectHelper.CreateFoeSpawner`).

Doomerfall needs: Soul Trap to fill traps with the Daggerfall creature that spawned the pack, and the break spawn done in Doom as the Doom monster (or pack) for that creature.
