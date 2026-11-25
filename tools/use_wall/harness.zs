version "4.14"

// Use-on-a-building-wall test. Every press is Doom's own Use button through the QA channel (use_wall.py answers each
// UWUSE line), so it runs Doom's whole Use path. Route, outside the store whose door is DOORDATA:
//   1. Use on the store's wall beside the door, from a few offsets until Daggerfall names a building.
//   2. Info (df_info) on the store's door from outside Use reach, so the runner can tell the wall and door share a building.
//   3. Use on the door: it must enter, as before.
class UWHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double OFFSETS[] = { 112, -112, 160, -160, 208, -208 };
	const LIMIT = 35 * 25;

	int phase, timer, tries;
	bool done, wantUse;
	double holdAngle;

	void Finish(String why) { Console.Printf("UWDONE %s", why); done = true; }
	void Next(int to) { phase = to; timer = 0; }

	void Stand(PlayerPawn p, double away, double side)
	{
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		vector2 along = (-normal.y, normal.x);
		p.SetOrigin(((DOORDATA[0], DOORDATA[1]) + normal * away + along * side, DOORDATA[2]), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
		p.pitch = 0;
	}

	void Press(PlayerPawn p, String what)
	{
		wantUse = true;
		holdAngle = p.angle;
		Console.Printf("UWPRESS %s at %.1f,%.1f angle %.1f", what, p.pos.x, p.pos.y, p.angle);
		Console.Printf("UWUSE");
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS";
		if (wantUse)
		{
			// Hold still until the press arrives. This tic's player think already ran it when BT_USE shows here.
			if (!(players[0].cmd.buttons & BT_USE)) { p.vel = (0, 0, 0); p.angle = holdAngle; p.pitch = 0; return; }
			wantUse = false;
			Console.Printf("UWUSED");
		}
		timer++;
		if (timer > LIMIT) { Console.Printf("UWFAIL timeout in phase %d", phase); Finish("failed"); return; }
		switch (phase)
		{
		case 0: // Wait for Daggerfall, then Use on the wall beside the door.
			if (inside) { Console.Printf("UWFAIL a wall press entered the building"); Finish("failed"); return; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			Stand(p, 40, OFFSETS[tries]);
			if (timer == 35) Press(p, String.Format("wall offset %.0f", OFFSETS[tries]));
			if (timer == 80) { if (++tries >= OFFSETS.Size()) Next(1); else timer = 30; } // use_wall.py reads what each press named.
			break;
		case 1: // Info on the door from outside Use reach: names the door's building without entering.
			if (inside) { Console.Printf("UWFAIL Info entered from outside reach"); Finish("failed"); return; }
			Stand(p, 160, 0);
			if (timer == 20) { Console.Printf("UWINFO door"); EventHandler.SendNetworkEvent("df_info"); }
			if (timer == 60) Next(2);
			break;
		case 2: // Use on the door enters, as before.
			if (inside) { Console.Printf("UWCASE pass Use on the door entered the store"); Finish("route finished"); return; }
			Stand(p, 48, 0);
			if (timer == 20) Press(p, "door");
			if (timer > 35 * 20) { Console.Printf("UWCASE FAIL Use on the door did not enter"); Finish("failed"); }
			break;
		}
	}
}
