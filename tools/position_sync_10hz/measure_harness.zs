version "4.14"

// Measurement route. Waits for Daggerfall, walks outdoors, or goes through a door, walks the room, and leaves.
class PSHarness : StaticEventHandler	// Static, so the route survives the map change at each door.
{
	const WALK_TICS = 420;
	const OUT_SPEED = 20.0;
	const IN_SPEED = 8.0;
	static const double DOOR[] = { @DOOR@ };	// x, y, z, nx, ny
	static const double EXIT[] = { @EXIT@ };	// x, y, z, nx, ny; all zero means return to the landing
	int phase, timer;
	double startX, startY, startZ, startAngle;
	bool done;

	bool Inside() { return level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01"; }
	bool DaggerfallReady() { return CVar.FindCVar("dd_sync_df_phase").GetInt() == 3; }
	void Finish() { Console.Printf("PSDONE"); done = true; }

	override void WorldTick()
	{
		let p = players[0].mo;
		if (done || !p) return;
		p.player.cheats |= CF_GODMODE;
		timer++;
		if (@OUTDOOR@) { Outdoor(p); return; }
		switch (phase)
		{
		case 0:	// Stand at the door until both games are ready.
			if (Inside() || level.maptime < 8 || !DaggerfallReady()) break;
			p.SetOrigin((DOOR[0] + DOOR[3] * 48, DOOR[1] + DOOR[4] * 48, DOOR[2]), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-DOOR[4], -DOOR[3]);
			if (timer < 70) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			phase = 1;
			timer = 0;
			break;
		case 1:
			if (Inside()) { phase = 2; timer = 0; break; }
			if (timer > 700) { Console.Printf("PSFAIL door did not open"); Finish(); }
			break;
		case 2:	// Let Daggerfall arrive, then walk a turning path with real collision.
			if (timer == 2) { startX = p.pos.x; startY = p.pos.y; startZ = p.pos.z; startAngle = p.angle; }
			if (timer < 70 || !DaggerfallReady()) { if (timer > 700) { Console.Printf("PSFAIL Daggerfall did not follow"); Finish(); } break; }
			if (timer == 70) Console.Printf("PSWALK start %.1f,%.1f", p.pos.x, p.pos.y);
			p.angle += 2.5;
			p.vel.xy = Actor.AngleToVector(p.angle, IN_SPEED);
			if (timer >= 70 + WALK_TICS)
			{
				Console.Printf("PSWALK end %.1f,%.1f moved %.1f", p.pos.x, p.pos.y, (p.pos.xy - (startX, startY)).Length());
				p.vel = (0, 0, 0);
				if (EXIT[0] != 0 || EXIT[1] != 0)
				{
					p.SetOrigin((EXIT[0] + EXIT[3] * 40, EXIT[1] + EXIT[4] * 40, EXIT[2]), false);
					p.angle = atan2(-EXIT[4], -EXIT[3]);
				}
				else
				{
					p.SetOrigin((startX, startY, startZ), false);
					p.angle = startAngle + 180;
				}
				phase = 3;
				timer = 0;
			}
			break;
		case 3:
			p.vel = (0, 0, 0);
			if (timer == 6) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!Inside()) { phase = 4; timer = 0; }
			else if (timer > 210) { Console.Printf("PSFAIL exit did not work"); Finish(); }
			break;
		case 4:
			if (timer > 70) Finish();
			break;
		}
	}

	void Outdoor(Actor p)
	{
		if (phase == 0)
		{
			if (!DaggerfallReady()) return;
			phase = 1;
			timer = 0;
			Console.Printf("PSWALK outdoor start");
		}
		if (timer < 70) return;
		double along = timer < 70 + WALK_TICS / 2 ? 0 : 90;
		p.vel.xy = Actor.AngleToVector(along, OUT_SPEED);
		if (timer >= 70 + WALK_TICS) { p.vel = (0, 0, 0); if (timer > 140 + WALK_TICS) Finish(); }
	}
}
