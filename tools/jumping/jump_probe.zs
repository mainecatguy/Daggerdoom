// Paired jumping probe (test only; tools/jumping/run_jump_test.py packs it into its own pk3). In a paired run on a
// Daggerfall map, sets DoomerfallJump's test skill to 0, 25, 50, 75 and 100 in turn and at each level:
//   jump in place, pressing Jump again at each apex (three tries), and reports the first rise, the total rise, the
//   mid-air jumps made and any falling damage ("JUMPTEST jump ...");
//   drops the player from 9 m above the ground and reports the falling damage against Daggerfall's rule
//   ("JUMPTEST drop ...");
// and at 0 and 75 walks the player off a real ledge found near the start ("JUMPTEST ledge ..."). Ends with
// "JUMPTEST done". tools/jumping/run_jump_test.py runs it and checks the lines.
class DoomerfallJumpTest : StaticEventHandler
{
	static const int levels[] = { 0, 25, 50, 75, 100 };
	const LevelCount = 5;
	const HighDropUnits = 2400.0; // 80 m
	const DropUnits = 270.0;   // 9 m: Daggerfall's rule gives 5 * (9 - 5) = 20 HP
	const Settle = 70;

	int phase, t, li, airJumps, damage, hpBefore, presses;
	double z0, firstRise, maxZ, lastVelZ, ledgeHigh;
	bool sawApex, active, finished, ledgeTried;
	Vector2 ledgeAt, ledgeDir;

	override void OnRegister() { SetOrder(-100); } // before DoomerfallJump, so a press set here is what it reads

	override void WorldLoaded(WorldEvent e)
	{
		active = !finished;
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (active && e.Thing && e.Thing.player && e.DamageType == 'Falling') damage += e.Damage;
	}

	bool Grounded(PlayerPawn mo) { return mo.pos.z <= mo.floorz || mo.bOnMobj; }

	override void WorldTick()
	{
		if (!active || finished) return;
		let p = players[consoleplayer];
		let mo = p.mo;
		let j = DoomerfallJump(StaticEventHandler.Find("DoomerfallJump"));
		if (!mo || !j) return;
		if (phase == 0) { if (j.rules && j.skill >= 0 && ++t > 140) { phase = 1; t = 0; Console.Printf("JUMPTEST start real Jumping=%d", j.skill); } return; }
		t++;
		int lv = li < LevelCount ? levels[li] : 100;
		if (phase == 1) // settle on the ground at this level
		{
			j.testSkill = lv;
			mo.vel.xy = (0, 0);
			if (t < Settle || !Grounded(mo)) return;
			z0 = maxZ = mo.pos.z; firstRise = 0; airJumps = 0; presses = 0; damage = 0; sawApex = false;
			p.cmd.buttons |= BT_JUMP; // Doom's own ground jump, with the JumpZ DoomerfallJump set
			mo.CheckJump();
			lastVelZ = mo.vel.z;
			Console.Printf("JUMPTEST level %d JumpZ=%.3f default=%.3f", lv, mo.JumpZ, mo.default.JumpZ);
			phase = 2; t = 0;
			return;
		}
		if (phase == 2) // in the air: count mid-air jumps, press again at each apex
		{
			if (mo.vel.z > lastVelZ + 1 && mo.vel.z > 1 && !Grounded(mo)) airJumps++; // not the landing's stop
			maxZ = max(maxZ, mo.pos.z);
			if (!sawApex && mo.vel.z <= 0) { sawApex = true; firstRise = maxZ - z0; }
			if (mo.vel.z <= 0 && presses < 3 && !Grounded(mo) && t > 2) { p.cmd.buttons |= BT_JUMP; presses++; }
			lastVelZ = mo.vel.z;
			if (t > 3 && Grounded(mo))
			{
				phase = 3; t = 0;
			}
			else if (t > 400) { Console.Printf("JUMPTEST level %d jump never landed", lv); phase = 3; t = 0; }
			return;
		}
		if (phase == 3) // landed: report after the hit, if any, reached Daggerfall
		{
			if (t < Settle) return;
			Console.Printf("JUMPTEST jump level=%d firstrise=%.1f totalrise=%.1f airjumps=%d landdz=%.1f falldamage=%d", lv, firstRise,
				maxZ - z0, airJumps, mo.pos.z - z0, damage);
			// Drop from 9 m (less if the ceiling is low).
			// At 75 (immune) also an 80 m drop, so a very fast landing is still seen as a landing (DFJUMP land ... immune).
			double h = min(lv == 75 ? HighDropUnits : DropUnits, mo.ceilingz - mo.pos.z - mo.height - 8);
			z0 = mo.pos.z; damage = 0; hpBefore = p.health;
			mo.SetOrigin(mo.pos + (0, 0, h), false);
			mo.vel = (0, 0, 0);
			maxZ = mo.pos.z;
			phase = 4; t = 0;
			return;
		}
		if (phase == 4)
		{
			if (t < 3 || !Grounded(mo)) { if (t > 400) { phase = 6; t = 0; } return; }
			if (t < Settle) return;
			double fell = maxZ - mo.pos.z;
			int expect = DoomerfallRules.FallImmune(lv) ? 0 : DoomerfallRules.FallDamage(fell);
			Console.Printf("JUMPTEST drop level=%d fell=%.1f falldamage=%d expected=%d hp=%d->%d", lv, fell, damage, expect, hpBefore, p.health);
			mo.GiveBody(1000);
			phase = (lv == 0 || lv == 75) ? 5 : 6; t = 0;
			return;
		}
		if (phase == 5) // walk off a real ledge
		{
			if (t == 1)
			{
				Vector2 store = (3616.0, -13410.75); // in front of a store (the climbing probe's start in this town)
				mo.SetOrigin((store, mo.GetZAt(store.x, store.y, 0, GZF_ABSOLUTEPOS)), false);
				if (!FindLedge(mo)) { Console.Printf("JUMPTEST ledge level=%d none found", lv); phase = 6; t = 0; return; }
				mo.SetOrigin((ledgeAt, ledgeHigh), false);
				mo.vel = (0, 0, 0);
				mo.angle = atan2(ledgeDir.y, ledgeDir.x);
				damage = 0;
				return;
			}
			if (t == 34) hpBefore = p.health; // after the last heal reached Daggerfall
			if (t < 35) return; // stand on the ledge first, so the fall starts from real ground
			if (t < 75 && Grounded(mo)) { mo.vel.xy = ledgeDir * 6; return; }
			if (!Grounded(mo) && t < 400) return;
			if (t < 75 + Settle) return;
			double fell = ledgeHigh - mo.pos.z;
			int expect = DoomerfallRules.FallImmune(lv) ? 0 : DoomerfallRules.FallDamage(fell);
			Console.Printf("JUMPTEST ledge level=%d fell=%.1f falldamage=%d expected=%d hp=%d->%d", lv, fell, damage, expect, hpBefore, p.health);
			mo.GiveBody(1000);
			phase = 6; t = 0;
			return;
		}
		if (phase == 6)
		{
			mo.GiveBody(1000);
			li++;
			phase = 1; t = 0;
			if (li >= LevelCount) { phase = 7; t = 0; }
		}
		if (phase == 7) // a mod changes JumpZ while active: it is kept as the base and scaled (x1.5 at 100)
		{
			if (t == 1) { j.testSkill = 100; return; }
			if (t == 10) { mo.JumpZ = 10; return; }
			if (t < 30) return;
			Console.Printf("JUMPTEST modjumpz got=%.3f want=15.000", mo.JumpZ);
			mo.JumpZ = mo.default.JumpZ * 1.5; // back to what the handler set from the default
			j.testSkill = -1;
			finished = true;
			Console.Printf("JUMPTEST done");
		}
	}

	// A roof next to the street: the nearest walls around the player (traced at chest height), then a trace straight
	// down from high above a point 40 units past each wall. A top surface 6 to 15 m above the street is a ledge; the
	// player stands on it and walks back toward the street, off the edge.
	bool FindLedge(PlayerPawn mo)
	{
		double best = 1e9, bestDrop = 0;
		int walls = 0;
		for (int a = 0; a < 360; a += 3)
		{
			FLineTraceData w;
			if (!mo.LineTrace(a, 1024, 0, TRF_THRUACTORS, 40, data: w) || w.HitType != FLineTraceData.TRACE_HitWall || w.Distance < 24) continue;
			walls++;
			FLineTraceData d;
			if (!mo.LineTrace(a, 3000, 90, TRF_THRUACTORS, 1500, w.Distance + 40, data: d)) continue;
			double drop = d.HitLocation.z - mo.pos.z;
			if (drop > bestDrop) bestDrop = drop;
			if (drop >= 180 && drop <= 450 && w.Distance < best)
			{
				best = w.Distance;
				ledgeAt = d.HitLocation.xy;
				ledgeHigh = d.HitLocation.z;
				ledgeDir = -Actor.AngleToVector(a);
			}
		}
		if (best > 1e8) Console.Printf("JUMPTEST ledge search: %d walls, highest top %.0f above the player", walls, bestDrop);
		return best < 1e8;
	}
}
