version "4.10"

// Loaded only by tools/first_room/run_cave_walk.py on Privateer's Hold's converted map: floods a 16-unit walk grid from
// the cave a new character wakes in (Daggerfall's enter marker, 510,1672 on floor 960) and prints the walking distance
// to each of the 42 enemy placements (origins from the placer's request, card 20261126-192455). Doors and other actors
// do not block (doors open). A step is walkable when a 16-radius, 56-high body fits, up at most 24, down any height.
class FirstRoomCaveWalk : EventHandler
{
	int tics;

	override void WorldTick()
	{
		if (++tics != 3) return;
		static const int px[] = { 563, 247, 992, 1328, 1824, 290, 1134, 576, 852, 1441, 1206, 980, 2246, 105, 1767, 96, 684, -893, 336, 1076, 2600, 1041, 237, 332, 1015, 458, 1245, 612, 1452, -841, 950, 780, 2054, 1113, 1432, -54, 405, 851, 1236, 1251, 951, 1319 };
		static const int py[] = { 1419, 2311, 1357, 2508, 531, -1011, 459, 170, 2764, -1300, 572, 113, 675, 578, 1208, 570, 2265, 321, -246, 305, 60, 1154, -672, 206, 95, 1292, 504, 152, 381, 1438, 764, 383, 1437, 1010, 337, 879, 525, 1049, 648, 385, 1002, -485 };
		static const int pz[] = { 960, 384, 392, 384, 384, 384, 1152, 384, 384, 960, 768, 384, 384, 192, 960, 960, 384, 960, 960, 384, 384, 0, 576, 960, 1152, 576, 384, 768, 192, 840, 1152, 0, 480, 192, 1248, 384, 1344, 381, 192, 1152, 1344, 384 };
		let probe = Actor.Spawn("MapSpot", (510, 1672, 1000));
		probe.A_SetSize(16, 56);
		probe.bSOLID = true;
		probe.bTHRUACTORS = true;
		probe.bISMONSTER = true;
		probe.bNOCLIP = false;
		Map<int, int> seen;
		Array<int> qx, qy, qz, qd;
		qx.Push(510); qy.Push(1672); qz.Push(960); qd.Push(0);
		seen.Insert(Key(510, 1672, 960), 0);
		static const int dx[] = { 16, -16, 0, 0 };
		static const int dy[] = { 0, 0, 16, -16 };
		Array<int> best;
		for (int i = 0; i < 42; i++) best.Push(-1);
		for (int h = 0; h < qx.Size() && h < 400000; h++)
		{
			for (int i = 0; i < 42; i++)
				if (best[i] < 0 && abs(qx[h] - px[i]) <= 12 && abs(qy[h] - py[i]) <= 12 && abs(qz[h] - pz[i]) <= 40) best[i] = qd[h];
			for (int k = 0; k < 4; k++)
			{
				int x = qx[h] + dx[k], y = qy[h] + dy[k];
				probe.SetOrigin((x, y, qz[h] + 1), false);
				FCheckPosition tm;
				if (!probe.CheckPosition((x, y), false, tm)) continue;
				int f = int(tm.floorz);
				if (f > qz[h] + 24 || tm.ceilingz - tm.floorz < 56) continue;
				int key = Key(x, y, f);
				if (seen.CheckKey(key)) continue;
				seen.Insert(key, 0);
				qx.Push(x); qy.Push(y); qz.Push(f); qd.Push(qd[h] + 16);
			}
		}
		Console.Printf("CAVEWALK nodes %d", qx.Size());
		for (int i = 0; i < 42; i++)
		{
			double d = ((px[i] - 510, py[i] - 1672, pz[i] - 960)).Length();
			Console.Printf("CAVEWALK p%d walk %d straight %d at %d,%d,%d", i, best[i], int(d), px[i], py[i], pz[i]);
		}
		Console.Printf("CAVEWALK done");
	}

	static int Key(int x, int y, int z) { return (((x >> 4) + 512) & 1023) << 20 | (((y >> 4) + 512) & 1023) << 10 | (((z >> 4) + 512) & 1023); }
}
