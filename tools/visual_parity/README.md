# Visual parity test: Doomerfall against Daggerfall Unity

Puts both games at the same place, or in the same window, and saves matched screenshots for the owner to triage.
Issue log and findings: `work/notes/20261127-052057.md`.

```powershell
python tools/visual_parity/scenes.py [--seed 1] [--count 12]   # pass 1: random spots in Privateer's Hold
python tools/visual_parity/menus.py  [--seed 1]                # pass 2: the same windows with the same items
```

Output goes to `D:\dev\DoomDaggerfall-loop\review\visualparity\scenes` and `...\menus` (`--out` to change; it must be
outside the repository, because screenshots are derived from game data). Open `index.html` there. Each pair is
`<id>.side.png`: Daggerfall Unity on the left, Doomerfall on the right. `scenes.csv` and `menus.csv` hold a rough
difference score and mean brightness. `--skip-df` and `--skip-doom` reuse one side's captures.

## What each side is

| | Daggerfall Unity | Doomerfall |
|---|---|---|
| Program | The capture player (`DungeonCaptureTest`, `-dfcapture <job>`, portable build `Builds/Capture/DFCapture.exe`) | The real paired game through the launcher, from the play folder in `common.py` (`VP_PLAY`) |
| Enemies, NPCs | Dungeon loaded without enemies; job line `nonpcs` hides NPC flats | `tools/visual_parity/doom` removes every monster and NPC each tic (pickups stay) |
| Scenes | Lit with the game's own lights, camera at 1.71 m (68.4 units) above the floor, 65 degree vertical FOV | Camera actor at the same eye (51.3 Doom units at world scale 0.75), Doom FOV 80.68 (65 vertical at 4:3) |
| Also | | `<id>.doomnative.png`: the player's own view as played (eye 48, FOV 90, weapon and HUD) |
| Menus | Blank `-dfsynctest -dfinventorytest` character at map pixel 207, 213; window opened by Daggerfall Unity's own message; UI drawn into a texture over the 3D frame | Same start; window opened with the real Doom command (`netevent df_inventory`, `df_fast_travel`, `df_journal`, `df_rest`, `togglemap`) and Doom's `screenshot` |

Spots are seeded random nodes of the converter's walk graph (`privateershold.points.txt`, reachable from the entrance,
72+ units of headroom), facing the most open of eight turns from a random start angle.

## Build

- Capture player: `Start-Process Unity.exe -Wait -ArgumentList '-projectPath daggerfall-unity-master -buildTarget Win64 -executeMethod CaptureBuild.BuildWindows64 -logFile daggerfall-unity-master/Logs/capture-build.log'` (through `quiet_run.py`). Discard the Addressables and ProjectSettings files the build touches.
- Play folder: `python scripts/play/install.py <folder> --build-dir <private build dir> --keep-data` after copying a play folder's `data` and `dfitems.pk3` into `<folder>`. The UZDoom and Daggerfall Unity in it must match this checkout's `doomerfall.pk3`.

## Known gaps

- Doom's `screenshot` comes out black while a Daggerfall window is open in Doomerfall, so pass 2's Doomerfall side is not yet usable (see the notes).
- Daggerfall Unity's menu shot is meant to be the UI drawn into a texture and laid over the 3D frame by the UI's alpha. On the hidden desktop the UI layer comes out empty (`*.dfui.png`), so only the 3D frame shows. Not solved.
- Pickups (DRLA stimpacks, Doomerfall ammo) are left in Doomerfall's scenes.
