version "4.14"

// Loaded only by tools/climb/run_cliff_probe.py on a converted dungeon map (no Daggerfall). Sends the rule and chance
// events a bridge session would, puts the player at the foot of a steep stair facing it, holds forward, and prints
// CLIFF lines: each climb start, stop, slip and top-out (from DFCLIMB lines too), z every 10 tics, and a summary.
class CliffProbePlayer : DoomPlayer
{
	override void PlayerThink()
	{
		let h = CliffProbe(EventHandler.Find("CliffProbe"));
		if (h)
		{
			player.cmd.forwardmove = h.fwd;
			player.cmd.sidemove = 0;
			player.cmd.buttons = 0;
			player.cmd.yaw = 0;
			player.cmd.pitch = 0;
		}
		player.cheats |= CF_GODMODE;
		Super.PlayerThink();
	}
}

class CliffProbe : EventHandler
{
	int fwd, t, starts, stops, phase, firstStart, topTic;
	double z0, zMax, topZ;
	bool was;

	override void WorldTick()
	{
		let mo = players[0].mo;
		let c = DoomerfallClimb(StaticEventHandler.Find("DoomerfallClimb"));
		if (!mo || !c || phase >= 2) return;
		t++;
		if (t == 2)
		{
			EventHandler.SendNetworkEvent("dfi_rules:1");
			EventHandler.SendNetworkEvent("dfi_climb:" .. CVar.FindCVar("cliff_chances").GetString());
			return;
		}
		if (t == 6)
		{
			Array<String> at;
			CVar.FindCVar("cliff_at").GetString().Split(at, ",");
			mo.SetOrigin((at[0].ToDouble(), at[1].ToDouble(), at[2].ToDouble()), false);
			mo.angle = at[3].ToDouble();
			topZ = at[4].ToDouble();
			mo.vel = (0, 0, 0);
			z0 = zMax = mo.pos.z;
			fwd = CVar.FindCVar("cliff_run").GetBool() ? 12800 : 6400;
			firstStart = topTic = -1;
			phase = 1;
			Console.Printf("CLIFF placed %.0f,%.0f z=%.0f angle %.0f", mo.pos.x, mo.pos.y, mo.pos.z, mo.angle);
			return;
		}
		if (phase != 1) return;
		let s = c.st[0];
		bool now = s && s.climbing;
		if (now && !was) { starts++; if (firstStart < 0) firstStart = t; Console.Printf("CLIFF t=%d start z=%.1f", t, mo.pos.z); }
		if (!now && was) { stops++; Console.Printf("CLIFF t=%d stop z=%.1f floor=%.1f", t, mo.pos.z, mo.floorz); }
		was = now;
		zMax = max(zMax, mo.pos.z);
		if (topTic < 0 && mo.pos.z >= topZ - 1 && mo.pos.z <= mo.floorz + 1) topTic = t;
		if (t % 35 == 0) Console.Printf("CLIFF t=%d z=%.1f floor=%.1f pos=%.1f,%.1f climbing=%d slipping=%d", t, mo.pos.z, mo.floorz, mo.pos.x, mo.pos.y, now, s && s.slipping);
		if (t >= CVar.FindCVar("cliff_tics").GetInt() || (topTic > 0 && t >= topTic + 35))
		{
			Console.Printf("CLIFF summary topped=%d starts=%d stops=%d firstStart=%d topTic=%d rose=%.0f z=%.1f", topTic > 0, starts, stops, firstStart, topTic, zMax - z0, mo.pos.z);
			fwd = 0;
			phase = 2;
		}
	}
}
