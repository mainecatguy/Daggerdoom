// Paired probe for Daggerfall's falling damage exemptions (test only; tools/jumping/run_fall_exempt_test.py packs it
// into its own pk3, and Daggerfall runs with -dffalltest, which switches Slowfall on and off every 20 seconds).
// At Jumping 0 it drops the player from 9 m (Daggerfall's rule: 20 HP):
//   once while Daggerfall reports Slowfall (no damage) and once after it ends (20 HP);
//   and, when the runner gives a water offset, once over Daggerfall's nearest outdoor water tile (no damage).
// Lines: "FALLTEST slowfall ...", "FALLTEST water ...", "FALLTEST done".
class DoomerfallFallExemptTest : StaticEventHandler
{
	const DropUnits = 270.0; // 9 m
	const Settle = 70;
	const WaterDX = @WATER_DX@;
	const WaterDY = @WATER_DY@;
	const HaveWater = @HAVE_WATER@;

	int phase, t, damage, hpBefore, flagsAtDrop;
	double topZ;
	Vector2 waterAt;
	bool active, finished;
	String what;

	override void WorldLoaded(WorldEvent e) { active = !finished; }

	override void WorldThingDamaged(WorldEvent e)
	{
		if (active && e.Thing && e.Thing.player && e.DamageType == 'Falling') damage += e.Damage;
	}

	bool Grounded(PlayerPawn mo) { return mo.pos.z <= mo.floorz || mo.bOnMobj; }

	void Drop(PlayerInfo p, PlayerPawn mo, String name)
	{
		what = name;
		damage = 0;
		hpBefore = p.health;
		flagsAtDrop = Actor.DD_PlayerFlags();
		mo.SetOrigin(mo.pos + (0, 0, min(DropUnits, mo.ceilingz - mo.pos.z - mo.height - 8)), false);
		mo.vel = (0, 0, 0);
		topZ = mo.pos.z;
	}

	// After a drop: true once landed and settled, with the report logged.
	bool Landed(PlayerInfo p, PlayerPawn mo)
	{
		if (t < 3 || !Grounded(mo)) return false;
		if (t < Settle) return false;
		double fell = topZ - mo.pos.z;
		Console.Printf("FALLTEST %s fell=%.1f falldamage=%d rule=%d flags_at_drop=%d flags_now=%d hp=%d->%d", what, fell, damage,
			DoomerfallJump.FallDamage(fell), flagsAtDrop, Actor.DD_PlayerFlags(), hpBefore, p.health);
		mo.GiveBody(1000);
		return true;
	}

	override void WorldTick()
	{
		if (!active || finished) return;
		let p = players[consoleplayer];
		let mo = p.mo;
		let j = DoomerfallJump(StaticEventHandler.Find("DoomerfallJump"));
		if (!mo || !j) return;
		if (phase == 0)
		{
			if (j.rules && j.skill >= 0 && ++t > 140) { phase = 1; t = 0; j.testSkill = 0; Console.Printf("FALLTEST start flags=%d", Actor.DD_PlayerFlags()); }
			return;
		}
		t++;
		mo.vel.xy = (0, 0);
		int flags = Actor.DD_PlayerFlags();
		if (phase == 1) // wait for Slowfall, then drop
		{
			if (t > 35 * 60) { Console.Printf("FALLTEST slowfall never reported"); phase = 5; t = 0; return; }
			if (!(flags & DoomerfallJump.FlagSlowfall) || !Grounded(mo) || t < 10) return;
			Drop(p, mo, "slowfall_on"); phase = 2; t = 0; return;
		}
		if (phase == 2) { if (Landed(p, mo)) { phase = 3; t = 0; } return; }
		if (phase == 3) // wait for Slowfall to end, then drop
		{
			if (t > 35 * 60) { Console.Printf("FALLTEST slowfall never ended"); phase = 5; t = 0; return; }
			if ((flags & DoomerfallJump.FlagSlowfall) || !Grounded(mo) || t < 10) return;
			Drop(p, mo, "slowfall_off"); phase = 4; t = 0; return;
		}
		if (phase == 4) { if (Landed(p, mo)) { phase = 5; t = 0; } return; }
		if (phase == 5) // go to the water tile, wait for Daggerfall to see it while Slowfall is off, then drop
		{
			if (!HaveWater) { phase = 8; return; }
			if (t == 1)
			{
				Vector2 at = mo.pos.xy + (WaterDX, WaterDY);
				waterAt = at;
				mo.SetOrigin((at, mo.GetZAt(at.x, at.y, 0, GZF_ABSOLUTEPOS)), false);
				Console.Printf("FALLTEST water moved to %.0f %.0f floor %.0f", at.x, at.y, mo.pos.z);
			}
			if (t > 35 * 90) { Console.Printf("FALLTEST water flags=%d never water without slowfall", flags); phase = 8; return; }
			if (t < 35) return;
			// Daggerfall's tile may be a step off the reported centre: search around it, 64 units apart, 8 tics a spot.
			if (!(flags & DoomerfallJump.FlagOutdoorWater))
			{
				if (t % 8 == 0)
				{
					int k = (t / 8) % 81;
					Vector2 at = waterAt + ((k % 9 - 4) * 64, (k / 9 - 4) * 64);
					mo.SetOrigin((at, mo.GetZAt(at.x, at.y, 0, GZF_ABSOLUTEPOS)), false);
				}
				return;
			}
			if (!Grounded(mo) || (flags & DoomerfallJump.FlagSlowfall)) return;
			Console.Printf("FALLTEST water found at %.0f %.0f", mo.pos.x, mo.pos.y);
			Drop(p, mo, "water"); phase = 6; t = 0; return;
		}
		if (phase == 6) { if (Landed(p, mo)) phase = 8; return; }
		if (phase == 8) { Console.Printf("FALLTEST done"); finished = true; }
	}
}
