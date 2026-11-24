version "4.14"

// Pickup test: enter the dungeon, press Interact on the nearest pile, autosave, leave, come back, and report.
// A run loaded from that autosave resumes in the same state and repeats the trip out and back.
class IPState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, before;
	bool saved;
	String target;
}

class IPHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 16;
	bool done, reported;

	void Finish(String why) { Console.Printf("IPDONE %s", why); done = true; }

	static int Piles(String id, out bool present)
	{
		present = false;
		int n = 0;
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
		{
			n++;
			if (item.dfId == id) present = true;
		}
		return n;
	}

	static DoomerfallWorldItem Nearest(Actor p)
	{
		DoomerfallWorldItem best = null;
		double range = 1e12;
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
		{
			// The dungeon has stacked floors, so height counts: a pile straight below is not the nearest.
			double d = (item.pos - p.pos).Length();
			Console.Printf("IPPILE %s %.1f,%.1f,%.1f distance %.0f", item.dfId, item.pos.x, item.pos.y, item.pos.z, d);
			if (d < range) { range = d; best = item; }
		}
		return best;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = IPState(p.FindInventory("IPState"));
		if (!st) st = IPState(p.GiveInventoryType("IPState"));
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		bool present;
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
		case 1: // Wait for the dungeon and Daggerfall's first list.
			if (st.timer > LIMIT) { Console.Printf("IPFAIL no piles listed"); Finish("failed"); break; }
			if (!inside) break;
			st.before = Piles("", present);
			if (st.before == 0) break;
			let item = Nearest(p);
			st.target = item.dfId;
			Console.Printf("IPLIST piles=%d target=%s count=%d texture=%s at %.1f,%.1f,%.1f scale %.3f,%.3f", st.before, st.target, item.dfCount, TexMan.GetName(item.picnum), item.pos.x, item.pos.y, item.pos.z, item.scale.x, item.scale.y);
			p.SetOrigin((item.pos.xy + (40, 0), item.pos.z - 8), false);
			p.vel = (0, 0, 0);
			p.angle = 180;
			double eye = p.pos.z + players[0].viewheight;
			p.pitch = -atan2(item.pos.z - eye, 40);
			st.phase = 2;
			st.timer = 0;
			break;
		case 2: // Let the hidden Daggerfall player catch up, then press Interact.
			p.vel = (0, 0, 0);
			if (st.timer <= 35)
			{
				// The player lands after the teleport, so aim from where the eye is now.
				let tracked = ThinkerIterator.Create("DoomerfallWorldItem");
				DoomerfallWorldItem aimed;
				while (aimed = DoomerfallWorldItem(tracked.Next()))
					if (aimed.dfId == st.target)
					{
						vector2 flat = aimed.pos.xy - p.pos.xy;
						p.angle = atan2(flat.y, flat.x);
						p.pitch = -atan2(aimed.pos.z - (p.pos.z + players[0].viewheight), flat.Length());
						if (st.timer == 34) Console.Printf("IPAIM target z %.1f player z %.1f floor %.1f horizontal %.1f", aimed.pos.z, p.pos.z, p.floorz, flat.Length());
						break;
					}
			}
			if (st.timer == 35)
			{
				Console.Printf("IPPRESS eye %.1f pitch %.1f", p.pos.z + players[0].viewheight, p.pitch);
				EventHandler.SendNetworkEvent("df_interact");
			}
			if (st.timer > 35 && "@MODE@" == "weight")
			{
				if (st.timer > 105) { Console.Printf("IPWEIGHT pile kept for the trip out and back"); st.phase = 3; st.timer = 0; }
			}
			else if (st.timer > 35)
			{
				int now = Piles(st.target, present);
				if (!present)
				{
					Console.Printf("IPTAKEN piles %d to %d", st.before, now);
					st.phase = 3;
					st.timer = 0;
				}
				else if (st.timer > 35 * 6) { Console.Printf("IPFAIL pile still there"); Finish("failed"); }
			}
			break;
		case 3: // Save with the pile gone, then leave.
			if (st.timer == 10 && !st.saved)
			{
				st.saved = true;
				Console.Printf("IPSAVE");
				level.MakeAutoSave();
			}
			if (st.timer < 70) break;
			Piles(st.target, present);
			Console.Printf("IPCHECK after save or load: target present=%d piles=%d", present, Piles(st.target, present));
			p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
			p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
			p.pitch = 0;
			st.phase = 4;
			st.timer = 0;
			break;
		case 4: // Use the exit.
			if (st.timer == 5) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { st.phase = 5; st.timer = 0; }
			if (st.timer > LIMIT) { Console.Printf("IPFAIL exit did not work"); Finish("failed"); }
			break;
		case 6: // Back inside: Daggerfall rebuilt the dungeon, and the pile must stay gone.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("IPFAIL no re-entry"); Finish("failed"); } break; }
			if (st.timer < 35 * 3 + 35) break;
			int count = Piles(st.target, present);
			Console.Printf("IPREENTRY target present=%d piles=%d (was %d before the pickup)", present, count, st.before);
			Finish(present == ("@MODE@" == "weight") ? "passed" : "failed");
			break;
		}
	}
}
