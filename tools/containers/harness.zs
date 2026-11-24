version "4.14"

// Container test. Dungeon mode: enter, press Use on the nearest pile (Daggerfall's test hook takes one item in its
// real loot window), autosave, leave, come back, and report what is left. A run loaded from that autosave repeats
// the trip. Building mode: enter, press Use on the nearest pile or furniture container named by @TARGET@, and report.
class CTState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, before, count;
	bool saved;
	String target;
}

class CTHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 16;
	bool done;

	void Finish(String why) { Console.Printf("CTDONE %s", why); done = true; }

	bool Dungeon() { return "@MODE@" == "dungeon"; }
	bool Boxes() { return "@TARGET@" == "box"; }

	// The number of targets, and whether `id` is among them with its item count.
	int Targets(String id, out bool present, out int count)
	{
		present = false;
		count = -1;
		int n = 0;
		ThinkerIterator it = ThinkerIterator.Create(Boxes() ? "DoomerfallWorldContainer" : "DoomerfallWorldItem");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			n++;
			let pile = DoomerfallWorldItem(mo);
			let box = DoomerfallWorldContainer(mo);
			String each = pile ? pile.dfId : box.dfId;
			if (each == id) { present = true; count = pile ? pile.dfCount : 0; }
		}
		return n;
	}

	// The nearest target after skipping the @PICK@ nearer ones.
	Actor Nearest(Actor p)
	{
		Actor best = null;
		double floorRange = -1;
		for (int skip = 0; skip <= @PICK@; skip++)
		{
			best = null;
			double range = 1e12;
			ThinkerIterator it = ThinkerIterator.Create(Boxes() ? "DoomerfallWorldContainer" : "DoomerfallWorldItem");
			Actor mo;
			while (mo = Actor(it.Next()))
			{
				double d = (mo.pos - p.pos).Length();
				if (d > floorRange && d < range) { range = d; best = mo; }
			}
			if (!best) return null;
			floorRange = range;
		}
		return best;
	}

	Actor Find(String id)
	{
		ThinkerIterator it = ThinkerIterator.Create(Boxes() ? "DoomerfallWorldContainer" : "DoomerfallWorldItem");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			let pile = DoomerfallWorldItem(mo);
			let box = DoomerfallWorldContainer(mo);
			if ((pile ? pile.dfId : box.dfId) == id) return mo;
		}
		return null;
	}

	// The point Use should aim at: a pile's sprite center, or the middle of a container's box.
	static vector3 AimPoint(Actor mo)
	{
		let box = DoomerfallWorldContainer(mo);
		if (box) return ((box.dfMinX + box.dfMaxX) / 2, (box.dfMinY + box.dfMaxY) / 2, (box.dfMinZ + box.dfMaxZ) / 2);
		return mo.pos;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = CTState(p.FindInventory("CTState"));
		if (!st) st = CTState(p.GiveInventoryType("CTState"));
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		bool present;
		int count;
		st.timer++;
		switch (st.phase)
		{
		case 0: // Outside: stand at the door and use it once Daggerfall is in play.
		case 5:
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (st.phase == 0 && CVar.FindCVar("dd_ui_test_hold").GetInt() != 0) break; // A load run waits for its save.
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (st.timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase++;
			st.timer = 0;
			break;
		case 1: // Wait for Daggerfall's first list.
			if (st.timer > LIMIT) { Console.Printf("CTFAIL nothing listed"); Finish("failed"); break; }
			if (!inside || st.timer < 35) break;
			st.before = Targets("", present, count);
			if (st.before == 0) break;
			let mo = Nearest(p);
			st.target = DoomerfallWorldItem(mo) ? DoomerfallWorldItem(mo).dfId : DoomerfallWorldContainer(mo).dfId;
			Targets(st.target, present, st.count);
			vector3 aim = AimPoint(mo);
			Console.Printf("CTLIST targets=%d target=%s count=%d at %.1f,%.1f,%.1f", st.before, st.target, st.count, aim.x, aim.y, aim.z);
			// Stand off the target, on the side the player came from, and drop to the floor.
			vector2 away = p.pos.xy - aim.xy;
			away = away.Length() > 1 ? away.Unit() : (1, 0);
			double reach = 40;
			let box = DoomerfallWorldContainer(mo);
			if (box) reach += max(box.dfMaxX - box.dfMinX, box.dfMaxY - box.dfMinY) / 2;
			if (box) p.SetOrigin((aim.xy + away * reach, box.dfMinZ + 8), false);
			else p.SetOrigin((aim.xy + (40, 0), aim.z - 8), false); // The pickup test's proven spot beside a pile.
			p.vel = (0, 0, 0);
			st.phase = 2;
			st.timer = 0;
			break;
		case 2: // Let the hidden Daggerfall player catch up, then press Use.
			p.vel = (0, 0, 0);
			let target = Find(st.target);
			if (target && st.timer <= 35)
			{
				vector3 aim = AimPoint(target);
				vector2 flat = aim.xy - p.pos.xy;
				p.angle = atan2(flat.y, flat.x);
				p.pitch = -atan2(aim.z - (p.pos.z + players[0].viewheight), flat.Length());
			}
			if (st.timer == 35)
			{
				Console.Printf("CTPRESS eye %.1f pitch %.1f floor %.1f", p.pos.z + players[0].viewheight, p.pitch, p.floorz);
				EventHandler.SendNetworkEvent("df_interact");
			}
			// Doom pauses while Daggerfall's window is open, so these tics count after it closed.
			if (st.timer == 35 * 4)
			{
				int now = Targets(st.target, present, count);
				Console.Printf("CTAFTER targets %d to %d, target present=%d count %d to %d", st.before, now, present, st.count, count);
				st.count = count;
				if (!Dungeon()) { Finish("building"); break; }
				st.phase = 3;
				st.timer = 0;
			}
			break;
		case 3: // Save, then leave.
			if (st.timer == 10 && !st.saved)
			{
				st.saved = true;
				Console.Printf("CTSAVE");
				level.MakeAutoSave();
			}
			if (st.timer < 70) break;
			Console.Printf("CTCHECK after save or load: target present=%d count %d", Targets(st.target, present, count) >= 0 && present, count);
			p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
			p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
			p.pitch = 0;
			st.phase = 4;
			st.timer = 0;
			break;
		case 4: // Use the exit.
			if (st.timer == 5) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { st.phase = 5; st.timer = 0; }
			if (st.timer > LIMIT) { Console.Printf("CTFAIL exit did not work"); Finish("failed"); }
			break;
		case 6: // Back inside: Daggerfall rebuilt the dungeon, and the pile must keep what was left.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("CTFAIL no re-entry"); Finish("failed"); } break; }
			if (st.timer < 35 * 4) break;
			Targets(st.target, present, count);
			Console.Printf("CTREENTRY target present=%d count %d, expected %d", present, count, st.count);
			Finish(st.count > 0 ? (present && count == st.count ? "passed" : "failed") : (!present ? "passed" : "failed"));
			break;
		}
	}
}
