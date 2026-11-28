# Bring back DRLA X gizmos as seeded pickups

Read `gamedesign.md`'s randomness principles first ("Randomness" and "Adding things to random pools").
Lane: `gizmos` (new). Model: Opus. Only when guns are enabled (always today; see backlog `guns-off-option`).

DRLA X's devices (deployers, revisers, recyclers, extractors and the like) were turned off on Daggerfall maps because
they spawned every 2-3 map loads, tying the world to the player's load history. Owner (2026-11-27): "Yes, let's bring
back the gizmos, daggerfall will need to be aware of them, we'll need them to be able to spawn instead of some other
power up such as health pickups. Maybe a 3% chance of a gizmo." Also: gizmos "should also be able to appear in dungeons
or drop in random loot".

- **Which gizmos:** all DRLA X devices that work on Daggerfall maps; the worker lists each with what it does and leaves
  out only ones that cannot work there (for example DRLA X's own quest objects, which would duplicate Daggerfall's
  quests), and says why for each one left out.
- **How often:** about 2% of the Doom dungeon pickup spots (owner, 2026-11-27: "About 2%") (the converter's Doom pickups, not Daggerfall loot) hold a
  gizmo instead, and gizmos also appear in Daggerfall's seeded random loot, overall about as common as weapon mods.
- **Fit into the existing systems:** gizmos join the existing pickup and loot "genetics" (per-place identity and leans,
  U-shaped spreads, spiky places, rare exceptions) rather than a flat roll, and never stop other items from dropping;
  the worker has latitude in how (owner, 2026-11-27: "incorporate it with existing 'item genetics' ... Use some level of
  judgement ... do it in an elegant way that meets our expectations and doesn't prevent other types of items from
  dropping and respects the game design constraints: procedural seeds always produce the same loot, and loot is very
  surprising"). See `gamedesign.md`, "Adding things to random pools".
- **Once taken:** a gizmo is a Daggerfall inventory item; a device the player deploys stays where it was put, recorded
  by Daggerfall. Shops do not sell gizmos.
- Once taken, a gizmo stays gone (owner, 2026-11-27: "They stay gone once taken (daggerfall at a minimum knows when
  they're gone and at a minimum their initial placement is deterministic seed)"): Daggerfall records it as taken, like
  other taken Doom pickups (`takenpickups` 01).

Done when: a survey of many dungeons shows gizmos in about 2% of Doom pickup spots, identical across runs; one is found
in seeded loot; a taken gizmo stays gone after leaving, returning, and a save and load in a paired run.
