> **Answered (owner, 2026-11-28):** 3D floors yes (`townoverhangs` 01); the 4-unit raster waits on `loadprofile` 01.
> **Sent back (2026-11-28):** waiting on two owner choices. The measuring work of `exteriorcollision` 02 is done (branch
> agent/exteriorcollision-20261128-011359, commit 61a39b75, notes work/notes/20261128-011359.md); reducing the error
> needs these answers.

# Exterior collision: reduce the error (part 3)

1. **Switch towns to the 4-unit raster?** The existing `--raster 4` option cuts the exterior collision error by 30%
   (set 0.2485 to 0.1750) and invisible-wall area by 91% (188M to 16M square units), and improves all nine test towns.
   The cost: runtime town conversion for the capital goes from about 6.5 s to about 11.9 s (card 01's measurement), and
   maps get 35% more lines (124k to 168k). If yes, the door, walk, flight and roof-parity checks must pass before it
   lands.
2. **Solid 3D floors for overhangs?** Arches, bridges, jutting upper floors and roof eaves over open street have no
   collision top, so a levitating or climbing player falls through them: about 74M square units, 24% of
   levitation-reachable walkable tops in the Daggerfall group. Card 01's sky-wall fix more than doubled this. Putting
   the tops back in the heightfield would block the passages below; the fix is solid 3D floors in every runtime town
   map (more conversion work and map complexity).
