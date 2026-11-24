# Doom weapon equipping and hotkeys

**Waiting on:** Daggerfall item pickup, the owner answers listed below, and owner approval to move to todo. The owner confirmed real mouse mapping in the inventory works (2026-11-23).

Doom will be the client, so this is not a Daggerfall-only feature. Daggerfall's inventory is shown through Doom by a cross-game overlay, and the hotkeys are Doom keybindings that act on that menu.

Keep Daggerfall's existing inventory. No inventory layout change is needed. Doom guns are drawn only by hotkey, never by equipping.

**Design so far (owner, 2026-11-22):**

- Hover over an item or spell and press 1 to 0. A popup shows five gray inventory-style squares: three for the plain key (overloading, so up to 3 things share it and pressing again cycles), one for Ctrl+key, one for Alt+key, each clearly labelled.
- Clicking a square overwrites it. A small red x in its corner deletes the assignment. The assigned item's icon fills the square.
- Hotkeys are references only. Hotkeying never removes anything from the inventory.
- Using a hotkey draws the item, readies the spell, or prepares the item to be used. Using it immediately is acceptable at first.
- The player starts with a Doom weapon already hotkeyed.
- Using DFU's normal equip action on a Doom weapon does not equip or auto-assign it. It always shows: "Press # over an item to assign hotkeys. Equip doom weapons through their hotkey."
- Assignments are stored in DFU's save data.

**Gun equipping (owner, 2026-11-23):**

- Daggerfall's inventory can hold unlimited guns, including duplicates. This is the source of truth.
- Doom holds only the active gun. If necessary this could become two, but Doom must never hold the whole collection.
- Pressing a hotkey removes the old Doom weapon and gives the new one, without altering ammo.
- Each gun's magazine state is tracked but not shown to the player.
- The active hotkey is tracked.
- Doom's stock 2-3-4-5-6 weapon slots are removed from the HUD by a separate task. See "Rework the Doom HUD".

**Keys (owner, 2026-11-23):** Ctrl and Alt are always the hotkey modifiers, however they are bound. Ctrl also stays crouch. Overloading is fine, and the player may overload them further.

**Magazines (owner, 2026-11-23):** swapping guns must not reload them. Save only as much magazine state as that needs. Exact rounds per gun can be skipped if overkill.

**Approved (owner, 2026-11-23):** card `work/queue/hotkeys`, to start after "Daggerfall holds Doom items" lands.

**Clothing (owner, 2026-11-23):** cannot be hotkeyed for now. See "Hotkey clothing".

**Technical constraint found in DRLA:** a weapon's loaded magazine is a separate per-class item (`RL<Weapon>Clip`), and mods and limits are also tracked by class name, such as `<Weapon>ModLimit` and `RLWeaponLimit`. A swap must save this state onto the outgoing Daggerfall item and restore it for the incoming one, or two copies of a gun will share a magazine and mods. The swap must also keep `RLWeaponLimit` correct.

**Missing items (owner, 2026-11-23):** when a hotkeyed weapon leaves the inventory, its assignment is deleted. When a consumable runs out, its square keeps a grey X overlay, and the hotkey works again when the player picks up more of that item.

**Armor (owner, 2026-11-23):** hotkeying armor is allowed but lowest priority and not important. Do it only if it is cheap, for example by calling Daggerfall's own equip action.
