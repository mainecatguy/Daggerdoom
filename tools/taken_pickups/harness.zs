version "4.14"

// Test only: Daggerfall remembers taken Doom pickups (tools/taken_pickups/run_taken.py). A static handler, so it is not
// in any save and lives across maps. Modes (@MODE@):
//   0 take:    town start -> Privateer's Hold by the town door; picks the nearest map pickups (stimpacks, tiered ammo),
//              takes @TAKE@ of them with the real touch path (Inventory.Touch) and keeps @KEEP@ untouched; leaves to town and
//              comes back (the map rebuilt with the record applied) and checks; autosave inside; leaves; autosave in town.
//   1 loadin:  loads the inside autosave (Doom's snapshot stands), checks; leaves, comes back, checks.
//   2 loadout: loads the town autosave in a new launch (Doom has no cache of the dungeon, the saves keep no world
//              table), enters by the town door and checks the map rebuilt from Daggerfall's record alone.
// Prints PTCASE lines, PTTAKEN/PTKEPT spots for the runner, and "PTDONE".

class PTHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double TAKENSPOTS[] = { @TAKENSPOTS@ };	// x, y per spot (load modes)
	static const double KEPTSPOTS[] = { @KEPTSPOTS@ };
	static const double ARRIVALSPOT[] = { @ARRIVAL@ };			// x, y, z, angle inside (load modes)
	const MODE = @MODE@;
	const TAKE = @TAKE@;
	const KEEP = @KEEP@;

	int phase, timer, passed, failed, insideFor;
	bool loaded;
	vector3 arrival;
	double arrivalAngle;
	Array<double> takenX, takenY, keptX, keptY;
	Array<String> takenClass, keptClass;

	override void OnRegister()
	{
		if (MODE == 0) return;	// the take run chooses its own; the arrays hold a placeholder
		for (int i = 0; i + 1 < TAKENSPOTS.Size(); i += 2) { takenX.Push(TAKENSPOTS[i]); takenY.Push(TAKENSPOTS[i + 1]); takenClass.Push(""); }
		for (int i = 0; i + 1 < KEPTSPOTS.Size(); i += 2) { keptX.Push(KEPTSPOTS[i]); keptY.Push(KEPTSPOTS[i + 1]); keptClass.Push(""); }
		if (ARRIVALSPOT.Size() >= 4) { arrival = (ARRIVALSPOT[0], ARRIVALSPOT[1], ARRIVALSPOT[2]); arrivalAngle = ARRIVALSPOT[3]; }
	}

	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame && MODE != 0 && !loaded)
		{
			loaded = true;
			phase = 1;
			timer = 0;
			Console.Printf("PTLOADED map %s", level.MapName);
		}
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("PTCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void Finish()
	{
		Console.Printf("PTRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("PTDONE %s", failed == 0 ? "passed" : "failed");
		phase = 99;
	}

	static bool Inside() { return level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01"; }

	static bool IsTestPickup(Inventory inv)
	{
		if (!inv || inv.Owner) return false;
		String n = inv.GetClassName();	// DRLA's stimpack is not a Health subclass
		return inv is "Health" || inv is "DoomerfallAmmoPickup" || inv is "Ammo" || n.IndexOf("Stimpack") >= 0 || n.IndexOf("Medikit") >= 0;
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	// The loose pickup within 6 units of a spot, if any.
	static Inventory At(double x, double y)
	{
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next()))
			if (IsTestPickup(inv) && (inv.pos.xy - (x, y)).Length() < 6) return inv;
		return null;
	}

	static int CountAt(double x, double y)
	{
		int n = 0;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next()))
			if (IsTestPickup(inv) && (inv.pos.xy - (x, y)).Length() < 6) n++;
		return n;
	}

	static int CountPickups()
	{
		int n = 0;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next())) if (IsTestPickup(inv)) n++;
		return n;
	}

	// The nearest TAKE + KEEP resting map pickups, each alone on its spot (no jackpot pile), nearest first.
	bool Choose(PlayerPawn p)
	{
		Array<Inventory> all;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next()))
			if (IsTestPickup(inv) && inv.vel.Length() < 0.01) all.Push(inv);
		Array<Inventory> picked;
		for (int n = 0; n < TAKE + KEEP; n++)
		{
			Inventory best;
			double bestd = 1e9;
			for (int i = 0; i < all.Size(); i++)
			{
				let c = all[i];
				if (!c || picked.Find(c) != picked.Size()) continue;
				bool alone = true;
				for (int j = 0; j < all.Size(); j++) if (j != i && all[j] && (all[j].pos.xy - c.pos.xy).Length() < 24) alone = false;
				if (!alone) continue;
				double d = (c.pos.xy - p.pos.xy).Length();
				// The taken ones include a stimpack when there is one, so health and ammo are both covered.
				String cn = c.GetClassName();
				if (n == 0 && !(c is "Health") && cn.IndexOf("Stimpack") < 0) d += 100000;
				if (d < bestd) { bestd = d; best = c; }
			}
			if (!best) return false;
			picked.Push(best);
			if (n < TAKE) { takenX.Push(best.pos.x); takenY.Push(best.pos.y); takenClass.Push(best.GetClassName()); }
			else { keptX.Push(best.pos.x); keptY.Push(best.pos.y); keptClass.Push(best.GetClassName()); }
		}
		return true;
	}

	// Every taken spot is empty and every kept spot still has its pickup.
	void Check(String when)
	{
		int missingKept = 0, backTaken = 0;
		for (int i = 0; i < takenX.Size(); i++)
		{
			let inv = At(takenX[i], takenY[i]);
			if (inv) { backTaken++; Console.Printf("PTSEEN %s: taken spot %.0f %.0f has %s", when, takenX[i], takenY[i], inv.GetClassName()); }
		}
		for (int i = 0; i < keptX.Size(); i++)
		{
			int n = CountAt(keptX[i], keptY[i]);
			if (n != 1) { missingKept++; Console.Printf("PTSEEN %s: kept spot %.0f %.0f has %d pickups", when, keptX[i], keptY[i], n); }
		}
		Report(takenX.Size() > 0 && backTaken == 0, String.Format("%s: the %d taken pickups are gone (%d back)", when, takenX.Size(), backTaken));
		Report(keptX.Size() > 0 && missingKept == 0, String.Format("%s: the %d untaken pickups are there, one each (%d wrong)", when, keptX.Size(), missingKept));
		Console.Printf("PTCOUNT %s: %d loose pickups", when, CountPickups());
	}

	void UseWayOut(PlayerPawn p)
	{
		if (timer == 10) { p.SetOrigin(arrival, false); p.vel = (0, 0, 0); p.angle = arrivalAngle + 180; }
		if (timer == 14) CVar.FindCVar("dd_tm_use").SetInt(1);
	}

	bool UseTownDoor(PlayerPawn p)
	{
		if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) return false;
		vector3 tdoor = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		p.SetOrigin((tdoor.xy + normal * 48, tdoor.z), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
		return true;
	}

	override void WorldTick()
	{
		if (phase == 99 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		bool inside = Inside();
		if (inside) RemoveMonsters();
		timer++;
		if (timer > 35 * 45) { Report(false, String.Format("stuck in step %d (mode %d)", phase, MODE)); Finish(); return; }
		if (MODE == 0) TakeRun(p, inside);
		else if (MODE == 1) LoadInRun(p, inside);
		else LoadOutRun(p, inside);
	}

	void TakeRun(PlayerPawn p, bool inside)
	{
		switch (phase)
		{
		case 0: // Town: enter by the town door.
			if (inside) { phase = 1; timer = 0; break; }
			if (!UseTownDoor(p)) { timer = min(timer, 1); break; }
			if (timer >= 12) { CVar.FindCVar("dd_tm_use").SetInt(1); phase = 1; timer = 0; }
			break;
		case 1: // Inside: settle, choose, take.
			if (!inside) break;
			if (arrival == (0, 0, 0)) { arrival = p.pos; arrivalAngle = p.angle; Console.Printf("PTARRIVAL %.3f %.3f %.3f %.3f", arrival.x, arrival.y, arrival.z, arrivalAngle); }
			if (++insideFor < 35 * 3) break;
			if (!Choose(p)) { Report(false, "not enough lone map pickups near the arrival"); Finish(); break; }
			Console.Printf("PTCOUNT before: %d loose pickups", CountPickups());
			// Hurt by real damage, so Daggerfall's HP (the owner of health) drops and a stimpack is wanted.
			p.DamageMobj(null, null, p.health * 2 / 3, 'None', DMG_NO_ARMOR);
			phase = 10; timer = 0;
			break;
		case 10: // After the HP sync: one touch per second, so each stimpack meets a hurt player.
			if (timer % 35 != 0) break;
			if (timer / 35 > takenX.Size()) { phase = 2; timer = 0; break; }
			if (timer / 35 >= 1)
			{
				int i = timer / 35 - 1;
				let inv = At(takenX[i], takenY[i]);
				Console.Printf("PTTOUCH %s with health %d", inv ? inv.GetClassName() : 'nothing', p.health);
				if (inv) inv.Touch(p);
			}
			break;
		case 2: // A tic later: the touched ones are gone.
			if (timer < 5) break;
			for (int i = 0; i < takenX.Size(); i++)
			{
				bool gone = At(takenX[i], takenY[i]) == null;
				Report(gone, String.Format("took %s at %.0f %.0f", takenClass[i], takenX[i], takenY[i]));
				Console.Printf("PTTAKEN %.3f %.3f %s", takenX[i], takenY[i], takenClass[i]);
			}
			for (int i = 0; i < keptX.Size(); i++) Console.Printf("PTKEPT %.3f %.3f %s", keptX[i], keptY[i], keptClass[i]);
			phase = 3; timer = 0; insideFor = 0;
			break;
		case 3: // Leave by the way in.
			if (!inside) { phase = 4; timer = 0; break; }
			UseWayOut(p);
			break;
		case 4: // Town: back in.
			if (inside) { phase = 5; timer = 0; insideFor = 0; break; }
			if (timer < 70) break;
			UseTownDoor(p);
			if (timer == 82) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 5: // Inside again: check, then the inside autosave.
			if (++insideFor < 35 * 3) break;
			Check("after leaving and coming back");
			Console.Printf("PTSAVE inside");
			LevelLocals.MakeAutoSave();
			phase = 6; timer = 0;
			break;
		case 6: // Leave again, then the town autosave.
			if (timer >= 35 * 4) { phase = 11; timer = 0; }
			break;
		case 11:
			if (!inside) { phase = 7; timer = 0; break; }
			UseWayOut(p);
			if (timer > 70) timer = 0;	// try again
			break;
		case 7:
			if (timer == 35 * 4) { Console.Printf("PTSAVE town"); LevelLocals.MakeAutoSave(); }
			if (timer == 35 * 10) Finish();
			break;
		}
	}

	void LoadInRun(PlayerPawn p, bool inside)
	{
		switch (phase)
		{
		case 0: break; // waiting for the load
		case 1:
			if (!inside || ++insideFor < 35 * 3) break;
			Check("after loading the save made inside");
			{
				// A take after the load: the nearest untaken pickup (a placed one, its id from the save) moves to the
				// taken list.
				let inv = At(keptX[0], keptY[0]);
				if (inv) inv.Touch(p);
				Console.Printf("PTTOUCH after the load %s", inv ? inv.GetClassName() : 'nothing');
				takenX.Push(keptX[0]); takenY.Push(keptY[0]); takenClass.Push("");
				keptX.Delete(0); keptY.Delete(0); keptClass.Delete(0);
			}
			phase = 5; timer = 0;
			break;
		case 5: // A tiered ammo take completes when Daggerfall answers (dfa_take), so look a moment later.
			if (timer < 35) break;
			Report(At(takenX[takenX.Size() - 1], takenY[takenY.Size() - 1]) == null, String.Format("after the load took the pickup at %.0f %.0f",
				takenX[takenX.Size() - 1], takenY[takenY.Size() - 1]));
			phase = 2; timer = 0;
			break;
		case 2:
			if (!inside) { phase = 3; timer = 0; break; }
			UseWayOut(p);
			break;
		case 3:
			if (inside) { phase = 4; timer = 0; insideFor = 0; break; }
			if (timer < 70) break;
			UseTownDoor(p);
			if (timer == 82) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 4:
			if (++insideFor < 35 * 3) break;
			Check("after the load, leaving and coming back");
			Finish();
			break;
		}
	}

	void LoadOutRun(PlayerPawn p, bool inside)
	{
		switch (phase)
		{
		case 0: break; // waiting for the load
		case 1: // Town, loaded: enter.
			if (inside) { phase = 2; timer = 0; insideFor = 0; break; }
			if (timer < 70) break;
			UseTownDoor(p);
			if (timer == 82) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (timer > 35 * 8) timer = 60;
			break;
		case 2:
			if (++insideFor < 35 * 3) break;
			Check("after loading the town save in a new launch (rebuilt from Daggerfall's record)");
			Finish();
			break;
		}
	}
}
