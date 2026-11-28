version "4.10"

// Hitbox verification (tools/monster_width/hitbox_check.py). Needs a converted dungeon with its _doors.pk3.
// A Zombieman, an Imp and a Demon (spawned with replacement, so DRLA picks its own) are tested twice:
// 1. In open space: bullets, melee (side offsets and reach) and an imp fireball must hit inside the stock radius and
//    miss outside it (HBHIT lines).
// 2. Walking every opened door with real TryMove steps. A step where the monster's stock body overlaps the level is a
//    squeeze (HBWALK). At squeezed spots the radius must still be stock, and every unobstructed bullet, punch and
//    fireball passing between the squeeze width and the stock radius must hit it (HBSQUEEZE).
// Then HBDONE.

class HBProbe : Actor
{
	Default { Radius 1; Height 56; +NOBLOCKMAP +NOGRAVITY +NOINTERACTION }
	States { Spawn: TNT1 A -1; Stop; }
}

class HBBall : DoomImpBall
{
	override int SpecialMissileHit(Actor victim)
	{
		let h = HBCheck(EventHandler.Find("HBCheck"));
		if (h && !h.touched)
		{
			h.touched = victim;
			Console.Printf("HBCONTACT %s victim=%.2f,%.2f,%.2f radius=%.2f ball=%.2f,%.2f,%.2f radius=%.2f", victim.GetClassName(), victim.pos.x, victim.pos.y,
				victim.pos.z, victim.radius, pos.x, pos.y, pos.z, radius);
		}
		return -1;
	}
}

class HBShot	// one queued fireball
{
	int mon;
	bool squeeze;
	vector3 stand, from;
	double angle, offset;
	bool want;
}

class HBTally
{
	String name;
	double radius, narrow;
	int ok[3], wrong[3];	// open space: bullet, melee, projectile
	int hitsIn[3], missesOut[3];
	int sqOk[3], sqWrong[3], sqBlocked[3];	// at squeezed spots
	int doors, passed, squeezedDoors, squeezedSteps, openSteps, radiusChanged, queued;
}

class HBCheck : EventHandler
{
	const REACH = 64;	// DEFMELEERANGE
	Array<Actor> mons;
	Array<HBTally> tally;
	Array<HBShot> shots;
	vector3 start, spot;
	double facing;
	Actor touched, ball, victim;
	int shot, shotTic;

	Actor Park(class<Actor> cls, vector3 pos)
	{
		let mo = Actor.Spawn(cls, pos, NO_REPLACE);
		if (!mo) return null;
		mo.Deactivate(null);
		mo.bNOGRAVITY = true;
		mo.SetOrigin(pos, false);
		return mo;
	}

	bool ClearAlong(vector3 from, double angle, double dist)
	{
		let s = Actor.Spawn("HBProbe", from, NO_REPLACE);
		FLineTraceData d;
		s.LineTrace(angle, dist, 0, TRF_THRUACTORS, 32, 0, 0, d);
		s.Destroy();
		return d.HitType == TRACE_HitNone;
	}

	// A point `x` along the shot direction (facing) and `y` to its left of the open spot.
	vector3 At(double x, double y, double z)
	{
		return spot + (x * cos(facing) - y * sin(facing), x * sin(facing) + y * cos(facing), z);
	}

	// An open spot on one of the dungeon's walkable points (DFPOINTS): every shot lane (44 to each side, 100 back, 35
	// on) along one axis is free of level geometry.
	bool FindSpot()
	{
		Array<String> lines;
		Wads.ReadLump(Wads.CheckNumForName("DFPOINTS", Wads.ns_global)).Split(lines, "\n", TOK_SKIPEMPTY);
		foreach (text : lines)
		{
			if (text.Left(2) != "N ") continue;
			Array<String> f;
			text.Split(f, " ");
			vector3 p = (f[2].ToDouble(), f[3].ToDouble(), f[4].ToDouble());
			for (int a = 0; a < 360; a += 90)
			{
				facing = a;
				spot = p;
				bool open = true;
				for (double o = -44; o <= 44 && open; o += 4)
					open = level.IsPointInLevel(At(-100, o, 32)) && ClearAlong(At(-100, o, 0), a, 135);
				if (open) return true;
			}
		}
		return false;
	}

	// A bullet or punch from `from` along `angle`: 1 hit the monster, 0 passed it, -1 the level or a door stopped it.
	int Attack(Actor mo, vector3 from, double angle, double range, bool melee)
	{
		let s = Actor.Spawn("HBProbe", from, NO_REPLACE);
		FTranslatedLineTarget t;
		s.LineAttack(angle, range, 0, 0, melee ? 'Melee' : 'Hitscan', "BulletPuff", (melee ? LAF_ISMELEEATTACK : 0) | LAF_NORANDOMPUFFZ, t);
		int result = t.linetarget == mo ? 1 : 0;
		if (!result)
		{
			FLineTraceData d;
			s.LineTrace(angle, range, 0, 0, 32, 0, 0, d);
			if (d.HitType != TRACE_HitNone && !(d.HitType == TRACE_HitActor && d.HitActor == mo)) result = -1;
		}
		s.Destroy();
		return result;
	}

	void OpenHit(int i, int kind, double offset, double dist, bool want)
	{
		let mo = mons[i];
		let t = tally[i];
		int got = Attack(mo, At(-dist, offset, 0), facing, kind == 1 ? REACH : 135, kind == 1);
		bool ok = got == (want ? 1 : 0);
		if (ok) { t.ok[kind]++; if (want) t.hitsIn[kind]++; else t.missesOut[kind]++; } else t.wrong[kind]++;
		Console.Printf("HBHIT %s %s offset=%.2f dist=%.2f radius=%.3f squeeze=%.3f got=%d want=%d %s", t.name, kind == 1 ? "melee" : "bullet",
			offset, dist, mo.radius, t.narrow, got, want, ok ? "ok" : "WRONG");
	}

	void Queue(int mon, bool squeeze, vector3 stand, vector3 from, double angle, double offset, bool want)
	{
		let q = new("HBShot");
		q.mon = mon; q.squeeze = squeeze; q.stand = stand; q.from = from; q.angle = angle; q.offset = offset; q.want = want;
		shots.Push(q);
	}

	void OpenSpace(int i)
	{
		let mo = mons[i];
		let t = tally[i];
		double r = t.radius, n = t.narrow;
		mo.SetOrigin(spot, false);
		for (int side = -1; side <= 1; side += 2)
		{
			// Bullets and punches: between the squeeze width and the stock radius, and just inside and outside it.
			for (int kind = 0; kind < 2; kind++)
			{
				double dist = kind == 1 ? r + 30 : 100;
				OpenHit(i, kind, side * (n + 1), dist, true);
				OpenHit(i, kind, side * (r - 1), dist, true);
				OpenHit(i, kind, side * (r + 1), dist, false);
			}
			// Fireball (radius 6): touches when its offset is under the radius sum.
			Queue(i, false, spot, At(-90, side * (n + 7), 20), facing, side * (n + 7), true);
			Queue(i, false, spot, At(-90, side * (r + 5), 20), facing, side * (r + 5), true);
			Queue(i, false, spot, At(-90, side * (r + 7), 20), facing, side * (r + 7), false);
		}
		OpenHit(i, 0, 0, 100, true);
		OpenHit(i, 1, 0, r + 30, true);
		// Melee reach is measured to the stock edge.
		OpenHit(i, 1, 0, REACH + r - 1, true);
		OpenHit(i, 1, 0, REACH + r + 1, false);
		mo.SetOrigin(spot + (0, 0, 4000), false);
	}

	bool Stand(Actor p, double x, double y, double floor)
	{
		p.SetOrigin((x, y, floor + 2), false);
		p.FindFloorCeiling();
		if (abs(p.floorz - floor) > 24 || p.ceilingz - p.floorz < p.height) return false;
		p.SetZ(p.floorz);
		if (p.TestMobjLocation()) return true;
		double keep = p.radius;	// may start squeezed, as the door check's bodies do
		p.A_SetSize(p.DD_MoveRadius(), p.height, false);
		bool fits = p.TestMobjLocation();
		p.A_SetSize(keep, p.height, false);
		return fits;
	}

	void SqueezeShots(int i, Actor mo, int door)
	{
		let t = tally[i];
		double r = t.radius, n = t.narrow;
		int clear = 0;
		for (int a = 0; a < 360; a += 90)
		{
			vector2 dir = (cos(a), sin(a)), perp = (-dir.y, dir.x);
			for (int side = -1; side <= 1; side += 2) for (int k = 0; k < 2; k++)
			{
				double offset = side * (k == 0 ? (n + r) / 2 : r - 1);
				for (int kind = 0; kind < 2; kind++)
				{
					vector2 xy = mo.pos.xy - dir * (r + 12) + perp * offset;
					vector3 from = (xy, mo.pos.z);
					if (!level.IsPointInLevel(from + (0, 0, 32))) { t.sqBlocked[kind]++; continue; }
					int got = Attack(mo, from, a, kind == 1 ? REACH : 100, kind == 1);
					if (got == 1) t.sqOk[kind]++; else if (got == 0) t.sqWrong[kind]++; else t.sqBlocked[kind]++;
					if (got != -1) Console.Printf("HBSQHIT %s door=%d %s angle=%d offset=%.2f radius=%.3f squeeze=%.3f %s", t.name, door,
						kind == 1 ? "melee" : "bullet", a, offset, mo.radius, n, got == 1 ? "hit ok" : "miss WRONG");
					// A fireball down the same lane, out past the squeeze width plus its radius.
					// One per doorway and eight per monster keep the run short.
					if (kind == 0 && k == 0 && got == 1 && clear < 1 && t.queued < 8)
					{
						double wide = side * ((n + r) / 2 + 6);
						vector2 b = mo.pos.xy - dir * (r + 12) + perp * wide;
						if (level.IsPointInLevel((b, mo.pos.z + 20))) { clear++; t.queued++; Queue(i, true, mo.pos, (b, mo.pos.z + 20), a, wide, true); }
					}
				}
			}
		}
	}

	void Walk(int i)
	{
		let t = tally[i];
		let body = Park(mons[i].GetClass(), start + (0, 0, 4000));
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		int door = -1;
		while (d = DFDoor(it.Next()))
		{
			door++;
			t.doors++;
			double a = d.closedAngle;
			vector2 c = d.ToWorld(d.centerX, d.centerY, a), nv = (-sin(a), cos(a)), along = (nv.y, -nv.x);
			double floor = d.swingDir < 0 ? d.bottom : d.pivotZ;
			bool passed = false, squeezed = false;
			for (int s = -1; s <= 1 && !passed; s += 2) for (int lane = -12; lane <= 15 && !passed; lane += 3)
			{
				vector2 o = c + along * lane;
				vector2 from = o + nv * s * 36;
				body.bSOLID = true;
				if (!Stand(body, from.x, from.y, floor)) continue;
				int steps = 0, open = 0;
				vector3 first;
				bool through = true;
				for (double dist = 33; dist >= -36 && through; dist -= 3)
				{
					vector2 to = o + nv * s * dist;
					through = body.TryMove(to, true);
					if (!through) break;
					body.SetZ(body.floorz);
					if (abs(body.radius - t.radius) > 0.001) t.radiusChanged++;
					if (body.TestMobjLocation()) open++;
					else { if (!steps) first = body.pos; steps++; }
				}
				if (!through) continue;
				passed = true;
				t.passed++;
				t.openSteps += open;
				t.squeezedSteps += steps;
				Console.Printf("HBWALK %s door=%d passed side=%d lane=%d openSteps=%d squeezedSteps=%d radius=%.3f", t.name, door, s, lane, open, steps, body.radius);
				if (steps) { squeezed = true; body.SetOrigin(first, false); SqueezeShots(i, body, door); }
			}
			if (squeezed) t.squeezedDoors++;
		}
		body.ClearCounters();
		body.Destroy();
	}

	override void WorldTick()
	{
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		int time = level.maptime;
		if (time == 2)
		{
			start = pmo.pos;
			Array<Actor> old;
			let it = ThinkerIterator.Create("Actor");
			Actor mo;
			while (mo = Actor(it.Next())) if (mo.bIsMonster && !mo.player) old.Push(mo);
			foreach (c : old) { c.ClearCounters(); c.Destroy(); }
			static const Name kinds[] = { 'ZombieMan', 'DoomImp', 'Demon' };
			for (int i = 0; i < 3; i++)
			{
				let m = Actor.Spawn(kinds[i], start, ALLOW_REPLACE);
				if (m) { m.bSOLID = false; m.Deactivate(null); }
			}
		}
		if (time == 20)
		{
			let it = ThinkerIterator.Create("Actor");
			Actor mo;
			while (mo = Actor(it.Next()))
				if (mo.bIsMonster && !mo.player && (mo.pos.xy - start.xy).Length() < 64) mons.Push(mo);
			pmo.bSOLID = false; pmo.bSHOOTABLE = false;
			if (!FindSpot()) { Console.Printf("HBFAIL no open spot"); return; }
			pmo.SetOrigin(start + (0, 0, 4000), false); pmo.bNOGRAVITY = true;
			Console.Printf("HBSTART map=%s monsters=%d spot=%.0f,%.0f,%.0f facing=%.0f", level.MapName, mons.Size(), spot.x, spot.y, spot.z, facing);
			// Open every door fully.
			let doors = ThinkerIterator.Create("DFDoor");
			DFDoor d;
			while (d = DFDoor(doors.Next())) { d.swung = 90; d.moving = 0; d.stalled = false; d.Place(false); d.UpdateBlocking(); }
			for (int i = 0; i < mons.Size(); i++)
			{
				let m = mons[i];
				let t = new("HBTally");
				t.name = m.GetClassName(); t.radius = m.Default.radius; t.narrow = m.DD_MoveRadius();
				tally.Push(t);
				m.bSOLID = true; m.bNOGRAVITY = true;
				m.SetOrigin(spot + (0, 0, 4000), false);
				Console.Printf("HBMON %s default=%.3f radius=%.3f squeeze=%.3f", t.name, t.radius, m.radius, t.narrow);
			}
			for (int i = 0; i < mons.Size(); i++) OpenSpace(i);
			for (int i = 0; i < mons.Size(); i++) Walk(i);
			shotTic = time + 1;
		}
		if (shotTic) Fireballs(time);
	}

	double flown;	// how far along its lane the live fireball got

	// One queued fireball every 24 tics.
	void Fireballs(int time)
	{
		if (victim && ball)
		{
			let q = shots[shot];
			flown = max(flown, (ball.pos.xy - q.from.xy) dot (cos(q.angle), sin(q.angle)));
			// DRLA's monsters can step even when deactivated: freeze the target's states and hold it on its spot.
			victim.tics = -1;
			victim.vel = (0, 0, 0);
			victim.SetOrigin(q.stand, false);
		}
		if (victim && time >= shotTic)
		{
			let q = shots[shot];
			let t = tally[q.mon];
			if (q.squeeze)
			{
				// A ball stopped short of the monster's centre (a wall, a door) says nothing about the hitbox. One that flew
				// past the centre without touching it is a miss.
				if (touched == victim) t.sqOk[2]++; else if (flown < t.radius + 12) t.sqBlocked[2]++; else t.sqWrong[2]++;
			}
			else if ((touched == victim) == q.want) { t.ok[2]++; if (q.want) t.hitsIn[2]++; else t.missesOut[2]++; }
			else t.wrong[2]++;
			Console.Printf("%s %s projectile angle=%.0f offset=%.2f radius=%.3f squeeze=%.3f %s want=%d", q.squeeze ? "HBSQHIT" : "HBHIT", t.name, q.angle,
				q.offset, victim.radius, t.narrow, touched == victim ? "hit" : touched ? "other" : "no contact", q.want);
			if (ball) ball.Destroy();
			if (q.squeeze) { victim.ClearCounters(); victim.Destroy(); } else victim.SetOrigin(spot + (0, 0, 4000), false);
			victim = null;
			shot++;
		}
		if (time < shotTic) return;
		if (shot >= shots.Size()) { Done(); shotTic = 0; return; }
		flown = 0;
		let q = shots[shot];
		if (q.squeeze) victim = Park(mons[q.mon].GetClass(), q.stand);
		else { victim = mons[q.mon]; victim.SetOrigin(q.stand, false); }
		victim.bSOLID = true;
		victim.bDONTTHRUST = true;
		victim.bNOPAIN = true;
		victim.tics = -1;
		victim.vel = (0, 0, 0);
		victim.SetOrigin(q.stand, false);
		victim.health = 100000;
		touched = null;
		ball = Actor.Spawn("HBBall", q.from, NO_REPLACE);
		ball.angle = q.angle;
		ball.Vel = (10 * cos(q.angle), 10 * sin(q.angle), 0);
		shotTic = time + 24;
	}

	void Done()
	{
		foreach (t : tally)
		{
			Console.Printf("HBOPEN %s radius=%.3f squeeze=%.3f bullet=%d/%d/%d/%d melee=%d/%d/%d/%d projectile=%d/%d/%d/%d", t.name, t.radius, t.narrow,
				t.ok[0], t.wrong[0], t.hitsIn[0], t.missesOut[0], t.ok[1], t.wrong[1], t.hitsIn[1], t.missesOut[1], t.ok[2], t.wrong[2], t.hitsIn[2], t.missesOut[2]);
			Console.Printf("HBSQUEEZE %s doors=%d passed=%d squeezedDoors=%d openSteps=%d squeezedSteps=%d radiusChanged=%d bullet=%d/%d/%d melee=%d/%d/%d projectile=%d/%d/%d",
				t.name, t.doors, t.passed, t.squeezedDoors, t.openSteps, t.squeezedSteps, t.radiusChanged,
				t.sqOk[0], t.sqWrong[0], t.sqBlocked[0], t.sqOk[1], t.sqWrong[1], t.sqBlocked[1], t.sqOk[2], t.sqWrong[2], t.sqBlocked[2]);
		}
		Console.Printf("HBDONE");
	}
}
