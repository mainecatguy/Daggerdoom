version "4.14"

// Town stitch test. Its state rides in the player inventory across map changes, and it reports in Daggerfall world units.
// Route: mark the world table, run to the town, stop at a closed gate, open it, walk in, walk back out,
// cross the exit line, return to the marked spot, and check every record.
// Carried by the player, so the test state survives map changes and saves.
class StitchState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, wait, gateTics, under, jumps;
	double startWX, startWY, lastWX, lastWY, maxStep;
	bool hasLast, marked, gateBlocked, resumed;
}

class StitchHarness : EventHandler
{
	StitchState st;
	bool loaded, saveTown, skipGate;

	void Pull()
	{
		phase = st.phase; wait = st.wait; gateTics = st.gateTics; under = st.under; jumps = st.jumps;
		startWX = st.startWX; startWY = st.startWY; lastWX = st.lastWX; lastWY = st.lastWY; maxStep = st.maxStep;
		hasLast = st.hasLast; marked = st.marked; gateBlocked = st.gateBlocked; resumed = st.resumed;
	}

	void Push()
	{
		st.phase = phase; st.wait = wait; st.gateTics = gateTics; st.under = under; st.jumps = jumps;
		st.startWX = startWX; st.startWY = startWY; st.lastWX = lastWX; st.lastWY = lastWY; st.maxStep = maxStep;
		st.hasLast = hasLast; st.marked = marked; st.gateBlocked = gateBlocked; st.resumed = resumed;
	}

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		let pawn = players[0].mo;
		if (!st) st = StitchState(pawn.FindInventory("StitchState"));
		if (!st) st = StitchState(pawn.GiveInventoryType("StitchState"));
		if (!st) return;
		if (!loaded) { Pull(); loaded = true; saveTown = @SAVETOWN@; skipGate = @SKIPGATE@; } // set at run time: a constant false in an if dropped the whole function body
		RunStitch();
		Push();
	}

	const S = 0.75;
	const HALF = 12288.0;
	const TILE = 192.0;
	const SPEED = @SPEED@;

	int phase, wait, stitchSeen, gateTics, under, bad, jumps;
	double townX, townY, startWX, startWY, lastWX, lastWY, maxStep, closedBest;
	bool hasLast, done, marked, gateBlocked, resumed;
	Vector2 outside, inside, gateMid;
	Array<DFDoor> leaves;

	static bool InTown() { return CVar.FindCVar("dd_tm_intown").GetInt() != 0; }
	static int Stitches() { return CVar.FindCVar("dd_tm_stitches").GetInt(); }

	void ReadTown()
	{
		String body = Wads.ReadLump(Wads.CheckNumForName("DDTOWN", Wads.ns_global));
		Array<String> rows;
		body.Split(rows, "\n", TOK_SKIPEMPTY);
		for (int i = 0; i < rows.Size(); i++)
		{
			Array<String> f;
			rows[i].Split(f, " ", TOK_SKIPEMPTY);
			if (f.Size() >= 3 && f[0] == "origin") { townX = f[1].ToDouble(); townY = f[2].ToDouble(); }
		}
	}

	double WX(Actor a)
	{
		if (InTown()) return a.pos.x / S + townX;
		return (a.pos.x + CVar.FindCVar("dd_tm_originx").GetInt() * TILE + HALF) / S;
	}

	double WY(Actor a)
	{
		if (InTown()) return a.pos.y / S + townY;
		return (a.pos.y + CVar.FindCVar("dd_tm_originy").GetInt() * TILE + HALF) / S;
	}

	Vector2 ToLocal(double wx, double wy)
	{
		if (InTown()) return ((wx - townX) * S, (wy - townY) * S);
		return (wx * S - CVar.FindCVar("dd_tm_originx").GetInt() * TILE - HALF, wy * S - CVar.FindCVar("dd_tm_originy").GetInt() * TILE - HALF);
	}

	void Finish(String text)
	{
		Console.Printf("STITCHRESULT %s jumps=%d under=%d maxStep=%.1f stitches=%d", text, jumps, under, maxStep, Stitches());
		Console.Printf("STITCHDONE");
		done = true;
	}

	void Drive(Actor p, Vector2 to)
	{
		Vector2 d = to - p.pos.xy;
		double len = d.Length();
		if (len < 1) { p.vel.xy = (0, 0); return; }
		p.vel.xy = d / len * min(SPEED, len);
		p.angle = atan2(d.y, d.x);
	}

	// Three marks beside the start: a corpse, a wounded imp, and a dropped item.
	void Mark(Actor p)
	{
		startWX = WX(p);
		startWY = WY(p);
		let dead = Actor.Spawn("ZombieMan", p.pos + (320, 200, 0));
		let hurt = Actor.Spawn("DoomImp", p.pos + (320, -200, 0));
		let item = Actor.Spawn("Clip", p.pos + (200, 0, 0));
		hurt.bDORMANT = false;
		hurt.A_SetHealth(17);
		hurt.bNOTARGET = true;
		dead.DamageMobj(null, null, 100000, 'None');
		item.bDROPPED = true;
		marked = true;
		Console.Printf("STITCHMARK start=%.1f,%.1f", startWX, startWY);
	}

	int Check(Actor p)
	{
		int corpses = 0, wounded = 0, items = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while ((a = Actor(it.Next())))
		{
			double dx = WX(a) - startWX, dy = WY(a) - startWY;
			if (a is "ZombieMan" && a.health <= 0 && (dx - 320 / S, dy - 200 / S).Length() < 64) corpses++;
			if (a is "DoomImp" && a.health == 17 && (dx - 320 / S, dy + 200 / S).Length() < 96) wounded++;
			if (a is "Clip" && !Inventory(a).owner && (dx - 200 / S, dy).Length() < 64) items++;
		}
		Console.Printf("STITCHCHECK corpses=%d wounded=%d items=%d records=%d", corpses, wounded, items, CVar.FindCVar("dd_tm_records").GetInt());
		return (corpses == 1 && wounded == 1 && items == 1) ? 1 : 0;
	}

	// The gate nearest the player: its leaves, midpoint, and the points on each side.
	bool FindGate(Actor p)
	{
		leaves.Clear();
		Array<DFDoor> all;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while ((d = DFDoor(it.Next()))) all.Push(d);
		if (all.Size() < 2) return false;
		DFDoor best = all[0];
		for (int i = 1; i < all.Size(); i++)
			if ((all[i].pivotX - p.pos.x, all[i].pivotY - p.pos.y).Length() < (best.pivotX - p.pos.x, best.pivotY - p.pos.y).Length()) best = all[i];
		DFDoor mate = null;
		for (int i = 0; i < all.Size(); i++)
		{
			if (all[i] == best) continue;
			if (!mate || (all[i].pivotX - best.pivotX, all[i].pivotY - best.pivotY).Length() < (mate.pivotX - best.pivotX, mate.pivotY - best.pivotY).Length()) mate = all[i];
		}
		leaves.Push(best);
		leaves.Push(mate);
		gateMid = ((best.pivotX + mate.pivotX) / 2, (best.pivotY + mate.pivotY) / 2);
		Vector2 along = (mate.pivotX - best.pivotX, mate.pivotY - best.pivotY).Unit();
		Vector2 normal = (-along.y, along.x);
		if ((p.pos.xy - gateMid) dot normal < 0) normal = -normal;	// points from the gate toward the player's side
		outside = gateMid + normal * 260;
		inside = gateMid - normal * 420;
		Console.Printf("STITCHGATE mid=%.0f,%.0f outside=%.0f,%.0f inside=%.0f,%.0f", gateMid.x, gateMid.y, outside.x, outside.y, inside.x, inside.y);
		return true;
	}

	void RunStitch()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		if (townX == 0) ReadTown();
		if (level.maptime < 2) { hasLast = hasLast && level.maptime >= 1; return; }
		if (skipGate && !resumed) { resumed = true; phase = 8; hasLast = false; }

		double wx = WX(p), wy = WY(p);
		if (hasLast)
		{
			double step = (wx - lastWX, wy - lastWY).Length() * S;
			maxStep = max(maxStep, step);
			if (step > SPEED * 1.6 + 4) { jumps++; Console.Printf("STITCHJUMP %.1f at tic %d phase %d", step, level.maptime, phase); }
		}
		if (p.pos.z < p.floorz - 0.1) under++;
		lastWX = wx;
		lastWY = wy;
		hasLast = true;

		switch (phase)
		{
		case 0:	// Mark the table in the wilderness, then wait for the corpse to settle.
			if (InTown()) { phase = 8; break; }	// A loaded town save starts here.
			if (!marked) { Mark(p); wait = level.maptime + 70; }
			if (level.maptime >= wait) phase = 1;
			break;
		case 1:	// Run west into the town's entry zone.
			p.vel.xy = (-SPEED, 0);
			p.angle = 180;
			if (InTown())
			{
				Console.Printf("STITCHENTER tic=%d", level.maptime);
				if (saveTown) { Level.MakeAutoSave(); wait = level.maptime + 35; phase = 9; break; }
				FindGate(p);
				phase = 2;
			}
			break;
		case 2:	// Reach the point in front of the closed gate.
			Drive(p, outside);
			if ((p.pos.xy - outside).Length() < 16) { closedBest = 1e9; gateTics = 0; phase = 3; }
			break;
		case 3:	// Push into the closed gate. It must hold.
			Drive(p, gateMid);
			closedBest = min(closedBest, (p.pos.xy - gateMid).Length());
			if (++gateTics > 50)
			{
				gateBlocked = closedBest > 8;
				Console.Printf("STITCHGATEHOLD closest=%.1f blocked=%d", closedBest, gateBlocked);
				for (int i = 0; i < leaves.Size(); i++) leaves[i].TryUse(p);
				wait = level.maptime + 60;
				phase = 4;
			}
			break;
		case 4:	// Let both leaves swing open.
			Drive(p, outside);
			if (level.maptime >= wait)
			{
				Console.Printf("STITCHGATEOPEN swung=%.1f,%.1f", leaves[0].swung, leaves[1].swung);
				gateTics = 0;
				phase = 5;
			}
			break;
		case 5:	// Walk through into the city.
			Drive(p, inside);
			if ((p.pos.xy - inside).Length() < 24) { Console.Printf("STITCHINSIDE at %.0f,%.0f", p.pos.x, p.pos.y); phase = 6; gateTics = 0; }
			else if (++gateTics > 700) { Finish("FAIL could not pass the open gate"); return; }
			break;
		case 6:	// Back out through the gate.
			Drive(p, outside);
			if ((p.pos.xy - outside).Length() < 24) phase = 7;
			else if (++gateTics > 700) { Finish("FAIL could not leave through the gate"); return; }
			break;
		case 7:	// Past the exit line and back to the wilderness.
		case 8:
			if (InTown())
			{
				Vector2 away = (outside - gateMid);
				if (phase == 8) { Vector2 goal = ToLocal(startWX != 0 ? startWX : wx + 8000, wy); Drive(p, goal); }
				else Drive(p, p.pos.xy + away.Unit() * 400);
			}
			else
			{
				Console.Printf("STITCHLEFT tic=%d", level.maptime);
				leaves.Clear();
				wait = level.maptime + 2;
				phase = 10;
			}
			break;
		case 9:	// Stop after writing the town save.
			if (level.maptime >= wait) Finish("SAVED");
			break;
		case 10:	// Return to the marks.
		{
			Vector2 target = ToLocal(startWX, startWY);
			Drive(p, target);
			if ((p.pos.xy - target).Length() < 48)
			{
				wait = level.maptime + 20;
				phase = 11;
			}
			break;
		}
		case 11:
			p.vel.xy = (0, 0);
			if (level.maptime >= wait)
			{
				int ok = Check(p);
				Finish(ok && (gateBlocked || skipGate) && jumps == 0 && under == 0 ? "PASS" : "FAIL");
			}
			break;
		}
	}
}
