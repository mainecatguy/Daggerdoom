version "4.10"

// In-game check of every flat trapdoor tile (action 18 or 8). Load after <slug>_doors.pk3 and overworld.pk3.
// The player stands on the closed tile, then its real trigger fires: walk-on through DFActionHandler, or the chain's root.
// Prints one TD row per tile, then TDDONE. The escape flood uses the real player body and walks only, with no climbing.

class DFTrapdoorCheck : EventHandler
{
	const SETTLE = 24;
	const WAIT = 110;
	const FLOOD_LIMIT = 60000;
	Array<DFAction> tiles;
	int index, startTic, firedTic;
	bool finished, fired, entered, hasSide, reachesStart;
	String exits;
	vector3 spawnAt;
	double closedZ, enteredZ;
	vector3 mid;
	String row;

	PlayerPawn Pawn() { return PlayerPawn(players[consoleplayer].mo); }

	static bool IsTile(DFAction a)
	{
		if (a.kind != 1 || (a.flag != 18 && a.flag != 8)) return false;
		double w = a.boxMax.x - a.boxMin.x, d = a.boxMax.y - a.boxMin.y;
		return w >= 90 && w <= 100 && d >= 90 && d <= 100 && a.boxMax.z - a.boxMin.z <= 8;
	}

	DFAction Root(DFAction a)
	{
		DFAction root = a;
		for (int depth = 0; depth < 64; depth++)
		{
			DFAction before = null;
			let it = ThinkerIterator.Create("DFAction");
			DFAction o;
			while (o = DFAction(it.Next())) if (o.nextAction == root) { before = o; break; }
			if (!before) break;
			root = before;
		}
		return root;
	}

	// Walks outward from the body's spot on an 8-unit lattice. Reports how far it got and whether it left the pit.
	void Flood(PlayerPawn p, DFAction a, double rim, out int count, out bool escaped, out double high)
	{
		Array<double> xs, ys, zs;
		Map<int, int> keys;
		vector3 from = p.pos;
		xs.Push(from.x); ys.Push(from.y); zs.Push(from.z);
		keys.Insert(32768 * 65536 + 32768, 1);
		// Closed doors do not count as walls here: a player can open them.
		Array<Actor> blockers;
		let doors = ThinkerIterator.Create("DFDoorBlocker");
		Actor door;
		while (door = Actor(doors.Next())) if (door.bSOLID) { blockers.Push(door); door.bSOLID = false; }
		escaped = false;
		high = from.z;
		static const int DX[] = { 8, -8, 0, 0 };
		static const int DY[] = { 0, 0, 8, -8 };
		for (int head = 0; head < xs.Size() && xs.Size() < FLOOD_LIMIT && !escaped; head++)
			for (int k = 0; k < 4; k++)
			{
				double nx = xs[head] + DX[k], ny = ys[head] + DY[k];
				int key = (int(round((nx - from.x) / 8)) + 32768) * 65536 + int(round((ny - from.y) / 8)) + 32768;
				if (keys.CheckKey(key)) continue;
				p.SetOrigin((xs[head], ys[head], zs[head]), false);
				p.FindFloorCeiling();
				p.SetZ(p.floorz);
				if (!p.TryMove((nx, ny), true)) continue;
				p.SetZ(p.floorz);
				keys.Insert(key, 1);
				xs.Push(p.pos.x); ys.Push(p.pos.y); zs.Push(p.pos.z);
				high = max(high, p.pos.z);
				if (p.pos.z >= rim - 1) { escaped = true; break; }
			}
		count = xs.Size();
		foreach (b : blockers) b.bSOLID = true;
		// What the landing area holds: the map start, and any lifts, teleports, or other triggers a player could use to leave.
		reachesStart = false;
		exits = "";
		for (int i = 0; i < xs.Size(); i++)
			if (abs(xs[i] - spawnAt.x) <= 8 && abs(ys[i] - spawnAt.y) <= 8 && abs(zs[i] - spawnAt.z) <= 24) { reachesStart = true; break; }
		let others = ThinkerIterator.Create("DFAction");
		DFAction o;
		while (o = DFAction(others.Next()))
		{
			if (o == a || o.door || !((o.flag >= 1 && o.flag <= 8) || o.flag == 14)) continue;
			vector3 c = o.ToWorld(o.center, o.fraction);
			int ox = int(round((c.x - from.x) / 8)), oy = int(round((c.y - from.y) / 8));
			bool near = false;
			for (int i = -3; i <= 3 && !near; i++)
				for (int j = -3; j <= 3 && !near; j++)
					near = keys.CheckKey((ox + i + 32768) * 65536 + oy + j + 32768);
			if (near && abs(c.z - from.z) <= 128) exits = exits .. String.Format("%s%d:f%d", exits.Length() ? "," : "", o.id, o.flag);
		}
		p.SetOrigin(from, false);
		p.FindFloorCeiling();
	}

	override void WorldTick()
	{
		if (finished) return;
		let p = Pawn();
		int t = level.maptime;
		if (t < 10) return;
		if (t == 10)
		{
			let it = ThinkerIterator.Create("DFAction");
			DFAction a;
			while (a = DFAction(it.Next())) if (IsTile(a)) tiles.Push(a);
			spawnAt = p.pos;
			Console.Printf("TDSTART tiles=%d radius=%.1f height=%.0f", tiles.Size(), p.radius, p.height);
			startTic = t + 1;
			if (tiles.Size() == 0) { Console.Printf("TDDONE"); finished = true; }
			return;
		}
		if (t < startTic) return;
		let a = tiles[index];
		int s = t - startTic;
		if (s > 0 && !fired && a.phase != DFAction.AT_START)
		{
			fired = true;
			firedTic = s;
		}
		if (s == 0)
		{
			mid = a.ToWorld(((a.boxMin.x + a.boxMax.x) / 2, (a.boxMin.y + a.boxMax.y) / 2, a.boxMax.z), 0);
			fired = false;
			firedTic = 0;
			entered = false;
			enteredZ = 0;
			hasSide = PickSide(p);
			if (!hasSide) p.SetOrigin((mid.x, mid.y, mid.z + 1), false);
			p.vel = (0, 0, 0);
			p.FindFloorCeiling();
		}
		else if (s < SETTLE)
		{
			if (hasSide)
			{
				vector2 toMid = mid.xy - p.pos.xy;
				double left = toMid.Length();
				p.vel.xy = left > 4 ? toMid / left * min(6, left) : (0, 0);
				// Measured in the closed tile's frame, because the walk-on trigger can fire on the same tic the body arrives.
				double fx = a.fraction;
				a.fraction = 0;
				vector3 l = a.ToLocal(p.pos);
				a.fraction = fx;
				if (!entered && l.x >= a.boxMin.x && l.x <= a.boxMax.x && l.y >= a.boxMin.y && l.y <= a.boxMax.y)
				{
					entered = true;
					enteredZ = p.pos.z;
				}
			}
		}
		else if (s == SETTLE)
		{
			closedZ = hasSide ? enteredZ : p.pos.z;
			int walkOn = !hasSide ? -1 : entered && abs(enteredZ - mid.z) <= 1;
			row = String.Format("TD record=%d flag=%d trig=%d at %.0f,%.0f,%.0f top=%.1f standZ=%.1f held=%d walkOn=%d", a.id, a.flag, a.trigger, a.pivot.x, a.pivot.y, a.pivot.z, mid.z, closedZ, abs(closedZ - mid.z) <= 1, walkOn);
			if (a.trigger == DFAction.TR_WALKON)
			{
				if (!hasSide) p.vel.x = 1; // the real handler sees a moving player on the tile
			}
			else
			{
				let root = Root(a);
				int source = root.trigger == DFAction.TR_WALKON ? DFAction.FROM_WALKON : root.trigger == DFAction.TR_WALKINTO ? DFAction.FROM_WALKINTO
					: root.trigger == DFAction.TR_ATTACK ? DFAction.FROM_ATTACK : root.trigger == DFAction.TR_DOOR ? DFAction.FROM_DOOR : DFAction.FROM_DIRECT;
				root.Receive(p, source);
				row = row .. String.Format(" root=%d rootTrig=%d", root.id, root.trigger);
			}
		}
		else if (s == SETTLE + WAIT)
		{
			row = row .. String.Format(" fired=%d firedAt=%d", fired, firedTic);
			int count; bool escaped; double high;
			row = row .. String.Format(" end=%d frac=%.2f stalled=%d bodyZ=%.1f drop=%.1f moved=%.1f", a.phase == DFAction.AT_END, a.fraction, a.stalled, p.pos.z, mid.z - p.pos.z, (p.pos.xy - mid.xy).Length());
			[count, escaped, high] = RunFlood(p, a);
			row = row .. String.Format(" walkCells=%d walkOut=%d highest=%.1f reachesStart=%d exits=%s", count, escaped, high, reachesStart, exits.Length() ? exits : "none");
			Console.Printf("%s", row);
			index++;
			startTic = t + 1;
			if (index >= tiles.Size()) { Console.Printf("TDDONE"); finished = true; }
		}
	}

	// Puts the body on the first floor beside the tile, level with it, from which it can really walk on.
	bool PickSide(PlayerPawn p)
	{
		for (int k = 0; k < 4; k++)
		{
			double sx = mid.x + (k == 0 ? 64 : k == 1 ? -64 : 0), sy = mid.y + (k == 2 ? 64 : k == 3 ? -64 : 0);
			p.SetOrigin((sx, sy, mid.z + 2), false);
			p.vel = (0, 0, 0);
			p.FindFloorCeiling();
			if (abs(p.floorz - mid.z) > 1 || p.ceilingz - p.floorz < p.height) continue;
			p.SetZ(p.floorz);
			if (!p.TestMobjLocation() || !p.CheckMove(mid.xy)) continue;
			// The straight walk to the middle must not cross a wall, at either edge of the body.
			double facing = atan2(mid.y - sy, mid.x - sx);
			bool clear = true;
			for (int lane = -1; lane <= 1 && clear; lane++)
			{
				FLineTraceData hit;
				p.LineTrace(facing, 64, 0, TRF_THRUACTORS, 20, 0, lane * p.radius, hit);
				if (hit.HitType != TRACE_HitNone) clear = false;
			}
			if (!clear) continue;
			return true;
		}
		return false;
	}

	int, bool, double RunFlood(PlayerPawn p, DFAction a)
	{
		int count; bool escaped; double high;
		Flood(p, a, mid.z, count, escaped, high);
		return count, escaped, high;
	}
}
