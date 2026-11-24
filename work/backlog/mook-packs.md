# Mook packs

**Waiting on:** MVP, and the remaining owner decisions in section 12 of the encounter report.

Post-MVP, but before initial release. Replace the one random enemy per placement with the mook pack design in `gamedesign.md`: encounters generate packs of Doom enemies from fixed seeds, and only deaths are tracked. Mook HP and resistances come from Doom's WAD and mod definitions. Daggerfall can at most apply a multiplier. Research found that `RandomSpawner` uses a shared random number generator, so packs must be expanded into concrete monster classes from the seed before spawning.

**Encounter design (owner, 2026-11-24):** see `work/notes/20261123-205402-fractal-encounter-variety.md`, sections 6 and 9. Doom owns the spawning algorithm and must be deterministic. Daggerfall sends the area level, dungeon type, location, region, world position, placements, and dead mook IDs.

**Placement rules for the spawner:**

- **Hard requirement:** each encounter's leader stands exactly on the Daggerfall placement's origin point, so quest triggers never break and nothing important spawns out of bounds. The leader is the highest-point monster in the encounter that fits at the origin. If none fits, the cheapest monster becomes the leader.
- Every placement holds at least one monster, and taking points away can never leave it unable to afford its cheapest monster, so every Daggerfall enemy has a kill trigger.
- The rest spread out widely: search outward from the origin in a fixed order, and keep going until each monster finds a valid spot reachable on foot from the origin.
- Points that do not fit are never lost. Spread wider, promote to fewer stronger monsters, or move the points to the nearest placement with room.
- Use the module's own integer hash for randomness, never Doom's shared generator. Spawn at map load, before anything moves.
