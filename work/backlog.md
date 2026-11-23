# Backlog

Work that needs owner input or depends on unfinished work. **Automated loops never take work from this file.** When an item is unblocked and the owner approves it, it moves to `work/todo.md`. Finished work moves to `CHANGELOG.md`, with details in `work/notes/`.

## Overworld and towns

### Distant terrain LOD

**Waiting on:** the town stitching task.

Show distant terrain, such as mountains, beyond the loaded treadmill window. The owner's idea is one LOD object in a Source-style 3D skybox. Both the overworld treadmill and dedicated town maps load the same LOD based on the player's true world XY position, so the horizon stays consistent between them.

Check whether UZDoom's sky viewpoints or the existing static-mesh pass is the better way to draw it. Key risks are the seam and popping where the LOD meets real terrain, and keeping parallax correct as the treadmill shifts. A rough seam is acceptable at first. The long-term aim is to hide it by making Doom terrain match Daggerfall's precisely, since terrain is a simple height field with no rooms.

### Distant town view

**Waiting on:** the town stitching task and distant terrain LOD.

Show a real town from outside its playable area and capture screenshots for the owner to judge.

### Overworld monsters outside the loaded window

**Waiting on:** owner decision, on hold. See `work/questions.md`.

## Dungeons

### Check the main quest dungeons

**Waiting on:** the dungeon audit, action system, and swimmable water.

Check that Daggerfall's main quest dungeons convert and can be completed. Candidates named in outside feedback include Direnni Tower, Scourg Barrow, Castle Wayrest, Orsinium, and Mantellan Crux. Confirm the real list from the game's data.

Tell the owner wherever a dungeon requires climbing or levitation to progress, with the dungeon and location.

### Climbing, levitation, and steep surfaces

**Waiting on:** owner design input after the research step.

Climbing and levitation will eventually be in the game. Doom currently lets the player walk up very steep hills and surfaces without limit. The player should be blocked, slide, or need Daggerfall's climbing wherever Daggerfall would require it.

When this starts, research Daggerfall Unity's real behavior first: which surfaces the player can walk up, when they slide or get blocked, and when climbing starts, continues, or fails, including skill checks. Start with `FrictionMotor.cs`, `ClimbingMotor.cs`, and the player's slope limit. Then design the Doom behavior with the owner.

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
