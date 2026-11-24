# DRLA recipes as Daggerfall rewards

**Waiting on:** inventory translation, and owner design for which rewards give recipes.

**Owner request (2026-11-23):** make DRLA's PDA recipes, its weapon and armor assemblies, an item the player can acquire. Daggerfall can give it as a reward, for example from quests or loot.

- **Only when DRLA is detected.** Without DRLA, the item must never appear, and nothing may break.
- In DRLA, assemblies are unlocked through its PDA. DRLA's own unlock pickup is `RLBlueprintComputer` (`DoomRL_Arsenal_1.1.5/actors/misc/ComputerMaps.txt:121`). DRLAX adds a blueprint tracker in `DRLAX_1.2b/zscript/DRLAX/BlueprintEX.zscript`. Start from these.
- Decide whether one item unlocks one recipe or a random one, how it appears in Daggerfall's inventory, and where Daggerfall can award it.
- The rest of the DRLA PDA, including the bestiary and kill counters, is not important to the mod right now. They ignore Colourful Hell kills, and that is acceptable.
