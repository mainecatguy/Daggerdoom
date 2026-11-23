# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 90%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

### 1. Launcher for both games

A launcher starts Daggerfall Unity and UZDoom as one package and exits both if either one exits or crashes. It includes a simple message channel between them. Launching UZDoom normally must behave exactly as it does today.

### 2. DaggerDoom mod scaffolding

Create our own Doom mod for DaggerDoom. Use whatever form fits best, likely a pk3 with custom key sections, menus, and event handlers. At minimum it adds a DaggerDoom section to the controls menu with bindable actions such as "Open Inventory" and "Open Fast Travel", and sends those actions to Daggerfall. The launcher loads it, so regular WADs and mods are unaffected.

### 3. Show Daggerfall's fast travel menu in Doom

Pressing the Fast Travel key pauses Doom and shows Daggerfall's real travel map inside the Doom window, with input routed to it. Closing it resumes Doom. Do not recreate the menu in Doom. Build this so other Daggerfall menus, such as inventory, can use the same path. Daggerfall's 3D world should not render while this runs. Arriving at the chosen destination is a separate backlog item.

### 4. Synchronized saving

Saving pauses both games with a handshake, so messages in flight are not lost, then saves both. Each writes temporary files, and the real save is replaced only after both succeed. Start with player HP and position. On Daggerfall maps, Doom's save command goes through this path. Regular WADs keep normal Doom saves.

### 5. Synchronized loading

Loading restores both games from the same save, and both confirm they are ready before resuming together. Doom's load command and death restart on Daggerfall maps go through this path. Regular WADs keep normal Doom loading.

### 6. Audit every dungeon

Run the converter on all dungeons and report what breaks, map size, load time, frame rate, and how often each feature appears, such as teleporters, water, lifts, climbing shafts, and special markers. Use the results to recommend priorities for the dungeon work.

Outside feedback raised these possible problems. Treat them as unverified until the audit or real data confirms them:

- Large multi-block dungeons may hit practical size or performance limits.
- Stacked floors may cause sliver sectors, sound bleeding through rock, automap clutter, or lighting and fog bleeding between floors.
- Tightly stacked sloped 3D floors may snag actors or show seams.
- Dungeon textures may need runtime swaps by region and dungeon type, and some are animated.
- Editor marker flats may carry teleporter destinations, quest anchors, fixed spawns, and ambient sounds.
- Some original blocks have misaligned doorways, small lips that snag movement, or broken action chains.

### 7. Update the parity test for swinging doors

The parity tool's closed-door stages were written for the old door slabs and no longer mean anything. Make them meaningful for swinging door objects.

### 8. Daggerfall action system

Build a system for Daggerfall's action records, extending the swinging door pattern. Moving dungeon objects should work faithfully to Daggerfall, and the implementing agent is empowered to make the engineering decisions. This also unblocks Scourg Barrow.

- **Doom handles the physical part:** moving, rotating, teleporting, triggers, and chains.
- **Daggerfall owns the rules:** spells, riddles and text, trap damage, and locks. These wait for the engine sync and should not be faked in Doom.
- Do not cull "sealed" rooms as sealed rooms as these may be the reason.

### 9. Swimmable water

Use each dungeon block's Daggerfall water level to create swimmable water, likely with UZDoom's swimmable 3D floors. Flooded rooms must not affect rooms above or below them.
