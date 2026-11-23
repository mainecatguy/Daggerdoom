# Mook packs

**Waiting on:** MVP, and the owner defining the point-buy system.

Post-MVP, but before initial release. Replace the one random enemy per placement with the mook pack design in `gamedesign.md`: encounters generate packs of Doom enemies from fixed seeds, and only deaths are tracked. Mook HP and resistances come from Doom's WAD and mod definitions. Daggerfall can at most apply a multiplier. Research found that `RandomSpawner` uses a shared random number generator, so packs must be expanded into concrete monster classes from the seed before spawning.
