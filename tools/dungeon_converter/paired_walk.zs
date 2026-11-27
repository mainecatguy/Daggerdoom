version "4.14"

// Paired collision walk, after a real New Game in Privateer's Hold: from each spot, run in 16 headings and print the
// player's position every tic, so tools/dungeon_converter/paired_walk.py can count snags and floor steps.
// Movement is the engine's own: the player's speed is set each tic and the normal player move (slides, step-ups,
// slopes) does the rest. Test only, loaded by paired_walk.py.
class PWHarness : StaticEventHandler
{
	static const double SPOTS[] = { @SPOTS@ };
	const HEADINGS = 16;
	const RUN = 60;      // Tics per heading.
	const SPEED = 16.0;  // About a running player's top speed.
	int phase, timer, spot, heading, saves;
	bool done;

	void Start(PlayerPawn p)
	{
		// The nearest place the player fits, in rings of 8 units around the spot (a bevel next to a wall is too narrow).
		double x0 = SPOTS[spot * 2], y0 = SPOTS[spot * 2 + 1];
		for (int r = 0; r <= 96; r += 8)
		{
			bool fits = false;
			for (int k = 0; k < (r ? 16 : 1) && !fits; k++)
			{
				double x = x0 + cos(k * 22.5) * r, y = y0 + sin(k * 22.5) * r;
				p.SetOrigin((x, y, p.GetZAt(x, y, 0, GZF_ABSOLUTEPOS)), false);
				p.FindFloorCeiling();
				p.SetZ(p.floorz);
				fits = p.TestMobjLocation();
			}
			if (fits) break;
		}
		p.vel = (0, 0, 0);
		p.angle = heading * 360.0 / HEADINGS;
		p.pitch = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		timer++;
		switch (phase)
		{
		case 0: // The New Game arrival in the dungeon, with Daggerfall in play.
			if (!(level.MapName ~== "MAP01") || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			if (timer < 35 * 3) break;
			Console.Printf("PWARRIVED %s health %d", level.MapName, p.health);
			players[0].cheats |= CF_GODMODE;
			p.bNOTARGET = true;
			p.bTHRUACTORS = true; // Walls and floors only: a monster in the hall would spoil the measure.
			spot = 0; heading = 0;
			Start(p);
			phase = 1; timer = 0;
			break;
		case 1: // Daggerfall's position at the first spot, through a real synchronized autosave.
			if (timer == 10) { Console.Printf("PWSAVE 1 at %.1f %.1f %.1f", p.pos.x, p.pos.y, p.pos.z); level.MakeAutoSave(); }
			if (timer == 35 * 4) { phase = 2; timer = 0; Start(p); }
			break;
		case 2: // One heading: settle, then run.
			if (timer <= 4) { p.vel = (0, 0, 0); break; }
			if (timer == 5) Console.Printf("PWWALK %d %d %.1f %.1f %.1f", spot, heading, p.pos.x, p.pos.y, p.pos.z);
			else Console.Printf("PWT %.2f %.2f %.2f %d", p.pos.x, p.pos.y, p.pos.z, p.pos.z <= p.floorz + 0.01); // Where the last tic's move ended.
			if (timer <= 5 + RUN)
			{
				p.angle = heading * 360.0 / HEADINGS;
				p.vel.xy = (cos(p.angle), sin(p.angle)) * SPEED;
				break;
			}
			if (++heading == HEADINGS)
			{
				heading = 0;
				if (++spot * 2 >= SPOTS.Size()) { phase = 3; timer = 0; break; }
			}
			Start(p);
			timer = 0;
			break;
		case 3: // Daggerfall's position at the end of the last run.
			if (timer == 10) { Console.Printf("PWSAVE 2 at %.1f %.1f %.1f", p.pos.x, p.pos.y, p.pos.z); level.MakeAutoSave(); }
			if (timer == 35 * 5) { Console.Printf("PWDONE walked"); done = true; }
			break;
		}
	}
}
