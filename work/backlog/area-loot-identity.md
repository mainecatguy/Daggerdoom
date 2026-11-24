# Area loot identity

**Waiting on:** "Inventory translation", which must have rules for weapons, ammo, and consumables, and the "Ammunition system". Both are in the backlog. Also needs "Fixed loot seeds for Daggerfall's random loot" in `work/todo.md`.

Owner decision (2026-11-23): convert the proposed area loot system into a task. Full design: `work/notes/20261123-215220-area-loot-variety.md`.

Each dungeon gets a fixed loot genome, built from its identity with its own loot seed. The genome leans **which kind** of item drops, such as the weapon family, ammo class, mod pack, or consumable. It runs only after Daggerfall's loot table has picked the count and category, and after the approved tier roll has picked the material.

- **Does not change:** fixed loot seeds, drop counts, gold, category chances, material tier odds, or Daedric's own check. The same pile still gives the same items in every game.
- **Every kind stays possible everywhere.** Each ammo class keeps at least 10% of ammo drops.
- **Never uses the player.** It reads only the area's identity, its area level, and the planned encounter.
- **Works with plain Doom,** using 5 stock weapon families and the 4 ammo classes.

## First version

From section 10 of the note:

1. A loot genome function with its own salt. Only Arsenal (weapon family) and Ammo stance are active, with a fixed 60% on-theme share and 10% ammo floors.
2. A hook in the translation step, after the tier roll, seeded from the area, the salt, and the pile or corpse index.
3. The plain-Doom fallback.
4. An offline check that rolls many drops for 20 dungeons. It shows each dungeon's family shares, and confirms that tier shares match the approved table with and without the genome.

Add the army echo, exceptions, cache recipes, Kit, and Mods one at a time afterwards.

## Open owner decisions

These are in section 11 of the note:

- How strong identities are.
- Whether loot echoes the army, and how strongly.
- Whether regions and towns get identities.
- Whether dungeon type leans the genome.
- Whether DRLA and Colourful Hell monsters' own drops (`A_DropItem("Clip")`, and `CH_HealthDrops`, `CH_AmmoDrops`, `CH_ExtraDrops`, `CH_BackPackDrops`) exist on Daggerfall maps.
