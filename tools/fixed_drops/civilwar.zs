version "4.14"

// Fixed drops, Civil War: after a real New Game arrival in Privateer's Hold (or a bundled load), let the two Civil War
// armies fight unfrozen with the player out of it (god mode, no target), and print the war's state at fixed war times.
// War time counts from the tic the war's thinker first appears, so it does not depend on when or how the player came.
// Modes (@MODE@): 0 watch; 1 watch and save at war time SAVE_AT; 2 the load of mode 1's autosave; 3 watch while the
// player walks about and burns numbers from Doom's shared random streams every tic; 4 the player kills, at war time
// KILL_AT, exactly the monsters listed in @KILLS@ (those the other army killed in a mode 0 run), so their drops can be
// compared. In every mode the rest is made dormant at the end and the new loose items are listed.
// Test only, loaded by tools/fixed_drops/civilwar.py. Every line starts with CW.
class CWHarness : EventHandler // Not static: a bundled load restores its state from the save.
{
	const SNAP1 = 35 * 6;
	const SAVE_AT = 35 * 3;
	const END_AT = 35 * 12;
	const KILL_AT = 35 * 2;
	const SETTLE = 35 * 8;
	static int Mode() { return @MODE@; }
	static String Kills() { return "@KILLS@"; }

	int warStart, timer, phase;
	bool done, resumed, saved;
	vector3 start;
	Array<Actor> before;

	void Finish(String how) { Console.Printf("CWDONE %s", how); done = true; }

	static bool InWar(Actor a) { return a && a.bISMONSTER && !a.player && (a.tid == 31741 || a.tid == 31742); }

	static String Id(Actor a) { return String.Format("%s %.1f %.1f", a.GetClassName(), a.SpawnPoint.x, a.SpawnPoint.y); }

	override void WorldThingDied(WorldEvent e)
	{
		if (done || !e.Thing || !e.Thing.bISMONSTER || e.Thing.player || warStart <= 0) return;
		String by = "other";
		if (e.Inflictor && e.Inflictor.player) by = "player";
		else if (e.Thing.target && e.Thing.target.player) by = "player";
		Console.Printf("CWDIED %d %s seed %08x war %d by %s", level.maptime - warStart, Id(e.Thing), e.Thing.DD_LootSeed(), InWar(e.Thing), by);
	}

	void Snapshot(String tag)
	{
		int alive = 0, dead = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (!InWar(a) && !(a.bISMONSTER && !a.player && a.health <= 0)) continue;
			if (a.health > 0) { alive++; Console.Printf("CWALIVE %s %s hp %d at %d %d %d", tag, Id(a), a.health, a.pos.x, a.pos.y, a.pos.z); }
			else { dead++; Console.Printf("CWDEAD %s %s seed %08x", tag, Id(a), a.DD_LootSeed()); }
		}
		Console.Printf("CWSNAP %s at war %d: %d alive, %d dead", tag, level.maptime - warStart, alive, dead);
	}

	// The end: no more deaths. Every monster becomes dormant and every shot in flight goes, so only death sequences run on.
	void StopFighting()
	{
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (a.bMISSILE) a.Destroy();
			else if (a.bISMONSTER && !a.player && a.health > 0) a.Deactivate(null);
		}
	}

	void ListDrops()
	{
		let it = ThinkerIterator.Create("Inventory");
		Inventory a;
		int n = 0;
		while (a = Inventory(it.Next()))
		{
			if (a.Owner || before.Find(a) != before.Size()) continue;
			n++;
			Console.Printf("CWDROP %s seed %08x", a.GetClassName(), a.DD_LootSeed());
		}
		Console.Printf("CWDROPS %d", n);
	}

	void KillListed(PlayerPawn p)
	{
		Array<String> want;
		Kills().Split(want, ";", TOK_SKIPEMPTY);
		int killed = 0, missing = 0;
		for (int i = 0; i < want.Size(); i++)
		{
			Actor found = null;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next())) if (a.bISMONSTER && !a.player && Id(a) == want[i]) { found = a; break; }
			if (!found || found.health <= 0) { missing++; Console.Printf("CWNOTFOUND %s", want[i]); continue; }
			if (!found.bSHOOTABLE && found.SeeState) { found.target = p; found.SetState(found.SeeState); }
			// Exactly its health: a plain death, as most deaths in the war are, not an overkill.
			found.DamageMobj(p, p, found.health, 'None', DMG_FORCED);
			if (found.health > 0) Console.Printf("CWALIVEAFTER %s", want[i]); else killed++;
		}
		Console.Printf("CWKILLED %d of %d, %d missing", killed, want.Size(), missing);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		if (Mode() == 2 && !saved) return; // The load run waits for the bridge to bring back mode 1's autosave.
		if (Mode() == 2 && !resumed) { resumed = true; Console.Printf("CWRESUMED %s at war %d", level.MapName, level.maptime - warStart); }
		if (Mode() == 3)
		{
			// Someone else in the world: other draws from every shared stream, a different amount each tic.
			for (int i = 0; i < 1 + level.maptime % 7; i++)
			{
				random(); random[Chase](); random[TryWalk](); random[NewChaseDir](); random[LookForPlayers]();
				random[CheckMissileRange](); random[DamageMobj](); frandom[Spread](0, 1);
			}
		}
		if (warStart <= 0)
		{
			if (!(level.MapName ~== "MAP01") || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) return;
			if (!ThinkerIterator.Create("DoomerfallCivilWar", Thinker.STAT_USER).Next()) return;
			warStart = level.maptime;
			start = p.pos;
			Console.Printf("CWWAR started at map time %d, player at %.0f %.0f %.0f", warStart, p.pos.x, p.pos.y, p.pos.z);
			let it = ThinkerIterator.Create("Inventory");
			Inventory a;
			while (a = Inventory(it.Next())) if (!a.Owner) before.Push(a);
			return;
		}
		int t = level.maptime - warStart;
		if (Mode() == 3)
		{
			// A different route: the player paces about the start instead of standing still.
			double ang = t * 3.0;
			p.vel.xy = (cos(ang), sin(ang)) * 4;
			p.angle = ang;
		}
		if (Mode() == 1 && t == SAVE_AT && !saved)
		{
			saved = true; // Written after this tic: the load run resumes with saved set.
			Console.Printf("CWSAVE at war %d", t);
			LevelLocals.MakeAutoSave();
		}
		if (Mode() == 4)
		{
			if (t == KILL_AT) { Snapshot("kill"); KillListed(p); StopFighting(); }
			if (t == KILL_AT + SETTLE) { ListDrops(); Finish("passed"); }
			return;
		}
		if (t == SNAP1) Snapshot("mid");
		if (t == END_AT) { Snapshot("end"); StopFighting(); }
		if (t == END_AT + SETTLE) { ListDrops(); Finish("passed"); }
	}
}
