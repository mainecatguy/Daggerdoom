version "4.14"

// Runtime location test. The route visits each listed location in one UZDoom session:
// warp nearby, run toward it while it converts, enter, walk in, walk back out.
class RTState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int leg, phase, timer, waited, baseStitches, wait2;
}

class RTHarness : EventHandler
{
	const SPEED = 40.0;
	const TILE = 192.0;
	const HALF = 12288.0;
	const WAIT_LIMIT = 35 * 25;

	// group, start tile x, start tile y, direction x, direction y, target edge along the direction, label index
	static const int ROUTE[] = { @ROUTE@ };
	const FIELDS = 6;
	bool done;

	static int CV(String name) { return CVar.FindCVar(name).GetInt(); }

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = RTState(p.FindInventory("RTState"));
		if (!st) st = RTState(p.GiveInventoryType("RTState"));
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		int count = ROUTE.Size() / FIELDS;
		if (st.leg >= count)
		{
			Console.Printf("RTDONE legs=%d", count);
			done = true;
			return;
		}
		int at = st.leg * FIELDS;
		int group = ROUTE[at], sx = ROUTE[at + 1], sy = ROUTE[at + 2], dx = ROUTE[at + 3], dy = ROUTE[at + 4], edge = ROUTE[at + 5];
		bool inTown = CV("dd_tm_intown") != 0;
		st.timer++;
		switch (st.phase)
		{
		case 0:	// Warp. Wait for any map change to settle first.
			p.vel = (0, 0, 0);
			if (inTown || level.maptime < 3) break;
			CVar.FindCVar("dd_tm_warp").SetString(String.Format("%d %d", sx, sy));
			Console.Printf("RTLEG start leg=%d group=%d tic=%d", st.leg, group, level.totaltime);
			st.phase = 1;
			st.timer = 0;
			st.waited = 0;
			break;
		case 1:	// Arrive.
			p.vel = (0, 0, 0);
			if (st.timer > 4 && level.maptime > 2 && !inTown && abs(CV("dd_tm_originx") + (p.pos.x + HALF) / TILE - sx) < 3 && abs(CV("dd_tm_originy") + (p.pos.y + HALF) / TILE - sy) < 3)
			{
				st.phase = 2;
				st.timer = 0;
			}
			else if (st.timer > 350) Fail(st, group, "no arrival");
			break;
		case 2:	// Approach, stopping short of the entry line until the location is ready.
		{
			if (inTown)
			{
				Console.Printf("RTLEG entered leg=%d group=%d map=%s waited_tics=%d", st.leg, group, level.MapName, st.waited);
				st.phase = 3;
				st.timer = 0;
				break;
			}
			double tx = CV("dd_tm_originx") + (p.pos.x + HALF) / TILE, ty = CV("dd_tm_originy") + (p.pos.y + HALF) / TILE;
			double along = dx != 0 ? (tx - edge) * -dx : (ty - edge) * -dy;	// Tiles still to travel to the location's edge.
			bool ready = CV("dd_tm_nearest") == group && CV("dd_tm_neareststate") == 3;
			if (along > 14 || ready) p.vel.xy = (dx * SPEED, dy * SPEED);
			else
			{
				p.vel.xy = (0, 0);
				st.waited++;
				if (CV("dd_tm_nearest") == group && CV("dd_tm_neareststate") == 4) { Console.Printf("RTLEG failed-as-designed leg=%d group=%d, still in overworld", st.leg, group); Next(st); break; }
				if (st.waited > WAIT_LIMIT) { Fail(st, group, "not ready"); break; }
			}
			if (st.timer > 1400) Fail(st, group, "approach timeout");
			break;
		}
		case 3:	// A little way inside the map, then back out.
			p.vel.xy = (dx * SPEED, dy * SPEED);
			if (st.timer >= 12) { st.phase = 4; st.timer = 0; }
			break;
		case 4:
			p.vel.xy = (-dx * SPEED, -dy * SPEED);
			if (st.timer % 35 == 1) Console.Printf("RTLEG leaving leg=%d tic=%d pos=%.0f,%.0f", st.leg, st.timer, p.pos.x, p.pos.y);
			if (!inTown)
			{
				Console.Printf("RTLEG left leg=%d group=%d", st.leg, group);
				Next(st);
			}
			else if (st.timer > 500) Fail(st, group, "could not leave");
			break;
		}
	}

	void Next(RTState st) { st.leg++; st.phase = 0; st.timer = 0; }
	void Fail(RTState st, int group, String why)
	{
		Console.Printf("RTLEG FAIL leg=%d group=%d %s", st.leg, group, why);
		Next(st);
	}
}
