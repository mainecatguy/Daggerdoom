version "4.14"

// Fixed drops, paired: after a real New Game (or a bundled load of the save run's autosave), kill every monster near
// the Privateer's Hold start, list what they dropped, and take one dropped gun with a real Use press, so Daggerfall
// rolls its material through the bridge. Every step prints a PD line. Test only, loaded by tools/fixed_drops/paired.py.
class PDHarness : EventHandler // Not static: a bundled load restores phase from the save, which is how the load run resumes.
{
	const RADIUS = 1200;
	// 0 fresh, 1 save before the kill, 2 load the save run's autosave. A function, not a const and not a field: constant
	// conditions upset UZDoom's script VM, and a field would be replaced from the save on load.
	static int Mode() { return @MODE@; }
	int phase, timer;
	bool done, resumed;
	vector3 start;
	Array<Actor> before, victims;
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

	static bool IsGunPickup(Actor a)
	{
		String n = a.GetClassName();
		return a.DD_LootSeed() != 0 && n.Left(2) == "RL" && n.Mid(n.Length() - 6) == "Pickup";
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		timer++;
		// From the first tic: the start room's neighbours otherwise wake and can kill the new character before the
		// test begins, which also wakes the pack and changes who is alive at the kill.
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		// Privateer's Hold rolls Civil War, so its two armies start fighting each other at once, and which monsters
		// that kills before the test's blow differs between games. The test is about drops, not that fight, so
		// everything but the player stays frozen until the kill.
		if (phase < 3 || (phase == 3 && timer < 35)) level.SetFrozen(true);
		// The load run waits for the bridge to load the save run's autosave, which was made in phase 2.
		if (Mode() == 2 && phase < 2) return;
		if (Mode() == 2 && !resumed) { resumed = true; Console.Printf("PDRESUMED %s phase %d", level.MapName, phase); }
		switch (phase)
		{
		case 0: // The New Game arrival in the dungeon, with Daggerfall in play.
			if (!(level.MapName ~== "MAP01") || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			if (timer < 35 * 3) break;
			players[0].cheats |= CF_GODMODE;
			p.bNOTARGET = true;
			start = p.pos;
			Console.Printf("PDARRIVED %s at %.0f %.0f %.0f", level.MapName, p.pos.x, p.pos.y, p.pos.z);
			phase = 1; timer = 0;
			break;
		case 1: // The save run saves before the fight. Every run waits the same time here.
			if (timer == 35 && Mode() == 1)
			{
				phase = 2; // The autosave is written after this tic, in phase 2: the load run resumes there.
				timer = 0;
				Console.Printf("PDSAVE autosave");
				LevelLocals.MakeAutoSave();
				break;
			}
			if (timer >= 35 * 10) { phase = 3; timer = 0; }
			break;
		case 2: // The save run, after asking for the save.
			if (timer >= 35 * 9) { phase = 3; timer = 0; }
			break;
		case 3: // Kill the entrance's monsters, all with the same blow, credited to the player.
		{
			if (timer < 35) break;
			level.SetFrozen(false);
			before.Clear();
			victims.Clear();
			int dead = 0;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next()))
			{
				if (a is "Inventory" && !Inventory(a).Owner) before.Push(a);
				// Chosen by where each was placed, near Privateer's Hold's start, not by where it stands now or where
				// the player arrived, which both drift by a few units between games.
				if (!a.bISMONSTER || a.player || (a.SpawnPoint - (380, 1270, 0)).Length() >= RADIUS) continue;
				if (a.health > 0) victims.Push(a); else dead++;
			}
			// The rest of the dungeon stays out of it: once unfrozen, the two Civil War armies would kill each other
			// during the wait below, and those deaths' drops vary with the fight. Deactivate makes a monster dormant.
			it = ThinkerIterator.Create("Actor");
			while (a = Actor(it.Next()))
				if (a.bISMONSTER && !a.player && a.health > 0 && victims.Find(a) == victims.Size()) a.Deactivate(null);
			for (int i = 0; i < victims.Size(); i++)
			{
				a = victims[i];
				Console.Printf("PDKILL %s spawned at %.0f %.0f %.0f", a.GetClassName(), a.SpawnPoint.x, a.SpawnPoint.y, a.SpawnPoint.z);
				a.DamageMobj(p, p, 100000, 'None', DMG_FORCED);
			}
			Console.Printf("PDKILLED %d, %d near the start already dead", victims.Size(), dead);
			phase = 4; timer = 0;
			break;
		}
		case 4: // Let the death sequences and the drops play out, then list the new loose items.
		{
			if (timer < 35 * 8) break;
			// A corpse's loot seed comes from its Daggerfall id; 0 means it died without one, so its drops are random.
			for (int i = 0; i < victims.Size(); i++)
				if (victims[i])
					Console.Printf("PDCORPSE %s spawned at %.0f %.0f %.0f seed %08x", victims[i].GetClassName(), victims[i].SpawnPoint.x, victims[i].SpawnPoint.y, victims[i].SpawnPoint.z, victims[i].DD_LootSeed());
			let it = ThinkerIterator.Create("Inventory");
			Inventory a;
			int n = 0;
			int best = 0;
			gun = null;
			while (a = Inventory(it.Next()))
			{
				if (a.Owner || before.Find(a) != before.Size()) continue;
				n++;
				Console.Printf("PDDROP %s seed %08x @ %.0f %.0f %.0f", a.GetClassName(), a.DD_LootSeed(), a.pos.x, a.pos.y, a.pos.z);
				String cn = a.GetClassName();
				if (!a.DD_LootSeed() && cn.Left(7) != "DFAmmo_")
				{
					String t = "none", m = "none";
					if (a.target) t = a.target.GetClassName();
					if (a.master) m = a.master.GetClassName();
					Console.Printf("PDUNSEEDED %s target %s master %s spawned at %.0f %.0f %.0f", cn, t, m, a.SpawnPoint.x, a.SpawnPoint.y, a.SpawnPoint.z);
				}
				if (IsGunPickup(a) && a.bSPECIAL && (!gun || a.DD_LootSeed() < best)) { gun = a; best = a.DD_LootSeed(); }
			}
			Console.Printf("PDDROPS %d", n);
			if (!gun) { Finish("nogun"); break; }
			Console.Printf("PDTAKE %s seed %08x", gun.GetClassName(), best);
			phase = 5; timer = 0;
			break;
		}
		case 5: // One real Use press in front of the gun. Daggerfall answers, then it leaves the floor.
			if (timer == 1)
			{
				// The gun lies among the corpses, whose Daggerfall loot piles would take the Use press. Its lasting
				// id does not depend on where it lies, so it is carried to a clear spot by the start, as in
				// tools/doomitems.
				p.SetOrigin(start, false);
				p.vel = (0, 0, 0);
				p.pitch = 0;
				for (int a = 0; a < 360; a += 45)
				{
					FLineTraceData t;
					if (!p.LineTrace(a, 96, 0, TRF_THRUACTORS, 16, 0, 0, t) || t.HitType == TRACE_HitNone) { p.angle = a; break; }
				}
				gun.SetOrigin((start.xy + (cos(p.angle), sin(p.angle)) * 48, start.z), false);
				gun.vel = (0, 0, 0);
			}
			if (timer == 4) PressUse(p);
			if (timer < 6) break;
			if (!gun || !gun.bSPECIAL) { Console.Printf("PDTAKEN after %d tics", timer - 4); phase = 6; timer = 0; }
			else if (timer > 35 * 5) Finish("gun still on the floor");
			break;
		case 6:
			if (timer == 35 * 3) Finish("passed");
			break;
		}
	}
}
