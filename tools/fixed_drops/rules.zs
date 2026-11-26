version "4.14"

// Fixed drops, the owner's rules for monsters Daggerfall did not place (2026-11-25), with Daggerfall and Doom together.
// Test only, loaded by tools/fixed_drops/rules.py. Every step prints an RL line (prefixed PD so the harness keeps it).
// Static, so it keeps its state across the dungeon exit and re-entry of the revisit mode.
//   0 revisit (DRLA, skill 3): a placed monster killed, raised by a stock Arch-vile and killed again drops nothing the
//     second time. A second one is raised and left alive, a Pain Elemental's Lost Soul is summoned and left alive, and
//     an id-less DRLA Adaptive spawner is held in its first state. The player leaves the dungeon and comes back; the
//     raised monster and the soul are killed and drop nothing, and the held spawner was not stored and brought back.
//   1 roster (DRLA Adaptive or Armageddon skill, the encounter planner removed so placements use the stock roster with
//     the skill's replacements): every monster on the level is killed; every death is listed with its loot seed, which
//     is nonzero only for a monster holding a Daggerfall id, and the drops are listed with theirs.
class PDRules : StaticEventHandler
{
	static const double DOORSPOT[] = { @DOOR@ };	// The dungeon door on DDT07154: x, y, z, nx, ny.
	static const double EXITSPOT[] = { 834.750, 342.750, 1153.500, 0.7071, 0.7071 };	// Privateer's Hold's exit (DDDUNGN).
	static int Mode() { return @MODE@; }
	int phase, timer, deaths, seeded, unseeded;
	bool done;
	Array<Actor> looseBefore;
	Actor v1, v2, soul, held;
	vector3 v2At, soulAt, heldAt;
	String v2Class, soulClass;

	void Finish(String how) { Console.Printf("PDDONE %s", how); done = true; }

	void Snapshot()
	{
		looseBefore.Clear();
		let it = ThinkerIterator.Create("Inventory");
		Inventory a;
		while (a = Inventory(it.Next())) if (!a.Owner) looseBefore.Push(a);
	}

	int NewLoose(String tag)
	{
		let it = ThinkerIterator.Create("Inventory");
		Inventory a;
		int n = 0;
		while (a = Inventory(it.Next()))
		{
			if (a.Owner || looseBefore.Find(a) != looseBefore.Size()) continue;
			n++;
			Console.Printf("PDRDROP %s %s seed %08x @ %.0f %.0f %.0f", tag, a.GetClassName(), a.DD_LootSeed(), a.pos.x, a.pos.y, a.pos.z);
		}
		return n;
	}

	static void Sleep(Actor except1 = null, Actor except2 = null)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
			if (a.bISMONSTER && !a.player && a.health > 0 && a != except1 && a != except2 && !(a is "RLAdaptiveSpawner") && a.GetClassName() != "RLTheHungrySpawner") a.Deactivate(null);	// Spawners must still spawn.
	}

	static void Kill(Actor a, Actor by)
	{
		if (!a || a.health <= 0) return;
		if (!a.bSHOOTABLE && a.SeeState) { a.target = by; a.SetState(a.SeeState); }
		a.DamageMobj(by, by, 100000, 'None', DMG_FORCED);
	}

	static Actor Nearest(String cls, vector3 at)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor a, best;
		double d = 256;
		while (a = Actor(it.Next()))
			if (a.GetClassName() == cls && a.health > 0 && (a.pos.xy - at.xy).Length() < d) { best = a; d = (a.pos.xy - at.xy).Length(); }
		return best;
	}

	static int CountAdaptive()
	{
		int n = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next())) if (a is "RLAdaptiveSpawner") n++;
		return n;
	}

	override void WorldThingDied(WorldEvent e)
	{
		let a = e.Thing;
		if (done || !a || !a.bISMONSTER || a.player || phase == 0) return;
		deaths++;
		if (a.DD_LootSeed()) seeded++; else unseeded++;
		Console.Printf("PDRDIED %s seed %08x at %.0f %.0f %.0f", a.GetClassName(), a.DD_LootSeed(), a.pos.x, a.pos.y, a.pos.z);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		bool inside = level.MapName ~== "MAP01";
		timer++;
		if (timer > 35 * 200) { Finish("timeout in phase " .. phase); return; }
		switch (phase)
		{
		case 0: // The New Game arrival in the dungeon, with Daggerfall in play. Everything but the player waits.
			if (!inside || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			level.SetFrozen(true);
			if (timer < 35 * 3) break;
			level.SetFrozen(false);
			Console.Printf("PDRARRIVED %s at %.0f %.0f %.0f adaptive %d", level.MapName, p.pos.x, p.pos.y, p.pos.z, CountAdaptive());
			Sleep();
			Snapshot();
			phase = Mode() == 0 ? 10 : 20; timer = 0;
			break;

		// ---- revisit ----
		case 10: // Kill the two placed monsters nearest the start.
		{
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			double d1 = 1e9, d2 = 1e9;
			while (a = Actor(it.Next()))
			{
				if (!a.bISMONSTER || a.player || a.health <= 0 || !a.bSHOOTABLE) continue;
				double d = (a.pos.xy - p.pos.xy).Length();
				if (d < d1) { v2 = v1; d2 = d1; v1 = a; d1 = d; } else if (d < d2) { v2 = a; d2 = d; }
			}
			if (!v1 || !v2) { Finish("no placed monsters"); break; }
			Console.Printf("PDRVICTIMS %s %s", v1.GetClassName(), v2.GetClassName());
			Kill(v1, p);
			Kill(v2, p);
			phase = 11; timer = 0;
			break;
		}
		case 11: // Their first deaths drop their seeded loot. Then a stock Arch-vile raises both.
		{
			if (timer < 35 * 8) break;
			Console.Printf("PDRFIRST drops %d", NewLoose("first"));
			Snapshot();
			let vile = Actor.Spawn("Archvile", p.pos + (0, 0, 0), NO_REPLACE);
			bool r1 = vile && vile.RaiseActor(v1, RF_NOCHECKPOSITION), r2 = vile && vile.RaiseActor(v2, RF_NOCHECKPOSITION);
			if (vile) vile.Destroy();
			Console.Printf("PDRRAISED %d %d", r1, r2);
			if (!r1 || !r2) { Finish("raise failed"); break; }
			phase = 12; timer = 0;
			break;
		}
		case 12: // The first raised monster is killed again at once.
			if (timer < 35 * 2) break;
			v1.A_StopSound(CHAN_BODY);
			Kill(v1, p);
			phase = 13; timer = 0;
			break;
		case 13: // Its second death drops nothing. Then the summons for the revisit.
		{
			if (timer < 35 * 8) break;
			Console.Printf("PDRREVIVED drops %d", NewLoose("revived"));
			// A soul that cannot move where it is shot out dies at once (A_PainAttack), so try directions until one lives.
			for (int ang = 0; ang < 360 && !soul; ang += 45)
			{
				let pe = Actor.Spawn("RLPainElemental", p.pos + (Actor.AngleToVector(ang, 128), 32));
				if (!pe) continue;
				pe.target = p;
				pe.angle = ang;
				pe.A_PainAttack("RLLostSoulPE", 0, PAF_NOSKULLATTACK);
				pe.Destroy();	// Only its summon stays.
				let it = ThinkerIterator.Create("Actor");
				Actor a;
				while (a = Actor(it.Next())) if (a.GetClassName() == "RLLostSoulPE" && a.health > 0) soul = a;
			}
			// An id-less Adaptive spawner, held in its first state so that the exit finds it still waiting.
			held = Actor.Spawn("RLAdaptiveFormerHuman", p.pos + (-96, 0, 0));
			if (held) { held.A_SetTics(35 * 1000); heldAt = held.pos; }
			if (!soul || !held || v2.health <= 0) { Finish(String.Format("summon failed soul %d held %d", soul != null, held != null)); break; }
			Sleep();
			soulAt = soul.pos; soulClass = soul.GetClassName();
			v2At = v2.pos; v2Class = v2.GetClassName();
			Console.Printf("PDRLEAVING soul %s at %.0f %.0f raised %s at %.0f %.0f held %s adaptive %d", soulClass, soulAt.x, soulAt.y, v2Class, v2At.x, v2At.y, held.GetClassName(), CountAdaptive());
			phase = 14; timer = 0;
			break;
		}
		case 14: // Leave through the exit.
			if (!inside) { Console.Printf("PDROUT %s", level.MapName); phase = 15; timer = 0; break; }
			p.SetOrigin((EXITSPOT[0] + EXITSPOT[3] * 40, EXITSPOT[1] + EXITSPOT[4] * 40, EXITSPOT[2]), false);
			p.angle = atan2(-EXITSPOT[4], -EXITSPOT[3]);
			p.vel = (0, 0, 0);
			if (timer % 35 == 4) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 15: // Outside on DDT07154: back in through the door.
			if (inside) { phase = 16; timer = 0; break; }
			if (timer < 35 * 2) break;
			p.SetOrigin((DOORSPOT[0] + DOORSPOT[3] * 48, DOORSPOT[1] + DOORSPOT[4] * 48, DOORSPOT[2]), false);
			p.angle = atan2(-DOORSPOT[4], -DOORSPOT[3]);
			p.vel = (0, 0, 0);
			if (timer % 70 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 16: // Back inside: find the soul and the raised monster where they were left, and nothing of the held spawner.
		{
			level.SetFrozen(true);
			if (timer < 35 * 3) break;
			level.SetFrozen(false);
			soul = Nearest(soulClass, soulAt);
			v2 = Nearest(v2Class, v2At);
			Console.Printf("PDRBACK soul %d raised %d adaptive %d heldspot %d", soul != null, v2 != null, CountAdaptive(), Nearest("RLAdaptiveFormerHuman", heldAt) != null);
			Sleep();
			Snapshot();
			deaths = seeded = unseeded = 0;
			Kill(soul, p);
			Kill(v2, p);
			phase = 17; timer = 0;
			break;
		}
		case 17:
			if (timer < 35 * 8) break;
			Console.Printf("PDRRETURNED drops %d deaths %d seeded %d", NewLoose("returned"), deaths, seeded);
			Finish("passed");
			break;

		// ---- roster ----
		case 20: // Every monster on the level, killed by the player, once the spawners have done their work.
		{
			if (timer < 35 || (CountAdaptive() > 0 && timer < 35 * 15)) break;
			Sleep();	// What the spawners made.
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			int n = 0;
			while (a = Actor(it.Next()))
				if (a.bISMONSTER && !a.player && a.health > 0) { n++; Console.Printf("PDRLIVE %s at %.0f %.0f %.0f", a.GetClassName(), a.pos.x, a.pos.y, a.pos.z); }
			Console.Printf("PDRALIVE %d adaptive %d", n, CountAdaptive());
			it = ThinkerIterator.Create("Actor");
			while (a = Actor(it.Next())) if (a.bISMONSTER && !a.player && a.health > 0 && !(a is "RLAdaptiveSpawner")) Kill(a, p);
			phase = 21; timer = 0;
			break;
		}
		case 21:
			if (timer == 35 * 4)	// Anything spawned by the deaths (DRLA's death spawns) goes too, unless it is a spawner.
			{
				let it = ThinkerIterator.Create("Actor");
				Actor a;
				while (a = Actor(it.Next())) if (a.bISMONSTER && !a.player && a.health > 0 && !(a is "RLAdaptiveSpawner")) Kill(a, p);
			}
			if (timer < 35 * 10) break;
			Console.Printf("PDRROSTER deaths %d seeded %d unseeded %d drops %d", deaths, seeded, unseeded, NewLoose("roster"));
			Finish("passed");
			break;
		}
	}
}
