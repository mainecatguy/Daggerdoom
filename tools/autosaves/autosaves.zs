version "4.14"

// Map change autosaves, test only (tools/autosaves/autosaves.py). Starts in Gothway Garden, walks east out of town into
// the wilderness, walks back into town, goes into a building through its real door, and back out. Each arrival prints
// an AS line with the map and Doom position; the bridge log shows the autosave each change made.
class ASHarness : StaticEventHandler // Static: it keeps its phase across map changes.
{
	static const double DOOR[] = { @DOOR@ };
	const LIMIT = 35 * 40;
	const STEP = 40;
	int phase, timer;
	vector3 arrival;
	double arrivalAngle;
	bool done;

	void Finish(String why) { Console.Printf("ASDONE %s", why); done = true; }
	void Fail(String why) { Console.Printf("ASFAIL %s", why); Finish("failed"); }

	void Arrived(PlayerPawn p, String what)
	{
		arrival = p.pos;
		arrivalAngle = p.angle;
		Console.Printf("ASARRIVE %s map=%s pos=%.1f,%.1f,%.1f angle=%.1f tic=%d", what, level.MapName, p.pos.x, p.pos.y, p.pos.z, p.angle, level.maptime);
	}

	void Walk(PlayerPawn p, double dx)
	{
		vector2 to = p.pos.xy + (dx, 0);
		p.SetOrigin((to, p.GetZAt(to.x, to.y, 0, GZF_ABSOLUTEPOS)), false);
		p.vel = (0, 0, 0);
		p.angle = dx > 0 ? 0 : 180;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		bool town = level.MapName ~== "DDT07154", wild = level.MapName ~== "DDOVER01", inside = level.MapName.Left(3) ~== "DDS";
		timer++;
		switch (phase)
		{
		case 0: // Both games in play in town.
			if (!town || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			if (timer < 35 * 4) break;
			players[0].cheats |= CF_GODMODE; // The test is about map changes, not fights.
			p.bNOTARGET = true;
			Arrived(p, "start");
			phase = 1; timer = 0;
			break;
		case 1: // Walk east until the town hands over to the wilderness.
			if (wild) { Arrived(p, "wilderness"); phase = 2; timer = 0; break; }
			if (timer > LIMIT) { Fail("never left town"); break; }
			Walk(p, STEP);
			break;
		case 2: // Stand a moment, then walk back west into town.
			if (town) { Arrived(p, "town"); phase = 3; timer = 0; break; }
			if (timer > 35 * 4 + LIMIT) { Fail("never came back into town"); break; }
			if (timer > 35 * 4) Walk(p, -STEP);
			break;
		case 3: // Into a building through its real door.
			if (inside) { Arrived(p, "building"); phase = 4; timer = 0; break; }
			if (timer > 35 * 4 + LIMIT) { Fail("the door did not lead inside"); break; }
			if (timer < 35 * 4 || timer % (35 * 3) != 1) break;
			p.SetOrigin((DOOR[0] + DOOR[3] * 48, DOOR[1] + DOOR[4] * 48, DOOR[2]), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-DOOR[4], -DOOR[3]);
			p.pitch = 0;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 4: // Back out through the door the player came in by, which is behind the arrival point.
			if (town) { Arrived(p, "outside"); phase = 5; timer = 0; break; }
			if (timer > 35 * 4 + LIMIT) { Fail("could not leave the building"); break; }
			if (timer < 35 * 4 || timer % (35 * 3) != 1) break;
			p.SetOrigin(arrival, false);
			p.vel = (0, 0, 0);
			p.angle = arrivalAngle + 180;
			p.pitch = 0;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 5:
			if (timer == 35 * 4) Finish("walked");
			break;
		}
	}
}

// The load run: reports where Doom's player is once the loaded game runs.
class ASLoadHarness : StaticEventHandler
{
	int wait;

	override void WorldLoaded(WorldEvent e) { if (e.IsSaveGame) wait = 35 * 3; }

	override void WorldTick()
	{
		if (wait <= 0 || --wait > 0 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		Console.Printf("ASLOADED map=%s pos=%.1f,%.1f,%.1f angle=%.1f health=%d", level.MapName, p.pos.x, p.pos.y, p.pos.z, p.angle, p.health);
	}
}
