version "4.14"

// Combined walk, after a real New Game: leave Privateer's Hold, go to Gothway Garden on the same map, count townspeople,
// press Use on one (twice), then ask the runner to press K for the travel map. Every step prints a DW line.
// Test only, loaded by tools/demo_combined/walk.py.
class DWHarness : StaticEventHandler // Static: it keeps its phase across map changes.
{
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 20;
	int phase, timer, talks;
	bool done;

	void Fail(String why) { Console.Printf("DWFAIL %s", why); Console.Printf("DWDONE failed"); done = true; }

	int Townsfolk(Actor from, out Actor nearest)
	{
		int n = 0;
		double best = 1e9;
		nearest = null;
		ThinkerIterator it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (a.GetClassName() != 'DFTownsperson') continue;
			n++;
			double d = a.Distance2D(from);
			if (d < best) { best = d; nearest = a; }
		}
		return n;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		bool inside = level.MapName ~== "MAP01";
		bool town = level.MapName.Left(3) ~== "DDT";
		timer++;
		switch (phase)
		{
		case 0: // Wait for the New Game arrival in the dungeon, with Daggerfall in play.
			if (!inside || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			if (timer < 35 * 3) break;
			Console.Printf("DWARRIVED %s health %d", level.MapName, p.health);
			players[0].cheats |= CF_GODMODE; // The walk is about the transitions, not the fights on the way.
			p.bNOTARGET = true;
			p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
			p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
			p.vel = (0, 0, 0);
			p.pitch = 0;
			phase = 1; timer = 0;
			break;
		case 1: // Use the exit door.
			if (timer == 8) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (town) { Console.Printf("DWTOWN %s", level.MapName); phase = 2; timer = 0; }
			else if (timer > LIMIT) Fail("the exit did not lead to town");
			break;
		case 2: // Privateer's Hold's exterior has no townsfolk. Gothway Garden's streets are on the same map.
			if (timer < 35 * 3) break;
			p.SetOrigin((3400, -6600, p.GetZAt(3400, -6600, 0, GZF_ABSOLUTEPOS)), false);
			p.vel = (0, 0, 0);
			Console.Printf("DWWALKTO Gothway Garden street at 3400,-6600");
			phase = 3; timer = 0;
			break;
		case 3: // Townspeople come from Daggerfall a little after arrival.
		{
			if (timer < 35 * 5) break;
			Actor near;
			int n = Townsfolk(p, near);
			if (n == 0) { if (timer > LIMIT) Fail("no townspeople"); break; }
			Console.Printf("DWTOWNSFOLK %d, nearest %.0f away", n, near.Distance2D(p));
			phase = 4; timer = 0;
			break;
		}
		case 4: // Stand in front of the nearest one and press Use, in the same tic, so it cannot walk off.
		{
			if (timer < 35 * 3) break; // Also leaves time for the runner to close a window from the first press.
			Actor near;
			Townsfolk(p, near);
			if (!near) { Fail("townsperson gone"); break; }
			p.SetOrigin((near.pos.xy + (cos(near.angle), sin(near.angle)) * 48, near.pos.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(near.pos.y - p.pos.y, near.pos.x - p.pos.x);
			p.pitch = 0;
			talks++;
			Console.Printf("DWTALK %d pressing Use on a townsperson at %.0f,%.0f", talks, near.pos.x, near.pos.y);
			EventHandler.SendNetworkEvent("df_interact");
			timer = 0;
			if (talks == 2) phase = 5;
			break;
		}
		case 5: // The runner presses K, which the engine turns into Daggerfall's travel map (Doom pauses while it is open).
			if (timer == 35 * 3) Console.Printf("DWTRAVEL press K now");
			if (timer == 35 * 6) { Console.Printf("DWDONE walked"); done = true; }
			break;
		}
	}
}
