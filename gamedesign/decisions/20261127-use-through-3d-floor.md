## 2026-11-27: Should Use take an item on another storey through a solid 3D floor? [looklabel, work/notes/20261127-084059.md]

- **Verdict:** Leans (refuse).
- **Answer:** Use (and probably Info) should skip an item when a solid 3D floor lies between the player's eye and the
  item, with the same storey test the look label now uses (`OtherStorey`). An item on a ledge seen from an open room
  stays usable.
- **Rests on:** `gamedesign.md`, "In-engine object permanence": "Things that exist in the world appear to the player
  as if they really exist in the world ... what moves goes somewhere the player could follow." Taking a clip that lies
  on the floor above, through solid ground, moves it from a place the player cannot reach. The label already hides
  such items, so Use and the label would disagree if Use did not.
- **Inference:** the principle is about appearance and movement, not interaction reach, so it points one way but does
  not settle it. Taking through floors was never owner-approved behavior. It came from a rough `P_CheckSight` test.
- **Challenge:** Could refusing break pickups the player can legitimately reach? The filter needs a solid floor in both
  the item's sector and the player's, so ledges still work. It is not a new system. It does not reach Follows clearly,
  because "common sense" alone never strikes an option and the quoted principle only covers it indirectly. Kept as Leans.
- **Update (2026-11-27):** the owner added the World logic principle to `gamedesign.md` ("outside of cheats nothing happens that makes no physical sense in that world"). This now follows clearly: Use refuses items through a solid 3D floor.
