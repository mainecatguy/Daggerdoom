version "4.14"

// Treadmill kill test harness: runs the player east and checks actors across shifts.
class TMPlayer : DoomPlayer
{
	override void PlayerThink()
	{
		player.cmd.forwardmove = 12800;
		player.cheats |= CF_GODMODE;
		Super.PlayerThink();
	}
}

class TMHarness : EventHandler
{
	const TILE = 256.0;
	const THRESHOLD = 4096.0;
	const STEP_LIMIT = 40.0;

	Actor walker, flyer, proj;
	Vector3 pg, wg, fg, mg;
	bool hasP, hasW, hasF, hasM, spawned, projSpawned, wTarget, fTarget;
	int lastShifts, cleanupAt, stuckTics;
	double walkerStart;

	int cycles, pJump, pUnder, pStuck, pInterp, pZJump;
	int wJump, wUnder, wFloat, wLost, wMoved;
	int fJump, fUnder, fLost, mJump, mUnder, mCrossed;

	ui int viewJumps, lastViewTic, reported;
	ui bool hasView;
	ui Vector2 lastView;

	clearscope static int OriginX() { return CVar.FindCVar("dd_tm_originx").GetInt(); }
	clearscope static int OriginY() { return CVar.FindCVar("dd_tm_originy").GetInt(); }

	clearscope static Vector3 GlobalPos(Actor a)
	{
		return (a.pos.x + OriginX() * TILE, a.pos.y + OriginY() * TILE, a.pos.z);
	}

	clearscope static double GlobalX(Actor a) { return a.pos.x + OriginX() * TILE; }

	void Alert(Actor m, Actor p)
	{
		if (!m) return;
		m.target = p;
		m.SetState(m.SeeState);
	}

	void SpawnSquad(Actor p)
	{
		double wx = p.pos.x + 420, wy = p.pos.y + 160;
		walker = Actor.Spawn("ZombieMan", (wx, wy, p.GetZAt(wx, wy, 0, GZF_ABSOLUTEPOS)));
		double fx = p.pos.x + 520, fy = p.pos.y - 200;
		flyer = Actor.Spawn("Cacodemon", (fx, fy, p.GetZAt(fx, fy, 0, GZF_ABSOLUTEPOS) + 96));
		Alert(walker, p);
		Alert(flyer, p);
		hasW = false;
		hasF = false;
		wTarget = true;
		fTarget = true;
		spawned = true;
	}

	void SpawnProjectile(Actor p)
	{
		double x = p.pos.x + 80, y = p.pos.y + 48;
		proj = Actor.Spawn("DoomImpBall", (x, y, p.GetZAt(x, y, 0, GZF_ABSOLUTEPOS) + 72));
		if (proj)
		{
			proj.target = walker;
			proj.vel = (24, 0, 0);
		}
		hasM = false;
		projSpawned = true;
	}

	// Returns 1 when the actor moved farther than one tic allows.
	int StepCheck(Actor a, Vector3 prev, bool has)
	{
		if (!a || !has) return 0;
		Vector3 g = GlobalPos(a);
		return (g.xy - prev.xy).Length() > STEP_LIMIT ? 1 : 0;
	}

	int UnderCheck(Actor a)
	{
		return a && a.pos.z < a.floorz - 0.1 ? 1 : 0;
	}

	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p || level.MapName != "TREADM01" || level.maptime < 2) return;

		int shifts = CVar.FindCVar("dd_tm_shifts").GetInt();
		bool shifted = shifts != lastShifts;
		Vector3 g = GlobalPos(p);

		if (hasP)
		{
			double step = (g.xy - pg.xy).Length();
			if (step > STEP_LIMIT) pJump++;
			if (abs(g.z - pg.z) > 64) pZJump++;
			stuckTics = step < 1 ? stuckTics + 1 : 0;
			if (stuckTics == 35) pStuck++;
		}
		if (p.pos.z < p.floorz - 0.1) pUnder++;
		if ((p.pos.xy - p.prev.xy).Length() > STEP_LIMIT) pInterp++;
		pg = g;
		hasP = true;

		if (!spawned && p.pos.x > THRESHOLD - 620 && p.pos.x < THRESHOLD) SpawnSquad(p);
		if (spawned && !projSpawned && p.pos.x > THRESHOLD - 150 && p.pos.x < THRESHOLD) SpawnProjectile(p);

		wJump += StepCheck(walker, wg, hasW);
		fJump += StepCheck(flyer, fg, hasF);
		mJump += StepCheck(proj, mg, hasM);
		wUnder += UnderCheck(walker);
		fUnder += UnderCheck(flyer);
		mUnder += UnderCheck(proj);
		hasW = walker != null;
		hasF = flyer != null;
		hasM = proj != null;
		if (walker) wg = GlobalPos(walker);
		if (flyer) fg = GlobalPos(flyer);
		if (proj) mg = GlobalPos(proj);

		if (walker && walker.health > 0 && !walker.bFloat && walker.pos.z - walker.floorz > 32 && walker.vel.z == 0) wFloat++;

		if (shifted)
		{
			lastShifts = shifts;
			cycles++;
			cleanupAt = level.maptime + 100;
			if (walker) { walkerStart = GlobalX(walker); }
			if (walker && walker.health > 0 && walker.target != p) { wLost++; wTarget = false; }
			if (flyer && flyer.health > 0 && flyer.target != p) { fLost++; fTarget = false; }
			if (proj && hasM) mCrossed++;
		}
		if (cleanupAt > 0 && level.maptime == cleanupAt)
		{
			if (walker && abs(GlobalX(walker) - walkerStart) > 4) wMoved++;
			if (walker) walker.Destroy();
			if (flyer) flyer.Destroy();
			if (proj) proj.Destroy();
			walker = null;
			flyer = null;
			proj = null;
			spawned = false;
			projSpawned = false;
			cleanupAt = 0;
			Console.Printf("TMSUM shifts=%d cycles=%d gx=%.3f pJump=%d pZJump=%d pUnder=%d pStuck=%d pInterp=%d wJump=%d wUnder=%d wFloat=%d wLost=%d wMoved=%d fJump=%d fUnder=%d fLost=%d mJump=%d mUnder=%d mCrossed=%d",
				shifts, cycles, g.x, pJump, pZJump, pUnder, pStuck, pInterp, wJump, wUnder, wFloat, wLost, wMoved, fJump, fUnder, fLost, mJump, mUnder, mCrossed);
		}
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (level.MapName != "TREADM01" || level.maptime < 4) return;
		Vector2 v = (e.ViewPos.x + OriginX() * TILE, e.ViewPos.y + OriginY() * TILE);
		int t = level.maptime;
		if (hasView && (v - lastView).Length() > 24.0 * (t - lastViewTic + 1))
		{
			viewJumps++;
			Console.Printf("TMVIEWJUMP tic=%d lastTic=%d dist=%.3f view=%.3f,%.3f last=%.3f,%.3f local=%.3f originx=%d frac=%.3f",
				t, lastViewTic, (v - lastView).Length(), v.x, v.y, lastView.x, lastView.y, e.ViewPos.x, OriginX(), e.FracTic);
		}
		lastView = v;
		lastViewTic = t;
		hasView = true;
		if (viewJumps != reported)
		{
			reported = viewJumps;
			Console.Printf("TMVIEW jumps=%d", viewJumps);
		}
	}
}
