version "4.10"

// Loaded only by tools/first_room/run_stairs_views.py on Privateer's Hold's converted map (no Daggerfall, no
// monsters). Puts the player at each view below in turn (floor under x,y nearest z; angle 0 = east, 90 = north;
// pitch down positive), holds it 20 tics and takes a screenshot. Prints "SVIEW <n> <label>" before each shot.
class FirstRoomStairsViews : EventHandler
{
	int tics;

	override void WorldTick()
	{
		static const double V[] = {
			510, 1672, 960, 270, 0,     // 0 the cave where New Game wakes you, looking south
			520, 1560, 960, 280, 5,     // 1 the cave mouth, looking into the next room
			550, 1470, 960, 270, 15,    // 2 inside p0's room, looking south at its raised part
			560, 1300, 960, 90, 5,      // 3 p0's room looking back north toward the cave
			560, 1300, 960, 0, 5,       // 4 p0's room looking east, toward the next room
			846, 1230, 960, 0, 5,       // 5 the floor east of p0's room, looking east toward the staircase
			930, 1264, 960, 0, 25,      // 6 top of the staircase, looking east down it
			1120, 1264, 790, 180, -15,  // 7 bottom of the staircase, looking back up west
			846, 1180, 960, 270, 50,    // 8 the edge south of that floor, looking down into p37's room
			851, 1110, 384, 270, 0,     // 9 p37's room (floor 384), looking south
			992, 1357, 392, 270, 0,     // 10 p2's spot (floor 392, under the staircase), looking south
			1142, 1180, 780, 270, 40,   // 11 the landing at the bottom of the staircase, looking down south
			1142, 1180, 780, 225, 15,   // 12 the landing, looking southwest across the hall
			675, 769, 384, 0, -10,      // 13 the hall's middle (floor 384), looking east
			675, 769, 384, 90, -20,     // 14 the hall's middle, looking north (up at the corridor above)
			675, 769, 384, 180, -10,    // 15 the hall's middle, looking west
			675, 769, 384, 270, -10,    // 16 the hall's middle, looking south
			1206, 572, 768, 180, 20,    // 17 p10's spot (floor 768), looking west
			1120, 552, 384, 0, 0        // 18 where p10's second monster stands (floor 384), looking east
		};
		static const String L[] = { "cave", "cave mouth", "p0 room south", "p0 room north", "p0 room east",
			"floor east of p0", "staircase top", "staircase bottom", "edge over p37 room", "p37 room", "p2 spot", "landing",
			"landing southwest", "hall east", "hall north", "hall west", "hall south", "p10 west", "p10 mook east" };
		tics++;
		let mo = players[0].mo;
		if (!mo) return;
		if (tics == 2) { mo.GiveInventory("PowerLightAmp", 1); mo.bNOGRAVITY = true; }
		int n = (tics - 5) / 20, t = (tics - 5) % 20;
		if (tics < 5) return;
		if (n >= 19) { if (t == 0) Console.Printf("SVIEWS done"); return; }
		mo.SetOrigin((V[n * 5], V[n * 5 + 1], V[n * 5 + 2] + 8), false);
		mo.SetZ(mo.floorz);
		mo.vel = (0, 0, 0);
		mo.angle = V[n * 5 + 3];
		mo.pitch = V[n * 5 + 4];
		if (t == 15) { Console.Printf("SVIEW %d %s floor %d", n, L[n], int(mo.floorz)); LevelLocals.MakeScreenShot(); }
	}
}
