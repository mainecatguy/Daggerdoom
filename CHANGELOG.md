# Changelog

What is done on the project, newest first. Agents do not need to read this unless a task asks them to. Details live in `work/notes/`, and planned work lives in `work/backlog.md`.

## Current state

- **Playable demo:** Privateer's Hold with Daggerfall visuals, Doom movement and combat, 42 Doom monsters, swinging doors, and angled collision. Run `D:\dev\DoomDaggerfall-loop\review\angled-demo\play.bat`.
- **Other demos:** City of Daggerfall at `D:\dev\DoomDaggerfall-loop\review\city-texture-fix\play.bat`, overworld at `D:\dev\DoomDaggerfall-loop\review\overworld-demo\play.bat`, and DRLAX on E1M1 at `D:\dev\DoomDaggerfall\play_drlax.bat`.
- **Launcher:** starts Daggerfall Unity and UZDoom as one package. Run `D:\dev\DoomDaggerfall-loop\review\launcher\play.bat`.
- **Branches:** `integration` is at `c73f16c`, with the wilderness height fix, the Daggerfall map command, door route fixes, both overnight lanes, the bridge and door fixes, dungeon flats, Daggerfall items, synchronized saving and loading, the death screen, fast travel arrival, connected door transitions, and the inventory menu.
- **Roughest spots:** some walls still bend where they stayed tied to the grid, and false walls and openings remain.

## 2026-11-23

### Merged to `integration` (`c73f16c`)
Notes only, with no code changes.

- **Code quality audit:** the core design is sound. The two fixes recommended soon are pointing regression scripts at the current engine and generating the C# bridge definitions from the header. See `work/notes/20261123-170733.md`.
- **Climbing research:** Daggerfall's climbing rules, a proposed Doom implementation, and four owner questions. Nothing was run in Daggerfall Unity itself. See `work/notes/20261123-171304.md`.

### Merged to `integration` (`cdfbc1a`)
This merge changes only the overworld tools and notes, so no engine rebuild was needed. Nobody has hand-played it.

- **Wilderness terrain height:** the player sank because overworld collision used raw heights while town meshes used Daggerfall's smoothed and flattened heights. The largest measured mismatch fell from 1,095.9 units to 0.146 across 131,696 mesh vertices. Existing demo folders keep their old `overworld.pk3` until they are reassembled.
- **Known gap:** small terrain bumps still differ from real Daggerfall, because the engine and converter use a stand-in for Unity's Perlin noise.

### Merged to `integration` (`70625fc`)
The engine code is identical to the map lane's verified build, and the merge only adds the separate door route tools. Scripted tests used both real games, and nobody has hand-played it.

- **Daggerfall map command:** Doom's map key opens Daggerfall's town map, interior or dungeon automap, or the travel map in the wilderness, which the owner confirmed on 2026-11-23. Regular Doom maps keep Doom's map. Fast travel closes Doom's map and leaves the collider view.
- **Known gap:** the dungeon automap opens but reveals no rooms in the Privateer's Hold test.

### Merged to `integration` (`72bd692`)
The converter builds from this merge. No engine files changed. Scripted door regressions passed, and nobody has hand-played the panels.

- **Door 15:** a false alarm from the test setup. It passes at the real player width of 10.5, and the door test now uses that width.
- **Secret door panels:** 3 non-door panels in Orsinium and Lysandus' Tomb now swing open through their real triggers. They guard small pockets, not a main route.
- **Trapdoors:** 4 main-quest trapdoors stay inert, because they open onto sealed pits that need climbing.

### Merged to `integration` (`079c841`)
UZDoom builds from this merge and passes its startup check. Its Daggerfall Unity code is identical to the engine lane's verified build. Nobody has hand-played these features.

- **Connected transitions:** Daggerfall follows the player through building and dungeon doors. Scripted runs passed 16 building types and Privateer's Hold, including saves and loads inside. Daggerfall does not track the player's position within a room yet.
- **Inventory menu:** the Open Inventory control shows Daggerfall's real inventory inside Doom. Scripted mouse input equipped a weapon. Real window mouse mapping, item use, and dropping are not proven.
- **Sprite scale:** `DaggerfallItem` now displays at the 75% world size with its images unchanged. Dungeon and town billboards were measured and already matched.
- **Survey:** the Daggerfall data and quest survey is in `work/notes/20261123-154554.md`.

### Merged to `integration` (`a954b0e`)
UZDoom builds from this merge and passes its startup check. Its Daggerfall Unity code is identical to the engine lane's verified build.

- **Fast travel arrival:** Daggerfall's real travel map now charges gold, advances time, and moves both games to the same place. Scripted trips to a hamlet, village, and farm ended with 0 world units of difference. A first visit freezes Doom for about 5 seconds while the location converts. Nobody has played it by hand.

### Merged to `integration` (`f97ed3b`)
UZDoom builds from this merge and passes its startup check. Its Daggerfall Unity code is identical to the engine lane's verified build. Scripted tests used both real games, but nobody has used the menus by hand.

- **Synchronized saving:** real bundled saves of both games, including autosaves on Daggerfall maps. Each save freezes the game for about 0.2 seconds.
- **Synchronized loading:** both games restore from one save, with a load freeze of about 2 seconds. Loading was only tested in the city, not in a building or dungeon.
- **Death screen:** Doom's death view leads to Load Last Save, Load Game, or Main Menu. Daggerfall no longer restarts itself in a bridge session.
- **Known gaps:** indoors, Daggerfall's half of a save records the player outside at the door until transitions are connected. New Game is refused until the real start flow exists.

### Merged to `integration` (`3816407`)
UZDoom builds from this merge and passes its startup check. Nobody has hand-played these features, and neither `play.bat` has been launched.

- **Animated textures and flats:** dungeons now show animated textures and ordinary flats such as torches and plants, with no measurable frame cost in Orsinium. Fixed treasure and NPC flats are not drawn yet, because loot and talking do not work on them.
- **Daggerfall items:** all 311 items exist as `DaggerfallItem` actors in a test gallery. 283 use their original sprite, and 28 show a placeholder because the game data has no usable image. Dye colors are not applied.

### Merged to `integration` (`3e74e18`)
UZDoom and Daggerfall Unity both build from this merge, and UZDoom passes its startup check. Most tests were scripted, and nobody has hand-played the combined build.

- **Startup and save research:** full proposal, with the owner's decisions recorded in `work/todo.md`.
- **Bridge:** position sync, Daggerfall's real travel map inside Doom, and HP sync. Daggerfall now stays at the door while Doom is indoors.
- **Dungeons:** tilted and flipped doors, doors that block like Daggerfall's, a traversal report for 19 dungeons, one random enemy per placement, and a texture pass. None of the 19 is proven fully traversable.
- **Towns:** roof-height building colliders with real slopes, and Doom-side entry and exit for buildings and Privateer's Hold.
- **Synchronized saving, not proven:** merged at the owner's request. It passed 45 of 45 checks against a scripted Daggerfall stand-in, but no real Daggerfall save has gone through it.

## 2026-11-22

### Bridge core
- UZDoom and Daggerfall Unity exchange messages and shared state through the launcher. The owner confirmed the IPC demo works.

### Parity test, action system, and water
- Closed-door parity stages use swinging doors, dungeon water is swimmable, and Daggerfall action objects move. The owner confirmed the Scourg Barrow coffin works, and textures need a second pass.

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
