# Guard behavior and pathfinding

**Delayed indefinitely by the owner (2026-11-24). Do not raise or start this until the owner brings it up.**

Two related items:

- **Guard behavior.** The owner's earlier request (2026-11-23) was to improve how Doom guards behave after the first guards landed. Play tests found guards stuck on counters and furniture, shooting into furniture, and sometimes landing no hits. A drafted card is held in `work/queue/guardsbetter/held/01.opus.guard-behavior.md`.
- **Pathfinding.** UZDoom has no pathfinding: monsters and Cajun bots step straight toward the target and pick another or a random direction when blocked (`P_NewChaseDir` in `p_enemy.cpp`). Daggerfall's maze dungeons and cluttered interiors may stop packs and guards from reaching the player. One idea discussed was a flow field over a walkable grid that the converter precomputes. This changes how the game plays, so it is the owner's call.

Agent question [20261123-233427], reported six times: should outdoor guard bots be part of the next guard task? Deferred to the owner. Held here because this item is not to be raised.
