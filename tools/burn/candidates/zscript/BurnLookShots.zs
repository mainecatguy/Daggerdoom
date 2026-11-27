// Burn look candidates and rendered frame-time probe (tools/burn/look_shots.py). Test only: this pack is built into a
// work folder by the tool and never ships with the game.
//   dd_bls_scene  1 small monsters, 2 large monsters, 3 a pack of 60 imps, 4 frame-time run (400 ZombieMen)
//   dd_bls_style  0 the real DoomerfallBurnLook (engine particles when the pick was made, now the Schism cut that
//                 won), 1 Arch-vile flame, 2 light Schism flames (the candidate),
//                 3 burning with the look off, 4 not burning
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
		else if (style == 2)
		{
			for (int i = 0; i < mons.Size(); i++)
			{
				let m = mons[i];
				if (!m || !DoomerfallBurn.Burning(m) || (Level.maptime + i) % 4 != 0) continue;
				double r = m.radius * 0.7;
				// More flames on bigger bodies: one per ZombieMan-sized area (20 x 56), up to 4.
				int n = clamp(int(m.radius * m.height / 1120.0 + 0.5), 1, 4);
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
		// Face the longest open line of sight, so the monsters stand in view.
		double bestA = pl.angle, bestD = 0;
		for (int a = 0; a < 360; a += 10)
		{
			FLineTraceData d;
			pl.LineTrace(a, 4096, 0, TRF_THRUACTORS, pl.height * 0.5, data: d);
			if (d.Distance > bestD) { bestD = d.Distance; bestA = a; }
		}
		pl.angle = bestA;
		pl.pitch = 0;
		Console.Printf("BLS setup scene=%d style=%d open=%.0f", scene, style, bestD);
		if (scene == 1)
		{
			static const String small[] = { "ZombieMan", "DoomImp", "ShotgunGuy", "Demon", "LostSoul" };
			double d = min(bestD * 0.5, 160);
			for (int i = 0; i < 5; i++) Put(pl, small[i], d + (i % 2) * 48, (i - 2) * 26);
		}
		else if (scene == 2)
		{
			static const String big[] = { "BaronOfHell", "Fatso", "Cyberdemon" };
			double d = min(bestD * 0.6, 380);
			for (int i = 0; i < 3; i++) Put(pl, big[i], d + (i == 1 ? 120 : 0), (i - 1) * 72);
		}
		else if (scene == 3)
		{
			double d0 = min(bestD * 0.3, 160);
			for (int i = 0; i < 60; i++) Put(pl, "DoomImp", d0 + (i / 10) * 40, ((i % 10) - 4.5) * 20);
		}
		else
		{
			for (int i = 0; i < 400; i++) Put(pl, "ZombieMan", 64 + (i / 20) * 24, ((i % 20) - 9.5) * 24);
		}
		fires.Resize(mons.Size());
	}

	void Put(Actor pl, String cls, double fwd, double side)
	{
		Vector2 sv = Actor.AngleToVector(pl.angle - 90, side);
		Vector3 p = pl.Vec3Angle(fwd, pl.angle, 0);
		p.x += sv.x;
		p.y += sv.y;
		Actor m = Actor.Spawn(cls, p, ALLOW_REPLACE);
		if (!m) return;
		m.health = 100000;
		m.angle = m.AngleTo(pl);
		if (m.bFloat) m.SetZ(m.floorz + 24);
		mons.Push(m);
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
