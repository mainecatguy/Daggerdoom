# Quest foes outside dungeons and quest ambushes as mook packs

Lane: `questfoes` (new). Model: Opus. Depends on nothing.

38 quests put a quest foe in a town building (for example M0C00Y11's giant scorpion in a small house), and 100 quests
use 'create foe' to spawn foes near the player anywhere. They should use the existing mook system: quest foes are
added on top of the place's seeded army with their own IDs (`gamedesign.md`, Handling multiple enemies), as packs.

Owner (2026-11-26): "Use the mook system for this, we have this already don't we?"

Done when: a quest foe placed in a town building and a 'create foe' ambush each spawn as a mook pack with a counted
leader, the quest's kill condition fires as for dungeon quest foes, and deaths persist; tested on a sample of quests.
Context: backlog `quest-targets-in-mook-packs` and `quest-packs-steal-points`.
