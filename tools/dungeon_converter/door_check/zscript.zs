version "4.10"

// In-game door check. Load this folder after <slug>_doors.pk3. Prints one DT row per door, then DTDONE.
// Uses the real use path, TryMove, line traces, projectiles, and door ticking.
// Row values: 1 pass, 0 fail, - the side has no standing room.

class DFTestBall : Actor
{
	bool dead, hitDoor;
	Default { Projectile; Radius 2; Height 4; Speed 8; Damage 0; +NOBLOOD +DONTSPLASH -ACTIVATEIMPACT -ACTIVATEPCROSS }
	States
	{
		Spawn: TNT1 A 1;
			Loop;
		Death: TNT1 A 200 { dead = true; hitDoor = BlockingMobj is "DFDoorBlocker"; }
			Stop;
	}
}

class DFTestBody : Actor
{
	Default { Radius 10.5; Height 56; +SOLID +NOGRAVITY +DONTSPLASH }
	States { Spawn: TNT1 A -1; Stop; }
}

class DFSightProbe : Actor
{
	Default { Radius 8; Height 56; +NOBLOCKMAP +NOGRAVITY +NOINTERACTION }
	States { Spawn: TNT1 A -1; Stop; }
}

class DFDoorRow
{
	DFDoor door;
	double cx, cy, nx, ny;
	String use[2], closedBlock[2], walk[2], walkFree[2], traceClosed[2], ballClosed[2], ballOpen[2];
	bool openRoom[2];
	String openBlock, traceOpen, swing, stall, stallWhy, sightClosed, sightOpen;
	int floorCases, floorFails;
	DFTestBall balls[2];
	Actor imp;
	bool overlapped;
}

class DFDoorCheck : EventHandler
{
	const FULL_SWING = 56;
	Array<DFDoorRow> rows;
	Array<double> nodeX, nodeY, nodeF;
	Map<int, int> walkable;
	int stallIndex, stallTic;
	vector3 parking;
	String playerResult;
	bool finished;

	PlayerPawn Pawn() { return PlayerPawn(players[consoleplayer].mo); }

	// A flipped door hangs below its pivot, so its pivot is at the top of the doorway.
	double FloorOf(DFDoor d) { return d.swingDir < 0 ? d.bottom : d.pivotZ; }

	// A flipped panel may extend either way from its hinge. Its tip sweeps toward this side of the closed door's normal.
	// Unflipped doors keep the original probe, so their results stay comparable with earlier runs.
	double PanelSide(DFDoor d) { return d.swingDir < 0 && d.centerX < 0 ? -1 : 1; }
	double SwingSide(DFDoor d) { return PanelSide(d) * d.swingDir; }
	vector2 SwingPoint(DFDoor d) { return d.ToWorld(20 * PanelSide(d), 20 * SwingSide(d), d.closedAngle); }

	void LoadRows()
	{
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		Array<DFDoor> found;
		while (d = DFDoor(it.Next())) found.Push(d);
		for (int i = 0; i < found.Size(); i++) // spawn order, which is DFDOORS order
		{
			let r = new("DFDoorRow");
			r.door = found[i];
			double a = r.door.closedAngle;
			vector2 c = r.door.ToWorld(r.door.centerX, r.door.centerY, a);
			r.cx = c.x; r.cy = c.y; r.nx = -sin(a); r.ny = cos(a);
			rows.Push(r);
		}
		int lump = Wads.CheckNumForName("DFPOINTS", Wads.ns_global);
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n", TOK_SKIPEMPTY);
		foreach (text : lines)
		{
			if (text.Left(2) != "N ") continue;
			Array<String> f;
			text.Split(f, " ");
			nodeX.Push(f[2].ToDouble()); nodeY.Push(f[3].ToDouble()); nodeF.Push(f[4].ToDouble());
			walkable.Insert(CellKey(nodeX[nodeX.Size() - 1], nodeY[nodeY.Size() - 1]), 1);
		}
	}

	int CellKey(double x, double y) { return ((int(floor(x / 12)) + 8192) << 14) | (int(floor(y / 12)) + 8192); }

	// A point in solid rock still resolves to a nearby sector, so require a converted walkable cell close by.
	bool NearWalkable(double x, double y)
	{
		for (int i = -1; i <= 1; i++)
			for (int j = -1; j <= 1; j++)
				if (walkable.CheckKey(CellKey(x + i * 12, y + j * 12))) return true;
		return false;
	}

	bool Stand(PlayerPawn p, DFDoorRow r, double x, double y)
	{
		if (!NearWalkable(x, y)) return false;
		p.SetOrigin((x, y, FloorOf(r.door) + 2), false);
		p.vel = (0, 0, 0);
		p.FindFloorCeiling();
		if (abs(p.floorz - FloorOf(r.door)) > 24 || p.ceilingz - p.floorz < p.height) return false;
		p.SetZ(p.floorz);
		return p.TestMobjLocation();
	}

	// Walks from one side of the doorway to the other with real moves.
	// Lanes shift away from the hinge, as a player would on a diagonal door whose square body is wider across it.
	bool WalkThrough(PlayerPawn p, DFDoorRow r, double side, double from, double to)
	{
		double ax = r.ny, ay = -r.nx; // along the closed door, from hinge to tip
		for (int lane = 0; lane <= 6; lane += 3)
		{
			double ox = r.cx + ax * lane, oy = r.cy + ay * lane;
			if (!Stand(p, r, ox + r.nx * side * from, oy + r.ny * side * from)) continue;
			bool through = true;
			for (double d = from - 3; d >= -to && through; d -= 3)
			{
				through = p.TryMove((ox + r.nx * side * d, oy + r.ny * side * d), true);
				if (through) p.SetZ(p.floorz);
			}
			if (through) return true;
		}
		return false;
	}

	bool RealUse(PlayerPawn p, DFDoorRow r)
	{
		p.angle = atan2(r.cy - p.pos.y, r.cx - p.pos.x);
		p.pitch = 0;
		r.door.moving = 0;
		p.player.usedown = false;
		p.player.cmd.buttons = BT_USE;
		p.CheckUse();
		p.player.cmd.buttons = 0;
		bool started = r.door.moving != 0;
		r.door.moving = 0;
		r.door.stalled = false;
		return started;
	}

	bool TraceHitsDoor(PlayerPawn p, double angle, double range, double height)
	{
		FLineTraceData data;
		p.LineTrace(angle, range, 0, 0, height, 0, 0, data);
		return data.HitType == TRACE_HitActor && data.HitActor is "DFDoorBlocker";
	}

	void ClosedChecks(PlayerPawn p)
	{
		foreach (r : rows)
		{
			for (int s = 0; s < 2; s++)
			{
				double side = s == 0 ? 1 : -1, x = r.cx + r.nx * side * 24, y = r.cy + r.ny * side * 24;
				if (!Stand(p, r, x, y))
				{
					r.use[s] = "-"; r.closedBlock[s] = "-"; r.traceClosed[s] = "-";
					continue;
				}
				r.use[s] = RealUse(p, r) ? "1" : "0";
				Stand(p, r, x, y);
				r.traceClosed[s] = TraceHitsDoor(p, atan2(-r.ny * side, -r.nx * side), 40, r.door.bottom - p.pos.z + 30) ? "1" : "0";
				r.closedBlock[s] = WalkThrough(p, r, side, 24, 24) ? "0" : "1";
			}
			r.sightClosed = SightAcross(p, r);
		}
	}

	// Sight between standing points on the two sides of the doorway. "-" when one side has no room.
	String SightAcross(PlayerPawn p, DFDoorRow r)
	{
		double x = r.cx - r.nx * 30, y = r.cy - r.ny * 30;
		if (!Stand(p, r, r.cx + r.nx * 30, r.cy + r.ny * 30)) return "-";
		vector3 eye = p.pos;
		if (!Stand(p, r, x, y)) return "-";
		let probe = Actor.Spawn("DFSightProbe", (eye.x, eye.y, eye.z), NO_REPLACE);
		bool sees = p.CheckSight(probe, SF_IGNOREVISIBILITY);
		probe.Destroy();
		return sees ? "see" : "blocked";
	}

	void SpawnBalls(PlayerPawn p, bool open)
	{
		foreach (r : rows)
		{
			double a = r.door.closedAngle + r.door.swung * r.door.swingDir;
			vector2 mid = r.door.ToWorld(r.door.centerX, r.door.centerY, a);
			double nx = -sin(a), ny = cos(a), z = r.door.bottom + 30;
			for (int s = 0; s < 2; s++)
			{
				double side = s == 0 ? 1 : -1;
				r.balls[s] = null;
				if (open ? !r.openRoom[s] : r.use[s] == "-") continue;
				let ball = DFTestBall(Actor.Spawn("DFTestBall", (mid.x + nx * side * 12, mid.y + ny * side * 12, z), NO_REPLACE));
				ball.target = p;
				ball.vel = (-nx * side * 8, -ny * side * 8, 0);
				r.balls[s] = ball;
			}
		}
	}

	void ScoreBalls(bool open)
	{
		foreach (r : rows)
		{
			for (int s = 0; s < 2; s++)
			{
				let b = r.balls[s];
				String result = !b ? "-" : b.dead && b.hitDoor ? "1" : "0";
				if (open) r.ballOpen[s] = result; else r.ballClosed[s] = result;
				if (b) b.Destroy();
			}
		}
	}

	void OpenChecks(PlayerPawn p)
	{
		foreach (r : rows)
		{
			r.swing = r.door.swung >= 90 ? "1" : "0";
			for (int s = 0; s < 2; s++)
			{
				double side = s == 0 ? 1 : -1;
				if (r.use[s] == "-") { r.walk[s] = "-"; r.walkFree[s] = "-"; continue; }
				r.walk[s] = WalkThrough(p, r, side, 24, 24) ? "1" : "0";
				foreach (l : r.door.links) l.bSOLID = false;
				r.walkFree[s] = WalkThrough(p, r, side, 24, 24) ? "1" : "0"; // the same walk with this door's collision off
				foreach (l : r.door.links) l.bSOLID = true;
			}
			// Approach the open panel's face from each side with real moves. A side inside a wall has no result.
			double a = r.door.closedAngle + 90 * r.door.swingDir;
			vector2 mid = r.door.ToWorld(r.door.centerX, r.door.centerY, a);
			double fx = -sin(a), fy = cos(a);
			r.openBlock = ""; r.traceOpen = "";
			for (int s = 0; s < 2; s++)
			{
				double side = s == 0 ? 1 : -1;
				double x = mid.x + fx * side * 18, y = mid.y + fy * side * 18;
				r.openRoom[s] = Stand(p, r, x, y);
				if (!r.openRoom[s]) { r.openBlock = r.openBlock .. "-"; r.traceOpen = r.traceOpen .. "-"; continue; }
				r.traceOpen = r.traceOpen .. (TraceHitsDoor(p, atan2(-fy * side, -fx * side), 30, r.door.bottom - p.pos.z + 30) ? "1" : "0");
				bool reached = true;
				for (double d = 16; d >= 0 && reached; d -= 2)
					reached = p.TryMove((mid.x + fx * side * d, mid.y + fy * side * d), true);
				r.openBlock = r.openBlock .. (reached ? "0" : "1");
			}
			r.sightOpen = SightAcross(p, r);
			CheckFloors(p, r);
		}
	}

	// A body on another floor of the door's column must not be blocked by the door.
	void CheckFloors(PlayerPawn p, DFDoorRow r)
	{
		double minX = min(r.door.pivotX, r.cx) - 40, maxX = max(r.door.pivotX, r.cx) + 40;
		double minY = min(r.door.pivotY, r.cy) - 40, maxY = max(r.door.pivotY, r.cy) + 40;
		for (int i = 0; i < nodeX.Size(); i++)
		{
			if (nodeX[i] < minX || nodeX[i] > maxX || nodeY[i] < minY || nodeY[i] > maxY) continue;
			double f = nodeF[i];
			if (f + p.height > r.door.bottom && f < r.door.top) continue;
			p.SetOrigin((nodeX[i], nodeY[i], f), false);
			foreach (l : r.door.links) l.bSOLID = false;
			bool without = p.TestMobjLocation();
			foreach (l : r.door.links) l.bSOLID = true;
			if (!without) continue;
			r.floorCases++;
			if (!p.TestMobjLocation()) r.floorFails++;
		}
	}

	bool Overlaps(DFDoorRow r, Actor t)
	{
		for (int i = 0; i < r.door.links.Size(); i++)
		{
			let l = r.door.links[i];
			if (abs(l.pos.x - t.pos.x) < l.radius + t.radius && abs(l.pos.y - t.pos.y) < l.radius + t.radius
				&& l.pos.z < t.pos.z + t.height && l.pos.z + l.height > t.pos.z) return true;
		}
		return false;
	}

	void SetAll(int dir) { foreach (r : rows) { r.door.moving = dir; r.door.stalled = false; } }

	void SpawnImps()
	{
		foreach (r : rows)
		{
			// In the swing path, clear of the closed door. A body the same size as the player.
			vector2 at = SwingPoint(r.door);
			if (!NearWalkable(at.x, at.y)) { r.stall = "-"; continue; } // swings into solid rock, where no body can stand
			r.imp = Actor.Spawn("DFTestBody", (at.x, at.y, r.door.bottom), NO_REPLACE);
		}
	}

	// The real player, then a real dormant Imp, stand in the swing of the prototype doors.
	void ActorStall(PlayerPawn p, int t)
	{
		static const int proto[] = { 0, 2, 21, 1 };
		if (stallIndex >= 8) return;
		bool imp = stallIndex >= 4;
		let r = rows[proto[stallIndex % 4]];
		int step = t - stallTic;
		vector2 at = SwingPoint(r.door);
		if (step == 0 && !NearWalkable(at.x, at.y))
		{
			playerResult = playerResult .. String.Format(" %s%d:swings-into-rock", imp ? "imp" : "player", proto[stallIndex % 4]);
			stallIndex++;
			stallTic = t + 1;
			return;
		}
		if (step == 0)
		{
			r.door.swung = 0; r.door.moving = 0; r.door.stalled = false; r.door.Place(false);
			p.SetOrigin((r.cx - r.nx * 24 * SwingSide(r.door), r.cy - r.ny * 24 * SwingSide(r.door), FloorOf(r.door)), false);
			if (imp)
			{
				r.imp = Actor.Spawn("DoomImp", (at.x, at.y, FloorOf(r.door)), NO_REPLACE);
				if (r.imp) { r.imp.bDORMANT = true; r.imp.A_SetSize(10.5, 56, false); }
			}
			else
			{
				Stand(p, r, at.x, at.y);
				p.SetOrigin((at.x, at.y, p.pos.z), false);
				r.imp = p;
			}
			r.overlapped = false;
			r.door.moving = 1;
		}
		else if (step <= 24)
		{
			if (r.imp && Overlaps(r, r.imp)) r.overlapped = true;
		}
		if (step == 24)
		{
			bool held = r.door.stalled && r.door.swung < 90 && !r.overlapped;
			playerResult = playerResult .. String.Format(" %s%d:%s(swung%.0f)", imp ? "imp" : "player", proto[stallIndex % 4], held ? "held" : "FAILED", r.door.swung);
			if (imp) { if (r.imp) r.imp.Destroy(); }
			else p.SetOrigin((r.cx - r.nx * 24 * SwingSide(r.door), r.cy - r.ny * 24 * SwingSide(r.door), FloorOf(r.door)), false);
			r.imp = null;
		}
		if (step == 24 + FULL_SWING)
		{
			playerResult = playerResult .. (r.door.swung >= 90 ? "+resumed" : "+NORESUME");
			r.door.swung = 0; r.door.moving = 0; r.door.stalled = false; r.door.Place(false);
			stallIndex++;
			stallTic = t + 1;
		}
	}

	void PrintRows()
	{
		int pass = 0;
		foreach (r : rows)
		{
			Console.Printf("DT door=%d use=%s%s closed=%s%s walk=%s%s walkfree=%s%s trace=%s%s ball=%s%s swing=%s openblock=%s traceopen=%s ballopen=%s%s stall=%s stallwhy=%s sightclosed=%s sightopen=%s floors=%d/%d",
				rows.Find(r), r.use[0], r.use[1], r.closedBlock[0], r.closedBlock[1], r.walk[0], r.walk[1], r.walkFree[0], r.walkFree[1], r.traceClosed[0], r.traceClosed[1],
				r.ballClosed[0], r.ballClosed[1], r.swing, r.openBlock, r.traceOpen, r.ballOpen[0], r.ballOpen[1], r.stall, r.stallWhy, r.sightClosed, r.sightOpen, r.floorCases - r.floorFails, r.floorCases);
		}
		Console.Printf("DTPLAYERSTALL %s", playerResult);
		Console.Printf("DTDONE");
	}

	override void WorldTick()
	{
		if (finished) return;
		int t = level.maptime;
		let p = Pawn();
		if (t == 10)
		{
			LoadRows();
			Console.Printf("DTSTART doors=%d nodes=%d radius=%.2f height=%.1f", rows.Size(), nodeX.Size(), p.radius, p.height);
			parking = p.pos;
			ClosedChecks(p);
			p.SetOrigin(parking, false);
			SpawnBalls(p, false);
		}
		else if (t == 22) { ScoreBalls(false); SetAll(1); }
		else if (t == 22 + FULL_SWING) { OpenChecks(p); p.SetOrigin(parking, false); SpawnBalls(p, true); }
		else if (t == 34 + FULL_SWING) { ScoreBalls(true); SetAll(-1); }
		else if (t == 34 + 2 * FULL_SWING) { SpawnImps(); SetAll(1); }
		else if (t > 34 + 2 * FULL_SWING && t < 34 + 3 * FULL_SWING)
		{
			foreach (r : rows) if (r.imp && Overlaps(r, r.imp)) r.overlapped = true;
		}
		else if (t == 34 + 3 * FULL_SWING)
		{
			foreach (r : rows)
			{
				if (r.stall == "-") { r.stallWhy = "rock"; continue; }
				r.stall = r.door.swung < 90 && r.door.stalled && !r.overlapped ? "1" : "0";
				r.stallWhy = String.Format("swung%.0f,stalled%d,overlap%d", r.door.swung, r.door.stalled, r.overlapped);
				if (r.imp) r.imp.Destroy();
			}
		}
		else if (t == 34 + 4 * FULL_SWING + 4)
		{
			foreach (r : rows) if (r.door.swung < 90) { r.stall = "0"; r.stallWhy = r.stallWhy .. ",noresume"; }
			SetAll(-1);
		}
		else if (t == 34 + 5 * FULL_SWING + 8)
		{
			foreach (r : rows) if (r.door.swung > 0) { r.stall = "0"; r.stallWhy = r.stallWhy .. ",noclose"; }
			stallTic = t + 1;
		}
		else if (stallTic > 0 && t >= stallTic)
		{
			ActorStall(p, t);
			if (stallIndex >= 8) { PrintRows(); finished = true; }
		}
	}
}
