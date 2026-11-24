version "4.14"

// Location state card 3 route (tools/location_ledger/ledger3.py): the ledger for a town street, a house and the
// wilderness. Route "first": in the town, kill and wound monsters, drop and take items; the same in a house; walk out
// of town into the wilderness and do it again; travel 600 tiles away and kill some overworld pack monsters there; come
// back; walk back into town and into the house; leave town, visit the far spot again, and save 1,200 tiles away. Route
// "load": load that save, visit the far spot, the wilderness spot, the street and the house. Every check point prints a signature of the place (each monster, corpse and loose item), so runs compare
// line by line: wild1/2/3, far1/2/3, street1/2/3, house1/2/3.
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, tries;
	vector3 street;			// the street spot, town map units
	vector2 wild, far;		// the wilderness spot and the far spot, world Doom units
	int wildTileX, wildTileY;
	bool houseDone, wildDone;
}

class MDHarness : EventHandler
{
	static const double HOUSEDOOR[] = { @HOUSEDOOR@ };
	static const double HOUSEEXIT[] = { @HOUSEEXIT@ };
	const LIMIT = 35 * 25;
	const HALF = 12288;		// half the overworld window, Doom units
	const SPACING = 192;	// one tile, Doom units
	const FARREACH = 10000;	// the far spot's check covers most of the overworld window, where pack monsters stand
	const STEPOUT = 20000;		// how far south of the street the player steps out of town
	bool done, loadRoute;

	override void OnRegister() { loadRoute = "@ROUTE@" ~== "load"; }

	void Finish(String why) { Console.Printf("MDDONE %s", why); done = true; }
	void Fail(String why) { Console.Printf("MDFAIL %s", why); Finish("failed"); }

	static bool InTown() { return level.MapName ~== "@TOWN@"; }
	static bool InHouse() { return level.MapName.Left(3) ~== "DDS"; }
	static bool InWild() { return level.MapName ~== "DDOVER01"; }

	// World Doom units of a spot on the overworld map.
	static vector2 ToWorld(vector2 v)
	{
		return (CVar.FindCVar("dd_tm_originx").GetInt() * SPACING + HALF + v.x, CVar.FindCVar("dd_tm_originy").GetInt() * SPACING + HALF + v.y);
	}
	static vector2 ToMap(vector2 w)
	{
		return (w.x - CVar.FindCVar("dd_tm_originx").GetInt() * SPACING - HALF, w.y - CVar.FindCVar("dd_tm_originy").GetInt() * SPACING - HALF);
	}

	// Ours: what the route spawned, what that dropped, map items, overworld pack monsters. Not Daggerfall's people.
	static bool Counted(Actor mo)
	{
		if (mo.player) return false;
		bool item = mo is "Inventory" && Inventory(mo).Owner == null;
		if (!mo.bISMONSTER && !item) return false;
		String c = mo.GetClassName();
		String head = c.Left(2);
		return !(head ~== "DD" || head ~== "DF" || c.Left(10) ~== "Doomerfall" && !item);
	}

	// Every counted actor within reach of a spot (map units), as rows in the place's own frame.
	static void Signature(String when, vector2 center, double reach, bool world)
	{
		Array<String> rows;
		int alive = 0, dead = 0, items = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (!Counted(mo) || (mo.pos.xy - center).Length() > reach) continue;
			bool item = mo is "Inventory";
			if (item) items++; else if (mo.health > 0) alive++; else dead++;
			vector2 at = world ? ToWorld(mo.pos.xy) : mo.pos.xy;
			rows.Push(String.Format("%s %s %d,%d,%d hp %d%s", item ? "item" : mo.health > 0 ? "alive" : "dead", mo.GetClassName(),
				int(floor(at.x / 8)), int(floor(at.y / 8)), int(floor(mo.pos.z / 8)), mo.health, mo.bDROPPED ? " dropped" : ""));
		}
		for (int i = 1; i < rows.Size(); i++)	// insertion sort, independent of thinker order
			for (int j = i; j > 0 && rows[j] < rows[j - 1]; j--) { String t = rows[j]; rows[j] = rows[j - 1]; rows[j - 1] = t; }
		Console.Printf("LLSIG %s begin %d alive %d dead %d items %d", when, rows.Size(), alive, dead, items);
		for (int i = 0; i < rows.Size(); i++) Console.Printf("LLSIG %s %s", when, rows[i]);
		Console.Printf("LLSIG %s end", when);
	}

	// Stops every living monster near a spot where it stands, so the place compares exactly at the next check point.
	static void Freeze(vector2 center, double reach)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && mo.health > 0 && !mo.player && (mo.pos.xy - center).Length() <= reach) { mo.vel.xy = (0, 0); mo.tics = -1; }
	}

	// Kills and wounds: spawns monsters around a spot, kills all but one, wounds that one; then drops a stimpack and
	// takes the nearest map item. Also kills up to two monsters that were already there (overworld pack monsters).
	static void Fight(PlayerPawn p, vector3 at, Class<Actor> cls, int count, String where)
	{
		int killed = 0, natives = 0;
		{
			let it = ThinkerIterator.Create("Actor");
			Actor mo;
			while (natives < 2 && (mo = Actor(it.Next())))
				if (Counted(mo) && mo.bISMONSTER && mo.health > 0 && (mo.pos.xy - at.xy).Length() < 3000)
				{
					Console.Printf("LLKILLNATIVE %s %s", where, mo.GetClassName());
					mo.DamageMobj(p, p, mo.health + 1000, 'None', DMG_FORCED);
					natives++;
				}
		}
		for (int i = 0; i < count; i++)
		{
			let mo = Actor.Spawn(cls, at + (96 * (i - count / 2), 160, 0));
			if (!mo) continue;
			if (i == count - 1)
			{
				mo.DamageMobj(p, p, max(1, mo.health / 2), 'None', DMG_FORCED);
				mo.vel.xy = (0, 0);
				mo.tics = -1;
				Console.Printf("LLWOUND %s %s hp %d", where, mo.GetClassName(), mo.health);
			}
			else { mo.DamageMobj(p, p, mo.health + 1000, 'None', DMG_FORCED); killed++; }
		}
		let med = p.Spawn("Stimpack", at + (-48, -48, 0));
		if (med) med.bDROPPED = true;
		Inventory best;
		double bestDist = 2048;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next()))
			if (inv.Owner == null && !inv.bDROPPED && Counted(inv) && (inv.pos.xy - at.xy).Length() < bestDist) { best = inv; bestDist = (inv.pos.xy - at.xy).Length(); }
		if (best) { Console.Printf("LLTAKE %s %s", where, best.GetClassName()); best.CallTryPickup(p); }
		Console.Printf("LLFIGHT %s killed %d of %s, %d natives, dropped a Stimpack", where, killed, cls.GetClassName(), natives);
	}

	static void KillNatives(PlayerPawn p, vector2 at, double reach, int most, String where)
	{
		int n = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (n < most && (mo = Actor(it.Next())))
			if (Counted(mo) && mo.bISMONSTER && mo.health > 0 && (mo.pos.xy - at).Length() < reach)
			{
				mo.DamageMobj(p, p, mo.health + 1000, 'None', DMG_FORCED);
				n++;
			}
		Console.Printf("LLKILLNATIVE %s %d", where, n);
	}

	static void Place(PlayerPawn p, vector3 at, double yaw)
	{
		p.SetOrigin(at, false);
		p.vel = (0, 0, 0);
		p.angle = yaw;
		p.pitch = 0;
	}

	static void Warp(int x, int y)
	{
		CVar.FindCVar("dd_tm_warp").SetString(String.Format("%d %d", x, y));
		Console.Printf("LLWARP %d %d", x, y);
	}

	void Next(MDState st, int phase) { st.phase = phase; st.timer = 0; st.tries = 0; }

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = MDState(p.FindInventory("MDState"));
		if (!st) st = MDState(p.GiveInventoryType("MDState"));
		if (!st) return;
		if (loadRoute && st.phase >= 90) Next(st, 50);	// the save carries the first route's state
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		st.timer++;
		if (level.maptime % 350 == 1) Console.Printf("MDSTATUS step %d, timer %d, map %s", st.phase, st.timer, level.MapName);
		if (st.timer > LIMIT) { Fail(String.Format("step %d timed out on %s", st.phase, level.MapName)); return; }
		vector3 door = (HOUSEDOOR[0], HOUSEDOOR[1], HOUSEDOOR[2]);
		vector2 normal = (HOUSEDOOR[3], HOUSEDOOR[4]);
		switch (st.phase)
		{
		case 0: // In town: wait until Daggerfall is in play, then fight on the street.
			if (!InTown() || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3 || CVar.FindCVar("dd_ui_test_hold").GetInt() != 0) break;
			if (st.timer < 70) break;
			st.street = p.pos;
			Fight(p, st.street, "Zombieman", 4, "street");
			Next(st, 1);
			break;
		case 1: // Let drops land, print the street, go to the house.
		case 21:
			Freeze(st.street.xy, 1500);
			if (st.timer < 140) break;	// corpses of forced kills slide and fall for a while
			Signature(st.phase == 1 ? "street1" : "street2", st.street.xy, 1500, false);
			Next(st, st.phase + 1);
			break;
		case 2: // At the house door: use it.
		case 22:
		case 52:
			Place(p, (door.xy + normal * 48, door.z), atan2(-normal.y, -normal.x));
			if (st.timer == 10) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (st.timer > 10 && st.timer % 70 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);	// again, if the interior was still converting
			if (InHouse()) Next(st, st.phase + 1);
			break;
		case 3: // In the house: fight once, print, leave.
		case 23:
		case 53:
			if (!InHouse()) break;
			if (st.phase == 3 && st.timer == 20) Fight(p, p.pos, "DoomImp", 3, "house");
			Freeze(p.pos.xy, 8192);
			if (st.timer < 70) break;
			Signature(st.phase == 3 ? "house1" : st.phase == 23 ? "house2" : "house3", (0, 0), 1e9, false);
			if (st.phase == 53) { Finish("passed"); break; }
			Place(p, (HOUSEEXIT[0] + HOUSEEXIT[3] * 40, HOUSEEXIT[1] + HOUSEEXIT[4] * 40, HOUSEEXIT[2]), atan2(-HOUSEEXIT[4], -HOUSEEXIT[3]));
			Next(st, st.phase + 1);
			break;
		case 4: // Leave the house.
		case 24:
			p.vel = (0, 0, 0);
			if (st.timer == 5 || st.timer % 70 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (InTown()) Next(st, st.phase + 1);
			break;
		case 5: // Step out of town to the south, into the wilderness.
		case 25:
			if (InWild()) { p.SetOrigin((p.pos.xy, p.floorz), false); p.vel = (0, 0, 0); Next(st, st.phase + 1); break; }
			if (st.timer % 20 == 5) { st.tries++; Place(p, (st.street.x, st.street.y - STEPOUT * st.tries, st.street.z), 0); }
			break;
		case 6: // In the wilderness: fight once, at the spot where the player landed.
			if (!InWild() || st.timer < 35) break;
			p.SetOrigin((p.pos.xy, p.floorz), false);
			st.wild = ToWorld(p.pos.xy);
			st.wildTileX = int(st.wild.x / SPACING);
			st.wildTileY = int(st.wild.y / SPACING);
			Console.Printf("LLWILD tile %d %d", st.wildTileX, st.wildTileY);
			Fight(p, p.pos, "Zombieman", 4, "wild");
			Next(st, 7);
			break;
		case 7: // Print the wilderness spot, then travel far away.
			Freeze(ToMap(st.wild), 4096);
			if (st.timer < 140) break;
			Signature("wild1", ToMap(st.wild), 4096, true);
			Warp(st.wildTileX + 600, st.wildTileY);
			Next(st, 8);
			break;
		case 26: // Out of town again: travel to the far spot again.
			if (!InWild()) break;
			Freeze(ToMap(st.wild), 4096);	// the wilderness spot's monsters came back here; they must not walk off before parking
			if (st.timer < 35) break;
			Warp(st.wildTileX + 600, st.wildTileY);
			Next(st, 27);
			break;
		case 8: // Far away (first visit): kill some of the overworld pack monsters here (Daggerfall-side seeded ids).
			if (!InWild() || st.timer < 70) break;
			st.far = ToWorld(p.pos.xy);
			KillNatives(p, p.pos.xy, FARREACH, 3, "far");
			Next(st, 12);
			break;
		case 12: // Print the far spot, then back to the wilderness spot.
			Freeze(ToMap(st.far), FARREACH);
			if (st.timer < 140) break;
			Signature("far1", ToMap(st.far), FARREACH, true);
			Warp(st.wildTileX, st.wildTileY);
			Next(st, 9);
			break;
		case 50: // Loaded: to the far spot first.
			if (!InWild() || st.timer < 70) break;
			if (CVar.FindCVar("dd_sync_df_phase").GetInt() != 3 || CVar.FindCVar("dd_ui_test_hold").GetInt() != 0) break;
			Warp(st.wildTileX + 600, st.wildTileY);
			Next(st, 56);
			break;
		case 27: // The far spot again (second visit, or after the load): print it.
		case 56:
			if (!InWild()) break;
			Freeze(ToMap(st.far), FARREACH);	// from the first tic
			if (st.timer < 140) break;
			Signature(st.phase == 27 ? "far2" : "far3", ToMap(st.far), FARREACH, true);
			if (st.phase == 27) Warp(st.wildTileX + 1200, st.wildTileY);	// the save spot, away from every place checked
			else Warp(st.wildTileX, st.wildTileY);
			Next(st, st.phase == 27 ? 28 : 51);
			break;
		case 9: // Back in the wilderness: let the chunks come back, print, walk north into town.
		case 51:
			if (!InWild()) break;
			Freeze(ToMap(st.wild), 4096);	// from the first tic, so what is checked is what came back, not what it did afterwards
			if (st.timer < 140) break;
			Signature(st.phase == 9 ? "wild2" : "wild3", ToMap(st.wild), 4096, true);
			Next(st, st.phase == 9 ? 20 : 30);
			break;
		case 20: // Walk north until the town takes over, then go to the street spot.
		case 30:
			if (InTown())
			{
				Place(p, st.street, 0);
				Next(st, st.phase == 20 ? 21 : 31);
				break;
			}
			if (!InWild()) break;
			p.SetOrigin((p.pos.x, p.pos.y + 120, p.pos.z), true);
			p.SetZ(p.floorz);
			p.vel = (0, 0, 0);
			break;
		case 31: // Loaded: print the street, then the house.
			Freeze(st.street.xy, 1500);
			if (st.timer < 70) break;
			Signature("street3", st.street.xy, 1500, false);
			Next(st, 52);
			break;
		case 28: // Save away from every checked place, so every place lives only in the ledgers.
			if (!InWild() || st.timer < 70) break;
			Console.Printf("MDSAVE away");
			level.MakeAutoSave();
			Next(st, 90);
			break;
		case 90:
			if (st.timer > 105) Finish("passed");
			break;
		}
	}
}
