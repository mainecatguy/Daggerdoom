# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

The owner approved this work on 2026-11-23. Each item runs from its reviewed card in `work/queue`.

**Owner decisions on the research (2026-11-23):**

- Each Doomerfall save is one bundled UZDoom `.zds` file using Doom's save and load menus. It must still make a real Daggerfall save and carry it in the bundle.
- After death, show Doom's death view, then a screen offering Load Last Save, Load Game, and Main Menu.
- New Game temporarily uses one difficulty prompt after Daggerfall character creation and a fixed default Doom class. See "Full Daggerfall new game flow" in the backlog.
- Leave quick keys and quit behavior alone for now.
- Autosaves on Daggerfall maps use the bundled save. Their frequency can be revisited if they slow the game down a lot.

### Prove and finish synchronized saving

The first version is merged to `integration`, but no real Daggerfall save has gone through it. Saving pauses both games with a handshake, so messages in flight are not lost, then saves both. Each writes temporary files, and the real save is replaced only after both succeed. Start with player HP and position. On Daggerfall maps, Doom's save command and autosaves go through this path. Regular WADs keep normal Doom saves.

### Synchronized loading

Loading restores both games from the same save, and both confirm they are ready before resuming together. Doom's load command and death restart on Daggerfall maps go through this path. Regular WADs keep normal Doom loading.

### Fast travel arrival

Daggerfall owns travel cost, time, and destination. Doom reports the player's world position to Daggerfall, then loads the chosen town or overworld position and places the player where Daggerfall would.

### Connect building and dungeon transitions to Daggerfall

When the player enters or leaves a building or dungeon in Doom, Daggerfall moves to the same place, so both games stay in the same area.

### Open the inventory menu from Doom

A Doom keybind opens Daggerfall's real inventory inside the Doom window, with input routed to it, and closing it resumes Doom. The exact key is not important, but it must be a bindable control. The "Open Inventory" action already exists in Doomerfall Controls.

### Animated textures and ordinary dungeon flats

Add these to the dungeon export so they match Daggerfall. Dungeons currently show only the first frame of animated textures, such as Scourg Barrow's 6-frame blue shard and 4-frame fireplace. Ordinary non-action flats, such as wall torches, lights, and plants, are not exported at all.

### Show Daggerfall items in Doom

Owner design (2026-11-23): Doom can show every Daggerfall item in the world with its original sprite, without crashing. Doom knows each one is a Daggerfall item, perhaps through a `DaggerfallItem` class holding Daggerfall's item ID and sprite index. This task only shows items. It does not drop or place them.
