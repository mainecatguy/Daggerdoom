version "4.10"

// Movement parity and bullet test. Uses UZDoom's real collision. Does nothing unless a DFPARITY lump is loaded.

class DFParityProbe : Actor
{
	Default { +NOGRAVITY; +SOLID; } // solid, so the door objects' collision actors block it
	States { Spawn: TNT1 A -1; Stop; }
}

class DFParity : EventHandler
{
	const ChecksPerTic = 60000;
	const DoorWait = 90;
	const Pitch = 8; // walking grid; results are reported on the shared 16-unit grid
	const LineItems = 40;
	const SubSteps = 2;

	Array<double> seedX, seedY, seedZ, shotX, shotY, shotZ, shotAngle, shotPitch;
	Array<int> doorIds;
	Array<double> queryX, queryY, queryZ;
	Array<double> queueX, queueY, queueZ;
	Map<int, int> seen;
	double radius, standHeight, crouchHeight, step, originX, originY, originZ;
	DFParityProbe probe;
	int stage, seedAt, queueAt, wait;
	bool active, shotsFired;
	String pending;
	Array<Actor> links;
	Array<double> linkX0, linkY0;
	int linksTotal;
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
			else if (p[0] == "Q") { queryX.Push(p[1].ToDouble()); queryY.Push(p[2].ToDouble()); queryZ.Push(p[3].ToDouble()); }
		}
		probe = DFParityProbe(Actor.Spawn("DFParityProbe", (originX, originY, originZ)));
		probe.A_SetSize(radius, standHeight);
		probe.MaxStepHeight = step;
		probe.MaxDropoffHeight = 32767;
		// The player start would block the probe. Door collision actors are the only actors the test should meet.
		for (int i = 0; i < MAXPLAYERS; i++) if (playeringame[i] && players[i].mo) players[i].mo.bSOLID = false;
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
		int i = int((x - originX) / Pitch), j = int((y - originY) / Pitch), k = int((z - originZ) / 8);
		return (i & 0x7FF) | ((j & 0x7FF) << 11) | ((k & 0x3FF) << 22);
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
		if (int(x - 12) % 16 == 0 && int(y - 12) % 16 == 0) Emit(x, y, z);
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
		if (!shotsFired)
		{
			shotsFired = true;
			let it = ThinkerIterator.Create("DFDoorBlocker", Thinker.STAT_DEFAULT);
			Actor a;
			while (a = Actor(it.Next())) { links.Push(a); linkX0.Push(a.pos.x); linkY0.Push(a.pos.y); }
			ReportDoors("closed");
			FireShots(); AnswerQueries();
		}
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
				// Short moves, settling on the floor after each, as a walking player does. One long
				// move would keep the body at the old height and falsely hit a lintel at the foot of a stair.
				double cx = x, cy = y, cz = z;
				bool ok = true;
				for (int s = 1; s <= SubSteps; s++)
				{
					FCheckPosition tm;
					double tx = x + dx[d] * Pitch * s / SubSteps, ty = y + dy[d] * Pitch * s / SubSteps;
					probe.SetOrigin((cx, cy, cz), false);
					budget--;
					if (!probe.CheckMove((tx, ty), PCM_DROPOFF, tm)) { ok = false; break; }
					cx = tx; cy = ty; cz = tm.floorz;
				}
				if (ok) Push(cx, cy, cz);
			}
		}
	}

	// Door objects are DFDoorBlocker actors from the doors package. Use on any link swings its whole door.
	void OpenDoors()
	{
		for (int i = 0; i < links.Size(); i++)
		{
			// The real use path, as the player takes it: DFDoorBlocker.Used asks its door to swing.
			// The user stands at the link's height, because a door ignores a user on another floor.
			probe.SetOrigin((originX, originY, links[i].pos.z + 1), false);
			links[i].Used(probe);
		}
		probe.SetOrigin((originX, originY, originZ), false);
		Console.Printf("DFDOORSTATE using %d links", links.Size());
	}

	void ReportDoors(String when)
	{
		int moved = 0;
		for (int i = 0; i < links.Size(); i++)
			if (abs(links[i].pos.x - linkX0[i]) + abs(links[i].pos.y - linkY0[i]) > 1) moved++;
		Console.Printf("DFDOORSTATE %s links %d moved %d", when, links.Size(), moved);
	}

	bool AdvanceMode()
	{
		stage++;
		if (stage == 2)
		{
			OpenDoors();
			wait = DoorWait;
		}
		if (stage == 3) ReportDoors("opened");
		if (stage >= 4)
		{
			active = false;
			Console.Printf("DFPARITYDONE");
			return false;
		}
		BeginMode();
		return true;
	}

	// Runs before any door opens, because the visible Daggerfall mesh shows doors closed.
	// Reports whether a standing body fits at each queried position, whether or not a flood can reach it.
	void AnswerQueries()
	{
		probe.A_SetSize(radius, standHeight);
		probe.bTHRUACTORS = true; // asks about the map alone, as before doors were objects
		for (int n = 0; n < queryX.Size(); n++)
		{
			FCheckPosition tm;
			probe.SetOrigin((queryX[n], queryY[n], queryZ[n]), false);
			bool fits = probe.CheckPosition((queryX[n], queryY[n]), false, tm) && tm.ceilingz - tm.floorz >= standHeight;
			Console.Printf("DFQ %d %.0f %.0f %.1f floor %.1f ceiling %.1f", fits ? 1 : 0, queryX[n], queryY[n], queryZ[n], tm.floorz, tm.ceilingz);
		}
		probe.bTHRUACTORS = false;
	}

	void FireShots()
	{
		for (int n = 0; n < shotX.Size(); n++)
		{
			FLineTraceData data;
			probe.SetOrigin((shotX[n], shotY[n], shotZ[n]), false);
			bool hit = probe.LineTrace(shotAngle[n], 4096, shotPitch[n], 0, 0, 0, 0, data);
			Console.Printf("DFB %d %d %.2f %.2f %.2f", n, hit ? 1 : 0, data.HitLocation.X, data.HitLocation.Y, data.HitLocation.Z);
		}
	}
}
