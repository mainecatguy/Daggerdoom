version "4.14"

// Test only. After a real New Game: leaves the dungeon, walks inside the start map pixel, crosses into the next
// pixel on foot, then asks for the fast travel menu. Prints LOCSTEP lines for the runner.
class RLHarness : StaticEventHandler
{
	static const double EXITSPOT[] = { @EXIT@ };	// x, y, z, nx, ny
	const PIXEL_TILES = 128;
	const SPACING = 192;
	const HALF = 128 * 192 / 2;
	const HOLD = 70;
	const WALK_STEP = 20;
	int phase, timer;

	void Next(String label)
	{
		Console.Printf("LOCSTEP %d %s", phase, label);
		phase++;
		timer = 0;
	}

	void Walk(PlayerPawn p)
	{
		Vector2 to = p.pos.xy + (WALK_STEP, 0);
		p.SetOrigin((to, p.CurSector.NextLowestFloorAt(to.x, to.y, p.pos.z + 64)), false);
		p.vel = (0, 0, 0);
	}

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		let p = PlayerPawn(players[0].mo);
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		bool ready = CVar.FindCVar("dd_sync_df_phase").GetInt() == 3;
		CVar.FindCVar("dd_ui_test_hold").SetInt(phase < 7 ? 1 : 0);	// -dfuitest opens the travel menu once this route lets it.
		timer++;
		switch (phase)
		{
		case 0:	// The real start, inside the dungeon.
			if (inside && ready && timer > HOLD) Next("in the start dungeon");
			break;
		case 1:	// Stand at the exit and press Use.
			if (!inside) { Next("through the exit"); break; }
			p.SetOrigin((EXITSPOT[0] + EXITSPOT[3] * 40, EXITSPOT[1] + EXITSPOT[4] * 40, EXITSPOT[2]), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-EXITSPOT[4], -EXITSPOT[3]);
			if (timer == 6) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 2:
			if (ready && timer > HOLD) Next("outside the dungeon door");
			break;
		case 3:	// On foot, east out of the location's own map onto open ground, still in the same map pixel.
			if (!(level.MapName ~== "DDOVER01") && timer < 900) Walk(p);
			else if (ready && timer > HOLD) Next(String.Format("walked away from the entrance on %s, same pixel", level.MapName));
			break;
		case 4:	// Close to the east edge of the start pixel.
		{
			// Doom's overworld tile under the player, from the window origin. One tile is 192 Doom units.
			int tx = CVar.FindCVar("dd_tm_originx").GetInt() + int((p.pos.x + HALF) / SPACING);
			int ty = CVar.FindCVar("dd_tm_originy").GetInt() + int((p.pos.y + HALF) / SPACING);
			CVar.FindCVar("dd_tm_warp").SetString(String.Format("%d %d", (tx / PIXEL_TILES) * PIXEL_TILES + PIXEL_TILES - 4, ty));
			Next(String.Format("warped near the east edge from tile %d,%d", tx, ty));
			break;
		}
			break;
		case 5:
			if (ready && timer > HOLD) Next("standing near the east edge");
			break;
		case 6:	// On foot across the map pixel border.
			if (timer <= 70) Walk(p);
			else if (ready && timer > 70 + HOLD) Next("walked into the next pixel");
			break;
		case 7:
			Next("ready for the fast travel menu");	// The runner presses the bound key, as a player would.
			break;
		}
	}
}
