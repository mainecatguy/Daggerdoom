// Paired probe for Daggerfall's outdoor swimming (test only; tools/outdoor_water/run_swim_test.py packs it into its own
// pk3). On the overworld it:
//   1. measures the walking move on dry land at the start (PlayerPawn.TweakSpeeds, as MovePlayer applies it), with the
//      eye height;
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
	const Demo = @DEMO@;     // 1: the review demo, which only takes the player to the water and stops
	const Walk = 6400;     // Doom's walking forwardmove (0x19 << 8)
	const SpeedTic = 40;   // the speed is read after this many tics of input

	int phase, t;
	Vector3 start, anchor;
	Vector2 waterAt;
	double landSpeed, landEye;
	bool active, finished, walked, lastSwim;
	int lastWater, dryTic;

	override void WorldLoaded(WorldEvent e) { active = !finished; }

	bool Grounded(PlayerPawn mo) { return mo.pos.z <= mo.floorz || mo.bOnMobj; }

	// The walking move PlayerPawn.MovePlayer would apply now, after every speed factor (TweakSpeeds multiplies the
	// inventory's GetSpeedFactor in), over the bare walking move. Held keys never reach a window on the private desktop.
	double Push(PlayerInfo p, PlayerPawn mo)
	{
		mo.SetOrigin(anchor, false);
		if (t < SpeedTic) return -1;
		double fm, sm;
		[fm, sm] = mo.TweakSpeeds(Walk, 0);
		return fm / (mo.ForwardMove1 * Walk);
	}

	// The overworld treadmill moves everything back by whole tiles as the player nears its window edge
	// (dd_treadmill.cpp); the spots kept here move with it.
	int ox, oy;
	void Follow()
	{
		int nx = CVar.FindCVar("dd_tm_originx").GetInt(), ny = CVar.FindCVar("dd_tm_originy").GetInt();
		Vector2 d = ((nx - ox) * 192, (ny - oy) * 192);
		ox = nx; oy = ny;
		if (d == (0, 0)) return;
		start.xy -= d; anchor.xy -= d; waterAt -= d;
		Console.Printf("SWIMTEST treadmill shift %.0f %.0f", d.x, d.y);
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
				ox = CVar.FindCVar("dd_tm_originx").GetInt(); oy = CVar.FindCVar("dd_tm_originy").GetInt();
				Console.Printf("SWIMTEST start at %.0f %.0f %.0f Swimming=%d flags=%d", start.x, start.y, start.z, Actor.DD_SheetSkill(17), Actor.DD_PlayerFlags());
			}
			return;
		}
		t++;
		Follow();
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
			// Daggerfall's tile may be a step off the reported centre: search around it, 64 units apart. Daggerfall sees a
			// move a few tics late, so each spot is held 24 tics and must still swim at its end.
			if (t % 24 != 0) return;
			if (!(Actor.DD_PlayerFlags() & 2) || !Actor.DD_OutdoorSwimming())
			{
				int k = (t / 24) % 81;
				MoveTo(mo, waterAt + ((k % 9 - 4) * 64, (k / 9 - 4) * 64));
				return;
			}
			anchor = mo.pos;
			if (Demo) { finished = true; return; }
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
			// Walk (thrust each tic, as MovePlayer would) from the water toward the start, logging every change of
			// Daggerfall's water tile flag and of Doom's swimming, with the position, until on land for 2 s.
			if (t < 35 * 60 && !walked)
			{
				Vector2 to = start.xy - mo.pos.xy;
				double fm, sm, fr, mf;
				[fm, sm] = mo.TweakSpeeds(Walk, 0);
				[fr, mf] = mo.GetFriction();
				if (mo.pos.z <= mo.floorz) mo.ForwardThrust(fm * mo.Speed / 256 * mf, atan2(to.y, to.x));
				int wf = Actor.DD_PlayerFlags() & 2;
				bool sw = Actor.DD_OutdoorSwimming();
				if (wf != lastWater || sw != lastSwim)
				{
					Console.Printf("SWIMTEST shore t=%d at %.0f %.0f df_water=%d swimming=%d", t, mo.pos.x, mo.pos.y, wf / 2, sw);
					lastWater = wf; lastSwim = sw; if (!sw && !wf) dryTic = t;
				}
				if (to.Length() < 64 || (dryTic > 0 && !sw && !wf && t - dryTic > 70)) walked = true;
				return;
			}
			if (!walked) { MoveTo(mo, start.xy); walked = true; t = 2; }
			if (t < 70 || (Actor.DD_OutdoorSwimming() && t < 35 * 30)) return; // Daggerfall follows a teleport within seconds
			Console.Printf("SWIMTEST back speed_ok eye=%.2f land_eye=%.2f swimming=%d flags=%d hp=%d", p.viewheight, landEye,
				Actor.DD_OutdoorSwimming(), Actor.DD_PlayerFlags(), p.health);
			Console.Printf("SWIMTEST done");
			finished = true;
		}
	}
}
