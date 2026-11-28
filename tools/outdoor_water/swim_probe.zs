// Paired probe for Daggerfall's outdoor swimming (test only; tools/outdoor_water/run_swim_test.py packs it into its own
// pk3). On the overworld it:
//   1. measures the walking speed on dry land at the start (forward input held, the player put back on its spot every
//      tic, so walls do not matter), with the eye height;
//   2. moves to Daggerfall's water tile near the given offset (searching a 9x9 grid, as the fall test does) and waits
//      for Actor.DD_OutdoorSwimming;
//   3. measures the speed and eye height there, and tries to jump;
//   4. stays in the water for StayTics, so Daggerfall's game minutes pass (Swimming tallies, fatigue);
//   5. goes back to the start and checks swimming ended and the eye height came back.
// Lines: "SWIMTEST <name> ...", "SWIMTEST done".
class DoomerfallSwimTest : StaticEventHandler
{
	const WaterDX = @WATER_DX@;
	const WaterDY = @WATER_DY@;
	const StayTics = @STAY_TICS@;
	const Walk = 6400;     // Doom's walking forwardmove (0x19 << 8)
	const SpeedTic = 40;   // the speed is read after this many tics of input

	int phase, t;
	Vector3 start, anchor;
	Vector2 waterAt;
	double landSpeed, landEye;
	bool active, finished;

	override void WorldLoaded(WorldEvent e) { active = !finished; }

	bool Grounded(PlayerPawn mo) { return mo.pos.z <= mo.floorz || mo.bOnMobj; }

	// One tic of forward input from the anchor. Returns the horizontal speed once SpeedTic tics have run, else -1.
	double Push(PlayerInfo p, PlayerPawn mo)
	{
		mo.SetOrigin(anchor, false);
		p.cmd.forwardmove = Walk;
		p.cmd.sidemove = 0;
		return t >= SpeedTic ? mo.vel.xy.Length() : -1;
	}

	void MoveTo(PlayerPawn mo, Vector2 at)
	{
		mo.SetOrigin((at, mo.GetZAt(at.x, at.y, 0, GZF_ABSOLUTEPOS)), false);
		mo.vel = (0, 0, 0);
	}

	override void WorldTick()
	{
		if (!active || finished) return;
		let p = players[consoleplayer];
		let mo = p.mo;
		if (!mo) return;
		if (phase == 0)
		{
			if (Actor.DD_SheetStat(0) >= 0 && Grounded(mo) && ++t > 140)
			{
				phase = 1; t = 0; start = mo.pos; anchor = mo.pos;
				Console.Printf("SWIMTEST start at %.0f %.0f %.0f Swimming=%d flags=%d", start.x, start.y, start.z, Actor.DD_SheetSkill(17), Actor.DD_PlayerFlags());
			}
			return;
		}
		t++;
		if (phase == 1) // dry land speed
		{
			double v = Push(p, mo);
			if (v < 0) return;
			landSpeed = v; landEye = p.viewheight;
			Console.Printf("SWIMTEST land speed=%.4f eye=%.2f swimming=%d flags=%d", v, p.viewheight, Actor.DD_OutdoorSwimming(), Actor.DD_PlayerFlags());
			phase = 2; t = 0; mo.vel = (0, 0, 0);
			return;
		}
		if (phase == 2) // find the water tile
		{
			if (t == 1) { waterAt = start.xy + (WaterDX, WaterDY); MoveTo(mo, waterAt); }
			if (t > 35 * 90) { Console.Printf("SWIMTEST water never swum flags=%d", Actor.DD_PlayerFlags()); phase = 5; t = 0; return; }
			if (t < 35) return;
			if (!(Actor.DD_PlayerFlags() & 2))
			{
				if (t % 8 == 0)
				{
					int k = (t / 8) % 81;
					MoveTo(mo, waterAt + ((k % 9 - 4) * 64, (k / 9 - 4) * 64));
				}
				return;
			}
			if (!Actor.DD_OutdoorSwimming()) return;
			anchor = mo.pos;
			Console.Printf("SWIMTEST water found at %.0f %.0f %.0f floor %.0f flags=%d", mo.pos.x, mo.pos.y, mo.pos.z, mo.floorz, Actor.DD_PlayerFlags());
			phase = 3; t = 0;
			return;
		}
		if (phase == 3) // speed, eye and jump in the water
		{
			if (t <= SpeedTic)
			{
				double v = Push(p, mo);
				if (v < 0) return;
				Console.Printf("SWIMTEST water speed=%.4f ratio=%.4f eye=%.2f eye_ratio=%.4f land_eye=%.2f swimming=%d Swimming=%d",
					v, landSpeed > 0 ? v / landSpeed : 0, p.viewheight, landEye > 0 ? p.viewheight / landEye : 0, landEye,
					Actor.DD_OutdoorSwimming(), Actor.DD_SheetSkill(17));
				mo.vel = (0, 0, 0);
				return;
			}
			if (t < SpeedTic + 6) { mo.SetOrigin(anchor, false); mo.vel = (0, 0, 0); return; }
			if (t < SpeedTic + 12) { p.cmd.buttons |= BT_JUMP; return; }
			if (t < SpeedTic + 30) return;
			Console.Printf("SWIMTEST jump rise=%.2f vel_z=%.2f swimming=%d", mo.pos.z - anchor.z, mo.vel.z, Actor.DD_OutdoorSwimming());
			phase = 4; t = 0;
			return;
		}
		if (phase == 4) // stay in the water while Daggerfall's minutes pass
		{
			mo.SetOrigin(anchor, false);
			mo.vel = (0, 0, 0);
			if (t % 350 == 0) Console.Printf("SWIMTEST stay t=%d swimming=%d hp=%d", t, Actor.DD_OutdoorSwimming(), p.health);
			if (t < StayTics) return;
			phase = 5; t = 0;
			return;
		}
		if (phase == 5) // back on land
		{
			if (t == 1) MoveTo(mo, start.xy);
			if (t < 70) return;
			Console.Printf("SWIMTEST back speed_ok eye=%.2f land_eye=%.2f swimming=%d flags=%d hp=%d", p.viewheight, landEye,
				Actor.DD_OutdoorSwimming(), Actor.DD_PlayerFlags(), p.health);
			Console.Printf("SWIMTEST done");
			finished = true;
		}
	}
}
