# Monster mix on stock Doom maps

**Waiting on:** owner design.

**Current rule (owner, 2026-11-23):** on ordinary Doom maps, stock monsters are replaced by DRLA monsters only. Colourful Hell's monsters never appear there. This happens because DRLA Monsters replaces stock monsters through skill `ReplaceActor` in MAPINFO, which the engine applies before Colourful Hell's DECORATE `replaces`. The Colourful Hell compatibility patch (`mods/ch-compat/`) loads Colourful Hell before DRLA.

This only affects ordinary Doom maps, such as Oblivion portal maps or custom WADs. Doomerfall's own encounters on Daggerfall maps spawn monsters by class name and are not affected.

Later, decide how stock maps should mix the two mods. Options include a mixed spawner like the 2018 patch's, which was about 50/50, or reusing the encounter genome rules on stock maps. Follow the same principles as encounters: no player-level scaling, deterministic choices, no `RandomSpawner`, and one colour per monster kind instead of a rainbow mix.
