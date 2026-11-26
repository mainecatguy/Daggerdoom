version "4.14"

// Fixed drops on the overworld with DRLA (test only, loaded by tools/fixed_drops/overworld.py). The overworld's seeded
// packs spawn stock classes with replacement on, so DRLA turns each into a RandomSpawner. The test start (Daggerfall
// city, DDOVER01): wait for the packs, list them, kill the nearest pack (seeds and drops), warp far away and back
// (the packs park and come back), list what came back, kill everything left (seeds and drops). Static, so it survives
// the overworld handoffs of the warp. Every step prints a PO line.
class POHarness : StaticEventHandler
{
	int phase, timer, dropWatch;
	bool done;
	vector2 home;	// The player's spot when the first pack was killed, for positions relative to the player.

	void Finish(String how) { Console.Printf("PODONE %s", how); done = true; }

	override void WorldThingDied(WorldEvent e)
	{
		let a = e.Thing;
		if (done || !a || !a.bISMONSTER || a.player) return;
		Console.Printf("PODIED %s seed %08x phase %d", a.GetClassName(), a.DD_LootSeed(), phase);
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		let a = Inventory(e.Thing);
		if (done || dropWatch <= 0 || !a || a.Owner) return;
		Console.Printf("PODROP %s seed %08x phase %d", a.GetClassName(), a.DD_LootSeed(), phase);
	}

	int Census(String tag)
	{
		let p = players[0].mo;
		int alive, dead, spawners;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (a is "RandomSpawner") spawners++;
			if (!a.bISMONSTER || a.player) continue;
			if (a.health > 0) alive++; else dead++;
			vector2 rel = a.pos.xy - p.pos.xy;
			Console.Printf("POMON %s %s %s rel %d %d", tag, a.health > 0 ? "alive" : "dead", a.GetClassName(), int(rel.x) / 64, int(rel.y) / 64);
		}
		Console.Printf("POCENSUS %s alive %d dead %d randomspawners %d at %s", tag, alive, dead, spawners, level.MapName);
		return alive;
	}

	void Kill(Actor a, Actor p)
	{
		if (!a.bSHOOTABLE && a.SeeState) { a.target = p; a.SetState(a.SeeState); }
		a.DamageMobj(p, p, 100000, 'None', DMG_FORCED);
		if (a.health > 0) Console.Printf("POALIVE %s after the blow", a.GetClassName());
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		timer++;
		if (dropWatch > 0) dropWatch--;
		bool ready = level.MapName ~== "DDOVER01" && CVar.FindCVar("dd_sync_df_phase").GetInt() == 3;
		switch (phase)
		{
		case 0: // Arrived: give the treadmill time to spawn the window's packs.
			if (!ready) { timer = 0; break; }
			if (timer < 35 * 6) break;
			if (Census("start") == 0) { Finish("no monsters"); break; }
			phase = 1; timer = 0;
			break;
		case 1: // Kill the pack nearest the player.
		{
			if (timer < 35) break;
			Actor nearest;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next()))
				if (a.bISMONSTER && !a.player && a.health > 0 && (!nearest || p.Distance2D(a) < p.Distance2D(nearest))) nearest = a;
			Array<Actor> pack;
			it = ThinkerIterator.Create("Actor");
			while (a = Actor(it.Next()))
				if (a.bISMONSTER && !a.player && a.health > 0 && nearest.Distance2D(a) < 800) pack.Push(a);
			home = p.pos.xy;
			dropWatch = 35 * 3;
			for (int i = 0; i < pack.Size(); i++) Kill(pack[i], p);
			Console.Printf("POKILLED first %d", pack.Size());
			phase = 2; timer = 0;
			break;
		}
		case 2: // Let the drops land, list, then warp far away (the packs park).
			if (timer < 35 * 4) break;
			Census("before");
			CVar.FindCVar("dd_tm_warp").SetString("29592 36608");
			Console.Printf("POWARP away");
			phase = 3; timer = 0;
			break;
		case 3:
			if (timer < 35 * 2 || !ready) break;
			if (timer < 35 * 8) break;
			Census("away");
			CVar.FindCVar("dd_tm_warp").SetString("26656 36672");
			Console.Printf("POWARP back");
			phase = 4; timer = 0;
			break;
		case 4: // Back: list what came back, then kill everything alive.
		{
			if (timer < 35 * 2 || !ready) break;
			if (timer < 35 * 8) break;
			Census("back");
			dropWatch = 35 * 3;
			int n;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			Array<Actor> all;
			while (a = Actor(it.Next())) if (a.bISMONSTER && !a.player && a.health > 0) all.Push(a);
			for (int i = 0; i < all.Size(); i++) Kill(all[i], p);
			Console.Printf("POKILLED second %d", all.Size());
			phase = 5; timer = 0;
			break;
		}
		case 5:
			if (timer < 35 * 4) break;
			Census("end");
			Finish("finished");
			break;
		}
	}
}
