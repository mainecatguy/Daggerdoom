version "4.10"

// Loaded only by tools/climb/find_steep_stairs.py on a converted dungeon map (no Daggerfall). Floods the walkable
// area from a start point (8-unit grid, Doom's 24-unit step) and looks, from every reached spot in each of four
// directions, for steep stairs: risers taller than the step height (up to 72) with short treads, stacked at least
// four high. Prints STEEP lines (spot, direction, rise, risers, run) for the best stair per 64-unit area.
class FindSteepStairs : EventHandler
{
	int tics;
	Actor probe;

	// Floor height under (x, y) for a body standing at or above z, searching upward to z + 96. -99999 if none fits.
	int FloorAt(int x, int y, int z)
	{
		for (int up = 0; up <= 96; up += 4)
		{
			probe.SetOrigin((x, y, z + up + 1), false);
			FCheckPosition tm;
			if (!probe.CheckPosition((x, y), false, tm)) continue;
			if (tm.ceilingz - tm.floorz < 32 || tm.floorz > z + up + 1) continue;
			return int(tm.floorz);
		}
		return -99999;
	}

	override void WorldTick()
	{
		if (++tics != 3) return;
		int sx = CVar.FindCVar("steep_x").GetInt(), sy = CVar.FindCVar("steep_y").GetInt(), sz = CVar.FindCVar("steep_z").GetInt();
		probe = Actor.Spawn("MapSpot", (sx, sy, sz + 1));
		probe.A_SetSize(5, 32);
		probe.bSOLID = true;
		probe.bTHRUACTORS = true;
		probe.bISMONSTER = true;
		Map<int, int> seen, bestAt;
		Array<int> qx, qy, qz;
		qx.Push(sx); qy.Push(sy); qz.Push(sz);
		seen.Insert(Key(sx, sy, sz), 0);
		static const int dx[] = { 8, -8, 0, 0 };
		static const int dy[] = { 0, 0, 8, -8 };
		for (int h = 0; h < qx.Size() && h < 400000; h++)
		{
			for (int k = 0; k < 4; k++)
			{
				int x = qx[h] + dx[k], y = qy[h] + dy[k];
				probe.SetOrigin((x, y, qz[h] + 1), false);
				FCheckPosition tm;
				if (!probe.CheckPosition((x, y), false, tm)) continue;
				int f = int(tm.floorz);
				if (f > qz[h] + 24 || tm.ceilingz - tm.floorz < 32) continue;
				int key = Key(x, y, f);
				if (seen.CheckKey(key)) continue;
				seen.Insert(key, 0);
				qx.Push(x); qy.Push(y); qz.Push(f);
			}
		}
		Console.Printf("STEEP nodes %d", qx.Size());
		int found = 0;
		for (int h = 0; h < qx.Size(); h++)
		{
			for (int k = 0; k < 4; k++)
			{
				int top = qz[h], risers = 0, run = 0, tread = 0;
				for (int d = 8; d <= 200; d += 8)
				{
					int f = FloorAt(qx[h] + dx[k] * d / 8, qy[h] + dy[k] * d / 8, top);
					if (f == -99999) break;
					int rise = f - top;
					if (rise > 24 && rise <= 72) { risers++; top = f; run = d; tread = 0; }
					else if (rise > -4 && rise <= 24) { top = f; tread += 8; if (tread > 32) break; }
					else break;
				}
				int total = top - qz[h];
				if (risers < 4 || total < 128) continue;
				int area = Key(qx[h] & ~63, qy[h] & ~63, qz[h] & ~63);
				int prev;
				bool had;
				[prev, had] = bestAt.CheckValue(area);
				if (had && prev >= total) continue;
				bestAt.Insert(area, total);
				Console.Printf("STEEP at %d,%d,%d dir %d,%d rise %d risers %d run %d", qx[h], qy[h], qz[h], dx[k], dy[k], total, risers, run);
				found++;
			}
		}
		Console.Printf("STEEP done %d", found);
	}

	static int Key(int x, int y, int z) { return (((x >> 3) + 1024) & 2047) << 20 | (((y >> 3) + 1024) & 2047) << 9 | (((z >> 4) + 256) & 511); }
}
