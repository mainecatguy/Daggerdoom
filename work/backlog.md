# Backlog

Work that needs owner input or depends on unfinished work. **Automated loops never take work from this file.** When an item is unblocked and the owner approves it, it moves to `work/todo.md`. Finished work moves to `CHANGELOG.md`, with details in `work/notes/`.

## Engine bridge

### Turn off Daggerfall's 3D simulation

**Waiting on:** owner design for how NPCs work.

Daggerfall Unity should eventually run with its 3D world rendering and entity physics turned off while its simulation loop and 2D UI keep working. This is one of the four core technical hurdles. Disabling entities and physics may break NPC behavior, so it should not start until the NPC design is settled. Normal Daggerfall Unity launches must behave as they do today.

## MVP

The MVP target is that the player can run around the world, kill enemies, enter and exit towns, use the fast travel menu, and do other basic things. Position sync, the fast travel menu, and synchronized saving and loading are in `work/todo.md`. Everything in this section is required before MVP is complete. Items come after the others and depend on the inventory menu.

### Fast travel arrival

**Waiting on:** position sync and the fast travel menu in `work/todo.md`.

Daggerfall owns travel cost, time, and destination. Doom reports the player's world position to Daggerfall, then loads the chosen town or overworld position and places the player where Daggerfall would.

### Building and dungeon entry and exit

**Waiting on:** position sync.

The player can go through a door into a building interior and back out, and can enter and exit dungeons from the overworld or a town, arriving where Daggerfall would place them.

### One random enemy per placement

**Waiting on:** owner approval to move to `work/todo.md`.

Owner decision (2026-11-22): for MVP, each Daggerfall enemy placement generates one random Doom enemy. Mook packs come later.

### Synchronize player HP

**Waiting on:** the bridge core.

MVP scope (owner, 2026-11-22): synchronize HP between the games. This does not commit to the full damage system. Damage scale, armor, and resistances come later.

- Daggerfall owns the player's HP value and death.
- Doom sends each hit or heal to Daggerfall as a numbered event through the queue. Daggerfall applies them in order. Damage that starts in Daggerfall is applied there directly.
- Damage values pass through unchanged for now.
- Daggerfall publishes current HP, max HP, and the last event number it applied in its half of the shared state.
- Doom shows that HP on the player and does not kill the player until Daggerfall reports death.

### Open the inventory menu from Doom

**Waiting on:** the fast travel menu, which proves the path for showing Daggerfall menus in Doom.

A Doom keybind opens Daggerfall's real inventory inside the Doom window, with input routed to it, and closing it resumes Doom. The exact key is not important, but it must be a bindable control. The "Open Inventory" action already exists in Doomerfall Controls.

### Daggerfall items in the world

**Waiting on:** the bridge core, position sync, and the inventory menu.

Owner design (2026-11-22): Doom must be tolerant of Daggerfall items. Doom is the dominant client, so it must show them and let the player interact with them.

- All Daggerfall items can drop in the world or appear in the world, including static placed items.
- Doom shows these items in the game, whether or not they have a Doom equivalent.
- The player presses the Interact keybind to pick an item up into their Daggerfall inventory. Interact is a bindable action in the existing Doomerfall Controls definitions, never a hardcoded key.
- Picked-up items stay gone, following the permanent location state rules.

- For loot piles and containers holding several items, Interact opens Daggerfall's real loot window through the Doom menu path.

### Rework Doom autopickup

**Waiting on:** Daggerfall items in the world.

Required before MVP. Owner decision (2026-11-22): on Daggerfall maps, only health and ammo pick up by touch. Everything else uses the Interact keybind, because items now have weight. Regular WADs and mods keep normal Doom pickup.

## Overworld and towns

### Distant terrain LOD

**Waiting on:** the town stitching task.

Show distant terrain, such as mountains, beyond the loaded treadmill window. The owner's idea is one LOD object in a Source-style 3D skybox. Both the overworld treadmill and dedicated town maps load the same LOD based on the player's true world XY position, so the horizon stays consistent between them.

Check whether UZDoom's sky viewpoints or the existing static-mesh pass is the better way to draw it. Key risks are the seam and popping where the LOD meets real terrain, and keeping parallax correct as the treadmill shifts. A rough seam is acceptable at first. The long-term aim is to hide it by making Doom terrain match Daggerfall's precisely, since terrain is a simple height field with no rooms.

### Distant town view

**Waiting on:** the town stitching task and distant terrain LOD.

Show a real town from outside its playable area and capture screenshots for the owner to judge.

### Town gates follow day and night

**Waiting on:** the engine sync, since Daggerfall owns time.

Owner decision (2026-11-22): town gates should follow Daggerfall's day and night cycle.

### Permanent location state owned by Daggerfall

**Waiting on:** runtime town loading being merged, and synchronized saving and loading.

The game never forgets what the player did in a location, apart from any Daggerfall dungeon resets the owner chooses to keep. Doom's world table holds this history for now and stores it in Doom saves. Move its authority to Daggerfall by extending Daggerfall's save data, since Daggerfall does not track Doom monsters or packs on its own.

Monster packs come from fixed seeds, so store only what changed, such as deaths, drops, pickups, and unlocked doors. Keep this in a stable format separate from Doom's save snapshots, so progress survives engine or mod updates.

### Identify and sort problem location groups

**Waiting on:** runtime town loading being merged.

Find locations that do not fit the normal one-map scheme and sort them by how much they matter. Known cases are groups too wide for one map, such as Wayrest and Merwark Hollow, which split into one map per location and do not show each other's buildings from inside. Decide fixes after seeing the full list.

### Restore autosaves on location changes

**Waiting on:** runtime town loading being merged.

Owner decision (2026-11-22): keep normal autosaving. The runtime work skipped autosaves on stitched map changes because each added a 220 to 240 ms hitch, and the owner considers that acceptable during a load.

### Revisit performance of generating fresh cities

**Waiting on:** owner request.

Fresh locations take about 5 to 7 seconds to convert in the background. Profile where that time goes, which is likely CPU rather than disk, and reduce it if worthwhile.

### Overworld monsters outside the loaded window

**Waiting on:** owner decision, on hold. See `work/questions.md`.

## Dungeons

### Audit and fix dungeons

**Waiting on:** the owner being satisfied that all travel methods are implemented correctly. Do this last, or earlier only if we are low on other tasks.

Run the converter on all non-random mainquest dungeons as well as some random dungeons (say 5) and report what breaks, map size, load time, frame rate, and how often each feature appears, such as teleporters, water, lifts, climbing shafts, and special markers. Use the results to recommend priorities for the dungeon work.

The audit includes fixing what it finds, and must be broken down into steps before it starts.

Outside feedback raised these possible problems. Treat them as unverified until the audit or real data confirms them:

- Large multi-block dungeons may hit practical size or performance limits.
- Stacked floors may cause sliver sectors, sound bleeding through rock, automap clutter, or lighting and fog bleeding between floors.
- Tightly stacked sloped 3D floors may snag actors or show seams.
- Dungeon textures may need runtime swaps by region and dungeon type, and some are animated.
- Editor marker flats may carry teleporter destinations, quest anchors, fixed spawns, and ambient sounds.
- Some original blocks have misaligned doorways, small lips that snag movement, or broken action chains.

### Support main quest dungeon quest steps

**Waiting on:** the main quest dungeon traversal check, and many more systems being ported into the game.

Reverse engineer how the quest steps in the main quest dungeons work, then support those steps.

### Climbing, levitation, and steep surfaces

**Waiting on:** owner design input after the research step.

Climbing and levitation will eventually be in the game. Doom currently lets the player walk up very steep hills and surfaces without limit. The player should be blocked, slide, or need Daggerfall's climbing wherever Daggerfall would require it.

When this starts, research Daggerfall Unity's real behavior first: which surfaces the player can walk up, when they slide or get blocked, and when climbing starts, continues, or fails, including skill checks. Start with `FrictionMotor.cs`, `ClimbingMotor.cs`, and the player's slope limit. Then design the Doom behavior with the owner.

## Inventory

### Doom weapon equipping and hotkeys

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

### Inventory translation

**Waiting on:** the two-game launcher and message channel, and owner-approved translation rules.

Translate between Daggerfall items and DRLA weapons, ammo, armor, and mods in both directions. Daggerfall stays the authority for inventory and loot rolls. Its drops become DRLA gear based on item tier and type, and Doom gear must be represented in Daggerfall's inventory, saves, shops, and containers. See `gamedesign.md` and `designgoals.md`.

### Grid inventory (shelved by owner, 2026-11-22)

**Waiting on:** the owner deciding to revisit it. The existing inventory stays for now.

A Diablo-style grid replacing Daggerfall's inventory, chest, and trade item lists, matching Daggerfall's UI. Ideas so far:

- Small but not tiny cells, around 8 Daggerfall UI units, with items at normal sprite size.
- An item occupies every cell its non-transparent sprite pixels intersect. No rotation, a stack takes the space of one item, and gold stays outside the grid.
- Keep Daggerfall's item collections underneath, with grid positions as a layer on top, and never lose items.
- Start with unlimited scrolling, with weight as the only limit. A later limit could be around 4 pages for the player. Scripts and quests could still force items in past it, and containers stay unlimited.
- Reference only, do not copy code: https://github.com/SinlessDevil/TetrisInventorySystem

## Collision and combat polish

### Remaining collision mismatches

**Waiting on:** the parity test update, and an owner-approved target for how close is good enough.

Angled collision was a large improvement, but on Privateer's Hold the parity test still reports 803 standing false walls and 1,282 false openings. Some straight walls have small bends where a vertex stayed on the grid.

### Weapon collision with the Daggerfall mesh

**Waiting on:** remaining collision mismatches, since better sector fit may reduce this work.

Bullets, rails, and projectiles should collide with the visible mesh, through engine hooks so weapon mods need no changes. Test hitscan, then projectiles, and measure the cost with large numbers of shots. Then check monster sight, splash damage, bouncing, and impact marks. Currently 142 of 200 test bullets land on the visible surface.

### Monsters at doors

**Waiting on:** owner decision.

Monsters currently cannot open doors, and most stock monsters are wider than a doorway. Whether monsters open doors, and how oversized monsters behave, is an owner decision.

### Locked doors with Daggerfall's requirements

**Waiting on:** the engine-sync contract.

Doors that were locked in Daggerfall must have the same requirements in Doom.

- Read each door's real lock data and requirements from Daggerfall. Do not infer them from appearance or assign them by hand.
- Daggerfall stays the authority for lock state, skill checks, keys, and whether a door has been unlocked. UZDoom asks it before opening the door.
- Monsters and scripted movement must not bypass a locked door unless Daggerfall's rules allow it.
- Verify with real locked, unlocked, lockpick, and key cases, including saving and reloading after a door is unlocked.
- Any other way past a lock, such as bashing or magic, follows Daggerfall's rules unless the owner decides otherwise.

### Doors that swing in both directions

**Waiting on:** owner request. The owner will judge the result by play-testing.

Generated actor-based swinging doors currently swing one way. Run an experiment on having them open in both directions.

## Before initial release

### Check whether quests depend on moving NPCs

**Waiting on:** the engine sync. Must be done before initial release.

Check whether Daggerfall has quest or other scripts that move NPCs and depend on that to work. If so, Daggerfall must be able to tell Doom where an NPC should go, with Doom carrying out the movement. If not, no work is needed.

### Sync wandering NPCs

**Waiting on:** owner design.

Decide how randomly wandering NPCs work across both games. The question is whether their positions need syncing at all, or whether it is enough to sync if they are alive or dead.

### Mook packs

**Waiting on:** MVP, and the owner defining the point-buy system.

Post-MVP, but before initial release. Replace the one random enemy per placement with the mook pack design in `gamedesign.md`: encounters generate packs of Doom enemies from fixed seeds, and only deaths are tracked. Research found that `RandomSpawner` uses a shared random number generator, so packs must be expanded into concrete monster classes from the seed before spawning.

### Quest targets in mook packs

**Waiting on:** owner design.

Decide how a Daggerfall quest target maps onto a pack of mooks. The current rule is that the entity's death triggers when most of its mooks are dead. Still open: whether one monster is the "real" target, how the player can tell, and where quest items drop.

### Daggerfall completeness review

**Waiting on:** owner request.

Go through every Daggerfall file type and its entries, records, and scripts. For each, check whether we have a system documented as completed, and report back everything that does not.

## After initial release

### Revisit damage and resistances

**Waiting on:** initial release.

The initial release design in `gamedesign.md` is not final. Revisit how DRLA resistances, Daggerfall's damage rules, and armor work together.

### Status effects on mooks

**Waiting on:** initial release and owner design.

For initial release, status effects apply only to the player. They need to reach Doom mooks eventually, or they will do almost nothing in slaughter-sized fights. Daggerfall does not track individual mooks, so the likely approach is that Daggerfall defines an effect, such as poison's damage and duration, and Doom runs it on each mook.

The engine bridge and status effect design must leave room for this from the start, so adding it later does not require reworking them.

## Late development polish

### Sort out keybinds

**Waiting on:** the late development and polish phase.

Resolve keybind conflicts across Doom, Daggerfall, and Doomerfall. For example, Doom binds Ctrl to fire and Alt to strafe by default, which conflicts with the planned Ctrl+number and Alt+number weapon hotkeys.
