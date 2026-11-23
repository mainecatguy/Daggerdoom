# Backlog

Work that needs owner input or depends on unfinished work. **Automated loops never take work from this index or `work/backlog/`.**

This is a one-line-per-item index. Open an item's file only when you need its details. Each file starts with what the item is waiting on. To add an item, create `work/backlog/<slug>.md` and add one line here. When an item moves to `work/todo.md` or is finished, move its details there or to `CHANGELOG.md` and `work/notes/`, then delete its file and line.

## Engine bridge

- [Turn off Daggerfall's 3D simulation](backlog/turn-off-daggerfalls-3d-simulation.md): Run DFU logic and 2D UI without its 3D world.

## MVP

The MVP target is that the player can run around the world, kill enemies, enter and exit towns, use the fast travel menu, and do other basic things. Position sync, the fast travel menu, and synchronized saving and loading are in `work/todo.md`. Everything in this section is required before MVP is complete. Items come after the others and depend on the inventory menu.

- [Daggerfall items in the world](backlog/daggerfall-items-in-the-world.md): Show all DF items in Doom, with Interact pickup.
- [Rework Doom autopickup](backlog/rework-doom-autopickup.md): On DF maps, only health and ammo pick up by touch.

## Overworld and towns

- [Distant terrain LOD](backlog/distant-terrain-lod.md): Show distant mountains beyond the loaded window.
- [Distant town view](backlog/distant-town-view.md): Show real towns from outside their playable area.
- [Town gates follow day and night](backlog/town-gates-follow-day-and-night.md): Gates follow Daggerfall's time cycle.
- [Permanent location state owned by Daggerfall](backlog/permanent-location-state-owned-by-daggerfall.md): Move location history from Doom saves to DF saves.
- [Identify and sort problem location groups](backlog/identify-and-sort-problem-location-groups.md): List and rank locations that do not fit one map.
- [Restore autosaves on location changes](backlog/restore-autosaves-on-location-changes.md): Bring back autosaves on stitched map changes.
- [Revisit performance of generating fresh cities](backlog/revisit-performance-of-generating-fresh-cities.md): Profile and reduce 5 to 7 second conversions.
- [Overworld monsters outside the loaded window](backlog/overworld-monsters-outside-the-loaded-window.md): Decide their fate off-window. On hold.

## Dungeons

- [Audit and fix dungeons](backlog/audit-and-fix-dungeons.md): Convert main quest and sample dungeons, fix breakage.
- [Support main quest dungeon quest steps](backlog/support-main-quest-dungeon-quest-steps.md): Reverse engineer and support their quest steps.
- [Investigate sealed 5-block graveyards](backlog/investigate-sealed-5-block-graveyards.md): Check two dungeons with disconnected blocks.
- [Climbing, levitation, and steep surfaces](backlog/climbing-levitation-and-steep-surfaces.md): Match DF slope limits, climbing, and levitation.

## Inventory

- [Doom weapon equipping and hotkeys](backlog/doom-weapon-equipping-and-hotkeys.md): Assign Doom weapons, items, and spells to hotkeys.
- [Inventory translation](backlog/inventory-translation.md): Translate DF items and DRLA gear both ways.
- [Grid inventory (shelved by owner, 2026-11-22)](backlog/grid-inventory.md): Diablo-style inventory grid. Shelved.

## Collision and combat polish

- [Remaining collision mismatches](backlog/remaining-collision-mismatches.md): Reduce false walls and openings in parity tests.
- [Weapon collision with the Daggerfall mesh](backlog/weapon-collision-with-the-daggerfall-mesh.md): Make shots hit the visible mesh.
- [Monsters at doors](backlog/monsters-at-doors.md): Decide door opening and oversized monster behavior.
- [Locked doors with Daggerfall's requirements](backlog/locked-doors-with-daggerfalls-requirements.md): Use DF's real lock data and rules in Doom.
- [Doors that swing in both directions](backlog/doors-that-swing-in-both-directions.md): Experiment with two-way swinging doors.

## Before initial release

- [Full Daggerfall new game flow](backlog/full-daggerfall-new-game-flow.md): New Game runs DF character creation and cutscene.
- [Load Daggerfall saves with no Doom data](backlog/load-daggerfall-saves-with-no-doom-data.md): Create default Doom data for plain DF saves.
- [Check whether quests depend on moving NPCs](backlog/check-whether-quests-depend-on-moving-npcs.md): Find scripts that need Doom to move NPCs.
- [Sync wandering NPCs](backlog/sync-wandering-npcs.md): Decide what wandering NPC state must sync.
- [Mook packs](backlog/mook-packs.md): Replace single spawns with seeded Doom packs.
- [Improve the random enemy roster](backlog/improve-the-random-enemy-roster.md): Weight or tier the uniform random roster.
- [Quest targets in mook packs](backlog/quest-targets-in-mook-packs.md): Decide how quest targets map onto packs.
- [Oblivion Portals](backlog/oblivion-portals.md): Portals that lead to Doom and custom WAD maps.
- [Daggerfall completeness review](backlog/daggerfall-completeness-review.md): Audit every DF data type for missing systems.

## After initial release

- [Revisit damage and resistances](backlog/revisit-damage-and-resistances.md): Rework how DRLA and DF damage rules combine.
- [Status effects on mooks](backlog/status-effects-on-mooks.md): Extend DF status effects to Doom mooks.
- [Should open doors block monster sight?](backlog/should-open-doors-block-monster-sight.md): Decide whether to match DF's door sight rule.
- [Support texture packs and lighting mods](backlog/support-texture-packs-and-lighting-mods.md): Carry DF visual mods into the converter.

## Late development polish

- [Sort out keybinds](backlog/sort-out-keybinds.md): Resolve Doom, DF, and Doomerfall key conflicts.
