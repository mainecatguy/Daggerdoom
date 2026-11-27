version "4.14"

// Test only (tools/restsync/restsync.py): stands in Gothway's street (street), enters its tavern (tavern), or enters
// Privateer's Hold by its town door and clears the monsters near the entrance so a rest is allowed (dungeon), then says RSREADY and lets -dfuitest open the rest window
// (the rest key's command). The driver picks Loiter or Rest in Daggerfall's window. This handler follows every townsperson and NPC Doom shows, on every tic it sees.
// WorldTick runs only on tics that play (not behind a menu, not during a frozen hold), so the first tic after a
// real-time gap of over 0.7 s is the first frame the player sees after the menu. For 4 s after that it reports any
// person who moves more than 32 units in one tic (RSJUMP), appears (RSNEW), vanishes (RSGONE), or an NPC that is
// shown or hidden (RSNPC); NPCs' positions are followed the same way. RSRESUME says how many people changed place across the menu, which nobody saw.
class RSHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 150;
	const WATCH_TICS = 35 * 4;
	const JUMP_UNITS = 32.0;
	const NEAR_UNITS = 3000.0;	// Daggerfall lists people up to 6000 of its units (4500 here) away; a pop out there is its range, not a sync.
	int phase, timer, lastMs, watch, resumes, jumps, news, gones, npcFlips, moved, near;
	Array<int> ids;
	Array<double> xs, ys;
	Array<bool> seen;
	Array<Actor> npcs;
	Array<bool> npcShown;
	Array<double> npcX, npcY;

	void Track(int tic)
	{
		for (int i = 0; i < seen.Size(); i++) seen[i] = false;
		let it = ThinkerIterator.Create((class<Actor>)("DFTownsperson"));
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			int id = mo.args[0];
			int at = ids.Find(id);
			if (at == ids.Size())
			{
				ids.Push(id); xs.Push(mo.pos.x); ys.Push(mo.pos.y); seen.Push(true);
				if (watch == WATCH_TICS) moved++;
				else if (watch > 0) { news++; if (players[0].mo.Distance2D(mo) < NEAR_UNITS) near++; Console.Printf("RSNEW tic %d %08x at %.0f %.0f, %.0f from the player", tic, id, mo.pos.x, mo.pos.y, players[0].mo.Distance2D(mo)); }
				continue;
			}
			double d = (mo.pos.xy - (xs[at], ys[at])).Length();
			if (watch == WATCH_TICS && d > JUMP_UNITS) moved++;	// The resume tic: what changed while the menu covered the view.
			else if (watch > 0 && d > JUMP_UNITS) { jumps++; if (players[0].mo.Distance2D(mo) < NEAR_UNITS) near++; Console.Printf("RSJUMP tic %d %08x moved %.0f in one tic, %.0f from the player", tic, id, d, players[0].mo.Distance2D(mo)); }
			xs[at] = mo.pos.x; ys[at] = mo.pos.y; seen[at] = true;
		}
		for (int i = ids.Size() - 1; i >= 0; i--)
		{
			if (seen[i]) continue;
			double away = (players[0].mo.pos.xy - (xs[i], ys[i])).Length();
			if (watch > 0 && watch < WATCH_TICS) { gones++; if (away < NEAR_UNITS) near++; Console.Printf("RSGONE tic %d %08x, %.0f from the player", tic, ids[i], away); }
			ids.Delete(i); xs.Delete(i); ys.Delete(i); seen.Delete(i);
		}
		let nit = ThinkerIterator.Create((class<Actor>)("DFNpc"));
		while (mo = Actor(nit.Next()))
		{
			bool shown = !mo.bINVISIBLE;
			int at = npcs.Find(mo);
			if (at == npcs.Size())
			{
				npcs.Push(mo); npcShown.Push(shown); npcX.Push(mo.pos.x); npcY.Push(mo.pos.y);
				if (watch > 0 && watch < WATCH_TICS) { news++; near++; Console.Printf("RSNEW tic %d npc %08x", tic, mo.args[0]); }
				continue;
			}
			double nd = (mo.pos.xy - (npcX[at], npcY[at])).Length();
			if (watch == WATCH_TICS && nd > JUMP_UNITS) moved++;
			else if (watch > 0 && nd > JUMP_UNITS) { jumps++; near++; Console.Printf("RSJUMP tic %d npc %08x moved %.0f in one tic", tic, mo.args[0], nd); }
			npcX[at] = mo.pos.x; npcY[at] = mo.pos.y;
			if (shown != npcShown[at] && watch > 0 && watch < WATCH_TICS) { npcFlips++; near++; Console.Printf("RSNPC tic %d npc %08x %s", tic, mo.args[0], shown ? "shown" : "hidden"); }
			npcShown[at] = shown;
		}
	}

	override void WorldTick()
	{
		if (phase >= 9 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		String mode = "@MODE@";
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		if (mode == "demo")	// play.bat: only stand the player by the tavern door, facing the street, then hand over.
		{
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) return;
			p.SetOrigin((DOORDATA[0] + DOORDATA[3] * 64, DOORDATA[1] + DOORDATA[4] * 64, DOORDATA[2]), false);
			p.angle = atan2(DOORDATA[4], DOORDATA[3]);
			phase = 9;
			return;
		}
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (timer > LIMIT) { Console.Printf("RSDONE timeout phase %d", phase); phase = 9; return; }

		int now = MSTime();
		if (phase >= 2 && lastMs > 0 && now - lastMs > 700)
		{
			resumes++;
			watch = WATCH_TICS;
			Console.Printf("RSGAP %d ms of no play before tic %d", now - lastMs, level.maptime);
		}
		lastMs = now;
		if (phase >= 1) Track(level.maptime);
		if (watch == WATCH_TICS) Console.Printf("RSRESUME people %d, %d of them in new places", ids.Size(), moved);
		if (watch > 0 && --watch == 0)
		{
			Console.Printf("RSRESULT seen_near %d (within %.0f) | jumps %d new %d gone %d npc_flips %d | people %d npcs %d, changed behind the menu %d", near, NEAR_UNITS, jumps, news, gones, npcFlips, ids.Size(), npcs.Size(), moved);
			Console.Printf("RSDONE ok");
			phase = 9;
			return;
		}

		switch (phase)
		{
		case 0:	// Wait for Daggerfall, then go where the rest is taken.
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (mode != "street")	// Through the door: Privateer's Hold, or the tavern.
			{
				if (inside) { phase = 1; timer = 0; break; }
				p.SetOrigin((door.xy + normal * 48, door.z), false);
				p.vel = (0, 0, 0);
				p.angle = atan2(-normal.y, -normal.x);
				if (timer % 35 == 20) CVar.FindCVar("dd_tm_use").SetInt(1);
				break;
			}
			p.SetOrigin((door.xy + normal * 64, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(normal.y, normal.x);
			if (timer < 420) break;	// Daggerfall lists the street.
			phase = 1;
			timer = 0;
			break;
		case 1:	// Settle, clear the monsters near a dungeon's entrance (test only: a rest needs none near), ask for the rest window.
			if (mode == "dungeon" && timer == 70)
			{
				let it = ThinkerIterator.Create("Actor");
				Actor mo;
				int killed = 0;
				while (mo = Actor(it.Next()))
					if (mo.bISMONSTER && mo.health > 0 && p.Distance2D(mo) < 4096) { mo.DamageMobj(null, null, mo.health + 1000, 'None', DMG_FORCED); killed++; }
				Console.Printf("RSKILLED %d monsters near the entrance", killed);
			}
			if (timer < 140) break;
			Console.Printf("RSREADY map %s people %d npcs %d", level.MapName, ids.Size(), npcs.Size());
			CVar.FindCVar("dd_ui_test_hold").SetInt(0);	// -dfuitest opens the rest window 3 s later, through the rest key's command.
			phase = 2;
			timer = 0;
			break;
		}
	}
}
