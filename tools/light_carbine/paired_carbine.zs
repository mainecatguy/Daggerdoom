version "4.14"

// Light Carbine on a Daggerfall map (test only, loaded by tools/light_carbine/paired_carbine.py): a carbine that
// replaced a dropped Battle Rifle keeps the rifle's loot identity, so Daggerfall names it with a fixed material.
// A real New Game in Privateer's Hold with DRLA: kill the start's monsters (as tools/droplabel/droplabel.zs), list every
// Battle Rifle and carbine they dropped with its loot seed, carry one carbine to a clear spot, look at it and take it.
// Every step prints a PDC line; the Daggerfall take is in Daggerfall's log.
class PDCarbine : StaticEventHandler
{
	const RADIUS = 1200;
	const LOOKTICS = 105;

	int phase, timer;
	bool done;
	vector3 start;
	Array<Actor> before;
	Actor gun;

	void Finish(String how) { Console.Printf("PDDONE %s", how); done = true; }

	void PressUse(PlayerPawn p)
	{
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	static double ClearAngle(PlayerPawn p, double dist = 160)
	{
		for (int a = 0; a < 360; a += 45)
		{
			FLineTraceData t;
			if (!p.LineTrace(a, dist, 0, TRF_THRUACTORS, 16, 0, 0, t) || t.HitType == TRACE_HitNone) return a;
		}
		return 0;
	}

	override void WorldTick()
	{
		if (done || !players[0].mo) return;
		let p = PlayerPawn(players[0].mo);
		timer++;
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		bool inside = level.MapName ~== "MAP01";
		bool ready = CVar.FindCVar("dd_sync_df_phase").GetInt() == 3;
		if (phase < 2 || (phase == 2 && timer < 35)) level.SetFrozen(true);
		switch (phase)
		{
		case 0:
			if (!inside || !ready) { timer = 0; break; }
			if (timer < 35 * 3) break;
			start = p.pos;
			Console.Printf("PDCARRIVED %s at %.0f %.0f %.0f", level.MapName, p.pos.x, p.pos.y, p.pos.z);
			phase = 2; timer = 0;
			break;
		case 2:
		{
			if (timer < 35) break;
			level.SetFrozen(false);
			before.Clear();
			Array<Actor> victims;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next()))
			{
				if (a is "Inventory" && !Inventory(a).Owner) before.Push(a);
				if (!a.bISMONSTER || a.player || a.health <= 0) continue;
				if ((a.SpawnPoint - (380, 1270, 0)).Length() < RADIUS) victims.Push(a); else a.Deactivate(null);
			}
			for (int i = 0; i < victims.Size(); i++)
			{
				a = victims[i];
				if (!a.bSHOOTABLE && a.SeeState) { a.target = p; a.SetState(a.SeeState); }
				a.DamageMobj(p, p, 100000, 'None', DMG_FORCED);
			}
			Console.Printf("PDCKILLED %d", victims.Size());
			phase = 3; timer = 0;
			break;
		}
		case 3: // Every Battle Rifle and carbine the kills dropped, with its seed. The carbine with the lowest seed is taken.
		{
			if (timer < 35 * 8) break;
			int rifles, carbines, unseeded;
			uint best = 0;
			let it = ThinkerIterator.Create("Inventory");
			Inventory a;
			while (a = Inventory(it.Next()))
			{
				if (a.Owner || before.Find(a) != before.Size()) continue;
				String n = a.GetClassName();
				bool carbine = n == "DoomerfallLightCarbine";
				if (!carbine && n != "RLBattleRiflePickup") continue;
				uint seed = a.DD_LootSeed();
				if (carbine) carbines++; else rifles++;
				if (!seed) unseeded++;
				Console.Printf("PDCDROP %s seed %08x", n, seed);
				if (carbine && seed && (!gun || seed < best)) { gun = a; best = seed; }
			}
			Console.Printf("PDCDROPS rifles %d carbines %d unseeded %d", rifles, carbines, unseeded);
			if (!gun) { Finish("nocarbine"); break; }
			p.SetOrigin(start, false);
			p.vel = (0, 0, 0);
			p.angle = ClearAngle(p);
			gun.SetOrigin((start.xy + Actor.AngleToVector(p.angle, 96), start.z), false);
			gun.vel = (0, 0, 0);
			Console.Printf("PDCTAKE DoomerfallLightCarbine seed %08x", best);
			phase = 4; timer = 0;
			break;
		}
		case 4: // Look (the label asks Daggerfall for the material), then take.
			if (timer == 1)
			{
				p.SetOrigin((gun.pos.xy - Actor.AngleToVector(p.angle, 48), gun.pos.z), false);
				p.vel = (0, 0, 0);
				p.pitch = 0;
			}
			if (timer <= LOOKTICS) break;
			if (timer == LOOKTICS + 1) { Console.Printf("PDCUSE"); PressUse(p); }
			if (timer < LOOKTICS + 10) break;
			if (!gun || !gun.bSPECIAL) { Console.Printf("PDCTAKEN"); phase = 5; timer = 0; }
			else if (timer > LOOKTICS + 35 * 5) Finish("carbine still on the floor");
			break;
		case 5: // Give Daggerfall time to log the take.
			if (timer > 35 * 3) Finish("passed");
			break;
		}
	}
}
