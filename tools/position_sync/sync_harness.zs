version "4.14"

// Position sync route. Waits for Daggerfall, then runs across map pixel borders on both axes.
class OWHarness : EventHandler
{
	const SPEED = 60.0;
	const HOLD_TICS = 175;	// Long enough for an awake enemy beside the player to attack.
	const EAST_TICS = 260;	// The route starts mid-pixel, 205 tics from the border.
	const NORTH_TICS = 260;
	int phase, ticsInPhase;
	bool done;

	override void WorldTick()
	{
		let p = players[0].mo;
		if (done || !p || level.MapName != "DDOVER01") return;
		p.player.cheats |= CF_GODMODE;
		if (phase == 0)
		{
			if (CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) return;
			Console.Printf("SYNCROUTE Daggerfall ready at tic %d", level.maptime);
			phase = 1;
		}
		ticsInPhase++;
		if (phase == 1 && ticsInPhase >= HOLD_TICS) { phase = 2; ticsInPhase = 0; }
		else if (phase == 2)
		{
			p.vel.xy = (SPEED, 0);
			if (ticsInPhase >= EAST_TICS) { phase = 3; ticsInPhase = 0; }
		}
		else if (phase == 3)
		{
			p.vel.xy = (0, SPEED);
			if (ticsInPhase >= NORTH_TICS) { phase = 4; ticsInPhase = 0; p.vel.xy = (0, 0); }
		}
		else if (phase == 4 && ticsInPhase >= 70)
		{
			Console.Printf("OWDONE");
			done = true;
			level.ChangeLevel("MAP01", 0, CHANGELEVEL_NOINTERMISSION);	// Leaving Daggerfall's world must release its hidden player.
		}
	}
}
