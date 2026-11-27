version "4.10"

// Loaded only by tools/first_room/run_hall_region.py on Privateer's Hold's converted map. Floods the floor around a
// seed point (radius-5, 32-high body, 8-unit grid, up at most 24), staying within a floor-height band and, if the seed
// asks, under a ceiling higher than a given height, and prints the area's bounds and the enemy placements on it.
// Actors (doors) do not block, so the band and ceiling are what end an area. The hall with stairs (seed 5: floor and
// stairs from 370 to 800 under a ceiling above 960) is also printed node by node (HN x y floor) for check_stair_hall.py.
class FirstRoomHallRegion : EventHandler
{
	int tics;

	override void WorldTick()
	{
		if (++tics != 3) return;
		static const int px[] = { 563, 247, 992, 1328, 1824, 290, 1134, 576, 852, 1441, 1206, 980, 2246, 105, 1767, 96, 684, -893, 336, 1076, 2600, 1041, 237, 332, 1015, 458, 1245, 612, 1452, -841, 950, 780, 2054, 1113, 1432, -54, 405, 851, 1236, 1251, 951, 1319 };
		static const int py[] = { 1419, 2311, 1357, 2508, 531, -1011, 459, 170, 2764, -1300, 572, 113, 675, 578, 1208, 570, 2265, 321, -246, 305, 60, 1154, -672, 206, 95, 1292, 504, 152, 381, 1438, 764, 383, 1437, 1010, 337, 879, 525, 1049, 648, 385, 1002, -485 };
		static const int pz[] = { 960, 384, 392, 384, 384, 384, 1152, 384, 384, 960, 768, 384, 384, 192, 960, 960, 384, 960, 960, 384, 384, 0, 576, 960, 1152, 576, 384, 768, 192, 840, 1152, 0, 480, 192, 1248, 384, 1344, 381, 192, 1152, 1344, 384 };
		// seed x, y, floor, band low, band high, ceiling must be above
		static const int SEED[] = { 851, 1049, 384, 370, 420, 0,   851, 1049, 384, 370, 420, 960,   851, 1049, 384, 370, 420, 700,
			992, 1357, 392, 370, 420, 0,   992, 1357, 392, 370, 420, 700,   851, 1049, 384, 370, 800, 960,   851, 1049, 384, 370, 1000, 1000 };
		static const String SN[] = { "p37 floor", "p37 floor, ceiling above 960", "p37 floor, ceiling above 700", "p2 floor",
			"p2 floor, ceiling above 700", "p37 floor and stairs up to 800, ceiling above 960", "p37 floor and stairs up to 1000, ceiling above 1000" };
		static const int dx[] = { 8, -8, 0, 0 };
		static const int dy[] = { 0, 0, 8, -8 };
		let probe = Actor.Spawn("MapSpot", (851, 1049, 424));
		probe.A_SetSize(5, 32);
		probe.bSOLID = true;
		probe.bTHRUACTORS = true;
		probe.bISMONSTER = true;
		Map<int, int> seen;
		Array<int> qx, qy, qz;
		for (int s = 0; s < 7; s++)
		{
			seen.Clear(); qx.Clear(); qy.Clear(); qz.Clear();
			int sx = SEED[s * 6], sy = SEED[s * 6 + 1], sz = SEED[s * 6 + 2], lo = SEED[s * 6 + 3], hi = SEED[s * 6 + 4], ceil = SEED[s * 6 + 5];
			qx.Push(sx); qy.Push(sy); qz.Push(sz);
			seen.Insert(Key(sx, sy, sz), 0);
			int x0 = 99999, x1 = -99999, y0 = 99999, y1 = -99999, cmax = 0;
			for (int h = 0; h < qx.Size() && h < 400000; h++)
			{
				x0 = min(x0, qx[h]); x1 = max(x1, qx[h]); y0 = min(y0, qy[h]); y1 = max(y1, qy[h]);
				for (int k = 0; k < 4; k++)
				{
					int x = qx[h] + dx[k], y = qy[h] + dy[k];
					probe.SetOrigin((x, y, qz[h] + 1), false);
					FCheckPosition tm;
					if (!probe.CheckPosition((x, y), false, tm)) continue;
					int f = int(tm.floorz);
					if (f > qz[h] + 24 || f < lo || f > hi || tm.ceilingz - tm.floorz < 32 || tm.ceilingz <= ceil) continue;
					int key = Key(x, y, f);
					if (seen.CheckKey(key)) continue;
					seen.Insert(key, 0);
					cmax = max(cmax, int(tm.ceilingz));
					qx.Push(x); qy.Push(y); qz.Push(f);
				}
			}
			String on = "";
			for (int i = 0; i < 42; i++)
				for (int h = 0; h < qx.Size(); h++)
					if (abs(qx[h] - px[i]) <= 8 && abs(qy[h] - py[i]) <= 8 && abs(qz[h] - pz[i]) <= 40) { on.AppendFormat(" p%d", i); break; }
			if (s == 5) for (int h = 0; h < qx.Size(); h++) Console.Printf("HN %d %d %d", qx[h], qy[h], qz[h]);
			Console.Printf("HALL %s: nodes %d x %d..%d y %d..%d highest ceiling %d placements:%s", SN[s], qx.Size(), x0, x1, y0, y1, cmax, on);
		}
		Console.Printf("HALLREGION done");
	}

	static int Key(int x, int y, int z) { return (((x >> 3) + 1024) & 2047) << 20 | (((y >> 3) + 1024) & 2047) << 9 | (((z >> 4) + 256) & 511); }
}
