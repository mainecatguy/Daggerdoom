version "4.14"

// Map keys. Lets the bridge's -dfuitest open Daggerfall's map screens one after another, through their real
// commands, while the Python side sends key presses to Doom's window. Doom pauses behind every Daggerfall menu, so
// a jump in real time between two tics means a menu was open and has closed. Stages:
//   0  town: open the exterior automap (dd_ui_test_menu 3)
//   1  town: open the travel map (dd_ui_test_menu 1)
//   2  walk into Privateer's Hold, then open the dungeon automap
//   3  done
// MKPOS lines give the player's position, so the test can see Doom never moved it while a menu was open.
class MKHarness : StaticEventHandler // Static: it must keep its stage across the trip into the dungeon.
{
	static const double DOORDATA[] = { @DOOR@ };
	const FIND_RUN = @FIND@;
	int stage, timer, lastMs, walk;
	bool done;
	vector3 lastPos;

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		int now = MSTime();
		bool paused = lastMs && now - lastMs > 700;
		lastMs = now;
		timer++;
		if (paused || p.pos != lastPos || timer % 35 == 0)
			Console.Printf("MKPOS stage %d%s %.2f %.2f %.2f", stage, paused ? " after-menu" : "", p.pos.x, p.pos.y, p.pos.z);
		lastPos = p.pos;
		bool inside = level.MapName.Left(3) ~== "DDS" || p.pos.z < DOORDATA[2] - 1000; // Dungeons may load below the town.
		CVar hold = CVar.FindCVar("dd_ui_test_hold"), menu = CVar.FindCVar("dd_ui_test_menu");

		switch (stage)
		{
		case 0:
			if (paused && level.maptime > 72) { stage = 1; timer = 0; menu.SetInt(1); Console.Printf("MKSTAGE 1 travel map"); break; }
			if (level.maptime == 70 && !inside) { menu.SetInt(3); hold.SetInt(0); Console.Printf("MKSTAGE 0 exterior automap"); }
			break;
		case 1:
			if (!paused) break;
			if (FIND_RUN) { stage = 3; Console.Printf("MKDONE"); done = true; break; } // The Find test stops after the travel map.
			stage = 2;
			timer = 0;
			walk = 0;
			hold.SetInt(1);
			menu.SetInt(3);
			Console.Printf("MKSTAGE 2 dungeon automap");
			break;
		case 2:
			if (paused && walk == 2) { stage = 3; Console.Printf("MKDONE"); done = true; break; }
			if (inside)
			{
				if (walk == 1 && timer > 140)
				{
					RemoveMonsters();
					walk = 2;
					hold.SetInt(0);
					Console.Printf("MKREADY dungeon");
				}
				if (walk == 0) { walk = 1; timer = 0; }
				break;
			}
			{
				vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
				vector2 normal = (DOORDATA[3], DOORDATA[4]);
				p.SetOrigin((door.xy + normal * 48, door.z), false);
				p.vel = (0, 0, 0);
				p.angle = atan2(-normal.y, -normal.x);
				if (timer == 12) CVar.FindCVar("dd_tm_use").SetInt(1);
			}
			break;
		}
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}
}
