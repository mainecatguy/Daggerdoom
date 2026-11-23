# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 90%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

### 1. Bridge core

Build the transport between the games: a small C++ bridge DLL used by both engines, two single-producer single-consumer queues, a fixed shared struct with Daggerfall-written and Doom-written halves in triple buffers, and FlatBuffers messages. The launcher creates the session. Prove a real message travels both ways between the running games. The field-level contract comes from `work/notes/bridge-contract.md`. UZDoom loads the bridge only when the launcher starts it, so regular WADs are unaffected.

### 2. Daggerfall with 3D off

Daggerfall Unity can run with its 3D world rendering and entity physics turned off while its simulation loop and 2D UI keep working. This is one of the four core technical hurdles. Normal Daggerfall Unity launches must behave as they do today.

### 3. Audit every dungeon (do LAST)

Run the converter on all non-random mainquest dungeons as well as some random dungeons (say 5) and report what breaks, map size, load time, frame rate, and how often each feature appears, such as teleporters, water, lifts, climbing shafts, and special markers. Use the results to recommend priorities for the dungeon work.

Outside feedback raised these possible problems. Treat them as unverified until the audit or real data confirms them:

- Large multi-block dungeons may hit practical size or performance limits.
- Stacked floors may cause sliver sectors, sound bleeding through rock, automap clutter, or lighting and fog bleeding between floors.
- Tightly stacked sloped 3D floors may snag actors or show seams.
- Dungeon textures may need runtime swaps by region and dungeon type, and some are animated.
- Editor marker flats may carry teleporter destinations, quest anchors, fixed spawns, and ambient sounds.
- Some original blocks have misaligned doorways, small lips that snag movement, or broken action chains.

### 4. Update the parity test for swinging doors

The parity tool's closed-door stages were written for the old door slabs and no longer mean anything. Make them meaningful for swinging door objects.

### 5. Daggerfall action system

Build a system for Daggerfall's action records, extending the swinging door pattern. Moving dungeon objects should work faithfully to Daggerfall, and the implementing agent is empowered to make the engineering decisions. This also unblocks Scourg Barrow.

- **Doom handles the physical part:** moving, rotating, teleporting, triggers, and chains.
- **Daggerfall owns the rules:** spells, riddles and text, trap damage, and locks. These wait for the engine sync and should not be faked in Doom.
- Do not cull "sealed" rooms as sealed rooms as these may be the reason.

### 6. Swimmable water

Use each dungeon block's Daggerfall water level to create swimmable water, likely with UZDoom's swimmable 3D floors. Flooded rooms must not affect rooms above or below them.

## Held for owner review

Approved work that waits until the owner has reviewed the bridge core. Automated loops do not take these yet.

### Show Daggerfall's fast travel menu in Doom

Pressing the Fast Travel key pauses Doom and shows Daggerfall's real travel map inside the Doom window, with input routed to it. Closing it resumes Doom. Do not recreate the menu in Doom. Build this so other Daggerfall menus, such as inventory, can use the same path. Daggerfall's 3D world should not render while this runs. Arriving at the chosen destination is a separate backlog item.

### Synchronized saving

Saving pauses both games with a handshake, so messages in flight are not lost, then saves both. Each writes temporary files, and the real save is replaced only after both succeed. Start with player HP and position. On Daggerfall maps, Doom's save command goes through this path. Regular WADs keep normal Doom saves.

### Synchronized loading

Loading restores both games from the same save, and both confirm they are ready before resuming together. Doom's load command and death restart on Daggerfall maps go through this path. Regular WADs keep normal Doom loading.
