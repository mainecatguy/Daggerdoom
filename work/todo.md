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

### 2. Update the parity test for swinging doors

The parity tool's closed-door stages were written for the old door slabs and no longer mean anything. Make them meaningful for swinging door objects.

### 3. Daggerfall action system

Build a system for Daggerfall's action records, extending the swinging door pattern. Moving dungeon objects should work faithfully to Daggerfall, and the implementing agent is empowered to make the engineering decisions. This should remove the physical blockers in Scourg Barrow. Parts may stay gated by Daggerfall rules or quests, which is an acceptable result.

- **Doom handles the physical part:** moving, rotating, teleporting, triggers, and chains.
- **Daggerfall owns the rules:** spells, riddles and text, trap damage, and locks. These wait for the engine sync and should not be faked in Doom.
- Do not cull "sealed" rooms as sealed rooms as these may be the reason.

### 4. Swimmable water

Use each dungeon block's Daggerfall water level to create swimmable water, likely with UZDoom's swimmable 3D floors. Flooded rooms must not affect rooms above or below them.

### 5. Build and check main quest dungeon traversal

Build the existing non-random main quest dungeons and about 5 random dungeons with the current converter, load each in UZDoom, and check that the player can physically traverse them. Report what works, what breaks, and which areas cannot be reached. This pass does not fix or test quests. Some dungeons depend on systems Doom does not have yet, such as talking to a character to open a door. Classify each as traversable, gated by a named missing system, broken, or unknown. Do not build or fake those systems. Success means an honest classification, not that every dungeon can be completed. Candidates named in outside feedback include Direnni Tower, Scourg Barrow, Castle Wayrest, Orsinium, and Mantellan Crux. Confirm the real list from the game's data. Do Mantellan Crux last, as the final boss, because it may be extremely hard.

Tell the owner wherever a dungeon requires climbing or levitation to progress, with the dungeon and location. Fixing what this finds is separate work.

## Held for owner review

Approved work that waits until the owner has reviewed the bridge core. Automated loops do not take these yet.

### Show Daggerfall's fast travel menu in Doom

Pressing the Fast Travel key pauses Doom and shows Daggerfall's real travel map inside the Doom window, with input routed to it. Closing it resumes Doom. Do not recreate the menu in Doom. Build this so other Daggerfall menus, such as inventory, can use the same path. Daggerfall should stop drawing its 3D world while this runs, but keep its entities and physics running, because how NPCs will work is not designed yet. Arriving at the chosen destination is a separate backlog item.

### Synchronized saving

Saving pauses both games with a handshake, so messages in flight are not lost, then saves both. Each writes temporary files, and the real save is replaced only after both succeed. Start with player HP and position. On Daggerfall maps, Doom's save command goes through this path. Regular WADs keep normal Doom saves.

### Synchronized loading

Loading restores both games from the same save, and both confirm they are ready before resuming together. Doom's load command and death restart on Daggerfall maps go through this path. Regular WADs keep normal Doom loading.
