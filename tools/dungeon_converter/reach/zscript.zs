version "4.10"

// Walks a 21-wide body through a converted dungeon with the engine's own collision, from the entrance,
// and records what it can reach. It does not use the converter's links. Inactive unless started with +set dfreach 1.
//
// Stage 1: a standing body (56 tall) walking and stepping up at most 24 units, falling off any ledge.
// Stage 2: also crouching (28 tall).
// Stage 3: also jumping, modelled as a step of up to 40 units (Doom's default jump rises about 40).
// Doors are not in the map file (they are separate objects), so every doorway is open here.
// Moving objects, locks, switches, and spells are not modelled, so what only they open stays unreached.

class DFReachProbe : Actor
{
	Default { Radius 10.5; Height 56; MaxStepHeight 24; +NOGRAVITY; +NOBLOCKMAP; +DROPOFF; +NOTRIGGER; }
	States { Spawn: TNT1 A -1; Stop; }
}

class DFReach : EventHandler
{
	const BATCH = 1200;
	const STEP = 12;
	Array<int> nx, ny, nf, nc, nb;
	int start;
	Array<int> qx, qy, qz;      // the search queue
	Map<int, int> seen;         // state key -> stage that first reached it
	int head, stage, phase, cursor;
	double stepHeight, bodyHeight;
	DFReachProbe probe;
	bool active;
	Array<int> nodeStage;
	int ticks;

	int Key(int x, int y, double z)
	{
		int xi = int(floor((x - nx[start]) / double(STEP) + 0.5)) + 1024, yi = int(floor((y - ny[start]) / double(STEP) + 0.5)) + 1024;
		int zi = int(floor(z / 8.0)) + 128;
		return (xi & 0x7FF) | ((yi & 0x7FF) << 11) | ((zi & 0x1FF) << 22);
	}

	override void PlayerEntered(PlayerEvent e)
	{
		int lump = Wads.CheckNumForName("DFPOINTS", Wads.ns_global);
		if (lump < 0 || !players[e.PlayerNumber].mo) return;
		Array<String> head;
		Wads.ReadLump(lump).Left(64).Split(head, " ");
		if (head.Size() < 5 || head[0] != "S") return;
		let mo = players[e.PlayerNumber].mo;
		mo.SetOrigin((head[2].ToInt(), head[3].ToInt(), head[4].ToInt()), false);
		mo.FindFloorCeiling();
	}

	override void WorldLoaded(WorldEvent e)
	{
		if (CVar.FindCVar("dfreach").GetInt() != 1) return;
		int lump = Wads.CheckNumForName("DFPOINTS", Wads.ns_global);
		if (lump < 0) { Console.Printf("DFREACH ERROR no DFPOINTS lump"); return; }
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n");
		for (int i = 0; i < lines.Size(); i++)
		{
			Array<String> p;
			lines[i].Split(p, " ");
			if (p.Size() < 2) continue;
			if (p[0] == "S") start = p[1].ToInt();
			else if (p[0] == "N") { nx.Push(p[2].ToInt()); ny.Push(p[3].ToInt()); nf.Push(p[4].ToInt()); nc.Push(p[5].ToInt()); }
		}
		for (int i = 0; i < nx.Size(); i++) nodeStage.Push(0);
		active = true;
		Console.Printf("DFREACH LOADED nodes=%d", nx.Size());
	}

	void Enqueue(int x, int y, double z, int st)
	{
		int k = Key(x, y, z);
		if (seen.CheckKey(k)) return;
		seen.Insert(k, st);
		qx.Push(x); qy.Push(y); qz.Push(int(z));
	}

	// Every state that stage s has reached is searched again with the stage's looser body, so its new moves are found.
	void BeginStage(int s)
	{
		stage = s;
		stepHeight = (s == 3) ? 40 : 24;
		bodyHeight = (s >= 2) ? 28 : 56;
		probe.A_SetSize(10.5, bodyHeight);
		probe.MaxStepHeight = stepHeight;
		head = 0;
		int n = qx.Size(); // the queue keeps every state found so far, so searching it again from the start finds the new moves
		Console.Printf("DFREACH STAGE %d begins with %d states", s, n);
	}

	override void WorldTick()
	{
		if (!active || !players[0].mo) return;
		PlayerPawn pawn = players[0].mo;
		if (phase == 0)
		{
			probe = DFReachProbe(Actor.Spawn("DFReachProbe", pawn.pos));
			pawn.bINVULNERABLE = true;
			Enqueue(nx[start], ny[start], nf[start], 1);
			BeginStage(1);
			phase = 1;
			return;
		}
		if (phase == 1)
		{
			if (++ticks % 100 == 0) Console.Printf("DFREACH PROGRESS stage %d searched %d of %d", stage, head, qx.Size());
			static const int dx[] = { 1, 1, 0, -1, -1, -1, 0, 1 };
			static const int dy[] = { 0, 1, 1, 1, 0, -1, -1, -1 };
			for (int n = 0; n < BATCH && head < qx.Size(); n++, head++)
			{
				int x = qx[head], y = qy[head];
				double z = qz[head];
				for (int d = 0; d < 8; d++)
				{
					probe.SetOrigin((x, y, z), false);
					probe.FindFloorCeiling();
					if (probe.floorz > z + stepHeight + 1) continue; // inside a slab or a different level
					probe.SetZ(max(z, probe.floorz)); // stand at the state's height, or on a floor the body is already inside
					int tx = x + dx[d] * STEP, ty = y + dy[d] * STEP;
					if (!probe.TryMove((tx, ty), 1)) continue;
					Enqueue(tx, ty, probe.floorz, stage);
				}
			}
			if (head >= qx.Size())
			{
				Console.Printf("DFREACH STAGE %d done: %d states", stage, qx.Size());
				phase = 2;
			}
			return;
		}
		if (phase == 2)
		{
			// Each converter node is reached when a searched state sits at its position and height.
			// The scan runs after every stage, so a stage that never finishes still leaves the earlier ones on record.
			for (int n = 0; n < BATCH && cursor < nx.Size(); n++, cursor++)
			{
				if (nodeStage[cursor]) continue;
				bool hit = false;
				for (int dz = -12; dz <= 12 && !hit; dz += 4) hit = seen.CheckKey(Key(nx[cursor], ny[cursor], nf[cursor] + dz));
				if (hit) { nodeStage[cursor] = stage; Console.Printf("DFREACH R %d %d", cursor, stage); }
			}
			if (cursor >= nx.Size())
			{
				cursor = 0;
				Console.Printf("DFREACH SCANNED %d", stage);
				if (stage < 3) { BeginStage(stage + 1); phase = 1; }
				else { Console.Printf("DFREACH DONE states=%d", seen.CountUsed()); phase = 3; }
			}
		}
	}
}
