# Daggerfall's random encounters as Doom packs

Lane: `randomencounters` (new). Model: Opus. Depends on nothing.

Since position sync, all of Daggerfall's random encounters are suppressed for the whole session: ambushes while
resting or loitering, and the guards that come for a low-reputation or banished player (`PlayerEntity.Update`, behind
`PreventEnemySpawns`). The Resting rule says rest is "interrupted by Doom ambush packs" (`gamedesign.md`).

Owner (2026-11-26): "Random encounters should be a card, yes. It should work as mooks in dungeons work."

Clarified (owner, 2026-11-26): "daggerfalls random encounter system should use Daggerfall's existing functions to
pick the enemy, but they should be scaled by area level if daggerfall didn't do that, and additionally, it should use
the Mook system we have (we have it right?) to generate packs of enemies." So Daggerfall's own encounter functions
choose the enemy (fed the area level, never the player's level), and the mook system turns it into a pack.

Done when: when Daggerfall rolls a random encounter (rest or loiter ambush, reputation or banishment guards, and its
other random spawns), Doom spawns a pack through the encounter and mook system, seeded like dungeon packs and sized by
area level; deaths are kept like other mooks; a paired run shows a rest interrupted by an ambush pack.
