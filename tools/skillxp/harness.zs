version "4.14"

// Skill XP test (skillxp.py). In town: spawns a Baron of Hell and two zombies in front of the player and hurts them
// for far more than their health as the player (overkill must not count), then hurts one townsperson the same way.
// Then it lets the bridge's -dfuitest open the skills menu through its key command (netevent df_skills, menu 15).
class SXHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	bool monsters, hurt, townsperson, released;
	int total, ready;

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (!ready && CVar.FindCVar("dd_sync_df_phase").GetInt() == 3) ready = level.maptime;
		if (!ready) return;
		if (level.maptime == ready + 1) // stand in the street by the town's first shop, where townspeople walk
		{
			p.SetOrigin(((DOORDATA[0], DOORDATA[1]) + (DOORDATA[3], DOORDATA[4]) * 200, DOORDATA[2]), false);
			p.vel = (0, 0, 0);
		}
		if (!monsters && level.maptime == ready + 35 * 4)
		{
			monsters = true;
			for (int i = 0; i < 3; i++)
			{
				Name kind = i == 0 ? 'BaronOfHell' : 'ZombieMan';
				let mo = Actor.Spawn(kind,p.Vec3Angle(160 + 40 * i, p.angle + 20 * (i - 1)), ALLOW_REPLACE);
				if (!mo) continue;
				Console.Printf("SXSPAWN %s", mo.GetClassName());
			}
		}
		if (monsters && !hurt && level.maptime == ready + 35 * 5) // DRLA spawners have placed the real monsters by now
		{
			hurt = true;
			Actor mo;
			let it = ThinkerIterator.Create("Actor");
			while (mo = Actor(it.Next()))
			{
				if (!mo.bIsMonster || mo.health <= 0 || mo.Distance2D(p) > 400) continue;
				int h = mo.health;
				int taken = mo.DamageMobj(p, p, 100000, 'None');
				total += h;
				Console.Printf("SXHIT %s health %d, hit for 100000, took %d", mo.GetClassName(), h, taken);
			}
		}
		if (hurt && !townsperson && level.maptime <= ready + 35 * 60)
		{
			Actor mo;
			let it = ThinkerIterator.Create("Actor");
			while (mo = Actor(it.Next()))
			{
				if (mo.GetClassName() != 'DFTownsperson' || mo.health <= 0) continue;
				int h = mo.health;
				int taken = mo.DamageMobj(p, p, 500, 'None');
				total += h;
				townsperson = true;
				Console.Printf("SXTOWNSPERSON health %d, hit for 500, took %d, total counted %d", h, taken, total);
				break;
			}
		}
		if (!released && (townsperson || level.maptime > ready + 35 * 60))
		{
			released = true;
			if (!townsperson) Console.Printf("SXTOWNSPERSON none found");
			CVar.FindCVar("dd_ui_test_hold").SetInt(0);
			Console.Printf("SXRELEASED total %d", total);
		}
	}
}
