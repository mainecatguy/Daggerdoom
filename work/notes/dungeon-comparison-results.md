# Dungeon comparison results: Privateer's Hold

**Result:** the comparison works and can be rerun. All 16 viewpoints produced a Daggerfall capture, a UZDoom capture, and a side-by-side image. The coordinate transform is correct. The main finding is that **the converter walls off real openings**, so at least part of the "unreachable" third of the map is a converter defect and not sealed source geometry.

Nobody has reviewed these images except the agent. The screenshots are in a session scratchpad that a reboot or cleanup can erase. The command below regenerates them.

**Screenshots:** `C:\Users\Patrick\AppData\Local\Temp\claude\2627cf03f9216b14\e1337a4b-b2e2-4614-86de-296544487c08\scratchpad\final\index.html`

## How to run it

See `tools/dungeon_compare/README.md` for the full steps. The comparison command is:

```powershell
python tools/dungeon_compare/compare.py --views tools/dungeon_compare/views/privateers_hold.txt --map <out>\map\privateershold.wad --out <out>\compare
```

## Coordinate transform

Doom `(x, y, z)` = Daggerfall `(X, Z, -Y)` = Daggerfall Unity dungeon-local `(x, z, y) / 0.025`. Unity yaw = 90 - Doom angle. Positive pitch looks down in both.

**Verification:** each viewpoint fires six rays in both engines (down, up, and four compass directions). At 11 of 16 viewpoints, all six distances agree within 24 units, and the images line up. Each of the other 5 is explained below. Four of them are at positions where the map really differs, and v04 is a lower ceiling.

## What each viewpoint showed

| View | Area | Probes | Finding |
|---|---|---|---|
| v01 | Entrance | Agree | Room shape and door position match. |
| v02 | Large room | Agree | Layout and pillar match. Ceiling and floor flats form jagged patches. |
| v03 | Corridor | Agree | Layout matches. Same jagged flat patches. |
| v04 | Door | Up differs: 163 vs 128 | Door is in the right place, but uses a wall texture. Ceiling in front of it is about 35 units lower in Doom. |
| v05 | Stairs | Agree | Ramp becomes stairs, an accepted approximation. |
| v06 | Stack, lowest level | Agree | Corridor matches. |
| v07 | Stack, top level | Agree | Corridor matches, so stacked levels are at the right heights. |
| v08 | Cut-off, north | Agree | Room matches. The door is not visually distinct. |
| v09 | Cut-off, east | Agree | Ramp becomes stairs. Layout matches. |
| v10 | Cut-off, northeast | North: no hit vs 296 | Daggerfall has a door-shaped hole to empty space. Doom has a wall. |
| v11 | Cut-off, south | Agree | Layout matches. |
| v12 | Campfire cave | 4 directions differ | Curved cave becomes a boxy, stepped room. South is the defect shown in v16. |
| v13 | Door, cut-off area | Agree | Door is in place, but the slab is wider than the source door and a gap above it shows the space behind. |
| v14 | Lost doorway | West: 418 vs 24 | **Defect.** Open doorway in Daggerfall, solid wall in Doom. |
| v15 | Suspected pit | Agree | Solid floor in both. The flood fill's drop here was a collision leak. |
| v16 | Cave, south | South: 746 vs 24 | **Defect.** Tunnel in Daggerfall, solid wall in Doom. |

## Confirmed converter defects

1. **An open doorway is walled off (v14, near 790, 1912, z 724).** Daggerfall's collision walks through it into cut-off area 11 (134 test points).
2. **The campfire cave's tunnel is walled off (v16, 504, 1432, z 0).** A ray travels 746 units south in Daggerfall and stops after 24 in Doom. This cave holds the "Enter" marker, so the earlier note calling it a sealed room was wrong.
3. **A door has a see-through gap above its slab (v13).** The slab is also wider than the source door.
4. **The ceiling is about 35 units too low in front of a door (v04).**
5. **Doors are not visually identifiable.** They use wall textures, so a player cannot tell where they are.
6. **Floor and ceiling flats form jagged patches (v02, v03).** This is cosmetic, and the map uses placeholder textures anyway.

I did not diagnose the root cause of defects 1 and 2. Both look like the wall and door-gap step closing a real opening, but this is untested.

**Accepted approximations:** ramps as stairs, stair-stepped curves, and small wall offsets within the 16-unit grid.

## Are the unreachable areas really sealed?

**Partly no.** Areas 11 and 13 are not sealed in the source, as defects 1 and 2 show.

For the other cut-off areas, the answer is **not proven**. A flood fill over Daggerfall's real collision, with doors open and a rise of up to 48 units per step, reached 90.9% of the converter's main area and none of those other areas. That is consistent with them being sealed, but it has three weaknesses:

- It leaked through the floor at v15, so its collision is imperfect.
- It did not find the v16 tunnel route on its own. It entered the cave through that leak.
- Moving objects stay at their start position, so any route that depends on them is invisible. How they should work remains an open owner decision.

Since the converter closed two real openings, the same defect may be hiding others. The next run should fix it and then re-measure reachability.

v10 also shows a door-shaped hole to empty space at the dungeon's edge in Daggerfall itself. I did not determine what it is for.

## Failures and corrections along the way

- UZDoom queues aliases during startup, so the first capture attempts did nothing. The script now waits until the game is running.
- A minimized UZDoom only renders 320x200. It now runs unminimized at an off-screen position without taking focus. I did not confirm the window stayed off-screen.
- Probes along exact grid lines gave false mismatches, so viewpoints moved to cell centers.
- The first flood fill was wrong: its more permissive run reached fewer positions. It searched for floors from above low ceilings and its body check collided with ramps. Both are fixed.
- At the strict 20-unit step, the flood reaches only 30.9% of the main area, so that run is too conservative to use as evidence.

## Isolation

Daggerfall ran from a separately named portable build. Its settings, saves, and logs were written to the build's `PortableAppdata` folder. I did not launch the build without `-dfcapture`. The code returns immediately when the flag is absent.

## Owner review list

1. Open `index.html` and check that v14 and v16 show real openings walled off in Doom.
2. In real Daggerfall, start in the campfire cave and confirm the v16 tunnel is the way out.
3. Look at the v10 door-shaped hole. Is it reachable or meaningful in normal play?
4. Check whether the door gap in v13 is visible from normal play positions.
5. Decide whether the stair-stepped cave in v12 is an acceptable approximation.
