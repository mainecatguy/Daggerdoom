# Random or deterministic options for loot and encounter theming

**Waiting on:** fixed loot seeds (in `work/todo.md`) and the encounter genome being built.

Owner decision (2026-11-23): the game is deterministic by default. See "Fixed seeds, not per-save randomness" in `gamedesign.md`. Add two player options:

- **Loot:** deterministic (the default) or random per save.
- **Dungeon encounter theming,** which decides the monsters: deterministic (the default) or random per save.

Loot and encounter theming use separate seed definitions. Each checkbox mixes a per-save value into its own seed only. Decide where the options live, such as the new-game flow, and whether they can change after a game starts.
