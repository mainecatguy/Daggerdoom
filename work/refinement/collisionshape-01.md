> **Sent back (2026-11-28):** waiting on owner choices. Stages 1 and 2 of the grid-shape refactor are done (latest branch
> agent/collisionshape-20261128-074035; notes work/notes/20261128-051657.md, 20261128-060616.md, 20261128-074035.md).
> Not run for the route fix: the door regression (special_door_regress.py points at a missing uzdoom-mesh build) and
> parity (needs Daggerfall Unity flood captures). Card: work/queue/collisionshape/done/01.opus.grid-shape-refactor.md.

# Dungeon collision grid: owner choices

1. **Answered (owner, 2026-11-28): accept.** Seeded output may change between versions before release
   (gamedesign/decisions/20261128-seed-stability-owner.md). Was: accept a default output change from the route fix? The fix that stops finer grids cutting the dungeon entrance
   route also changes the default 12-unit output. Collision is byte-identical on all 33 test maps. Only the route graph
   (DFPOINTS) and pickup placement change: 875 pickups move on 23 maps, and no player start moves. Entrance reach goes
   from 52.5% to 52.9%, doors joining separate areas from 8 to 3, and links crossing a raw wall from 453 to 457 (all 4
   new ones on map 1001).
   - (a) Accept the default change.
   - (b) Apply the fix only to finer grids, so the default stays byte-identical.
2. **Answered (owner, 2026-11-28): stay on square 12 for now; `loadprofile` 01 profiles load times first.** Was: which grid? The default stays square 12 until you choose. Against 12-unit:
   - 8-unit: -34% error, +29% conversion time, +35% sectors. One real cut remains: map 187853213 is stuck at a 45-degree
     door, so 8-unit is not ready yet.
   - Quad 12/6: -45% error, +42% time, +77% sectors.
   - Dropped: quad 16/8 (cuts the route on 27 of 33 maps); triangle (-36% error, +67% time, +225% sectors).
   Dungeons convert at the door (7-11 s today when not prefetched), so the time cost is felt.
