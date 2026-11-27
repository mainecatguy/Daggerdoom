// Burn look candidates and rendered frame-time probe (tools/burn/look_shots.py). Test only: this pack is built into a
// work folder by the tool and never ships with the game.
//   dd_bls_scene  1 small monsters, 2 large monsters, 3 a pack of 60 imps, 4 frame-time run (400 ZombieMen)
//   dd_bls_style  0 the real DoomerfallBurnLook (engine particles when the pick was made, now the Schism cut that
//                 won), 1 Arch-vile flame, 2 light Schism flames (the candidate),
//                 3 burning with the look off, 4 not burning, 5 engine particles (the previous look)
// Every 70 tics each monster gets 60 more burn (via the real DoomerfallBurn), so they keep burning and flinching.

class BLSVileFire : BLSFlame
{
	States
	{
	Spawn:
		FIRE ABABCBCDCDEDEFEFGHGH 2 Bright;
		Stop;
	}
	// Called by the handler each tic: in front of the monster as seen by the player, like the Arch-vile's fire.
	void Follow()
	{
		if (!tracer || tracer.health <= 0 || !DoomerfallBurn.Burning(tracer)) { Destroy(); return; }
		let cam = players[consoleplayer].camera;
		double a = cam ? tracer.AngleTo(cam) : tracer.angle;
		SetOrigin(tracer.Vec3Angle(tracer.radius + 2, a, 0), true);
	}
}

class BLSFlame : Actor
{
	Default
	{
		+NOINTERACTION
		+NOBLOCKMAP
		+NOGRAVITY
		RenderStyle "Add";
		Scale 0.5;
	}
	States
	{
	Spawn:
		FRPR ABCDEFGH 3 Bright;
		Stop;
	}
}

class BurnLookShots : EventHandler
{
	Array<Actor> mons;
	Array<Actor> fires;
	int scene, style, startTic;
	bool started;
	ui bool printed;
	ui double lastMs, sumMs, maxMs;
	ui int frames, over20, over33, over50;
	ui Array<int> hist;

	static int IntCVar(String n)
	{
		let c = CVar.FindCVar(n);
		return c ? c.GetInt() : 0;
	}

	override void WorldTick()
	{
		scene = IntCVar("dd_bls_scene");
		if (scene <= 0) return;
		style = IntCVar("dd_bls_style");
		let pl = players[consoleplayer].mo;
		if (!pl) return;
		if (!started && Level.maptime == 5) Setup(pl);
		if (!started) return;
		int t = Level.maptime - startTic;
		if (style != 4 && t % 70 == 0)
			for (int i = 0; i < mons.Size(); i++) DoomerfallBurn.Apply(mons[i], 60, null);
		if (style == 1)
		{
			for (int i = 0; i < mons.Size(); i++)
				if (mons[i] && DoomerfallBurn.Burning(mons[i]) && !fires[i])
				{
					let cam = players[consoleplayer].camera;
					double a = cam ? mons[i].AngleTo(cam) : mons[i].angle;
					let f = Actor.Spawn("BLSVileFire", mons[i].Vec3Angle(mons[i].radius + 2, a, 0), NO_REPLACE);
					f.tracer = mons[i];
					f.vel = mons[i].vel;
					double s = clamp(mons[i].height / 56.0, 0.6, 2.2);
					f.scale = (s, s);
					// The first flames start at a random frame, so a pack does not flicker in step.
					if (t < 2) f.SetState(f.SpawnState + random(0, 19));
					fires[i] = f;
				}
		}
		else if (style == 5)
		{
			// The engine-particle candidate: the previous DoomerfallBurnLook.Draw (commit 44afc87e), unchanged.
			for (int i = 0; i < mons.Size(); i++)
			{
				let v = mons[i];
				if (!v || !DoomerfallBurn.Burning(v) || (Level.maptime + v.SpawnTime) % 3 != 0) continue;
				double r = v.radius * 0.8;
				double h = v.height;
				int colour = Random(0, 2);
				Color c = colour == 0 ? Color(255, 255, 160, 0) : (colour == 1 ? Color(255, 255, 80, 0) : Color(255, 255, 220, 60));
				v.A_SpawnParticle(c, SPF_FULLBRIGHT | SPF_RELATIVE, Random(18, 30), FRandom(3, 6), 0,
					FRandom(-r, r), FRandom(-r, r), FRandom(0, h * 0.8), FRandom(-0.3, 0.3), FRandom(-0.3, 0.3), FRandom(0.8, 1.6),
					0, 0, 0.02, 1.0, -1, -0.1);
			}
		}
		else if (style == 2)
		{
			for (int i = 0; i < mons.Size(); i++)
			{
				let m = mons[i];
				if (!m || !DoomerfallBurn.Burning(m) || (Level.maptime + i) % 4 != 0) continue;
				double r = m.radius * 0.7;
				// More flames on bigger bodies, as in DoomerfallBurnLook.
				int n = clamp(int(m.radius * m.height / 700.0), 1, 4);
				for (int k = 0; k < n; k++)
				{
					let f = Actor.Spawn("BLSFlame", m.Vec3Offset(frandom(-r, r), frandom(-r, r), frandom(m.height * 0.15, m.height * 0.75)), NO_REPLACE);
					double s = 0.5 * clamp(m.height / 56.0, 0.6, 1.6);
					f.scale = (s, s);
					f.vel = (m.vel.x + frandom(-0.4, 0.4), m.vel.y + frandom(-0.4, 0.4), frandom(1.0, 2.0));
				}
			}
		}
	}

	void Setup(Actor pl)
	{
		started = true;
		startTic = Level.maptime;
		players[consoleplayer].cheats |= CF_NOTARGET;
		FindOpenSpot(pl);
		int placed = 0;
		if (scene == 1)
		{
			static const String small[] = { "ZombieMan", "DoomImp", "ShotgunGuy", "Demon", "LostSoul" };
			for (int i = 0; i < 5; i++) placed += Put(pl, small[i], 170, (i - 2) * 44);
		}
		else if (scene == 2)
		{
			static const String big[] = { "BaronOfHell", "Cyberdemon", "Fatso" };
			for (int i = 0; i < 3; i++) placed += Put(pl, big[i], 330, (i - 1) * 140);
		}
		else if (scene == 3)
		{
			for (int i = 0; i < 60; i++) placed += Put(pl, "DoomImp", 220 + (i / 10) * 40, ((i % 10) - 4.5) * 30);
		}
		else
		{
			// 20 x 20 at 24 units, 300-756 units ahead: the whole pack inside the field of view.
			for (int i = 0; i < 400; i++) placed += Put(pl, "ZombieMan", 300 + (i / 20) * 24, ((i % 20) - 9.5) * 24);
		}
		Console.Printf("BLS placed=%d of %d (in level, clear of walls)", placed, mons.Size());
		fires.Resize(mons.Size());
	}

	// Moves the player to the spot on a 96-unit grid whose forward cone (+-40 degrees) is clear the furthest, so every
	// scene, including the 760-unit-deep frame-time pack, is fully on screen. Looks slightly down at the pack.
	void FindOpenSpot(Actor pl)
	{
		double x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
		for (int i = 0; i < Level.Vertexes.Size(); i++)
		{
			let v = Level.Vertexes[i].p;
			x0 = min(x0, v.x); y0 = min(y0, v.y); x1 = max(x1, v.x); y1 = max(y1, v.y);
		}
		Vector3 start = pl.pos;
		Vector3 bestP = start;
		double bestA = pl.angle, best = -1;
		double dist[36];
		for (double x = x0 + 48; x < x1; x += 96)
			for (double y = y0 + 48; y < y1; y += 96)
			{
				let s = Level.PointInSector((x, y));
				double fz = s.floorplane.ZAtPoint((x, y));
				if (s.ceilingplane.ZAtPoint((x, y)) - fz < 120) continue;
				Vector3 p = (x, y, fz);
				if (!Level.IsPointInLevel(p + (0, 0, 1))) continue;
				pl.SetOrigin(p, false);
				for (int a = 0; a < 36; a++)
				{
					FLineTraceData d;
					pl.LineTrace(a * 10, 1200, 0, TRF_THRUACTORS, 40, data: d);
					dist[a] = d.Distance;
				}
				for (int a = 0; a < 36; a++)
				{
					double m = 1e9;
					for (int k = -4; k <= 4; k++) m = min(m, dist[(a + k + 36) % 36]);
					if (m > best) { best = m; bestP = p; bestA = a * 10; }
				}
			}
		pl.SetOrigin(bestP, false);
		pl.angle = bestA;
		pl.pitch = scene == 4 ? 12 : 4;
		Console.Printf("BLS setup scene=%d style=%d spot=%.0f,%.0f angle=%.0f cone_clear=%.0f", scene, style, bestP.x, bestP.y, bestA, best);
	}

	// Returns 1 when the monster stands inside the level, clear of walls.
	int Put(Actor pl, String cls, double fwd, double side)
	{
		Vector2 sv = Actor.AngleToVector(pl.angle - 90, side);
		Vector3 p = pl.Vec3Angle(fwd, pl.angle, 0);
		p.x += sv.x;
		p.y += sv.y;
		// Stock monsters even with DRLA loaded (DRLA's replacements are spawners that remove themselves).
		Actor m = Actor.Spawn(cls, p, NO_REPLACE);
		if (!m) return 0;
		m.health = 100000;
		m.angle = m.AngleTo(pl);
		m.SetZ(m.floorz + (m.bFloat ? 24 : 0));
		mons.Push(m);
		// In view: inside the level, on about the player's floor, and no wall between it and the player.
		return Level.IsPointInLevel(m.pos + (0, 0, 1)) && abs(m.floorz - pl.pos.z) < 32 && pl.CheckSight(m, SF_IGNOREVISIBILITY) ? 1 : 0;
	}

	// Rendered frame times, 3 s to 13 s after the monsters appear (frame-time scene only).
	override void RenderOverlay(RenderEvent e)
	{
		if (scene != 4 || !started || printed) return;
		int t = Level.maptime - startTic;
		double now = MSTimeF();
		if (t > 105 && t <= 455 && lastMs > 0)
		{
			double dt = now - lastMs;
			if (hist.Size() == 0) hist.Resize(1000);
			hist[clamp(int(dt * 10), 0, 999)]++;
			frames++; sumMs += dt; maxMs = max(maxMs, dt);
			if (dt > 20) over20++;
			if (dt > 33.3) over33++;
			if (dt > 50) over50++;
		}
		lastMs = now;
		if (t > 455 && frames > 0 && !printed)
		{
			printed = true;
			Console.Printf("BLS frames style=%d n=%d avg_ms=%.2f p50_ms=%.2f p99_ms=%.2f max_ms=%.2f over20=%d over33=%d over50=%d",
				style, frames, sumMs / frames, Pct(0.5), Pct(0.99), maxMs, over20, over33, over50);
			Console.Printf("BLS done");
		}
	}

	// Percentile from the 0.1 ms histogram.
	ui double Pct(double q)
	{
		int want = int(frames * q), seen = 0;
		for (int i = 0; i < hist.Size(); i++)
		{
			seen += hist[i];
			if (seen > want) return i * 0.1;
		}
		return maxMs;
	}
}
