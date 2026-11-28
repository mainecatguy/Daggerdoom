## 2026-11-28: Collision grids wait on load-time profiling; town overhang floors; shotgun knockback 10/20 ft

- **Verdict:** Owner decided.
- **Dungeon collision grid:** stays square 12. Finer grids (8-unit, quad 12/6) are too slow for now; load times come
  first. A profiling task finds why conversion is slow and how to speed it up.
- **Town 4-unit raster:** not yet. Profile town conversion first: find the worst-case slowdown, why it is slow, and show
  the owner the offending code blocks; the owner will design the speed-up.
- **Town overhangs:** yes, solid 3D floors for arches, bridges, jutting upper floors and roof eaves over open street, so
  a levitating or climbing player can stand on them.
- **Shotgun knockback:** Shotguns 75 adds about 10 ft and Shotguns 100 about 20 ft of extra push on a full Double
  Shotgun blast, on top of Doom's own pellet push (not the total slide). Stock pellet push is unchanged.
- **Owner's words:** "going to those other schemes is too slow right now, we need to get loading times down next";
  "(b) yes (a) again can we performance profile this ... identify where the slowdown is worst case identify WHY it's so
  slow and show me the offending blocks of code and I'll figure out a way to make it faster"; "make it 10/20 and it is
  extra push in addition to what they usually do".
- **Long saves:** saves keep waiting out Daggerfall (busy announcements as built). A separate card fixes Doom's
  "Unknown net command" crash on a load after a long frozen save. Owner: "a".
