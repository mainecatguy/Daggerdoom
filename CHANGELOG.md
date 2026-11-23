# Changelog

What is done on the project, newest first. Agents do not need to read this unless a task asks them to. Details live in `work/notes/`, and planned work lives in `work/backlog.md`.

## Current state

- **Playable demo:** Privateer's Hold with Daggerfall visuals, Doom movement and combat, 42 Doom monsters, swinging doors, and angled collision. Run `D:\dev\DoomDaggerfall-loop\review\angled-demo\play.bat`.
- **Other demos:** City of Daggerfall at `D:\dev\DoomDaggerfall-loop\review\city-texture-fix\play.bat`, overworld at `D:\dev\DoomDaggerfall-loop\review\overworld-demo\play.bat`, and DRLAX on E1M1 at `D:\dev\DoomDaggerfall\play_drlax.bat`.
- **Launcher:** starts Daggerfall Unity and UZDoom as one package. Run `D:\dev\DoomDaggerfall-loop\review\launcher\play.bat`.
- **Branches:** `integration` is at `26dc6b8`, with the city, overworld, town stitch, runtime towns, launcher, and Doomerfall mod.
- **Roughest spots:** some walls still bend where they stayed tied to the grid, and false walls and openings remain.

## 2026-11-22

### Launcher (`7e80862`)
- A native launcher runs both games in one Job Object and closes both when either exits or is killed. It passes an ordered mod list to UZDoom. There is no message channel yet.
- The owner tested it and confirmed it works. Doom had no sound because the launcher build lacked `sndfile.dll` and `soft_oal.dll`. They were copied in, and OpenAL now initializes.
- Known gaps: hung games are not detected, a UZDoom fatal dialog holds both games open, and shutdown does not coordinate saves.

### Doomerfall mod (`b564fc0`)
- Our own mod adds unbound "Open Fast Travel" and "Open Inventory" controls that log when fired. It works with and without the DRLA set. The owner tested it.

### Project renamed to Doomerfall (`17ea32a`)
- Engine code markers now use the new name. The local folder keeps its old name.

### Town stitch and runtime towns (`e2181f0`)
- The overworld stitches to generated towns, and Daggerfall locations convert and load during play with a disk cache.

### Work tracking
- Added `work/todo.md` for owner-approved work that is ready to run automatically. `work/backlog.md` now holds only work that needs owner input or depends on unfinished work.

### City cart texture fix (`fb172ee`, not merged)
- Carts, hedges, and some furniture no longer pick up the wrong textures from an overly broad climate swap. Not yet checked in game.

### Overworld treadmill (`88674d4`, not merged)
- Real Daggerfall terrain streams around the player at 75% scale in any direction, with a saved world table for touched monsters, corpses, and drops.
- Owner decisions: dropping a frame or two during shifts with huge packs is fine, and frozen monsters return idle for now.
- The owner tried the demo and it functioned.

### City of Daggerfall (`d9a7313`, not merged)
- The full city and nearby terrain run as a Doom map using Daggerfall's real models, ground tiles, billboards, and sky.
- The owner play-tested it and found it went well, apart from the cart texture bug.

### DRLAX on stock Doom
- DRLA, DRLA Monsters, and DRLAX run on E1M1 with no engine changes. Added the missing OGG sound decoder to the local build.

### Angled collision (`e997464`)
- Generated sectors now follow Daggerfall's real wall edges and sloped planes where they fit, and fall back to the grid elsewhere.
- On Privateer's Hold, test bullets landing on the visible surface rose from 106 to 142 of 200, and sectors fell from 4,975 to 3,036.
- Some straight walls have small bends, and false walls and openings remain.
- The owner play-tested it and called it a huge improvement.

### Converter scale default (`77c48c5`)
- The dungeon converter and comparison tools now default to 75% world scale.

### Swinging doors (`c1c103c`)
- Doors are now separate objects that show the real Daggerfall model and swing on a hinge.
- Rows of small invisible actors give each door collision that follows the model, closed and open.
- 46 of 58 Privateer's Hold doors lead through. The other 12 are dead ends in the Daggerfall data.
- The owner play-tested the doors and confirmed they work.

### Test launches (`32006bd`)
- UZDoom launched with `-noactivate` stays off-screen, does not take focus, and exits on fatal errors.

### World scale and player size (`f5012b2`)
- Daggerfall maps use 75% world scale.
- The player keeps stock Doom height, eye height, step, speed, and weapons, with a 21-wide collision box on Daggerfall maps only.
- The earlier Daggerfall-size player remains available as an opt-in converter setting.
- The owner play-tested this and confirmed the proportions are fixed.

### Player size and collision parity goal, completed (`5ad3f37` to `131a13e`)
- Measured the Daggerfall and Doom player sizes and added an opt-in Daggerfall-size player layer.
- Added a two-way test comparing where Daggerfall and Doom each let the player move, plus a simple bullet check.
- Reduced some false openings and limited ceiling relief. Large mismatches remain.

### Daggerfall mesh layer (`56c6872`, `15b264d`)
- Generated maps can draw Daggerfall's real meshes and textures over invisible Doom collision.
- F1 toggles between the Daggerfall view and the Doom collision view. Regular Doom maps are unaffected.

### Terrain treadmill test (`dbc58d0`)
- Rewriting real sloped terrain while running fit within one 60 FPS frame for all 32 shifts on one straight route with few actors.
- Slaughter-sized packs, saves, decals, sounds, and north-south shifts are untested.

### Dungeon connectivity (`15e0552`)
- Fixed false walls found by the comparison test. Privateer's Hold matched at 15 of 16 viewpoints at the time.

## 2026-11-21

### Dungeon converter (`510ddb5`)
- Built the converter from real Daggerfall dungeon data, with an automated map check.
- Tried Scourg Barrow as a stress test. Its route past the entrance crypt depends on moving dungeon objects, which are not built yet.

### World conversion research (`c8f3d4a`)
- Researched how to convert Daggerfall's world and recorded the open design questions.
