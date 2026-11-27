version "4.10"

// Loaded only by tools/first_room/run_cave_stairs.py on Privateer's Hold's converted map. Same walk flood as
// cave_walk.zs (8-unit grid from the cave a new character wakes in, 510,1672 floor 960; radius-5, 32-high body, up at
// most 24, down any height, doors open), but it prints geometry instead of placement distances:
//   CSTEP x y zfrom zto walk   every grid edge whose floor changes by 1..24 units (a stair step or a slope)
//   CDROP x y zfrom zto walk   every grid edge whose floor drops more than 24 (a ledge or a lift)
//   CPATH i walk x y z         the walk from the cave to placement i (one line per node where the floor changes,
//                              plus the first and last node), for the placements nearest on foot
class FirstRoomCaveStairs : EventHandler
{
	int tics;

	override void WorldTick()
	{
		if (++tics != 3) return;
		static const int px[] = { 563, 247, 992, 1328, 1824, 290, 1134, 576, 852, 1441, 1206, 980, 2246, 105, 1767, 96, 684, -893, 336, 1076, 2600, 1041, 237, 332, 1015, 458, 1245, 612, 1452, -841, 950, 780, 2054, 1113, 1432, -54, 405, 851, 1236, 1251, 951, 1319 };
		static const int py[] = { 1419, 2311, 1357, 2508, 531, -1011, 459, 170, 2764, -1300, 572, 113, 675, 578, 1208, 570, 2265, 321, -246, 305, 60, 1154, -672, 206, 95, 1292, 504, 152, 381, 1438, 764, 383, 1437, 1010, 337, 879, 525, 1049, 648, 385, 1002, -485 };
		static const int pz[] = { 960, 384, 392, 384, 384, 384, 1152, 384, 384, 960, 768, 384, 384, 192, 960, 960, 384, 960, 960, 384, 384, 0, 576, 960, 1152, 576, 384, 768, 192, 840, 1152, 0, 480, 192, 1248, 384, 1344, 381, 192, 1152, 1344, 384 };
		let probe = Actor.Spawn("MapSpot", (510, 1672, 1000));
		probe.A_SetSize(5, 32);
		probe.bSOLID = true;
		probe.bTHRUACTORS = true;
		probe.bISMONSTER = true;
		probe.bNOCLIP = false;
		Map<int, int> seen;
		Array<int> qx, qy, qz, qd, qp;
		qx.Push(510); qy.Push(1672); qz.Push(960); qd.Push(0); qp.Push(-1);
		seen.Insert(Key(510, 1672, 960), 0);
		static const int dx[] = { 8, -8, 0, 0 };
		static const int dy[] = { 0, 0, 8, -8 };
		Array<int> best;
		for (int i = 0; i < 42; i++) best.Push(-1);
		for (int h = 0; h < qx.Size() && h < 2000000; h++)
		{
			for (int i = 0; i < 42; i++)
				if (best[i] < 0 && abs(qx[h] - px[i]) <= 8 && abs(qy[h] - py[i]) <= 8 && abs(qz[h] - pz[i]) <= 40) best[i] = h;
			for (int k = 0; k < 4; k++)
			{
				int x = qx[h] + dx[k], y = qy[h] + dy[k];
				probe.SetOrigin((x, y, qz[h] + 1), false);
				FCheckPosition tm;
				if (!probe.CheckPosition((x, y), false, tm)) continue;
				int f = int(tm.floorz);
				if (f > qz[h] + 24 || tm.ceilingz - tm.floorz < 32) continue;
				if (f != qz[h])
				{
					if (abs(f - qz[h]) <= 24) Console.Printf("CSTEP %d %d %d %d %d", x, y, qz[h], f, qd[h]);
					else Console.Printf("CDROP %d %d %d %d %d", x, y, qz[h], f, qd[h]);
				}
				int key = Key(x, y, f);
				if (seen.CheckKey(key)) continue;
				seen.Insert(key, 0);
				qx.Push(x); qy.Push(y); qz.Push(f); qd.Push(qd[h] + 8); qp.Push(h);
			}
		}
		static const int show[] = { 0, 37, 15, 2, 10, 26, 23, 35, 4, 25 };
		for (int s = 0; s < 10; s++)
		{
			int i = show[s];
			if (best[i] < 0) continue;
			Array<int> path;
			for (int h = best[i]; h >= 0; h = qp[h]) path.Push(h);
			for (int j = path.Size() - 1; j >= 0; j--)
			{
				int h = path[j];
				bool edge = j == 0 || j == path.Size() - 1 || qz[path[j + 1]] != qz[h] || qz[path[j - 1]] != qz[h];
				if (edge) Console.Printf("CPATH %d %d %d %d %d", i, qd[h], qx[h], qy[h], qz[h]);
			}
		}
		Console.Printf("CAVESTAIRS done nodes %d", qx.Size());
	}

	static int Key(int x, int y, int z) { return (((x >> 3) + 1024) & 2047) << 20 | (((y >> 3) + 1024) & 2047) << 9 | (((z >> 4) + 256) & 511); }
}
