version "4.10"

class DFWaterProbe : Actor
{
	Default { Radius 1; Height 16; +NOINTERACTION; +NOGRAVITY; +NOBLOCKMAP; }
	States { Spawn: TNT1 A -1; Stop; }
}

// The engine thinks for players before event handlers and thinkers run, so the held button is added here.
class DFWaterPlayer : DoomPlayer
{
	bool holdJump;
	override void PlayerThink()
	{
		if (holdJump) player.cmd.buttons |= BT_JUMP;
		Super.PlayerThink();
	}
}

// Reads DFWPROBE, checks wet and dry points in the real map, then swims the player.
class DFWaterCheck : EventHandler
{
	int tick, swimStart, startLevel;
	double swimX, swimY, swimFloor, swimTop, startZ, sunkZ, peakZ;
	bool hasSwim;

	override void WorldTick()
	{
		tick++;
		let mo = players[0].mo;
		let swimmer = DFWaterPlayer(mo);
		if (swimmer) swimmer.holdJump = tick > 41 && tick <= 176;
		if (tick == 5) RunProbes();
		if (tick == 6 && !hasSwim) { Console.Printf("DFWATER DONE"); return; }
		if (!hasSwim || tick < 6) return;
		if (tick == 6)
		{
			startZ = (swimFloor + swimTop) / 2 - mo.Height / 2;
			if (startZ < swimFloor) startZ = swimFloor;
			mo.SetOrigin((swimX, swimY, startZ), false);
			mo.vel = (0, 0, 0);
		}
		if (tick == 8) startLevel = mo.waterlevel;
		if (tick == 41) { sunkZ = mo.pos.z; peakZ = sunkZ; }
		if (tick > 41 && tick <= 176)
		{
			peakZ = max(peakZ, mo.pos.z);
		}
		if (tick == 177)
		{
			Console.Printf("DFWATER SWIM floor=%.0f top=%.0f start=%.1f level=%d after1s=%.1f peak=%.1f endlevel=%d", swimFloor, swimTop, startZ, startLevel, sunkZ, peakZ, mo.waterlevel);
			Console.Printf("DFWATER DONE");
		}
	}

	void RunProbes()
	{
		int lump = Wads.CheckNumForFullName("DFWPROBE.txt");
		if (lump < 0) lump = Wads.CheckNumForName("DFWPROBE", Wads.ns_global);
		if (lump < 0) { Console.Printf("DFWATER ERROR no probe lump"); return; }
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n");
		let probe = Actor.Spawn("DFWaterProbe", (0, 0, 0));
		int total, bad, wetCount, dryCount, printed, moved;
		foreach (text : lines)
		{
			Array<String> f;
			text.Split(f, " ");
			if (f.Size() == 5 && f[0] == "S")
			{
				hasSwim = true;
				swimX = f[1].ToDouble(); swimY = f[2].ToDouble(); swimFloor = f[3].ToDouble(); swimTop = f[4].ToDouble();
			}
			if (f.Size() != 5 || f[0] != "P") continue;
			double x = f[1].ToDouble(), y = f[2].ToDouble(), z = f[3].ToDouble();
			bool wet = f[4].ToInt() != 0;
			probe.SetOrigin((x, y, z), false);
			probe.UpdateWaterLevel(false);
			bool got = probe.waterlevel > 0;
			total++;
			if (wet) wetCount++; else dryCount++;
			if (got != wet)
			{
				// A fitted wall can move a cell's center into the next sector. Then this floor is not here at all.
				double found = probe.CurSector.NextLowestFloorAt(x, y, z + 1);
				if (abs(found - (z - 1)) > 1) { moved++; continue; }
				bad++;
				if (printed++ < 8) Console.Printf("DFWATER MISMATCH %.0f %.0f %.0f expected %d got %d", x, y, z, wet, got);
			}
		}
		probe.Destroy();
		Console.Printf("DFWATER PROBES total=%d wet=%d dry=%d mismatches=%d offspan=%d", total, wetCount, dryCount, bad, moved);
	}
}
