# Terrain treadmill kill test (Proposal B): results

## Result: PASS for feasibility, with limits

UZDoom rewrote 32,768 real sloped Daggerfall terrain sectors in place during a straight run across 8 map pixels. All 32 shifts fit inside one 60 FPS frame. The worst shift frame was **13.41 ms** against the 16.67 ms budget. No shift caused a position jump, a fall through terrain, or a lost monster target.

This does not yet prove the approach under real combat. The test had only a handful of live actors per shift, one route, and one machine. See "Remaining risks".

## Test setup

| Item | Value |
|---|---|
| Grid | 128 x 128 cells, 2 triangles per cell, **32,768 sectors** |
| Spacing | 256 Doom units per tile |
| Scale (open owner question) | 1 Daggerfall unit = 1 Doom unit, 1.5 vertical scale. Change with `--unit` and `--vscale` in `treadmill_gen.py` |
| Shift | 32 tiles (8,192 units) when the player passes local X = 4,096 |
| Route | Map pixels 862-871 at row 442, chosen for relief. 8 pixels (262,144 units) were run |
| Terrain | 25,053 units of relief. Steepest cell 51.8 degrees, 419 cells over 45 degrees |
| Render | Vulkan, 3044 x 1649, visible window, vsync off, run after 2AM |

Heights use a Python port of `DefaultTerrainSampler` reading the real `WOODS.WLD`. **One term is not exact:** `Mathf.PerlinNoise` is native Unity code, so the small extra-noise term uses a Perlin surrogate with the same frequencies and scale. It can contribute up to about 150 units, so fine bumps differ from Daggerfall Unity while the large landforms do not.

## Timing

Frame times are in ms over the full run, excluding the first 300 frames. "GPU upload" is the CPU-side time spent writing plane vertices to the GPU buffer. Actual GPU execution time was not measured separately and is only reflected in total frame time.

**With rewrites (106,635 frames, 32 shifts)**

| Measure | Median | 95th pct | Worst |
|---|---:|---:|---:|
| All frames, total | 2.82 | 4.04 | 13.41 |
| Frames away from shifts, total | 2.82 | 4.03 | 8.07 |
| **Shift frame, total** | **12.11** | **13.16** | **13.41** |
| Frame after shift, total | 6.88 | 7.71 | 8.63 |
| Shift frame, simulation (rewrite + actor move) | 1.70 | 1.90 | 2.20 |
| Shift frame, GPU upload | 1.14 | 1.20 | 1.20 |

**Baseline: same shifts, no rewrite (170,898 frames, 32 shifts)**

| Measure | Median | 95th pct | Worst |
|---|---:|---:|---:|
| All frames, total | 2.56 | 3.55 | 7.21 |
| Frames away from shifts, total | 2.56 | 3.55 | 6.06 |
| Shift frame, total | 6.81 | 7.07 | 7.21 |
| Frame after shift, total | 4.95 | 5.32 | 5.51 |
| Shift frame, simulation | 0.01 | 0.01 | 0.04 |
| Shift frame, GPU upload | 0.00 | 0.01 | 0.02 |

- The rewrite adds about **5.3 ms** to the shift frame compared with the baseline, and about 1.9 ms to the frame after it.
- Simulation and upload explain about 2.8 ms of that 5.3 ms. The rest is unattributed, and is probably GPU or driver work on the changed buffer. This was not confirmed.
- The baseline's own shift frame is also about 4 ms slower than a normal frame. The cause was not investigated.
- The baseline is not a perfect match. Without rewrites it repeats the first terrain window, so it renders different terrain and the player moves at a different speed.
- No frame in either timing run exceeded 16.67 ms.

## Glitch checks

Full 8-pixel run with 31 monitored shift cycles, each with one `ZombieMan`, one `Cacodemon`, and one `DoomImpBall`.

| Check | Result |
|---|---|
| Terrain height after each shift | Worst error **0.000001 units**, from 512 random points per shift across 32 shifts |
| Player position jumps | **None caused by a shift.** 9 ticks flagged by a strict velocity check, all 2-7% over and at least 43 tics from a shift |
| Player below floor, stuck | 0, 0 |
| Camera interpolation | **0 jumps** after fixing a double-shift bug found by this check |
| Walking monster | 0 jumps, 0 below floor, 0 floating, 0 lost targets. It moved after the shift in 30 of 31 cycles. The other cycle is unexplained |
| Flying monster | 0 jumps, 0 lost targets. **11 ticks up to about 2.8 units below the floor**, none within 2 tics of a shift, so likely ordinary slope behavior. Not confirmed |
| Projectile | Crossed 31 of 31 shifts with 0 jumps and 0 below floor |
| Actors leaving the grid | 14 actors removed over the run, class not recorded. Removal is a **test placeholder**, because off-window behavior is the owner's decision |

**Player speed on slopes.** The scripted player reached **77 units per tic** on this terrain, against a normal 16.7. An ordinary static map of one terrain window, with the treadmill off, also reached 47. So Doom's slope physics produces the speedup without the treadmill. The two numbers cover different stretches of terrain and are not directly comparable. It also means the 8-pixel run took about 5 minutes rather than the 7.5 expected.

## Compatibility and patch size

- Stock `DOOM2.WAD` startup check with the patched engine: **exit code 1337** (success).
- Stock MAP01 entered and was still running after 20 s, with the treadmill inactive.
- The patch activates only when the map is `TREADM01` **and** `-ddtreadmill` is passed.
- **Patch: 364 added lines, 0 removed, 8 files.** 345 lines are in the new `UZDoom/src/playsim/dd_treadmill.cpp` and `.h`, which include test logging and verification. 19 lines are hooks in 6 existing files, marked `[DoomDaggerfall]`.

## Commands

```powershell
cmake -S UZDoom -B D:/dev/DoomDaggerfall-build/uzdoom-treadmill -G "Visual Studio 18 2026" -A x64
cmake --build D:/dev/DoomDaggerfall-build/uzdoom-treadmill --config Release --parallel 6
python work/spikes/treadmill_gen.py --route 862,442
python work/spikes/treadmill_suite.py          # rewrite, baseline, and verify runs
python work/spikes/treadmill_run.py glitch 262144 -ddtmverify
python work/spikes/treadmill_control.py        # static-map physics and stock map checks
python work/spikes/treadmill_analyze.py rewrite baseline verify glitch
```

The harness was tightened after the `rewrite`, `baseline`, and `verify` runs, so regenerating before the suite will use the newer checks. Timing tables come from the `rewrite` and `baseline` runs. Glitch results come from the `glitch` run. Height error is from the `verify` and `glitch` runs.

## Remaining risks

- **Slaughter-sized packs are untested.** Actor shift cost grows with actor count, and this test moved only a few actors per shift.
- **Rendering hitch is partly unexplained.** About 2.5 ms of the rewrite's added frame cost has no measured cause, and slower GPUs may exceed one frame.
- **Only one machine, route, and resolution** were measured.
- **Not shifted or tested:** decals, positioned sounds, and saving during a treadmill run. Particles are shifted in code, but no check covers them.
- **Only straight eastward travel** was tested. The code handles Y shifts, but the test data cannot exercise them.
- **Towns and buildings remain unsolved** by this approach, as Proposal B already noted.

## Review images

`D:\dev\DoomDaggerfall-loop\review\terrain-treadmill\shots\`. The first two files, `Screenshot_Doom_20261122_023114.png` and `..._01.png`, are the before and after pair at the first shift. The later two are the second shift. In the first pair the terrain and sky line up with only the small forward motion expected. These files are derived from game data and are not committed.

## Owner play-test list

1. Run the treadmill and watch for any visible stutter or pop at each shift (about every 14 s at normal speed).
2. Judge whether a roughly 12 ms frame among 3 ms frames is noticeable on your display.
3. Judge how the slope speedup feels when running downhill.
4. Fight near a shift and check that monsters and projectiles look continuous.
