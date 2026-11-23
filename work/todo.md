# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends on nothing unfinished. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 60%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

### 1. Audit every dungeon

Run the converter on all dungeons and report what breaks, map size, load time, frame rate, and how often each feature appears, such as teleporters, water, lifts, climbing shafts, and special markers. Use the results to recommend priorities for the dungeon work.

Outside feedback raised these possible problems. Treat them as unverified until the audit or real data confirms them:

- Large multi-block dungeons may hit practical size or performance limits.
- Stacked floors may cause sliver sectors, sound bleeding through rock, automap clutter, or lighting and fog bleeding between floors.
- Tightly stacked sloped 3D floors may snag actors or show seams.
- Dungeon textures may need runtime swaps by region and dungeon type, and some are animated.
- Editor marker flats may carry teleporter destinations, quest anchors, fixed spawns, and ambient sounds.
- Some original blocks have misaligned doorways, small lips that snag movement, or broken action chains.

### 2. Update the parity test for swinging doors

The parity tool's closed-door stages were written for the old door slabs and no longer mean anything. Make them meaningful for swinging door objects.

### 3. Daggerfall action system

Build a system for Daggerfall's action records, extending the swinging door pattern. Moving dungeon objects should work faithfully to Daggerfall, and the implementing agent is empowered to make the engineering decisions. This also unblocks Scourg Barrow.

- **Doom handles the physical part:** moving, rotating, teleporting, triggers, and chains.
- **Daggerfall owns the rules:** spells, riddles and text, trap damage, and locks. These wait for the engine sync and should not be faked in Doom.
- Do not cull "sealed" rooms as sealed rooms as these may be the reason.

### 4. Swimmable water

Use each dungeon block's Daggerfall water level to create swimmable water, likely with UZDoom's swimmable 3D floors. Flooded rooms must not affect rooms above or below them.
