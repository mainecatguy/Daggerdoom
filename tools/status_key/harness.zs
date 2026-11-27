version "4.14"

// Status key test (statuskey.py). Lets the bridge's -dfuitest open Daggerfall's status boxes (dd_ui_test_menu 13)
// through the real command, netevent df_status, once outdoors in town and once indoors behind the test door, while
// the Python side presses keys in Doom's window. Doom pauses behind every Daggerfall menu, so a jump in real time
// between two tics means the menu was open and has closed. Stages:
//   0  town: open the status boxes
//   1  walk through the test door (a building or Privateer's Hold), then open them again
//   2  done
class SKHarness : StaticEventHandler // Static: it must keep its stage across the trip indoors.
{
	static const double DOORDATA[] = { @DOOR@ };
	int stage, timer, lastMs, walk;
	bool done;

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
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01"; // Interiors and dungeons load as their own map.
		CVar hold = CVar.FindCVar("dd_ui_test_hold");

		switch (stage)
		{
		case 0:
			if (paused && level.maptime > 72) { stage = 1; timer = 0; walk = 0; Console.Printf("SKSTAGE 1 indoors"); break; }
			if (level.maptime == 70 && !inside) { hold.SetInt(0); Console.Printf("SKSTAGE 0 outdoors in %s", level.MapName); }
			break;
		case 1:
			if (walk == 0) hold.SetInt(1);
			if (paused && walk == 2) { stage = 2; Console.Printf("SKDONE"); done = true; break; }
			if (inside)
			{
				if (walk == 1 && timer > 140)
				{
					RemoveMonsters();
					walk = 2;
					hold.SetInt(0);
					Console.Printf("SKREADY indoors in %s", level.MapName);
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
				if (timer == 12 || timer % 140 == 139) CVar.FindCVar("dd_tm_use").SetInt(1);
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
