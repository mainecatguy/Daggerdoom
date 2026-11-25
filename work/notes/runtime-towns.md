# Runtime Daggerfall locations

## Result

The player can travel the overworld and enter Daggerfall locations that did not exist when UZDoom started. Each one is converted in the background, loaded into the running game, and kept in a size-capped disk cache.

Demo: `D:\dev\DoomDaggerfall-loop\review\runtime-towns\play.bat`. You start east of the City of Daggerfall. `WARPS.txt` in that folder has console lines that jump to other locations.

## How it works

- **One shared package.** `ddruntime.pk3` (28 MB, built once) holds the index of all 15,242 location groups, every Daggerfall texture, the gate models, and the scripts. It replaces the per-town package on the command line.
- **One cache file per location.** `T<group>.ddt` holds the map, mesh, billboards, gates, and world placement, compressed. It is written to a temporary name and renamed, so a partial file is never read.
- **Map names carry the location.** `DDT09183` is group 9183. A save records that name, so loading it can find or rebuild the location. The engine opens these maps from the cache instead of its file list, which is why no restart is needed.
- **Background conversion.** Within 100 tiles of a location the engine queues it, nearest first. One converter process runs at a time, below normal priority, and is killed if the game exits. Decompression runs on a worker thread.
- **If a location is not ready,** the overworld stays playable and the player can walk across the ground there. If it finishes while they stand on it, it stays hidden until they walk clear, so they cannot appear inside a wall.
- **Cache.** The default cap is 2 GB (`-ddtowncachemb`). The least recently used files are evicted. A damaged file is deleted and rebuilt once.
- **Progress stays in the world table and saves.** The cache holds only data that can be rebuilt. Conversion is deterministic: repeat conversions were byte-identical.
- **Fast travel.** `dd_tm_warp "tileX tileY"` moves the player through the same handoff, and `DDTownCache::GetBlocking` waits for a location. A fast travel transition can use both.

## What I learned

- Stock save code only writes snapshots for maps in MAPINFO. Generated maps need their own loop, or a load silently restarts the map.
- Stock autosave code assumes a map came from a loaded file. It crashed on a generated map until the map reported the runtime package as its file.
- Every handoff also triggered an autosave, a 220 to 240 ms hitch about a second after arrival. Stitched changes no longer autosave. See the questions below. (2026-11-24: owner decision, autosaves are back; they now run before the new map's first frame. See `work/notes/20261124-123655.md`.)
- Two groups were too wide for one map, including Wayrest. They now become one map per location.

## Engine changes

All marked `[DoomDaggerfall]`, and inactive without the runtime package and its command-line options:

| File | Change |
|---|---|
| `playsim/dd_towncache.cpp`, `.h` | New: cache, converter process, worker reads, test crash capture |
| `playsim/dd_treadmill.cpp`, `.h` | Location index, requests, distant view, handoff to generated maps |
| `p_openmap.cpp` | Opens a generated map from the cache |
| `gamedata/g_mapinfo.cpp`, `g_level.cpp` | Level info and save snapshots for generated maps. A stitched change autosaves through the bridge before its first frame |
| `hw_dfmesh.cpp` | Mesh can come from the cache |

## Evidence

Run with `tools/overworld/runtime_test.py`. Logs are in `D:\dev\DoomDaggerfall-build\runtime-tests`. All runs were scripted and minimized.

| Check | Result |
|---|---|
| One session, 6 new locations plus a return from cache (city group, Wayrest, Merwark Hollow, hamlet, temple, ruin) | Pass, no crash |
| Background conversion in that session | 4.8 to 6.3 s |
| Entering | 0.2 s (small) to 1.0 s (largest), with nodes cached |
| First-ever entry to the largest group, nodes not yet cached | 1.73 s |
| Returning to the overworld | 0.66 to 0.98 s, median 0.71 s |
| Cache after 6 locations | 34.7 MB, largest file 12.8 MB |
| Frame time while converting vs idle (minimized) | Median 7.9 vs 5.1 ms, p99 16.5 vs 8.7 ms, worst 48 vs 60 ms |
| Stratified sample, 65 groups, all 15 location types | 63 converted. The other 2 were too wide, and now convert after the split |
| Seam height, 5 locations | Worst 0.0014 Doom units |
| Converter missing | Player stays in the overworld, no crash |
| Damaged cache file | Deleted, rebuilt, entered |
| 16 MB cache cap | Evicted oldest files and kept playing |
| Save in town, empty the cache, load | Location rebuilt, wounded imp restored at 17 health |
| DOOM.WAD `-norun` | Exit 1337 |
| DOOM.WAD E1M1, save, load | Pass |
| Existing overworld-to-city stitch, east gate | Pass, 0 jumps |
| Privateer's Hold | WAD hash matches the baseline (`6958922D`), 58 doors spawn |

## Known gaps

- **The engine's node cache is not under the size cap.** UZDoom stores built nodes in `%LOCALAPPDATA%\doom\nodes`, shared with stock maps. Deleting them only makes the next entry slower.
- **Only the nearest ready location is drawn from the overworld.** A second location in view appears when it becomes the nearest.
- **Split groups do not show each other from inside.** In Wayrest's map, Merwark Hollow's buildings are absent until you cross into it.
- **One sky and one overworld ground tile** are used everywhere, so climate does not change them yet.
- **Windows only** for background conversion. On other platforms a location reports as failed and the overworld stays playable.
- The `.NET 9` runtime must be installed for the converter.
- Only 65 of 15,242 groups were converted in the sample, and 7 were entered in the engine.

## Not verified

- Real keyboard play and real windowed frame rate.
- Sound across a handoff.
- Combat during a handoff.
- Whether converting hurts frame rate on a machine with fewer cores.

## Play-test list

1. Run into the City of Daggerfall from a fresh cache. Does it appear before you reach it?
2. Is a 1 to 1.7 s hold on a first entry acceptable? How does a cached entry feel?
3. Use `WARPS.txt` to visit a hamlet, temple, ruin, and Wayrest. Do they look right, with the right climate textures?
4. Walk between Wayrest and Merwark Hollow. Is the missing neighbor noticeable?
5. Run onto a location before it finishes converting, then walk off and come back.
6. Save in a town, quit, delete `D:\dev\DoomDaggerfall-loop\town-cache\demo`, and load.

## Questions for the owner

1. ~~Stitched map changes no longer autosave, because each autosave caused a visible hitch. Should autosaves happen at some other moment, such as on a timer or when resting?~~ Answered 2026-11-22: keep normal autosaving; the hitch is acceptable during a load.
2. Should adjacent locations that are too wide for one map, like Wayrest and Merwark Hollow, show each other's buildings from inside? It needs a second mesh layer.
