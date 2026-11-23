# Daggerfall items in the world

**Waiting on:** the bridge core, position sync, the inventory menu, and "Show Daggerfall items in Doom" in `work/todo.md`, which covers display only.

Owner design (2026-11-22): Doom must be tolerant of Daggerfall items. Doom is the dominant client, so it must show them and let the player interact with them.

- All Daggerfall items can drop in the world or appear in the world, including static placed items.
- Doom shows these items in the game, whether or not they have a Doom equivalent.
- The player presses the Interact keybind to pick an item up into their Daggerfall inventory. Interact is a bindable action in the existing Doomerfall Controls definitions, never a hardcoded key.
- Picked-up items stay gone, following the permanent location state rules.

- For loot piles and containers holding several items, Interact opens Daggerfall's real loot window through the Doom menu path.
