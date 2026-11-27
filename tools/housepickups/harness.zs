version "4.14"

// House pickups test (housepickups.py). Counts generated pickups outdoors in town, enters by the test door (the
// dd_tm_use test hook), and counts them inside. WANT 0: a house, which must have none. WANT 1: a dungeon, which must
// have some. Generated pickups are what DoomerfallPickupMarker spawns: health, ammo and powerups.
class HPHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const WANT = @WANT@;
	const LIMIT = 35 * 40;

	int phase, timer, passed, failed;
	bool done;

	static bool IsPickup(Actor mo)
	{
		let inv = Inventory(mo);
		if (!inv || inv.Owner) return false;
		if (mo is "DoomerfallAmmoPickup") return true; // Ammo tiers (DoomerfallAmmo.zs) turn clips and shells into these.
		Name n = mo.GetClassName();
		static const Name kinds[] = { 'RLStimpack', 'RLClip', 'RLShell', 'RLRocketAmmo', 'RLCell', 'RLBerserk', 'RLBlurSphere', 'RLInfrared',
			'RLSoulsphere', 'RLMegasphere', 'RLInvulnerabilitySphere', 'Stimpack', 'Clip', 'Shell', 'RocketAmmo', 'Cell', 'Berserk', 'BlurSphere',
			'Infrared', 'Soulsphere', 'Megasphere', 'InvulnerabilitySphere' };
		for (int i = 0; i < kinds.Size(); i++) if (n == kinds[i]) return true;
		return false;
	}

	int Count()
	{
		int n = 0, markers = 0;
		let it = ThinkerIterator.Create("Inventory");
		Actor mo;
		while (mo = Actor(it.Next())) if (IsPickup(mo)) n++;
		let im = ThinkerIterator.Create("DoomerfallPickupMarker");
		while (im.Next()) markers++;
		Console.Printf("HPCOUNT map=%s pickups=%d markers=%d", level.MapName, n, markers);
		return n + markers;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("HPCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void Finish()
	{
		Console.Printf("HPRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("HPDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		timer++;
		if (timer > LIMIT) { Report(false, String.Format("phase %d timed out", phase)); Finish(); return; }
		switch (phase)
		{
		case 0: // Outdoors in town, once Daggerfall is in play.
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			Console.Printf("HPNOTE outdoors (town %s)", level.MapName);
			Count();
			phase = 1; timer = 0;
			break;
		case 1: // Stand at the door and press Use through the test hook until the space loads.
			if (inside) { phase = 2; timer = 0; break; }
			{
				vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
				vector2 normal = (DOORDATA[3], DOORDATA[4]);
				p.SetOrigin((door.xy + normal * 48, door.z), false);
				p.vel = (0, 0, 0);
				p.angle = atan2(-normal.y, -normal.x);
				if (timer == 12 || timer % 140 == 139) CVar.FindCVar("dd_tm_use").SetInt(1);
			}
			break;
		case 2: // Inside: give markers time to turn into items, then count.
			if (timer < 70) break;
			{
				int n = Count();
				if (WANT) Report(n > 0, String.Format("%s has generated pickups (%d)", level.MapName, n));
				else Report(n == 0, String.Format("the house %s has no generated pickups (%d)", level.MapName, n));
			}
			Finish();
			break;
		}
	}
}
