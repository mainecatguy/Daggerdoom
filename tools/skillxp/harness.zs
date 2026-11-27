version "4.14"

// Skill XP test (skillxp.py). In town: spawns a Baron of Hell and two zombies in front of the player and hurts them
// for far more than their health as the player (overkill must not count), then hurts one townsperson the same way.
// Then it lets the bridge's -dfuitest open the skills menu through its key command (netevent df_skills, menu 15).
class SXHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	bool monsters, hurt, townsperson, released;
	int total, ready;
	Actor baron;

	// The mod's own running tally of damage not yet reported (DoomerfallSkillXp.xpHp). WorldThingDamaged runs inside
	// DamageMobj, so reading it just before and after one hit gives what the mod counted for that hit.
	static int Counted()
	{
		let h = DoomerfallSkillXp(StaticEventHandler.Find('DoomerfallSkillXp'));
		return h ? h.xpHp : -1;
	}

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
				if (h >= 1000) baron = mo;
				int c0 = Counted();
				int taken = mo.DamageMobj(p, p, 100000, 'None');
				int counted = Counted() - c0;
				total += counted;
				Console.Printf("SXHIT %s health %d, hit for 100000, took %d, mod counted %d", mo.GetClassName(), h, taken, counted);
			}
		}
		if (hurt && baron && level.maptime == ready + 35 * 6) // raised and killed again: must give nothing more (cap per enemy)
		{
			bool raised = p.RaiseActor(baron, RF_NOCHECKPOSITION);
			int h = baron.health;
			int c0 = Counted();
			int taken = baron.DamageMobj(p, p, 100000, 'None');
			Console.Printf("SXRAISED %d health %d, hit for 100000, took %d, mod counted %d (must be 0)", raised, h, taken, Counted() - c0);
		}
		if (hurt && !townsperson && level.maptime > ready + 35 * 7 && level.maptime <= ready + 35 * 60)
		{
			Actor mo;
			let it = ThinkerIterator.Create("Actor");
			while (mo = Actor(it.Next()))
			{
				if (mo.GetClassName() != 'DFTownsperson' || mo.health <= 0) continue;
				int h = mo.health;
				int c0 = Counted();
				int taken = mo.DamageMobj(p, p, 500, 'None');
				int counted = Counted() - c0;
				total += counted;
				townsperson = true;
				Console.Printf("SXTOWNSPERSON health %d, hit for 500, took %d, mod counted %d (tally before %d, after %d)", h, taken, counted, c0, c0 + counted);
				break;
			}
		}
		if (!released && (townsperson || level.maptime > ready + 35 * 60))
		{
			released = true;
			if (!townsperson) Console.Printf("SXTOWNSPERSON none found");
			CVar.FindCVar("dd_ui_test_hold").SetInt(0);
			Console.Printf("SXRELEASED total mod counted %d, mod tally left %d", total, Counted());
		}
	}
}
