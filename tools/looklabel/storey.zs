version "4.10"

// Test only (tools/looklabel/storey.py): after the owner's "YouGotAPickup" save loads, wait while the player stands
// where the save left them (PDAT spot). Then stand 50 units from the save's DRLA stimpack at (-6, -102) and look at it
// (PDAT stim), then replace it with a DRLA Battle Rifle on the same spot (PDAT gun). The engine's own look label lines
// ("look: ...") between the marks are what is checked.
class PDHarness : StaticEventHandler // Static: a loaded save brings back only the level handlers it was saved with.
{
	int wait;

	override void WorldTick()
	{
		if (!(level.MapName ~== "DDS5LK5G")) return; // The save's map; the run starts on another.
		wait++;
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		if (wait == 1) Console.PrintfEx(PRINT_LOG, "PDAT spot");
		else if (wait == 175)
		{
			Console.PrintfEx(PRINT_LOG, "PDSTOREY map %s pos %.1f %.1f %.1f yaw %.1f pitch %.1f", level.MapName, pmo.pos.x, pmo.pos.y, pmo.pos.z, pmo.angle, pmo.pitch);
			Console.PrintfEx(PRINT_LOG, "PDEND");
			// The first of eight spots 48 units around the stimpack where the player fits and can see it.
			Actor stim = FindStim();
			Vector3 start = pmo.pos;
			for (int i = 0; stim && i < 8; i++)
			{
				pmo.SetOrigin((stim.pos.x - 48 * cos(i * 45), stim.pos.y - 48 * sin(i * 45), stim.floorz), false);
				pmo.SetZ(pmo.floorz);
				if (pmo.TestMobjLocation() && pmo.CheckSight(stim) && abs(pmo.floorz - stim.floorz) < 1)
				{
					pmo.angle = i * 45;
					pmo.pitch = 30;
					break;
				}
				pmo.SetOrigin(start, false);
			}
			Console.PrintfEx(PRINT_LOG, "PDMOVE stim %d at %.1f %.1f, player %.1f %.1f %.1f angle %.0f", stim != null, stim ? stim.pos.x : 0, stim ? stim.pos.y : 0, pmo.pos.x, pmo.pos.y, pmo.pos.z, pmo.angle);
			Console.PrintfEx(PRINT_LOG, "PDAT stim");
		}
		else if (wait == 280)
		{
			Console.PrintfEx(PRINT_LOG, "PDEND");
			Actor stim = FindStim();
			if (stim)
			{
				Actor.Spawn("RLBattleRiflePickup", stim.pos);
				stim.Destroy();
			}
			Console.PrintfEx(PRINT_LOG, "PDAT gun");
		}
		else if (wait == 420)
		{
			Console.PrintfEx(PRINT_LOG, "PDEND");
			Console.PrintfEx(PRINT_LOG, "PDDONE passed");
		}
	}

	// The save's stimpack nearest the player's saved spot, at (-6, -102).
	static Actor FindStim()
	{
		let it = ThinkerIterator.Create("Inventory");
		Actor mo;
		while (mo = Actor(it.Next()))
			if (mo.GetClassName() == "RLStimpack" && (mo.pos.xy - (-6, -102)).Length() < 2) return mo;
		return null;
	}
}
