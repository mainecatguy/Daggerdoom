version "4.10"

// Movement parity and bullet test. Uses UZDoom's real collision. Does nothing unless a DFPARITY lump is loaded.

class DFParityProbe : Actor
{
	Default { +NOGRAVITY; +THRUACTORS; }
	States { Spawn: TNT1 A -1; Stop; }
}

class DFParity : EventHandler
{
	const ChecksPerTic = 6000;
	const DoorWait = 90;
	const Cell = 16;
	const LineItems = 40;

	Array<double> seedX, seedY, seedZ, shotX, shotY, shotZ, shotAngle, shotPitch;
	Array<int> doorIds;
	Array<double> queueX, queueY, queueZ;
	Map<int, int> seen;
	double radius, standHeight, crouchHeight, step, originX, originY, originZ;
	DFParityProbe probe;
	int stage, seedAt, queueAt, wait;
	bool active;
	String pending;
	int pendingCount;

	static const String modeNames[] = { "stand_closed", "crouch_closed", "stand_open", "crouch_open" };

	override void WorldLoaded(WorldEvent e)
	{
		int lump = Wads.CheckNumForName("DFPARITY", Wads.ns_global);
		if (lump < 0 || e.IsSaveGame) return;
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n");
		for (int i = 0; i < lines.Size(); i++)
		{
			Array<String> p;
			lines[i].Split(p, " ");
			if (p.Size() < 2) continue;
			if (p[0] == "B")
			{
				radius = p[1].ToDouble(); standHeight = p[2].ToDouble(); crouchHeight = p[3].ToDouble(); step = p[4].ToDouble();
				originX = p[5].ToDouble(); originY = p[6].ToDouble(); originZ = p[7].ToDouble();
			}
			else if (p[0] == "P") { seedX.Push(p[1].ToDouble()); seedY.Push(p[2].ToDouble()); seedZ.Push(p[3].ToDouble()); }
			else if (p[0] == "T") { shotX.Push(p[1].ToDouble()); shotY.Push(p[2].ToDouble()); shotZ.Push(p[3].ToDouble()); shotAngle.Push(p[4].ToDouble()); shotPitch.Push(p[5].ToDouble()); }
			else if (p[0] == "D") doorIds.Push(p[1].ToInt());
		}
		probe = DFParityProbe(Actor.Spawn("DFParityProbe", (originX, originY, originZ)));
		probe.A_SetSize(radius, standHeight);
		probe.MaxStepHeight = step;
		probe.MaxDropoffHeight = 32767;
		active = true;
		wait = 10;
		BeginMode();
	}

	void BeginMode()
	{
		seen.Clear();
		queueX.Clear(); queueY.Clear(); queueZ.Clear();
		seedAt = -1;
		queueAt = 0;
		probe.A_SetSize(radius, stage % 2 == 0 ? standHeight : crouchHeight);
		Console.Printf("DFMODE %s", modeNames[stage]);
	}

	int KeyOf(double x, double y, double z)
	{
		int i = int((x - originX) / Cell), j = int((y - originY) / Cell), k = int((z - originZ) / 4);
		return (i & 0x3FF) | ((j & 0x3FF) << 10) | ((k & 0x7FF) << 20);
	}

	void Emit(double x, double y, double z)
	{
		pending = pending .. String.Format(" %.0f,%.0f,%.1f", x, y, z);
		if (++pendingCount >= LineItems) Flush();
	}

	void Flush()
	{
		if (pendingCount > 0) Console.Printf("DFF %s %d%s", modeNames[stage], seedAt, pending);
		pending = "";
		pendingCount = 0;
	}

	void Push(double x, double y, double z)
	{
		int key = KeyOf(x, y, z);
		if (seen.CheckKey(key)) return;
		seen.Insert(key, 1);
		queueX.Push(x); queueY.Push(y); queueZ.Push(z);
		Emit(x, y, z);
	}

	// Starts the next seed. A seed Doom cannot stand on is reported and skipped.
	bool NextSeed()
	{
		Flush();
		while (++seedAt < seedX.Size())
		{
			FCheckPosition tm;
			probe.SetOrigin((seedX[seedAt], seedY[seedAt], seedZ[seedAt] + 2), false);
			bool fits = probe.CheckPosition((seedX[seedAt], seedY[seedAt]), false, tm);
			if (fits && abs(tm.floorz - seedZ[seedAt]) <= 24 && tm.ceilingz - tm.floorz >= probe.Height)
			{
				if (!seen.CheckKey(KeyOf(seedX[seedAt], seedY[seedAt], tm.floorz))) { Push(seedX[seedAt], seedY[seedAt], tm.floorz); return true; }
			}
			else Console.Printf("DFSEEDFAIL %s %d", modeNames[stage], seedAt);
		}
		return false;
	}

	override void WorldTick()
	{
		if (!active) return;
		if (wait > 0) { wait--; return; }
		int budget = ChecksPerTic;
		while (budget > 0)
		{
			if (queueAt >= queueX.Size())
			{
				if (NextSeed()) continue;
				Flush();
				if (!AdvanceMode()) return;
				return;
			}
			double x = queueX[queueAt], y = queueY[queueAt], z = queueZ[queueAt];
			queueAt++;
			// Diagonal steps matter: a square body crosses a 45-degree doorway diagonally.
			static const int dx[] = { 1, 0, -1, 0, 1, 1, -1, -1 };
			static const int dy[] = { 0, 1, 0, -1, 1, -1, 1, -1 };
			for (int d = 0; d < 8; d++)
			{
				FCheckPosition tm;
				double nx = x + dx[d] * Cell, ny = y + dy[d] * Cell;
				probe.SetOrigin((x, y, z), false);
				budget--;
				if (probe.CheckMove((nx, ny), PCM_DROPOFF | PCM_NOACTORS, tm)) Push(nx, ny, tm.floorz);
			}
		}
	}

	bool AdvanceMode()
	{
		stage++;
		if (stage == 2)
		{
			for (int i = 0; i < doorIds.Size(); i++) level.ExecuteSpecial(254, null, null, 0, doorIds[i], 64);
			wait = DoorWait;
		}
		if (stage >= 4)
		{
			FireShots();
			active = false;
			Console.Printf("DFPARITYDONE");
			return false;
		}
		BeginMode();
		return true;
	}

	// Runs after the doors-open floods, so door slabs do not count as Doom hits.
	void FireShots()
	{
		for (int n = 0; n < shotX.Size(); n++)
		{
			FLineTraceData data;
			probe.SetOrigin((shotX[n], shotY[n], shotZ[n]), false);
			bool hit = probe.LineTrace(shotAngle[n], 4096, shotPitch[n], TRF_THRUACTORS, 0, 0, 0, data);
			Console.Printf("DFB %d %d %.2f %.2f %.2f", n, hit ? 1 : 0, data.HitLocation.X, data.HitLocation.Y, data.HitLocation.Z);
		}
	}
}
