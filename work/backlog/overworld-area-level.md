# Overworld area level

**Waiting on:** an owner design chat.

Owner (2026-11-24): the overworld may inherit a level bonus from its area or nearby location. Needs discussion.

What exists: `DoomerfallAreaLevels.cs` already gives every land map pixel a terrain level from 1 to 30, ranked over
all land, from the region's lean plus a smooth geography field. Towns, houses and shops use the terrain level of their
map pixel. The countryside around the City of Daggerfall is level 1. Dungeons get their own level, ranked within their
size class. Open: whether the wilderness near a dangerous place should rise toward it, and how towns relate to it.
