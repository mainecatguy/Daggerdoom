# Ship boarding lands the player in the water, not on deck

Waiting on: the owner (priority) and an engineering card. Found while merging traveloptions 01 (2026-11-27, report
20261127-113137).

Choosing **Ship** in the transport menu works in Daggerfall (its world teleports to the ship's map pixel), and Doom
follows with a `DFB_KIND_TRAVEL` arrival and loads a generated map there. But Doom puts the player at water level, not
on the deck:

- Small ship (map pixel 2,2, map `DDT00000`): player at x 12323.3, y -12766.5, **z 0.0, floorz 0.0**, facing open
  water; no ship in view.
- Large ship (map pixel 5,5, map `DDT00131`): player at x -211.5, y -394.5, **z 0.0, floorz 0.0**; the ship's hull and
  deck planking are overhead, so the player is in the water under or beside the hull.

Screenshots (kept in the merge stage folder): `D:\dev\DoomDaggerfall-loop\review\batch6-stage\ship-shots\`
(`small-1-forward.png`, `small-2-back.png`, `large-1-forward.png`, `large-2-back.png`). Taken with a scratch copy of
`tools/transport/transport.py` (modes `small` and `large`, `-ddqa pos` plus `con screenshot`) on the merge build; the
test hook's `-dftransporttest <file> large` option gives the large ship.

Cause to check first: the `KIND_TRAVEL` event carries only the world x/z position, yaw and map pixel, no height, so Doom
places the player on whatever floor is under that point (here the water surface, or the sea floor under the deck).
Either the event needs Daggerfall's arrival height (Daggerfall puts its player on the deck), or the generated map needs
a walkable ship deck at that spot (the ship models may not be converted as solid floors).

Also: from the ship, choosing Ship again returns the player to where they boarded (works; `transport.py run owned`).
