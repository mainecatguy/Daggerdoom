version "4.14"

// Skill XP test (skillxp.py). In town: first the player's own equipped gun fires (held attack button, facing the
// nearest monster) at four Demons for 20 seconds, so real shots, puffs and projectiles are counted. Then it spawns a
// Baron of Hell, two zombies and five Cyberdemons and hurts them for far more than their health as the player
// (overkill must not count; enough Skill XP to buy a cheap point with earned XP alone), then hurts one townsperson.
// Then it lets the bridge's -dfuitest open the skills menu through its key command (netevent df_skills, menu 15).
class SXHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const FIRESTART = 35 * 4;  // fire phase: the player's own gun, held trigger, at monsters spawned ahead
	const FIREEND = 35 * 24;
	const HURTAT = FIREEND + 35 * 2; // then the bulk phase below (DamageMobj as the player), shifted after the fire phase
	bool monsters, hurt, townsperson, released, fireSpawned, fireLogged;
	int total, ready, fireTics, fireHp, fireHits;
	Actor baron;

	// Fire phase bookkeeping: every hit the player's real gunfire lands on a monster, by the same overkill rule the mod
	// uses (the mod's per-enemy cap is not repeated here), so the run can compare it with what the bridge reported.
	override void WorldThingDamaged(WorldEvent e)
	{
		if (!ready || level.maptime > ready + FIREEND || !e.DamageSource || !e.DamageSource.player || !e.Thing || !e.Thing.bIsMonster) return;
		fireHits++;
		fireHp += e.Damage + min(0, e.Thing.health);
	}

	// Fire phase diagnostics: what the player's gun spawns (puffs and projectiles carry the player as target).
	int shotsSpawned;
	override void WorldThingSpawned(WorldEvent e)
	{
		if (!ready || level.maptime > ready + FIREEND || !e.Thing || !players[0].mo || e.Thing.target != players[0].mo || e.Thing.bIsMonster) return;
		if (++shotsSpawned <= 5) Console.Printf("SXSHOT %s at %.0f,%.0f,%.0f", e.Thing.GetClassName(), e.Thing.pos.x, e.Thing.pos.y, e.Thing.pos.z);
	}

	// Each tic of the fire phase: face the nearest living monster ahead and hold the attack button, so the equipped
	// weapon fires through its own states.
	void Fire(PlayerPawn p)
	{
		Actor best, mo;
		double bestDist = 1500;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
		{
			if (!mo.bIsMonster || mo.health <= 0 || mo.bFriendly) continue;
			double d = mo.Distance3D(p);
			if (d < bestDist) { best = mo; bestDist = d; }
		}
		if (!best) return;
		p.A_Face(best, 0, 0);
		// The button set here does not survive to the player's own think (attackdown stayed 0 in run 2), so run the
		// engine's own held-trigger check right away: it fires through FireWeapon and the gun's states when ready.
		players[0].cmd.buttons |= BT_ATTACK;
		p.CheckWeaponFire();
		fireTics++;
		if (fireTics % 70 == 1)
		{
			let w = players[0].ReadyWeapon;
			let psp = players[0].FindPSprite(PSP_WEAPON);
			Console.Printf("SXFIRING %s at %s (%d health, %.0f away), hits %d, HP %d, shots spawned %d, ammo %d, in Fire %d, weaponstate %d, attackdown %d, pitch %.1f, player at %.0f,%.0f,%.0f, target at %.0f,%.0f,%.0f, sight %d",
				w ? w.GetClassName() : 'none', best.GetClassName(), best.health, bestDist, fireHits, fireHp, shotsSpawned,
				w && w.Ammo1 ? w.Ammo1.Amount : -1, w && psp ? w.InStateSequence(psp.CurState, w.FindState('Fire')) : -1,
				players[0].WeaponState, players[0].attackdown, p.pitch, p.pos.x, p.pos.y, p.pos.z, best.pos.x, best.pos.y, best.pos.z, p.CheckSight(best));
		}
	}

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
		if (!fireSpawned && level.maptime == ready + FIRESTART - 35)
		{
			fireSpawned = true;
			players[0].cheats |= CF_INFINITEAMMO;
			for (int i = 0; i < 4; i++)
			{
				let mo = Actor.Spawn('Demon', p.Vec3Angle(220 + 30 * i, p.angle + 10 * (i - 1.5)), ALLOW_REPLACE);
				if (mo) Console.Printf("SXFIRESPAWN %s", mo.GetClassName());
			}
		}
		if (level.maptime > ready + FIRESTART && level.maptime <= ready + FIREEND) Fire(p);
		if (!fireLogged && level.maptime == ready + FIREEND + 35 * 2) // after the mod's next flush
		{
			fireLogged = true;
			Console.Printf("SXFIREDONE weapon %s, %d tics held, %d hits, %d HP (expected about %d Skill XP), mod tally left %d",
				players[0].ReadyWeapon ? players[0].ReadyWeapon.GetClassName() : 'none', fireTics, fireHits, fireHp, fireHp / 100, Counted());
		}
		if (!monsters && level.maptime == ready + HURTAT - 35)
		{
			monsters = true;
			for (int i = 0; i < 8; i++)
			{
				Name kind = i == 0 ? 'BaronOfHell' : i < 3 ? 'ZombieMan' : 'Cyberdemon';
				let mo = Actor.Spawn(kind,p.Vec3Angle(160 + 40 * i, p.angle + 20 * (i - 1)), ALLOW_REPLACE);
				if (!mo) continue;
				Console.Printf("SXSPAWN %s", mo.GetClassName());
			}
		}
		if (monsters && !hurt && level.maptime == ready + HURTAT) // DRLA spawners have placed the real monsters by now
		{
			hurt = true;
			Actor mo;
			let it = ThinkerIterator.Create("Actor");
			while (mo = Actor(it.Next()))
			{
				if (!mo.bIsMonster || mo.health <= 0 || mo.Distance2D(p) > 700) continue;
				int h = mo.health;
				if (h >= 1000) baron = mo;
				int c0 = Counted();
				int taken = mo.DamageMobj(p, p, 100000, 'None');
				int counted = Counted() - c0;
				total += counted;
				Console.Printf("SXHIT %s health %d, hit for 100000, took %d, mod counted %d", mo.GetClassName(), h, taken, counted);
			}
		}
		if (hurt && baron && level.maptime == ready + HURTAT + 35) // raised and killed again: must give nothing more (cap per enemy)
		{
			bool raised = p.RaiseActor(baron, RF_NOCHECKPOSITION);
			int h = baron.health;
			int c0 = Counted();
			int taken = baron.DamageMobj(p, p, 100000, 'None');
			Console.Printf("SXRAISED %d health %d, hit for 100000, took %d, mod counted %d (must be 0)", raised, h, taken, Counted() - c0);
		}
		if (hurt && !townsperson && level.maptime > ready + HURTAT + 70 && level.maptime <= ready + HURTAT + 35 * 40)
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
		if (!released && (townsperson || level.maptime > ready + HURTAT + 35 * 40))
		{
			released = true;
			if (!townsperson) Console.Printf("SXTOWNSPERSON none found");
			CVar.FindCVar("dd_ui_test_hold").SetInt(0);
			Console.Printf("SXRELEASED total mod counted %d, mod tally left %d", total, Counted());
		}
	}
}
