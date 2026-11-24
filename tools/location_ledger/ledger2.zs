version "4.14"

// Location state card 2 route (tools/location_ledger/ledger2.py). Route "first": enter Privateer's Hold at a slaughter
// area level, kill most of the pack, wound one monster and let it chase the player, take, move and drop items, leave,
// come back, leave again and save outside. Route "load": load that save, enter, and print the place. Every check point
// prints a signature of each monster, corpse and loose item, so runs compare line by line.
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, stable, lastLiving, killed;
	Array<Actor> pack;
	Actor wounded;
}

class MDHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 20;
	bool done, loadRoute;

	override void OnRegister() { loadRoute = "@ROUTE@" ~== "load"; }

	void Finish(String why) { Console.Printf("MDDONE %s", why); done = true; }

	static int Living()
	{
		int n = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && mo.health > 0 && !mo.player) n++;
		return n;
	}

	static void Signature(String when)
	{
		Array<String> rows;
		int alive = 0, dead = 0, items = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (mo.player) continue;
			bool item = mo is "Inventory" && Inventory(mo).Owner == null;
			if (!mo.bISMONSTER && !item) continue;
			if (item) items++; else if (mo.health > 0) alive++; else dead++;
			rows.Push(String.Format("%s %s %d,%d,%d hp %d%s", item ? "item" : mo.health > 0 ? "alive" : "dead", mo.GetClassName(),
				int(mo.pos.x / 8), int(mo.pos.y / 8), int(mo.pos.z / 8), mo.health, mo.bDROPPED ? " dropped" : ""));
		}
		for (int i = 1; i < rows.Size(); i++)	// insertion sort, independent of thinker order
			for (int j = i; j > 0 && rows[j] < rows[j - 1]; j--) { String t = rows[j]; rows[j] = rows[j - 1]; rows[j - 1] = t; }
		Console.Printf("LLSIG %s begin %d alive %d dead %d items %d", when, rows.Size(), alive, dead, items);
		for (int i = 0; i < rows.Size(); i++) Console.Printf("LLSIG %s %s", when, rows[i]);
		Console.Printf("LLSIG %s end", when);
	}

	// Stops every living monster where it stands, so the place compares exactly at the next check point.
	static void Freeze()
	{
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && mo.health > 0 && !mo.player) { mo.vel = (0, 0, 0); mo.tics = -1; }
	}

	static bool NeverKept(Actor mo) { return mo is "Archvile" || mo is "PainElemental" || mo is "LostSoul"; }

	// Takes the nearest loose item, moves the next one, and drops a clip and a stimpack.
	static void ChangeItems(PlayerPawn p)
	{
		Array<Inventory> loose;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next())) if (inv.Owner == null && !(inv is "DoomerfallWorldItem")) loose.Push(inv);
		Console.Printf("LLITEMS %d loose items", loose.Size());
		if (loose.Size() > 0) { Console.Printf("LLTAKE %s", loose[0].GetClassName()); loose[0].CallTryPickup(p); }
		if (loose.Size() > 1) { loose[1].SetOrigin(loose[1].pos + (24, 0, 0), false); Console.Printf("LLMOVE %s", loose[1].GetClassName()); }
		let clip = p.Spawn("Clip", p.pos + (32, 32, 0));
		if (clip) { clip.bDROPPED = true; Console.Printf("LLDROP Clip"); }
		let med = p.Spawn("Stimpack", p.pos + (32, -32, 0));
		if (med) { med.bDROPPED = true; Console.Printf("LLDROP Stimpack"); }
	}

	void GoToExit(PlayerPawn p)
	{
		p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
		p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
		p.pitch = 0;
		p.vel = (0, 0, 0);
	}

	// True once the planner has placed the pack: the living count held still for a second.
	static bool Settled(MDState st)
	{
		int now = Living();
		if (now != st.lastLiving) { st.lastLiving = now; st.stable = 0; return false; }
		return ++st.stable >= 35 && st.timer >= 140;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = MDState(p.FindInventory("MDState"));
		if (!st) st = MDState(p.GiveInventoryType("MDState"));
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName ~== "MAP01" || level.MapName.Left(3) ~== "DDS";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		st.timer++;
		if (level.maptime % 350 == 1) Console.Printf("MDSTATUS step %d, timer %d, map %s, living %d", st.phase, st.timer, level.MapName, Living());
		switch (st.phase)
		{
		case 0: // Outside: use the door once Daggerfall is in play.
		case 5:
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (CVar.FindCVar("dd_ui_test_hold").GetInt() != 0) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (st.timer < 50) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase = st.phase == 0 && !loadRoute ? 1 : 6;
			st.timer = 0;
			break;
		case 1: // Inside: wait for the pack, then pick the monster to wound.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("MDFAIL no entry"); Finish("failed"); } break; }
			if (!Settled(st)) break;
			{
				let it = ThinkerIterator.Create("Actor");
				Actor mo;
				double best = 1e9;
				while (mo = Actor(it.Next()))
				{
					if (!mo.bISMONSTER || mo.health <= 0 || mo.player) continue;
					st.pack.Push(mo);
					if (!NeverKept(mo) && mo.Distance3D(p) < best) { best = mo.Distance3D(p); st.wounded = mo; }
				}
			}
			Console.Printf("LLINSIDE living %d", st.pack.Size());
			Signature("first");
			if (st.wounded)
			{
				st.wounded.DamageMobj(p, p, max(1, st.wounded.health / 2), 'None', DMG_FORCED);
				st.wounded.target = p;
				st.wounded.SetState(st.wounded.SeeState);
				Console.Printf("LLWOUND %s hp %d at %d,%d", st.wounded.GetClassName(), st.wounded.health, int(st.wounded.pos.x), int(st.wounded.pos.y));
			}
			st.phase = 2;
			st.timer = 0;
			break;
		case 2: // Kill most of the pack: everything but every tenth monster, 150 a tic.
		{
			int now = 0;
			for (int i = 0; i < st.pack.Size() && now < 150; i++)
			{
				Actor mo = st.pack[i];
				if (!mo || mo.health <= 0 || mo == st.wounded || (i % 10 == 0 && !NeverKept(mo))) continue;
				mo.DamageMobj(p, p, mo.health + 1000, 'None', DMG_FORCED);
				st.killed++;
				now++;
			}
			// Whatever the dead left alive (a Pain Elemental's souls) goes too.
			let it = ThinkerIterator.Create("Actor");
			Actor mo;
			while (now < 150 && (mo = Actor(it.Next())))
				if (mo.bISMONSTER && mo.health > 0 && !mo.player && st.pack.Find(mo) == st.pack.Size()) { mo.DamageMobj(p, p, mo.health + 1000, 'None', DMG_FORCED); st.killed++; now++; }
			if (now > 0 || st.timer < 10) break;
			Console.Printf("LLKILLED %d, living %d", st.killed, Living());
			ChangeItems(p);
			st.phase = 3;
			st.timer = 0;
			break;
		}
		case 3: // Let the wounded one chase for three seconds, then stop the place and leave.
			if (st.timer < 105) break;
			Freeze();
			if (st.wounded) Console.Printf("LLWOUNDED %s hp %d now at %d,%d", st.wounded.GetClassName(), st.wounded.health, int(st.wounded.pos.x), int(st.wounded.pos.y));
			Signature("leave");
			GoToExit(p);
			st.phase = 4;
			st.timer = 0;
			break;
		case 4: // Leave.
		case 8:
			p.vel = (0, 0, 0);
			if (st.timer == 5) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { st.phase = st.phase == 4 ? 5 : 9; st.timer = 0; }
			else if (st.timer > LIMIT) { Console.Printf("MDFAIL exit did not work"); Finish("failed"); }
			break;
		case 6: // Back inside (or loaded and entered): print the place.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("MDFAIL no re-entry"); Finish("failed"); } break; }
			if (!Settled(st) || st.timer < 35 * 5) break;
			Freeze();
			Signature(loadRoute ? "loaded" : "reentry");
			if (loadRoute) { Finish("passed"); break; }
			GoToExit(p);
			st.phase = 8;
			st.timer = 0;
			break;
		case 9: // Outside: save, so the dungeon's history lives only in Daggerfall's ledger and Doom's table.
			if (st.timer == 35) { Console.Printf("MDSAVE outside"); level.MakeAutoSave(); }
			if (st.timer > 35 * 4) Finish("passed");
			break;
		}
	}
}
