version "4.10"

// Monster width check (tools/monster_width/monster_width.py).
// 1. Spawns a few monsters with replacement (so DRLA's spawners pick their own monsters when DRLA is loaded), waits for
//    spawners to resolve, then prints every monster's class, default radius, live radius and movement width (MW lines).
//    The radius (the hitbox) must always stay stock; only the movement width narrows, and only on Daggerfall maps.
// 2. Hit tests against a stock DoomImp (radius 20): hitscans and an imp fireball passed beside it at chosen offsets.
//    Each must hit inside the stock edge and miss outside it, whatever the squeeze width is (MWHIT lines).
// 3. Spacing against another monster, the player and an open wall (MWSPACE lines; see Spacing).
// Then MWDONE.
class DFHitShooter : Actor
{
	Default { Radius 1; Height 56; +NOBLOCKMAP +NOGRAVITY +NOINTERACTION }
	States { Spawn: TNT1 A -1; Stop; }
}

// An imp fireball that records the first thing it touched (PIT_CheckThing calls SpecialMissileHit on contact).
class DFHitBall : DoomImpBall
{
	override int SpecialMissileHit(Actor victim)
	{
		let h = DFMonsterWidthCheck(EventHandler.Find("DFMonsterWidthCheck"));	// the ball is gone soon after it explodes
		if (h && !h.touched) h.touched = victim;
		return -1;
	}
}

class DFMonsterWidthCheck : EventHandler
{
	Actor target;
	vector3 at;
	int hits, misses, wrong;
	DFHitBall ball;
	Actor touched;
	double ballOffset;

	void Report(String kind, double offset, bool hit, bool want)
	{
		if (hit == want) { if (hit) hits++; else misses++; } else wrong++;
		Console.Printf("MWHIT %s offset=%.1f radius=%.3f move=%.3f %s %s", kind, offset, target.radius, target.DD_MoveRadius(),
			hit ? "hit" : "miss", hit == want ? "ok" : "WRONG");
	}

	// A level shot along +x that passes the target's centre `offset` units to the side.
	bool Hitscan(double offset)
	{
		let s = Actor.Spawn("DFHitShooter", at + (-80, offset, 0), NO_REPLACE);
		FTranslatedLineTarget t;
		s.LineAttack(0, 160, 0, 0, 'Hitscan', "BulletPuff", LAF_NORANDOMPUFFZ, t);
		s.Destroy();
		return t.linetarget == target;
	}

	void Fire(double offset)
	{
		ballOffset = offset;
		touched = null;
		ball = DFHitBall(Actor.Spawn("DFHitBall", at + (-60, offset, 20), NO_REPLACE));
		ball.angle = 0;
		ball.Vel = (10, 0, 0);
	}

	override void WorldTick()
	{
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		if (level.maptime == 2)
		{
			startPos = pmo.pos;
			static const Name kinds[] = { 'ZombieMan', 'ShotgunGuy', 'DoomImp', 'Demon', 'Cacodemon', 'HellKnight', 'Arachnotron', 'Cyberdemon' };
			for (int i = 0; i < kinds.Size(); i++)
			{
				// Far above the map's play space would fall back, so spawn at the player, non-solid until counted.
				let mo = Actor.Spawn(kinds[i], pmo.pos, ALLOW_REPLACE);
				if (mo) { mo.bSOLID = false; mo.Deactivate(null); }
			}
		}
		if (level.maptime == 20)
		{
			int narrow = 0, stock = 0, other = 0;
			Array<Actor> counted;
			let it = ThinkerIterator.Create("Actor");
			Actor mo;
			while (mo = Actor(it.Next()))
			{
				if (!mo.bIsMonster || mo.player) continue;
				counted.Push(mo);
				double d = mo.Default.radius, m = mo.DD_MoveRadius();
				String state = abs(mo.radius - d) >= 0.001 ? "other" : abs(m - d) < 0.001 ? "stock" : abs(m - d * 10.5 / 16) < 0.001 ? "narrow" : "other";
				if (state == "stock") stock++; else if (state == "narrow") narrow++; else other++;
				Console.Printf("MW %s default=%.3f radius=%.3f move=%.3f height=%.1f %s", mo.GetClassName(), d, mo.radius, m, mo.height, state);
			}
			Console.Printf("MWSUMMARY map=%s narrow=%d stock=%d other=%d", level.MapName, narrow, stock, other);
			// Clear the space for the hit tests: only the target may be hit.
			foreach (c : counted) { c.ClearCounters(); c.Destroy(); }
			pmo.bSHOOTABLE = false; pmo.bSOLID = false;
			at = pmo.pos;
			target = Actor.Spawn("DoomImp", at, NO_REPLACE);
			target.Deactivate(null);
			target.bNOGRAVITY = true;
			target.SetOrigin(at, false);
			// Hitscan: the imp is 20 wide for hits. 19 is outside its movement width on Daggerfall maps but inside its hitbox.
			Report("hitscan", 0, Hitscan(0), true);
			Report("hitscan", 19, Hitscan(19), true);
			Report("hitscan", -19, Hitscan(-19), true);
			Report("hitscan", 21, Hitscan(21), false);
			Report("hitscan", -21, Hitscan(-21), false);
			// Projectile: the fireball (radius 6) touches the imp when the offset is under 20 + 6.
			Fire(24);
		}
		if (level.maptime == 40)
		{
			Report("projectile", ballOffset, touched == target, true);
			if (ball) ball.Destroy();
			Fire(28);
		}
		if (level.maptime == 60)
		{
			Report("projectile", ballOffset, touched == target, false);
			if (ball) ball.Destroy();
			Console.Printf("MWHITSUMMARY hits=%d misses=%d wrong=%d", hits, misses, wrong);
			target.ClearCounters();
			target.Destroy();
			Spacing(pmo);
			Console.Printf("MWSPACESUMMARY ok=%d wrong=%d skipped=%d", spaceOk, spaceWrong, spaceSkipped);
			Console.Printf("MWDONE");
		}
	}

	// 3. Spacing: monsters squeeze only through gaps in the level, so against another monster, the player and an open
	//    wall they stop at their stock radius (MWSPACE lines).
	int spaceOk, spaceWrong, spaceSkipped;
	vector3 startPos;	// the player's start: spawned monsters may have pushed the player since

	void SpaceReport(String kind, double got, double want, String why = "")
	{
		if (why != "") { spaceSkipped++; Console.Printf("MWSPACE %s skipped %s", kind, why); return; }
		bool ok = abs(got - want) <= 1.01;
		if (ok) spaceOk++; else spaceWrong++;
		Console.Printf("MWSPACE %s stopped=%.2f want=%.2f %s", kind, got, want, ok ? "ok" : "WRONG");
	}

	// An open axis direction from the point (Doom's bodies are square, so contact distances are the radius sums only along
	// an axis): level traces down the middle and both sides of a 40-wide lane run at least `need` units with no wall.
	double OpenDir(Actor from, double need)
	{
		for (double a = 0; a < 360; a += 90)
		{
			bool open = true;
			for (int side = -1; side <= 1 && open; side++)
			{
				FLineTraceData d;
				from.LineTrace(a, need, 0, TRF_THRUACTORS, 32, 0, side * 24, d);
				open = d.HitType == TRACE_HitNone;
			}
			if (open) return a;
		}
		return -1;
	}

	// Moves the body toward the point in 1-unit steps with real moves until a move fails; returns the distance left.
	double Approach(Actor body, vector2 to, double dist, double angle)
	{
		vector2 dir = (cos(angle), sin(angle));
		for (double d = dist - 1; d >= 0; d -= 1)
		{
			if (!body.TryMove(to - dir * d, true)) return d + 1;
		}
		return 0;
	}

	Actor Imp(vector3 pos)
	{
		let mo = Actor.Spawn("DoomImp", pos, NO_REPLACE);
		if (mo) { mo.Deactivate(null); mo.SetOrigin(pos, false); }
		return mo;
	}

	void Spacing(PlayerPawn pmo)
	{
		pmo.SetOrigin(startPos, false);
		pmo.vel = (0, 0, 0);
		pmo.bSOLID = true; pmo.bSHOOTABLE = true;
		double a = OpenDir(pmo, 200);
		if (a < 0) { SpaceReport("monster", 0, 0, "no open direction"); SpaceReport("player", 0, 0, "no open direction"); }
		else
		{
			vector2 dir = (cos(a), sin(a));
			vector3 base = pmo.pos + (dir * 90, 0);
			// Two monsters: B walks into A.
			let ia = Imp(base), ib = Imp(base + (dir * 70, 0));
			SpaceReport("monster", Approach(ib, base.xy, 70, a + 180), ia.radius + ib.radius);
			ia.ClearCounters(); ia.Destroy(); ib.ClearCounters(); ib.Destroy();
			// A monster walks into the player, then the player walks into the monster.
			ib = Imp(base);
			SpaceReport("monster-to-player", Approach(ib, pmo.pos.xy, 90, a + 180), ib.radius + pmo.radius);
			ib.SetOrigin(base, false);
			vector3 home = pmo.pos;
			SpaceReport("player-to-monster", Approach(pmo, base.xy, 90, a), ib.radius + pmo.radius);
			pmo.SetOrigin(home, false);
			ib.ClearCounters(); ib.Destroy();
		}
		// A monster walks straight at a wall in an open room: an axis-aligned wall straight ahead, and open space to both
		// sides near it, so it is no gap. It must stop at its stock radius, not its squeeze width.
		for (double wa = 0; wa < 360; wa += 90)
		{
			FLineTraceData d;
			pmo.LineTrace(wa, 600, 0, TRF_THRUACTORS, 32, 0, 0, d);
			if (d.HitType != TRACE_HitWall || !d.HitLine || d.Distance < 80) continue;
			vector2 dir = (cos(wa), sin(wa)), delta = d.HitLine.delta.Unit();
			if (abs(delta dot dir) > 0.01) continue;
			vector2 wall = pmo.pos.xy + dir * d.Distance;
			vector2 near = wall - dir * 30;
			let probe = Actor.Spawn("DFHitShooter", (near, pmo.pos.z), NO_REPLACE);
			bool open = true;
			for (int side = -1; side <= 1; side += 2)
			{
				FLineTraceData s;
				probe.LineTrace(wa + 90 * side, 60, 0, TRF_THRUACTORS, 32 - probe.pos.z + pmo.pos.z, 0, 0, s);
				if (s.HitType != TRACE_HitNone) open = false;
			}
			probe.Destroy();
			if (!open) continue;
			let imp = Imp((wall - dir * 70, pmo.pos.z));
			if (!imp) continue;
			pmo.bSOLID = false;
			SpaceReport("wall", Approach(imp, wall, 70, wa), imp.radius);
			pmo.bSOLID = true;
			imp.ClearCounters(); imp.Destroy();
			return;
		}
		SpaceReport("wall", 0, 0, "no open wall found");
	}
}
