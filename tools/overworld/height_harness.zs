version "4.14"

// Measures how the player's feet and eye sit against the terrain the renderer draws.
// Mode "walk" drives the player over the ground. Mode "scan" samples floorz at many points.
// Prints HTRESULT lines, then OWDONE so the runner can close the game.
class OWHarness : EventHandler
{
	const TILE = 192.0;
	const WALK_TICS = 630;
	const SCAN_TICS = 240;
	const SCAN_PER_TIC = 256;
	const WALK_SPEED = 16.7;

	int tics, samples, sunk, eyeLow;
	double worstSink, worstFloat, worstEye, sumFloat, worstSinkX, worstSinkY, worstFloatX, worstFloatY, worstEyeX, worstEyeY, worstFloorzFloat;
	bool done;
	Vector3 home;

	override void OnRegister() { worstEye = 1000; }

	clearscope static int OX() { return CVar.FindCVar("dd_tm_originx").GetInt(); }
	clearscope static int OY() { return CVar.FindCVar("dd_tm_originy").GetInt(); }
	double TileX(double x) { return OX() + (x + 128 * TILE / 2) / TILE; }
	double TileY(double y) { return OY() + (y + 128 * TILE / 2) / TILE; }

	void Record(Actor p)
	{
		double ground = p.curSector.floorplane.ZAtPoint(p.pos.xy);
		double nz = abs(p.curSector.floorplane.Normal.z);
		double sink = ground - p.pos.z, rise = p.pos.z - ground;
		double eye = (p.player.viewz - ground) * nz;	// Distance from the eye to the surface, along its normal.
		samples++;
		sumFloat += rise;
		if (sink > 0.01) sunk++;
		if (eye < 8) eyeLow++;
		if (sink > worstSink) { worstSink = sink; worstSinkX = TileX(p.pos.x); worstSinkY = TileY(p.pos.y); }
		if (rise > worstFloat) { worstFloat = rise; worstFloatX = TileX(p.pos.x); worstFloatY = TileY(p.pos.y); }
		if (eye < worstEye) { worstEye = eye; worstEyeX = TileX(p.pos.x); worstEyeY = TileY(p.pos.y); }
	}

	void Finish(String mode)
	{
		Console.Printf("HTRESULT mode=%s samples=%d sunkTics=%d worstSink=%.3f at %.1f,%.1f worstFloat=%.3f at %.1f,%.1f meanFloat=%.3f worstEyeClearance=%.3f at %.1f,%.1f eyeUnder8=%d scanFloorzFloat=%.3f",
			mode, samples, sunk, worstSink, worstSinkX, worstSinkY, worstFloat, worstFloatX, worstFloatY, samples ? sumFloat / samples : 0, worstEye, worstEyeX, worstEyeY, eyeLow, worstFloorzFloat);
		Console.Printf("OWDONE");
		done = true;
	}

	override void WorldTick()
	{
		if (done || !players[consoleplayer].mo) return;
		Actor p = players[consoleplayer].mo;
		p.bInvulnerable = true;
		tics++;
		if (tics < 8) { home = p.pos; return; }
		String mode = "@MODE@";
		if (mode == "scan")
		{
			for (int n = 0; n < SCAN_PER_TIC; n++)
			{
				double x = frandom[HT](-10000, 10000), y = frandom[HT](-10000, 10000);
				Sector s = Level.PointInSector((x, y));
				double ground = s.floorplane.ZAtPoint((x, y));
				p.SetOrigin((x, y, ground), false);
				p.FindFloorCeiling();
				worstFloorzFloat = max(worstFloorzFloat, p.floorz - ground);
				samples++;
			}
			p.SetOrigin(home, false);
			p.FindFloorCeiling();
			if (tics >= SCAN_TICS) Finish(mode);
			return;
		}
		double a = 35 + 25 * sin(tics * 1.7);	// A wavering line, long enough to cross treadmill shifts and map pixel borders.
		p.vel.x = cos(a) * WALK_SPEED;
		p.vel.y = sin(a) * WALK_SPEED;
		if (tics > 16 && p.pos.z <= p.floorz + 0.01) Record(p);
		if (tics >= WALK_TICS) Finish(mode);
	}
}
