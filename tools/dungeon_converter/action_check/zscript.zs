version "4.10"

// In-game Scourg Barrow action check, run by action_check.py. Prints "AC <name> PASS|FAIL <detail>", then ACDONE.
// Uses real aiming, the real door use path, real physics for falls and jumps, and real ticking.

class DFACBody : Actor
{
	Default { Radius 10; Height 40; +SOLID +NOGRAVITY +DONTSPLASH }
	States { Spawn: TNT1 A -1; Stop; }
}

class DFActionCheck : EventHandler
{
	DFActionHandler sys;
	int stage, wait, passed, failed, sub;
	Actor body;
	double mark;
	bool finished;
	Array<DFDoor> doors;
	int pushTics;
	vector2 push;

	PlayerPawn Pawn() { return PlayerPawn(players[consoleplayer].mo); }
	DFAction Rec(int id) { return sys.actions[id]; }

	void Report(String name, bool ok, String detail = "")
	{
		if (ok) passed++; else failed++;
		Console.Printf("AC %s %s %s", name, ok ? "PASS" : "FAIL", detail);
	}

	vector3 Middle(DFAction a) { return a.ToWorld((a.boxMin + a.boxMax) / 2, a.fraction); }

	void Put(PlayerPawn p, vector3 at)
	{
		p.SetOrigin(at, false);
		p.vel = (0, 0, 0);
		p.FindFloorCeiling();
		p.player.viewz = p.pos.z + p.player.viewheight;
	}

	// Stands where the record can be aimed at, as a player would, and sends the real direct use.
	bool UseReal(DFAction a)
	{
		let p = Pawn();
		vector3 mid = Middle(a);
		double reach = max(a.boxMax.x - a.boxMin.x, a.boxMax.y - a.boxMin.y) / 2;
		for (int dist = int(reach) + 16; dist <= reach + 56; dist += 12)
			for (int k = 0; k < 16; k++)
			{
				double turn = k * 22.5;
				// Try each walkable level from the object's top downward, aiming at the closest height on it.
				for (double z = mid.z + 40; z >= mid.z - 200; z -= 24)
				{
					Put(p, (mid.x + cos(turn) * dist, mid.y + sin(turn) * dist, z));
					if (p.floorz > z || p.ceilingz - p.floorz < p.height) continue;
					p.SetZ(p.floorz);
					if (!p.TestMobjLocation()) continue;
					p.player.viewz = p.pos.z + p.player.viewheight;
					p.angle = turn + 180;
					double flat = (mid.xy - p.pos.xy).Length();
					double bottom = a.pivot.z + a.boxMin.z + 1, top = a.pivot.z + a.boxMax.z - 1;
					double aimZ = bottom < top ? clamp(p.player.viewz, bottom, top) : mid.z;
					p.pitch = -atan2(aimZ - p.player.viewz, flat);
					if (sys.Aimed(p, p.UseRange) == a) { a.Receive(p, DFAction.FROM_DIRECT); return true; }
				}
			}
		return false;
	}

	override void WorldTick()
	{
		if (finished || level.time < 10) return;
		if (!sys)
		{
			sys = DFActionHandler(EventHandler.Find("DFActionHandler"));
			let it = ThinkerIterator.Create("DFDoor");
			DFDoor d;
			while (d = DFDoor(it.Next())) doors.Push(d);
			if (!sys || sys.actions.Size() != 50) { Report("load", false, "records missing"); Finish(); return; }
			Report("load", true, String.Format("%d records", sys.actions.Size()));
			// Keeps one launch near 30 s. Records 1 and 5 keep real timing; the others are checked for route and end state.
			foreach (a : sys.actions) if (a.id != 1 && a.id != 5) a.rate *= 3;
		}
		if (pushTics > 0) { pushTics--; Pawn().vel.x = push.x; Pawn().vel.y = push.y; } // holding forward through a jump
		if (wait > 0) { wait--; return; }
		Step();
	}

	void Finish()
	{
		finished = true;
		Console.Printf("ACDONE passed %d failed %d", passed, failed);
	}

	// Lever or switch records and what each moves. A negative target is a door record.
	int SourceOf(int i)
	{
		switch (i) { case 0: return 30; case 1: return 31; case 2: return 37; case 3: return 44; case 4: return 46; case 5: return 40; }
		return 41;
	}

	int TargetOf(int i)
	{
		switch (i) { case 0: return 29; case 1: return 32; case 2: return 39; case 3: return 48; case 4: return 49; case 5: return -43; }
		return -42;
	}

	void Step()
	{
		let p = Pawn();
		DFAction lid = Rec(1);
		switch (stage)
		{
		case 0: // Trigger rules: a click-only lid ignores a walk-on.
			lid.Receive(p, DFAction.FROM_WALKON);
			Report("trigger-filter", lid.phase == DFAction.AT_START);
			Put(p, Middle(lid) + (0, 0, 60));
			mark = 0; wait = 45; stage++;
			break;
		case 1: // A closed lid holds the player up.
			Report("closed-lid-solid", p.pos.z > 1340, String.Format("z %.1f", p.pos.z));
			Put(p, (672, 439, 1345));
			Report("lid-real-aim", UseReal(lid));
			Report("lid-started", lid.phase == DFAction.FORWARD);
			Put(p, (672, 439, 1345)); // out of the lid's swing, which would otherwise wait for the player
			wait = 75; stage++;
			break;
		case 2: // Duration 40 = 2 s = 70 tics. Open coffin drops the player into the level below.
			Report("lid-finished", lid.phase == DFAction.AT_END, String.Format("fraction %.2f", lid.fraction));
			Put(p, lid.ToWorld(((lid.boxMin.x + lid.boxMax.x) / 2, (lid.boxMin.y + lid.boxMax.y) / 2, 0), 0) + (0, 0, 40));
			wait = 60; stage++;
			break;
		case 3:
			Report("open-coffin-drop", p.pos.z < 1200, String.Format("landed z %.1f at %.0f,%.0f", p.pos.z, p.pos.x, p.pos.y));
			sub = 0; stage++;
			break;
		case 4: // Real jump from the crypt floor over the rim, trying each side.
		{
			if (sub >= 8) { Report("jump-into-coffin", false, String.Format("no side worked; best peak %.1f", mark)); stage = 6; break; }
			double turn = sub * 45;
			vector3 c = lid.ToWorld(((lid.boxMin.x + lid.boxMax.x) / 2, (lid.boxMin.y + lid.boxMax.y) / 2, 0), 0);
			Put(p, (c.x + cos(turn) * 62, c.y + sin(turn) * 62, 1345));
			if (!p.TestMobjLocation() || abs(p.floorz - 1344) > 10) { sub++; break; }
			p.SetZ(p.floorz);
			push = (-cos(turn) * 6, -sin(turn) * 6);
			p.vel = (push.x, push.y, p.JumpZ);
			pushTics = 14;
			wait = 45; stage = 5;
			break;
		}
		case 5:
			Console.Printf("ACINFO jump side %d ended %.0f,%.0f,%.0f", sub, p.pos.x, p.pos.y, p.pos.z);
			if (p.pos.z < 1200) { Report("jump-into-coffin", true, String.Format("side %d landed z %.1f", sub, p.pos.z)); stage = 6; }
			else { sub++; stage = 4; }
			break;
		case 6: // Door 16 used directly moves its linked wall.
			Put(p, Rec(16).pivot + (0, 0, 2));
			Rec(16).door.TryUse(p);
			Report("door-chain-start", Rec(5).phase == DFAction.FORWARD, "door 16 -> wall 5");
			wait = Rec(5).rate > 0 ? int(1 / Rec(5).rate) + 4 : 4; stage++;
			break;
		case 7:
			Report("door-chain-end", Rec(5).phase == DFAction.AT_END, String.Format("moved %.0f", Rec(5).travel.Length()));
			// Walk-on plate 27 casts through the seam, then opens door 26.
			Put(p, Rec(27).pivot + (0, 0, 2));
			p.vel = (1, 0, 0);
			wait = 6; stage++;
			break;
		case 8:
			Report("walkon-chain", Rec(27).activationCount > 0 && Rec(26).door.swung > 0, String.Format("rule requests %d", Rec(27).ruleRequests));
			sub = 0; stage++;
			break;
		case 9: // Every lever and switch, by real aim, moves its target.
		{
			if (sub >= 7) { stage = 11; break; }
			int source = SourceOf(sub);
			Report(String.Format("use-%d", source), UseReal(Rec(source)));
			int target = TargetOf(sub);
			Put(p, (672, 439, 1345)); // clear of every moving object
			wait = (target >= 0 ? int(1 / Rec(target).rate) : 56) + 4; stage = 10;
			break;
		}
		case 10:
		{
			int t = TargetOf(sub);
			bool ok = t >= 0 ? Rec(t).phase == DFAction.AT_END : Rec(-t).door.swung > 0;
			Report(String.Format("chain-target-%d", abs(t)), ok);
			sub++; stage = 9;
			break;
		}
		case 11: // Reverse on the next activation, as Daggerfall does.
			Rec(39).Receive(p, DFAction.FROM_ACTION);
			Report("reverse-start", Rec(39).phase == DFAction.REVERSE);
			wait = int(1 / Rec(39).rate) + 4; stage++;
			break;
		case 12:
		{
			Report("reverse-end", Rec(39).phase == DFAction.AT_START && Rec(39).fraction == 0);
			// A body in the path stalls the move. It resumes when clear.
			let a = Rec(29);
			a.Receive(p, DFAction.FROM_ACTION); // portcullis back up
			wait = int(1 / a.rate) + 4; stage++;
			break;
		}
		case 13:
		{
			let a = Rec(29);
			let c = a.cells[0];
			vector3 at = a.ToWorld((c.lx, c.ly, c.lz), 0.5);
			body = Actor.Spawn("DFACBody", (at.x, at.y, at.z - 20), NO_REPLACE);
			a.Receive(p, DFAction.FROM_ACTION);
			wait = int(1 / a.rate) + 10; stage++;
			break;
		}
		case 14:
		{
			let a = Rec(29);
			Report("stall-holds", a.phase == DFAction.FORWARD && a.stalled && a.fraction < 1, String.Format("fraction %.2f", a.fraction));
			body.Destroy();
			wait = int(1 / a.rate) + 4; stage++;
			break;
		}
		case 15:
			Report("stall-resumes", Rec(29).phase == DFAction.AT_END);
			stage++;
			break;
		case 16: // A body riding the top of a moving object is carried.
		{
			let a = Rec(39);
			double best = -1e9; vector3 top = a.pivot;
			foreach (c : a.cells) if (c.pos.z > best) { best = c.pos.z; top = c.pos; }
			Put(p, (top.x, top.y, top.z + 16));
			p.SetZ(top.z + 16);
			mark = p.pos.z;
			a.Receive(p, DFAction.FROM_ACTION);
			wait = int(1 / a.rate) + 4; stage++;
			break;
		}
		case 17:
		{
			let a = Rec(39);
			double moved = p.pos.z - mark;
			// The object may sink into the floor at the end of its move. The rider then correctly stops on that floor.
			bool onWorldFloor = moved > a.travel.z && p.pos.z <= p.floorz + 1 && p.floorz == p.CurSector.NextLowestFloorAt(p.pos.x, p.pos.y, p.pos.z + 1);
			Report("rider-carried", abs(moved - a.travel.z) < 6 || onWorldFloor, String.Format("moved %.1f of %.1f, world floor %d, z %.1f floorz %.1f", moved, a.travel.z, onWorldFloor, p.pos.z, p.floorz));
			Finish();
			break;
		}
		}
	}
}
