# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

### 1. Startup and save flow research

Research only. Today Doom drops the player straight into a game while Daggerfall sits at its opening menu. Propose how startup, new game, loading, saving, and death should work with Doom as the controlling window and Daggerfall as the save controller, then break it into tasks. The owner's starting idea is that the player chooses Start, which goes through Daggerfall's start workflows, or Load. A save is only offered if both games have a matching save. Better ideas are welcome.

### 2. Position sync

Keep Daggerfall and Doom loaded into the same area, through a deterministic coordinate transform at the 75% world scale. This is one of the four core technical hurdles.

- Perfect sync is not needed. Daggerfall applying the player's position about once per second should be enough. Area changes should not wait for that update.
- Daggerfall must keep the same world objects in memory as Doom, so leave its terrain and location streaming running and measure the cost.
- Daggerfall's hidden player must not take fall damage, get stuck, or trigger anything from being moved this way.
- Daggerfall's 3D drawing is controlled by a flag the launcher passes, such as `--nodraw`. Without the flag Daggerfall draws normally, because tests compare screenshots from both games to check areas and LODs. The simulation safeguards below apply either way.
- The hidden Daggerfall world must not change real game state on its own. How to do that is an engineering call. The suggested approach is to stop the hidden player's motor and physics, and turn off AI and attacks for Daggerfall's enemies while keeping those objects in memory. Leave peaceful NPCs alone until the NPC design is settled.

### 3. Show Daggerfall's fast travel menu in Doom

Pressing the Fast Travel key pauses Doom and shows Daggerfall's real travel map inside the Doom window, with input routed to it. Closing it resumes Doom. Do not recreate the menu in Doom. Build this so other Daggerfall menus, such as inventory, can use the same path. Daggerfall's 3D drawing follows the launcher's `--nodraw` flag from position sync. Keep its entities and physics running, apart from the position sync safeguards, because how NPCs will work is not designed yet. Arriving at the chosen destination is a separate backlog item.

### 4. Fix the tilted door export crash

Mesh export crashes on the main quest Daggerfall castle with `door 55004 is tilted; only yaw is supported` at `MeshExport.cs:94`. Fix it, and check whether other dungeons use tilted doors.

### 5. Build and check main quest dungeon traversal

Build the existing non-random main quest dungeons and about 5 random dungeons with the current converter, load each in UZDoom, and check that the player can physically traverse them. Report what works, what breaks, and which areas cannot be reached. This pass does not fix or test quests. Some dungeons depend on systems Doom does not have yet, such as talking to a character to open a door. Classify each as traversable, gated by a named missing system, broken, or unknown. Do not build or fake those systems. Success means an honest classification, not that every dungeon can be completed. Candidates named in outside feedback include Direnni Tower, Scourg Barrow, Castle Wayrest, Orsinium, and Mantellan Crux. Confirm the real list from the game's data. Do Mantellan Crux last, as the final boss, because it may be extremely hard.

Tell the owner wherever a dungeon requires climbing or levitation to progress, with the dungeon and location. Fixing what this finds is separate work.

### 6. Town building colliders

Building colliders in towns currently stretch up forever instead of ending at roof height. Generate them so the player can climb onto buildings:

- Find the building's sides and model those, ignoring any part of the roof that overhangs them.
- Go up from the sides and stop at the top of the building.
- If the roof is sloped, apply the correct slope to the Doom collider.

### 7. One random enemy per placement

For MVP, each Daggerfall enemy placement generates one random Doom enemy, the same one each time. Mook packs come later.

### 8. Dungeon texture second pass

The owner found bugged textures in the Scourg Barrow action demo. Do a second pass that finds and fixes textures that do not match Daggerfall.

### 9. Synchronize player HP

MVP scope (owner, 2026-11-22): synchronize HP between the games. This is not the permanent solution and does not commit to the full damage system. Damage scale, armor, and resistances are covered by "Revisit damage and resistances".

- Daggerfall owns the player's HP value and death.
- Doom sends each hit or heal to Daggerfall as a numbered event through the queue. Daggerfall applies them in order. Damage that starts in Daggerfall is applied there directly.
- Damage values pass through unchanged for now.
- Daggerfall publishes current HP, max HP, and the last event number it applied in its half of the shared state.
- Doom shows that HP on the player and does not kill the player until Daggerfall reports death.

### 10. Building and dungeon entry and exit, Doom side

Let the player go through a building's door into its real Daggerfall interior and back out, and enter and exit dungeons from the overworld or a town, arriving where Daggerfall would place them. World state must survive the trip. Telling Daggerfall about the move is a separate backlog item.

## Held for owner review

Approved work that waits until the owner has reviewed the startup and save flow research. Automated loops do not take these yet.

### Synchronized saving

Saving pauses both games with a handshake, so messages in flight are not lost, then saves both. Each writes temporary files, and the real save is replaced only after both succeed. Start with player HP and position. On Daggerfall maps, Doom's save command goes through this path. Regular WADs keep normal Doom saves.

### Synchronized loading

Loading restores both games from the same save, and both confirm they are ready before resuming together. Doom's load command and death restart on Daggerfall maps go through this path. Regular WADs keep normal Doom loading.
