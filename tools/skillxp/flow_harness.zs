version "4.14"

// Skill XP in a real New Game session (skillxp.py flow, through tools/new_game/run_new_game.py create): once the new
// character has arrived and Daggerfall is in play (dd_sync_df_phase 3), every 6 seconds it spawns a Baron of Hell in
// front of the player and, a second later, hurts every living monster near the player for far more than its health
// as the player, so the mod reports Skill XP to Daggerfall as in play.
class SXFlowHarness : StaticEventHandler // static: a loaded save restores only the level handlers it holds
{
	int ready;

	override void OnRegister() { Console.Printf("SXFLOWREGISTERED"); }

	override void WorldTick()
	{
		if (level.maptime % 350 == 1) Console.Printf("SXFLOWTICK maptime %d player %d", level.maptime, playeringame[0] && players[0].mo);
		if (!playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE;
		let phase = CVar.FindCVar("dd_sync_df_phase");
		int ph = phase ? phase.GetInt() : -1;
		if (!ready && level.maptime % 175 == 0) Console.Printf("SXFLOWWAIT maptime %d phase %d", level.maptime, ph);
		// Phase 3 is Daggerfall in play; a loaded flow session may not report it here, so 10 s of map time also counts.
		if (!ready && (ph == 3 || level.maptime >= 350)) { ready = level.maptime; Console.Printf("SXFLOWREADY at %d, phase %d", ready, ph); }
		if (!ready) return;
		int t = level.maptime - ready;
		if (t == 35 * 24) Console.Printf("SXFLOWDONE");
		if (t < 35 * 3 || t > 35 * 20) return;
		if (t % (35 * 6) == 0)
		{
			let mo = Actor.Spawn('BaronOfHell', p.Vec3Angle(160, p.angle), ALLOW_REPLACE);
			if (mo) Console.Printf("SXFLOWSPAWN %s", mo.GetClassName());
		}
		if (t % (35 * 6) == 35)
		{
			Actor mo;
			let it = ThinkerIterator.Create("Actor");
			while (mo = Actor(it.Next()))
			{
				if (!mo.bIsMonster || mo.health <= 0 || mo.bFriendly || mo.Distance2D(p) > 700) continue;
				int h = mo.health;
				int taken = mo.DamageMobj(p, p, 100000, 'None');
				Console.Printf("SXFLOWHIT %s health %d, took %d", mo.GetClassName(), h, taken);
			}
		}
	}
}
