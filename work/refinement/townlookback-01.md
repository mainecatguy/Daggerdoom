# Nature flats beyond a town or dungeon exterior map's edge

UNREFINED (owner, 2026-11-27: "take an item into refinement to resolve the remaining problem mark it as unrefined").
Lane: `townlookback` (new). Model: Opus.

From inside a town or dungeon exterior map, Daggerfall's nature flats (trees, rocks) show only on the map's own ground,
which ends 24 tiles from the location. The forest beyond it is missing: 125 of 256 flats within 20 tiles at the City of
Daggerfall and 130 at Ruins of Gaerhart Manor (`tools/nature/town_lookback.py`). Spawning them farther out would leave
them floating, because the town map has no ground there. The agent said a fix needs a change to how town maps are
built. One possible route, not decided: the distant terrain ring from `distantlod` (render-only far terrain) could
carry these flats too.

Done when: (to refine) looking out from a town or dungeon exterior shows the surrounding forest, in a paired run.
Context: `work/notes/20261126-230950.md` (terrainflats run 3, "Questions for the owner"); `distantlod` 01 in todo.
