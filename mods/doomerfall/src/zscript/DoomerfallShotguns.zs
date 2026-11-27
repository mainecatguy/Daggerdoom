// The Shotguns skill in Doom (the Shotguns perks card). Daggerfall decides the rules from the live skill and sends them
// in the character sheet (DFB_SHEET_SHOT_*, DoomerfallShotgunsRules.cs); Doom applies them to guns whose skill is
// Shotguns (DoomerfallWeaponCategory.SkillSlotOf): stock Doom's Shotgun and Super Shotgun, or a DRLA shotgun. Without a
// Daggerfall character every rule reads off, so a Doom-only game is unchanged.
//
//   damage bonus   every pellet from the gun does +x% (0 to 75%).
//   faster reload  reload frames are shortened by x% in whole tics: each frame's tics times x% are added to a running
//                  total, and each frame loses the whole tics of that total (never below 1 tic, and 0-tic frames stay
//                  0), so over a reload the cut comes to x% of the frames longer than 1 tic. A reload is a DRLA gun's
//                  reload (the player pressed reload, fired with an empty magazine, or DRLA's autoreload took over after
//                  the shot that emptied it), or, for a gun with no Reload state such as stock Doom's, everything after
//                  the frame that fired (the pump or the reload) until the gun is ready again.
//   more pellets   each spread shot fires x% more pellets (the engine asks Inventory.ModifyPellets); fractions round up
//                  with their chance, so a 1-pellet call such as the DRLA Assault Shotgun's gets 2 pellets half the time.
//   knockback      once per shot (all pellets that hit an enemy in one tic), the enemy is pushed away from the player:
//                  BaseKnock units/tic x the rule's strength x (pellets that hit / RefPellets x the pellet bonus, at
//                  most 1) x sqrt(100 / mass) (at most 1, so bigger enemies move less). A clear shove staggers (pain
//                  state). If the enemy's flight is stopped by a wall it takes up to the rule's slam damage, scaled by
//                  its speed then over the strongest launch; if it is stopped by another actor, both take up to the
//                  collision damage the same way. Once per shot each.
//
// Only hits from a Shotguns gun count: hitscan damage comes with its puff as the inflictor and lands in the tic it is
// fired, so a puff hit while a Shotguns gun is held came from that gun.
class DoomerfallShotguns : StaticEventHandler
{
	// DFB_SHEET_* indices; must match bridge/doomerfall_bridge.h.
	const SheetValid = 2;
	const SkillShotguns = 4;
	const ShotDamageBp = 162;
	const ShotReloadBp = 163;
	const ShotPelletBp = 164;
	const ShotKnockBp = 165;
	const ShotSlamDamage = 166;
	const ShotCollideDamage = 167;

	const BaseKnock = 16.;     // Units per tic at strength 10000 with every pellet hitting a 100-mass enemy.
	const RefPellets = 14.;    // A DRLA Double Shotgun blast: the full effect.
	const StaggerSpeed = 4.;   // Shoves at least this fast stagger.
	const FlightTics = 35;     // Watch a knocked enemy this long for a slam.

	clearscope static int Rule(int index)
	{
		return max(0, Actor.DD_SheetValue(index));
	}

	clearscope static bool IsShotgun(Weapon w)
	{
		return w && DoomerfallWeaponCategory.SkillSlotOf(w) == SkillShotguns;
	}

	// x * factor, rounding the fraction up with its chance.
	static int Scale(int x, double factor)
	{
		double y = x * factor;
		int whole = int(y);
		if (frandom[DoomerfallShotguns](0, 1) < y - whole) whole++;
		return max(1, whole);
	}

	// Perk log lines: always in the log, capped unless dd_perklog is on (tests).
	int logged;
	static void Log(String msg)
	{
		let h = DoomerfallShotguns(StaticEventHandler.Find("DoomerfallShotguns"));
		let all = CVar.FindCVar("dd_perklog");
		if (!h || (h.logged >= 200 && !(all && all.GetBool()))) return;
		h.logged++;
		DDLog.Debug(String.Format("shotguns: %s", msg));
	}

	// Whether damage through this inflictor came from a Shotguns gun of this player.
	static bool FromGun(Actor player, Actor inflictor)
	{
		if (!player || !player.player || !inflictor) return false;
		if (inflictor.bIsPuff) return IsShotgun(player.player.ReadyWeapon);
		let h = DoomerfallShotguns(StaticEventHandler.Find("DoomerfallShotguns"));
		return h && h.shots.Find(inflictor) < h.shots.Size();
	}

	// Projectile pellets (such as DRLA's Plasma Shotgun, when Shotguns is its higher skill): a missile the player fires
	// next to them while a Shotguns gun is mid-shot is that gun's, and its hits count when it lands, even after a switch.
	// Not kept by saves.
	Array<Actor> shots;

	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		if (!m || !m.bMissile || !m.target || !m.target.player || m.target.player.mo != m.target) return;
		let p = m.target.player;
		if (!IsShotgun(p.ReadyWeapon) || (p.WeaponState & WF_WEAPONREADY)) return;
		if (m.Distance2D(m.target) > m.target.radius + m.radius + 64) return; // Spawned by something else out in the world.
		shots.Push(m);
	}

	// Pellets that hit each enemy this tic, and who fired them.
	Array<Actor> hitVictims;
	Array<Actor> hitShooters;
	Array<int> hitPellets;
	// Enemies in flight from a knockback.
	Array<Actor> flyers;
	Array<Actor> flyShooters;
	Array<double> flyLastSpeed;
	Array<int> flyTics;

	override void WorldThingDamaged(WorldEvent e)
	{
		let victim = e.Thing;
		let src = e.DamageSource;
		if (e.Damage <= 0 || !victim || victim.player || !src || !src.player || src.player.mo != src) return;
		if (Rule(ShotKnockBp) <= 0 || !FromGun(src, e.Inflictor)) return;
		int i = hitVictims.Find(victim);
		if (i < hitVictims.Size()) { hitPellets[i]++; return; }
		hitVictims.Push(victim);
		hitShooters.Push(src);
		hitPellets.Push(1);
	}

	override void WorldTick()
	{
		for (int i = 0; i < hitVictims.Size(); i++) Knock(hitVictims[i], hitShooters[i], hitPellets[i]);
		hitVictims.Clear();
		hitShooters.Clear();
		hitPellets.Clear();
		Fly();
		for (int i = shots.Size() - 1; i >= 0; i--) if (!shots[i]) shots.Delete(i);

		if (Actor.DD_SheetValue(SheetValid) != 1) return; // Rules come from Daggerfall's character only.
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = playeringame[i] ? players[i].mo : null;
			if (mo && mo.health > 0 && !mo.FindInventory("DoomerfallShotgunsPerks")) mo.GiveInventory("DoomerfallShotgunsPerks", 1);
		}
	}

	// Strongest launch at the current strength: every pellet on a 100-mass enemy.
	static double FullSpeed()
	{
		return BaseKnock * Rule(ShotKnockBp) / 10000.;
	}

	void Knock(Actor victim, Actor shooter, int pellets)
	{
		if (!victim || !shooter || victim.health <= 0 || victim.bDontThrust) return;
		double full = FullSpeed();
		if (full <= 0) return;
		double share = min(1., pellets / (RefPellets * (1 + Rule(ShotPelletBp) / 10000.)));
		double size = min(1., sqrt(100. / max(1, victim.Mass)));
		double speed = full * share * size;
		if (speed < 0.5) return;
		victim.Vel.XY += Actor.AngleToVector(shooter.AngleTo(victim), speed);
		bool stagger = speed >= StaggerSpeed && !victim.bNoPain && victim.FindState("Pain");
		if (stagger) victim.SetState(victim.FindState("Pain"));
		Log(String.Format("knock %s pellets %d share %.3f size %.3f speed %.2f%s", victim.GetClassName(), pellets, share, size, speed, stagger ? " stagger" : ""));
		int i = flyers.Find(victim);
		if (i == flyers.Size())
		{
			flyers.Push(victim);
			flyShooters.Push(shooter);
			flyLastSpeed.Push(0);
			flyTics.Push(0);
		}
		flyShooters[i] = shooter; // A new shot: a new slam and collision are allowed.
		flyLastSpeed[i] = victim.Vel.XY.Length();
		flyTics[i] = 0;
	}

	// Each tic of a knocked enemy's flight: the movement Doom just ran stopped on a wall (MovementBlockingLine, cleared
	// each tic before the move) or on an actor (its speed suddenly lost) -> slam or collision damage, then done.
	void Fly()
	{
		for (int i = flyers.Size() - 1; i >= 0; i--)
		{
			let mo = flyers[i];
			bool done = !mo || mo.health <= 0 || ++flyTics[i] > FlightTics;
			if (!done)
			{
				double last = flyLastSpeed[i], now = mo.Vel.XY.Length(), full = FullSpeed();
				double strength = full > 0 ? min(1., last / full) : 0;
				if (mo.MovementBlockingLine && now < last * 0.5)
				{
					Hit(mo, flyShooters[i], Rule(ShotSlamDamage), strength, "slam");
					done = true;
				}
				else if (mo.BlockingMobj && now < last * 0.5 && mo.BlockingMobj != flyShooters[i] && mo.BlockingMobj.bShootable)
				{
					let other = mo.BlockingMobj;
					Hit(mo, flyShooters[i], Rule(ShotCollideDamage), strength, "collide");
					Hit(other, flyShooters[i], Rule(ShotCollideDamage), strength, "collided");
					done = true;
				}
				else if (now < 1) done = true;
				flyLastSpeed[i] = now;
			}
			if (!done) continue;
			flyers.Delete(i);
			flyShooters.Delete(i);
			flyLastSpeed.Delete(i);
			flyTics.Delete(i);
		}
	}

	static void Hit(Actor mo, Actor shooter, int most, double strength, String what)
	{
		if (!mo || mo.health <= 0) return;
		int dmg = int(round(most * strength));
		Log(String.Format("%s %s speed share %.3f damage %d (most %d)", what, mo.GetClassName(), strength, dmg, most));
		if (dmg > 0) mo.DamageMobj(null, shooter, dmg, 'None', DMG_THRUSTLESS);
	}
}

// On the player while Daggerfall's character is loaded: the damage bonus, more pellets and faster reloads.
class DoomerfallShotgunsPerks : Inventory
{
	Weapon trackedGun;
	State lastState;
	int lastTics;
	bool reloading, firedSinceReady, readyLastTic;
	double cutCarry;
	int shotTic;
	int lastAmmo;

	Default
	{
		Inventory.MaxAmount 1;
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
	}

	override void BeginPlay()
	{
		Super.BeginPlay();
		shotTic = -1;
	}

	override int ModifyPellets(Weapon weap, int pellets)
	{
		if (!DoomerfallShotguns.IsShotgun(weap) || pellets <= 0) return pellets;
		shotTic = level.maptime;
		int bp = DoomerfallShotguns.Rule(DoomerfallShotguns.ShotPelletBp);
		if (bp <= 0) return pellets;
		int more = DoomerfallShotguns.Scale(pellets, 1 + bp / 10000.);
		DoomerfallShotguns.Log(String.Format("pellets %s %d -> %d", weap.GetClassName(), pellets, more));
		return more;
	}

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		// Active: source is the actor being hit. The player's own hits on others only.
		if (passive || damage <= 0 || !owner || source == owner || !DoomerfallShotguns.FromGun(owner, inflictor)) return;
		int bp = DoomerfallShotguns.Rule(DoomerfallShotguns.ShotDamageBp);
		if (bp <= 0) return;
		newdamage = DoomerfallShotguns.Scale(damage, 1 + bp / 10000.);
		DoomerfallShotguns.Log(String.Format("hit %s with %s: %d -> %d", source ? source.GetClassName() : 'None', owner.player.ReadyWeapon.GetClassName(), damage, newdamage));
	}

	// Runs after the player's weapon frames moved this tic, so a frame entered this tic still has all its tics.
	override void DoEffect()
	{
		Super.DoEffect();
		let p = owner ? owner.player : null;
		let w = p ? p.ReadyWeapon : null;
		let psp = p ? p.FindPSprite(PSP_WEAPON) : null;
		int cut = DoomerfallShotguns.Rule(DoomerfallShotguns.ShotReloadBp);
		if (!psp || cut <= 0 || !DoomerfallShotguns.IsShotgun(w) || p.PendingWeapon != WP_NOCHANGE || w != trackedGun)
		{
			trackedGun = (psp && DoomerfallShotguns.IsShotgun(w) && p.PendingWeapon == WP_NOCHANGE) ? w : null;
			reloading = false;
			readyLastTic = p && (p.WeaponState & WF_WEAPONREADY);
			lastState = psp ? psp.CurState : null;
			lastTics = psp ? psp.Tics : 0;
			lastAmmo = AmmoNow(w);
			return;
		}

		int ammo = AmmoNow(w);
		bool shot = shotTic == level.maptime || (ammo < lastAmmo && (p.cmd.buttons & (BT_ATTACK | BT_ALTATTACK)));
		lastAmmo = ammo;
		bool entered = psp.CurState != lastState || psp.Tics > lastTics;
		bool hasReload = w.FindState("Reload") != null;
		bool magEmpty = w.AmmoType1 && w.AmmoType2 && owner.CountInv(w.AmmoType1) < w.AmmoUse1;
		bool wasReady = readyLastTic;
		readyLastTic = p.WeaponState & WF_WEAPONREADY;
		if (p.WeaponState & WF_WEAPONREADY)
		{
			reloading = false;
			firedSinceReady = false;
		}
		else if (shot)
		{
			// The frames after a shot: a stock gun's pump or reload, or DRLA's autoreload when the magazine ran dry.
			let autoOption = CVar.GetCVar("DRLA_autoreload", p);
			reloading = !hasReload || (magEmpty && autoOption && autoOption.GetBool());
			firedSinceReady = true;
			entered = false; // Not the frame that fired.
			cutCarry = 0;
		}
		else if (entered && (psp.CurState == w.FindState("Fire") || psp.CurState == w.FindState("Hold")))
			reloading = false; // Firing again (a stock gun's A_ReFire): the next shot's frames are not a reload.
		// A reload starts only as the gun leaves its ready state without firing: the reload key (A_WeaponReady's reload)
		// or a pull on an empty magazine (DRLA's Fire goes to Reload). Holding the key later changes nothing.
		else if (!reloading && wasReady && hasReload && ((p.cmd.buttons & BT_RELOAD) || magEmpty))
		{
			reloading = true;
			cutCarry = 0;
		}

		if (reloading && entered && psp.Tics > 1)
		{
			int before = psp.Tics;
			cutCarry += before * cut / 10000.;
			int remove = min(int(cutCarry), before - 1);
			cutCarry -= remove;
			psp.Tics -= remove;
			DoomerfallShotguns.Log(String.Format("reload %s frame %d -> %d tics", w.GetClassName(), before, psp.Tics));
		}
		lastState = psp.CurState;
		lastTics = psp.Tics;
	}

	int AmmoNow(Weapon w)
	{
		return (w && w.AmmoType1) ? owner.CountInv(w.AmmoType1) : 0;
	}
}
