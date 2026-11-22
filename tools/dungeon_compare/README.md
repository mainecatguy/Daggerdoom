# Dungeon comparison test

Places the camera at the same position and angle in Daggerfall Unity and in a converted UZDoom map, then writes paired screenshots, a side-by-side image, and distance probes for each viewpoint.

## Run it

Run from the repo root. Keep all output outside the repository, because it is derived from game data.

```powershell
# 1. Convert the dungeon.
python tools/dungeon_converter/run.py "Privateer's Hold" --out <out>\map

# 2. Build the capture player. Needed once, and after changing DungeonCaptureTest.cs.
#    Close any Unity editor using this project first. Afterward, discard the Addressables and
#    ProjectSettings files the build touches: they are build side effects.
Start-Process Unity.exe -Wait -ArgumentList '-projectPath daggerfall-unity-master -buildTarget Win64 -executeMethod CaptureBuild.BuildWindows64 -logFile daggerfall-unity-master/Logs/capture-build.log'

# 3. Capture and compare.
python tools/dungeon_compare/compare.py --views tools/dungeon_compare/views/privateers_hold.txt --map <out>\map\privateershold.wad --out <out>\compare

# 4. Optional: compare the converter's connected areas with Daggerfall's collision.
python tools/dungeon_compare/flood_report.py <out>\map\privateershold.points.txt <out>\compare
```

Open `<out>\compare\index.html` to review. Daggerfall is on the left and UZDoom is on the right. `probes.csv` holds the distances. `--skip-df` and `--skip-doom` reuse an existing capture.

## Movement parity and bullet check

```powershell
python tools/dungeon_compare/parity.py "Privateer's Hold" --out <out> [--baseline] [--unity-flood <df_flood_walk.txt>] [--world-scale 1.0]
python tools/dungeon_compare/player_check.py --map <out>\privateershold.wad --player <out>\privateershold_player.pk3 --out <out>\player
```

Writes `parity.csv`, `bullets.txt`, `worst_views.txt`, and `frontier.txt` under `<out>\parity`. `--baseline` turns off the ceiling fix. Pass `worst_views.txt` to `compare.py` with `--no-flood` for side-by-side images.

## Viewpoint file

One viewpoint per line: `id | kind | x y floor yaw pitch | note`. The first viewpoint must be the entrance, because the flood fill starts there. Use cell centers (8 mod 16), since probes along exact grid lines can slip between map lines.

## Coordinate transform

| Quantity | Daggerfall data | Daggerfall Unity (dungeon local) | Converted Doom map |
|---|---|---|---|
| East | `X` | `x = X * 0.025` | `x = X` |
| North | `Z` | `z = Z * 0.025` | `y = Z` |
| Up | `-Y` | `y = -Y * 0.025` | `z = -Y` |
| Facing | | Unity yaw `= 90 - angle`, clockwise from north | Doom `angle`, counterclockwise from east |
| Pitch | | positive looks down | positive looks down |

Block offsets of 2048 units are already part of `X` and `Z`. The dungeon root was at Unity (0, 0, 0) in the capture.

## Isolation

- The capture only runs with `-dfcapture <job>`, and refuses to run unless `Portable.txt` is beside the executable.
- `CaptureBuild` uses a separate product name, so Unity's registry entries and data folder differ from the real game. Settings and saves stay in the build's `PortableAppdata` folder.
- UZDoom uses a private `doom.ini` in the output folder.

## Limits

- `compare.py` currently requests Privateer's Hold by name, so another dungeon needs a small script change.
- Lighting is deliberately flat in both engines, and the converted map uses placeholder textures. Compare shapes, not appearance.
- A minimized UZDoom renders only 320x200, so it runs unminimized at an off-screen position without taking focus.
- Probes are single rays. A ray can pass through a one-sided Daggerfall face, so confirm a mismatch in the image.
- The flood fill is evidence, not proof. It treats doors as open and other moving objects as fixed, and it can leak through mesh cracks.
