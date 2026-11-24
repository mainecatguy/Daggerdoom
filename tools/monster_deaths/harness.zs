version "4.14"

// Monster death test: enter the dungeon, kill the real quest foe and placed monsters, take a drop, autosave,
// leave, and come back. A run loaded from that autosave repeats the trip.
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, alive, kills;
	bool saved;
	String known, drop;
}

class MDHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 16;
	const MAXKILLS = 12;
	bool done;
	bool presave;

	// The mode must be a runtime value. A literal comparison such as ("normal" == "presave") folds to a constant
	// false, and a constant-false "if" that holds a "break" inside the switch made the whole WorldTick silently
	// never run (UZDoom 5.0.3 ZScript codegen), so every normal-mode route timed out at the town door.
	override void OnRegister() { presave = "@MODE@" ~== "presave"; }

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

	static String PileIds()
	{
		String all = "";
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next())) all = all .. item.dfId .. ",";
		return all;
	}

	static DoomerfallWorldItem NewPile(String known)
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
			if (known.IndexOf(item.dfId) < 0) return item;
		return null;
	}

	static DoomerfallWorldItem PileById(String id)
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
			if (item.dfId == id) return item;
		return null;
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
		switch (st.phase)
		{
		case 0: // Outside: use the door once Daggerfall is in play and has started the quest.
		case 6:
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (st.phase == 0 && CVar.FindCVar("dd_ui_test_hold").GetInt() != 0) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (st.timer < 50) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase++;
			st.timer = 0;
			break;
		case 1: // Inside: let the ids and Daggerfall's list arrive, then kill the quest foe.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("MDFAIL no entry"); Finish("failed"); } break; }
			if (st.timer < 140) break;
			if (presave && !st.saved) // Save before the kill, so a load must undo it and allow it once more.
			{
				st.saved = true;
				st.timer = 60;
				Console.Printf("MDPRESAVE living %d", Living());
				level.MakeAutoSave();
				break;
			}
			st.known = PileIds();
			st.alive = Living();
			Console.Printf("MDINSIDE living %d", st.alive);
			CVar.FindCVar("dd_mon_test_kill").SetInt(2);
			st.kills = 1;
			st.phase = 2;
			st.timer = 0;
			break;
		case 2: // Kill placed monsters until one of them drops something.
			if (st.timer % 50 != 0) break;
			{
				let pile = NewPile(st.known);
				if (pile)
				{
					st.drop = pile.dfId;
					Console.Printf("MDDROP %s after %d kills, living %d", st.drop, st.kills, Living());
					p.SetOrigin((pile.pos.xy + (40, 0), pile.pos.z - 8), false);
					p.vel = (0, 0, 0);
					st.phase = 3;
					st.timer = 0;
				}
				else if (st.kills >= MAXKILLS) { Console.Printf("MDFAIL no drop in %d kills", st.kills); Finish("failed"); }
				else { CVar.FindCVar("dd_mon_test_kill").SetInt(1); st.kills++; }
			}
			break;
		case 3: // Take the drop through the real Interact path.
			p.vel = (0, 0, 0);
			{
				let pile = PileById(st.drop);
				if (pile && st.timer <= 40)
				{
					vector2 flat = pile.pos.xy - p.pos.xy;
					p.angle = atan2(flat.y, flat.x);
					p.pitch = -atan2(pile.pos.z - (p.pos.z + players[0].viewheight), flat.Length());
				}
				if (st.timer == 40) EventHandler.SendNetworkEvent("df_interact");
				if (st.timer > 40 && !pile) { Console.Printf("MDTAKEN %s", st.drop); st.phase = 4; st.timer = 0; }
				else if (st.timer > 35 * 7) { Console.Printf("MDFAIL drop not taken"); Finish("failed"); }
			}
			break;
		case 4: // Save with the monsters dead and the drop taken.
			if (st.timer == 20) st.alive = Living();
			if (st.timer == 20 && !st.saved)
			{
				st.saved = true;
				Console.Printf("MDSAVE living %d", st.alive);
				level.MakeAutoSave();
			}
			if (st.timer < 90) break;
			Console.Printf("MDCHECK living %d, expected %d, drop present %d", Living(), st.alive, PileById(st.drop) != null);
			p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
			p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
			p.pitch = 0;
			st.phase = 5;
			st.timer = 0;
			break;
		case 5: // Leave.
			if (st.timer == 5) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { st.phase = 6; st.timer = 0; }
			else if (st.timer > LIMIT) { Console.Printf("MDFAIL exit did not work"); Finish("failed"); }
			break;
		case 7: // Back inside: nothing may return.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("MDFAIL no re-entry"); Finish("failed"); } break; }
			if (st.timer < 35 * 5) break;
			int now = Living();
			bool present = PileById(st.drop) != null;
			Console.Printf("MDREENTRY living %d, expected %d, drop present %d", now, st.alive, present);
			Finish(now == st.alive && !present ? "passed" : "failed");
			break;
		}
	}
}
