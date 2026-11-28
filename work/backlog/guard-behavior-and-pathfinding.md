# Guard behavior and pathfinding

**Delayed indefinitely by the owner (2026-11-24). Do not raise or start this until the owner brings it up.**

Two related items:

- **Guard behavior.** The owner's earlier request (2026-11-23) was to improve how Doom guards behave after the first guards landed. Play tests found guards stuck on counters and furniture, shooting into furniture, and sometimes landing no hits. A drafted card is held in `work/queue/guardsbetter/held/01.opus.guard-behavior.md`.
- **Pathfinding.** UZDoom has no pathfinding: monsters and Cajun bots step straight toward the target and pick another or a random direction when blocked (`P_NewChaseDir` in `p_enemy.cpp`). Daggerfall's maze dungeons and cluttered interiors may stop packs and guards from reaching the player. One idea discussed was a flow field over a walkable grid that the converter precomputes. This changes how the game plays, so it is the owner's call.

Agent question [20261123-233427], reported six times: should outdoor guard bots be part of the next guard task? Deferred to the owner. Held here because this item is not to be raised.


Defect recorded 2026-11-27 (game designer, `gamedesign/decisions/20261127-outdoor-watchman-vanishes.md`): a town watchman shot outdoors vanishes after the blood splash, because Daggerfall turns him into a city watch knight and Doom relays guards only indoors (`dd_guards.cpp`). The same cause means crimes in town call guards that never reach Doom. The design's only fix is outdoor guard bots (this item).


Owner, 2026-11-27: outdoor guards are now queued as todo card `outdoorguards` 01 (work/queue/outdoorguards/01.opus.outdoor-guard-bots.md). Guard behavior and pathfinding stay delayed.
