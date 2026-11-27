// Test hook: with +set dd_burn_test N (N monsters), spawns N ZombieMen around the player on the first map, sets them
// burning, and prints "BURNTEST" lines ending with "BURNTEST done". tools/burn/run_test.py runs it.
//   pack      every monster gets two stacks of 300 (unlimited stacking) and must lose exactly 600 in about 3 s.
//   take      one extra monster gets 300, then Take(0.5) must return 150 and it must lose only the other 150.
//   player    Apply on the player must do nothing.
//   timing    the burn handler's own cost per tic and the largest real gap between tics while the pack burns.
// Registered just before DoomerfallBurn (MAPINFO order), so the gap to DoomerfallBurnTest is the burn handler's own tick.
class DoomerfallBurnTestClock : EventHandler
{
	double stamp;
	override void WorldTick() { stamp = MSTimeF(); }
}

class DoomerfallBurnTest : EventHandler
{
	const HP = 100000;
	Array<Actor> pack;
	Actor taker, frac, tiny, whole;
	bool takeAllOk;
	int startTic, playerStart;
	double tookBack, lastMs, maxGapMs, burnMsTotal, burnMsMax;
	int gaps;
	bool done;

	override void WorldTick()
	{
		if (done) return;
		let flag = CVar.FindCVar("dd_burn_test");
		int n = flag ? flag.GetInt() : 0;
		if (n <= 0) return;
		let pl = players[consoleplayer].mo;
		if (!pl) return;
		if (Level.maptime == 10) Start(pl, n);
		if (startTic == 0) return;
		int t = Level.maptime - startTic;
		double now = MSTimeF();
		if (t > 2 && t < 105) { maxGapMs = max(maxGapMs, now - lastMs); burnMsTotal += now - lastMs; gaps++; }
		lastMs = now;
		let clock = DoomerfallBurnTestClock(EventHandler.Find("DoomerfallBurnTestClock"));
		if (clock && t > 0 && t < 105) burnMsMax = max(burnMsMax, now - clock.stamp);
		if (t == 50)
		{
			// Take(1.0) after some payouts (non-integer pool with carry) must return the whole Pool and leave nothing.
			double before = DoomerfallBurn.Pool(whole);
			double got = DoomerfallBurn.Take(whole, 1.0);
			takeAllOk = before > 0 && abs(got - before) < 0.0001 && DoomerfallBurn.Pool(whole) < 0.0001;
			Console.Printf("BURNTEST takeall pool=%.3f took=%.3f left=%.3f", before, got, DoomerfallBurn.Pool(whole));
		}
		if (t == 140) Finish(pl);
	}

	void Start(Actor pl, int n)
	{
		players[consoleplayer].cheats |= CF_NOTARGET;
		playerStart = pl.health;
		int side = int(ceil(sqrt(n)));
		for (int i = 0; i < n; i++)
		{
			let m = Actor.Spawn("ZombieMan", pl.Vec3Offset(64 + (i % side) * 24, ((i / side) - side / 2) * 24, 0), NO_REPLACE);
			if (!m) continue;
			m.health = HP;
			pack.Push(m);
			// No source: a burning monster turns on its burner (normal pain behaviour) and would shoot the pack.
			DoomerfallBurn.Apply(m, 300, null);
			DoomerfallBurn.Apply(m, 300, null);
		}
		taker = Actor.Spawn("ZombieMan", pl.Vec3Offset(-64, 0, 0), NO_REPLACE);
		taker.health = HP;
		DoomerfallBurn.Apply(taker, 300, null);
		tookBack = DoomerfallBurn.Take(taker, 0.5);
		frac = Actor.Spawn("ZombieMan", pl.Vec3Offset(-64, 64, 0), NO_REPLACE);
		frac.health = HP;
		DoomerfallBurn.Apply(frac, 10.5, null);
		DoomerfallBurn.Apply(frac, 0.9, null);
		tiny = Actor.Spawn("ZombieMan", pl.Vec3Offset(-64, -64, 0), NO_REPLACE);
		tiny.health = HP;
		DoomerfallBurn.Apply(tiny, 0.9, null);
		whole = Actor.Spawn("ZombieMan", pl.Vec3Offset(-128, 0, 0), NO_REPLACE);
		whole.health = HP;
		DoomerfallBurn.Apply(whole, 7.3, null);
		DoomerfallBurn.Apply(pl, 500, null);
		Console.Printf("BURNTEST start monsters=%d pool0=%.1f look=%d", pack.Size(), pack.Size() ? DoomerfallBurn.Pool(pack[0]) : 0, DoomerfallBurnLook.Enabled());
		startTic = Level.maptime;
		lastMs = MSTimeF();
	}

	void Finish(Actor pl)
	{
		done = true;
		int ok = 0, bad = 0;
		for (int i = 0; i < pack.Size(); i++)
		{
			int lost = pack[i] ? HP - pack[i].health : -1;
			if (lost == 600) ok++;
			else { bad++; if (bad <= 5) Console.Printf("BURNTEST pack-bad index=%d lost=%d", i, lost); }
		}
		int takerLost = taker ? HP - taker.health : -1;
		Console.Printf("BURNTEST pack ok=%d bad=%d %s", ok, bad, bad == 0 && ok > 0 ? "PASS" : "FAIL");
		Console.Printf("BURNTEST take returned=%.1f lost=%d %s", tookBack, takerLost, abs(tookBack - 150) < 0.01 && takerLost == 150 ? "PASS" : "FAIL");
		Console.Printf("BURNTEST player pool=%.1f lost=%d %s", DoomerfallBurn.Pool(pl), playerStart - pl.health, DoomerfallBurn.Pool(pl) == 0 && pl.health == playerStart ? "PASS" : "FAIL");
		// 10.5 + 0.9 = 11.4: 11 always, the last 0.4 by chance. 0.9 alone: 0 or 1. Neither may lose its tail.
		int fracLost = HP - frac.health, tinyLost = HP - tiny.health;
		bool fracOk = (fracLost == 11 || fracLost == 12) && (tinyLost == 0 || tinyLost == 1) && !DoomerfallBurn.Burning(frac) && !DoomerfallBurn.Burning(tiny);
		Console.Printf("BURNTEST fraction lost11.4=%d lost0.9=%d takeall=%d %s", fracLost, tinyLost, takeAllOk, fracOk && takeAllOk ? "PASS" : "FAIL");
		Console.Printf("BURNTEST timing tics=%d max_gap_ms=%.2f avg_gap_ms=%.2f burn_tick_max_ms=%.3f", gaps, maxGapMs, gaps ? burnMsTotal / gaps : 0, burnMsMax);
		Console.Printf("BURNTEST done");
	}
}
