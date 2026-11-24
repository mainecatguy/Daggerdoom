// Climbing test harness (test only). Drives the player's input on CLIMB01 and prints CLIMBTEST lines that
// tools/climb/run_test.py checks. Part 1: climb a wall, hold, fire, jump off, strafe. Part 2: slip, 75-degree
// slope, 60-degree slope, rules off. The engine has no bridge session here, so the harness sends the rule and
// chance events the engine would send on a Daggerfall map.
class ClimbTestPlayer : DoomPlayer
{
	override void PlayerThink()
	{
		let h = ClimbHarness(EventHandler.Find("ClimbHarness"));
		if (h)
		{
			player.cmd.forwardmove = h.fwd;
			player.cmd.sidemove = h.side;
			player.cmd.buttons = h.buttons;
			player.cmd.yaw = 0;
			player.cmd.pitch = 0;
		}
		player.cheats |= CF_GODMODE;
		Super.PlayerThink();
	}
}

class ClimbHarness : EventHandler
{
	const Walk = 6400;   // 0x19 * 256
	const Strafe = 6144; // 0x18 * 256
	int fwd, side, buttons;
	int scen, uses, ammo0;
	int lt;
	override void OnRegister() { lt = -1; }
	int startTic, slipTic, everClimbed;
	double z0, y0, zA;
	bool done;

	DoomerfallClimbState St()
	{
		let c = DoomerfallClimb(StaticEventHandler.Find("DoomerfallClimb"));
		return c ? c.st[0] : null;
	}

	bool Climbing() { let s = St(); return s && s.climbing && !s.slipping; }
	bool Slipping() { let s = St(); return s && s.climbing && s.slipping; }

	void Place(double x, double y)
	{
		let mo = players[0].mo;
		let c = DoomerfallClimb(StaticEventHandler.Find("DoomerfallClimb"));
		if (c && c.st[0]) c.EndClimb(mo, c.st[0]);
		mo.SetOrigin((x, y, mo.GetZAt(x, y, 0, GZF_ABSOLUTEPOS)), false);
		mo.angle = 0;
		mo.pitch = 0;
		mo.vel = (0, 0, 0);
		fwd = side = buttons = 0;
		startTic = slipTic = -1;
		everClimbed = 0;
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(9) == "dfc_uses:") uses += e.Name.Mid(9).ToInt();
	}

	void Next() { scen++; lt = -1; }

	override void WorldTick()
	{
		let mo = players[0].mo;
		int t = level.maptime;
		if (!mo || done) return;
		int part = CVar.FindCVar("climbtest_part").GetInt();
		if (t == 2)
		{
			EventHandler.SendNetworkEvent("dfi_rules:1");
			EventHandler.SendNetworkEvent("dfi_climb:100:100:100:100:0");
		}
		if (t < 6) return;
		lt++;
		if (Climbing() || Slipping()) everClimbed = 1;
		if (startTic < 0 && Climbing()) startTic = lt;
		if (slipTic < 0 && Slipping()) { slipTic = lt; fwd = 0; } // stop pushing, or the climb starts again at the bottom
		if (part == 1) Part1(mo); else Part2(mo);
	}

	void Part1(PlayerPawn mo)
	{
		if (scen == 0) // Walk into the wall and keep pushing: climb starts after a second, climbs at walk/3, tops out.
		{
			if (lt == 0) { Place(480, 512); fwd = Walk; return; }
			if (startTic >= 0 && lt == startTic + 10) z0 = mo.pos.z;
			if (startTic >= 0 && lt == startTic + 45) zA = mo.pos.z;
			if ((mo.pos.x > 530 && mo.pos.z >= 191.9 && mo.pos.z <= mo.floorz) || lt > 400)
			{
				Console.Printf("CLIMBTEST wall start=%d speed=%.3f topped=%d x=%.1f z=%.1f steep=%.5f", startTic, (zA - z0) / 35,
					mo.pos.x > 530 && mo.pos.z >= 191.9 ? 1 : 0, mo.pos.x, mo.pos.z, mo.MaxSlopeSteepness);
				Next();
			}
		}
		else if (scen == 1) // Hold still on the wall, fire, then jump off.
		{
			if (lt == 0) { Place(480, 512); fwd = Walk; return; }
			if (startTic >= 0 && mo.pos.z >= 60 && fwd != 0) { fwd = 0; lt = 1000; ammo0 = mo.CountInv("Clip"); }
			if (lt == 1000 + 2) z0 = mo.pos.z; // after the tic already under way
			if (lt == 1000 + 20) buttons = BT_ATTACK;
			if (lt == 1000 + 50) buttons = 0;
			if (lt == 1000 + 70)
			{
				Console.Printf("CLIMBTEST hold dz=%.3f climbing=%d fired=%d", mo.pos.z - z0, Climbing() ? 1 : 0, ammo0 - mo.CountInv("Clip"));
				buttons = BT_JUMP;
			}
			if (lt == 1000 + 71) buttons = 0;
			if (lt == 1000 + 140)
			{
				Console.Printf("CLIMBTEST jump climbing=%d z=%.1f", Climbing() || Slipping() ? 1 : 0, mo.pos.z);
				Next();
			}
			if (lt == 300) { Console.Printf("CLIMBTEST hold never-started"); Next(); }
		}
		else if (scen == 2) // Strafe along the wall.
		{
			if (lt == 0) { Place(480, 512); fwd = Walk; return; }
			if (startTic >= 0 && mo.pos.z >= 40 && fwd != 0) { fwd = 0; side = Strafe; lt = 1000; }
			if (lt == 1000 + 2) { z0 = mo.pos.z; y0 = mo.pos.y; }
			if (lt == 1000 + 20) // 64 units of wall on this side of the start point
			{
				Console.Printf("CLIMBTEST strafe dy=%.2f dz=%.2f climbing=%d", mo.pos.y - y0, mo.pos.z - z0, Climbing() ? 1 : 0);
				side = 0;
				Console.Printf("CLIMBTEST part1 done uses=%d", uses);
				done = true;
			}
			if (lt == 300) { Console.Printf("CLIMBTEST strafe never-started"); done = true; }
		}
	}

	void Part2(PlayerPawn mo)
	{
		if (scen == 0) // A failed continue roll slips; regain 0 means the player falls to the ground.
		{
			if (lt == 0) { EventHandler.SendNetworkEvent("dfi_climb:100:100:0:0:0"); Place(480, 512); fwd = Walk; return; }
			if (lt == 150)
			{
				Console.Printf("CLIMBTEST slip start=%d slip=%d climbing=%d z=%.1f", startTic, slipTic, everClimbed ? (Climbing() || Slipping() ? 1 : 0) : -1, mo.pos.z);
				EventHandler.SendNetworkEvent("dfi_climb:100:100:100:100:0");
				Next();
			}
		}
		else if (scen == 1) // A 75-degree slope is climbed.
		{
			if (lt == 0) { Place(470, 200); fwd = Walk; return; }
			if (lt == 120) { Console.Printf("CLIMBTEST slope75 climbed=%d z=%.1f x=%.1f", everClimbed, mo.pos.z, mo.pos.x); Next(); }
		}
		else if (scen == 2) // A 60-degree slope is walked (Daggerfall's 70-degree limit), never climbed.
		{
			if (lt == 0) { Place(470, 800); fwd = Walk; zA = 0; return; }
			zA = max(zA, mo.pos.z); // the player walks over the top and off the far side
			if (lt == 120) { Console.Printf("CLIMBTEST slope60 climbed=%d z=%.1f x=%.1f", everClimbed, zA, mo.pos.x); Next(); }
		}
		else if (scen == 3) // Off a Daggerfall map: no climbing, and Doom's own 45-degree limit.
		{
			if (lt == 0) { EventHandler.SendNetworkEvent("dfi_rules:0"); Place(480, 512); fwd = Walk; return; }
			if (lt == 100) { Console.Printf("CLIMBTEST off-wall climbed=%d z=%.1f", everClimbed, mo.pos.z); Place(470, 800); fwd = Walk; zA = 0; }
			zA = max(zA, mo.pos.z);
			if (lt == 220)
			{
				Console.Printf("CLIMBTEST off-slope60 climbed=%d z=%.1f steep=%.5f", everClimbed, zA, mo.MaxSlopeSteepness);
				Console.Printf("CLIMBTEST part2 done uses=%d", uses);
				done = true;
			}
		}
	}
}
