# Doom weapon equipping and hotkeys

**Waiting on:** showing a Daggerfall menu inside Doom, inventory translation, and the owner answers listed below.

Doom will be the client, so this is not a Daggerfall-only feature. Daggerfall's inventory is shown through Doom by a cross-game overlay, and the hotkeys are Doom keybindings that act on that menu. Do this after the fast travel proof of concept.

Keep Daggerfall's existing inventory. No inventory layout change is needed. Doom guns are drawn only by hotkey, never by equipping.

**Design so far (owner, 2026-11-22):**

- Hover over an item or spell and press 1 to 0. A popup shows five gray inventory-style squares: three for the plain key (overloading, so up to 3 things share it and pressing again cycles), one for Ctrl+key, one for Alt+key, each clearly labelled.
- Clicking a square overwrites it. A small red x in its corner deletes the assignment. The assigned item's icon fills the square.
- Hotkeys are references only. Hotkeying never removes anything from the inventory.
- Using a hotkey draws the item, readies the spell, or prepares the item to be used. Using it immediately is acceptable at first.
- The player starts with a Doom weapon already hotkeyed.
- Using DFU's normal equip action on a Doom weapon does not equip or auto-assign it. It always shows: "Press # over an item to assign hotkeys. Equip doom weapons through their hotkey."
- Assignments are stored in DFU's save data.

**Open questions for the owner:**

- Missing item: grey X overlay or delete? Claude's recommendation is an overlay that works again when the item returns, deleting only when the item is destroyed or consumed, with stacks tracked by item type.
- Which items can be hotkeyed: only drawable, readyable or usable ones, or also armor and clothing?
