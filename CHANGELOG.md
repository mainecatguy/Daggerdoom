# Changelog

What is done on the project, newest first. Agents do not need to read this unless a task asks them to. Details live in `work/notes/`, and planned work lives in `work/backlog.md`.

## Current state

- **Playable demo:** Privateer's Hold with Daggerfall visuals, Doom movement and combat, 42 Doom monsters, and swinging doors. Run `D:\dev\DoomDaggerfall-loop\review\door-demo\play.bat`.
- **Branches:** the work below through swinging doors is on `integration` at `c1c103c`. `main` has not received the 2026-11-22 parity, scale, launch, or door work yet.
- **Roughest spot:** movement collision is built on a grid, so angled walls and ceilings are jagged.

## 2026-11-22

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

### Collision parity test (`5ad3f37` to `131a13e`)
- Added a two-way test comparing where Daggerfall and Doom each let the player move.
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
- Tried Scourg Barrow as a stress test. Its route past the entrance crypt depends on moving dungeon objects, which still need an owner decision.

### World conversion research (`c8f3d4a`)
- Researched how to convert Daggerfall's world and recorded the open design questions.
