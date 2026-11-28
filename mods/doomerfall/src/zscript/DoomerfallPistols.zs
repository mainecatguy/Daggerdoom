// The Pistols skill in Doom (the Pistols perks card). Daggerfall decides the rules from the live skill and sends them in
// the character sheet (DFB_SHEET_PIST_*, DoomerfallPistolsRules.cs); Doom applies them to guns whose skill is Pistols
// (DoomerfallWeaponCategory.SkillSlotOf): stock Doom's Pistol or a DRLA pistol-type gun, never a rifle. Without a
// Daggerfall character every rule reads off, so a Doom-only game is unchanged.
//
//   fire-rate multipliers  (25 and 75) fast and slow are DRLA's Scout definition (owner, 2026-11-27): each pistol's
//                  Scout damage multiplier (x3 for the fastest guns to x8 for the slowest; ScoutOf below, listed by
//                  tools/pistols/scout_scale.py). Each multiplier goes linearly from its fast value to its slow value
//                  along that scale; the two multiply. A gun beyond an end counts as that end. Damage only: the gun
//                  fires as before.
//   faster reload  a DRLA pistol's reload frames are shortened by x% in whole tics, as for Shotguns. Stock Doom's Pistol
//                  has no reload, so nothing changes for it.
//   bonus pool     every pistol shot spends the whole pool, hit or miss (owner, 2026-11-27): a bullet that hits in the
//                  tic it is fired gets it added to its damage after the multipliers (Deadeye does not multiply it); a
//                  projectile pistol's shot carries what it spent to its first hit; a miss wastes it. It refills from
//                  empty in the rule's time.
//   carry-through  when a pistol hit kills, the damage beyond the kill (minus the victim's health after the hit) goes on
//                  along the shot's line to the next shootable thing behind the corpse, and so on while damage remains.
//   shrapnel       every pistol hit and every carry-through hit bursts into fragments behind the enemy, forking in a V,
//                  each dealing a share of that hit's damage (a carry-through hit: of the damage it carried). A fragment
//                  never hits the enemy it split from, makes no fragments and no carry-through. Fragments are hitscan,
//                  fan out in a 30-degree V (the outer two 15 degrees either side of the shot's line), have no range
//                  limit, and fly straight unless an enemy is within the lock-on angle (2.5 degrees) of the path, which
//                  they then hit. Their hit effect is smaller than a bullet's: the smallest blood, a half-size puff.
// Carry-through and fragment damage are slices of a hit that already had every damage boost, so they are dealt with
// DMG_NO_ENHANCE (no boost twice) and no inflictor; the victim's own damage factors and armor still apply. They are
// dealt at the next tick (the WorldTick after the hit), all chains in that same tick.
class DoomerfallPistols : StaticEventHandler
{
	// DFB_SHEET_* indices; must match bridge/doomerfall_bridge.h.
	const SheetValid = 2;
	const SkillPistols = 7;
	const SprayFastBp = 181;
	const SpraySlowBp = 182;
	const DeadeyeFastBp = 183;
	const DeadeyeSlowBp = 184;
	const ScaleFast = 185;
	const ScaleSlow = 186;
	const ReloadBp = 187;
	const Carry = 188;
	const Pool = 189;
	const PoolRefillMs = 190;
	const Fragments = 191;
	const FragmentBp = 192;
	const FragmentTurnCdeg = 193;

	const CarryRange = 8192.;     // as far as a hitscan bullet
	const FragmentRange = 65536.; // no range limit: farther than a Doom map is wide
	const FragmentV = 30.;        // degrees between the outermost fragments of the V
	const MaxSteps = 4096;        // safety stop for one tick's chains

	enum EDeal { DealNone, DealCarry, DealFragment }

	clearscope static int Rule(int index)
	{
		return max(0, Actor.DD_SheetValue(index));
	}

	clearscope static bool IsPistol(Weapon w)
	{
		return w && DoomerfallWeaponCategory.SkillSlotOf(w) == SkillPistols;
	}

	// Perk log lines: always in the log, capped unless dd_perklog is on (tests).
	int logged;
	static void Log(String msg)
	{
		let h = DoomerfallPistols(StaticEventHandler.Find("DoomerfallPistols"));
		let all = CVar.FindCVar("dd_perklog");
		if (!h || (h.logged >= 200 && !(all && all.GetBool()))) return;
		h.logged++;
		DDLog.Debug(String.Format("pistols: %s", msg));
	}

	// The Pistols gun behind damage this player deals through this inflictor (DoomerfallShots.Find: the held gun for a
	// bullet's puff, the shot's tag for a projectile), or null.
	static class<Weapon> FromGun(Actor player, Actor inflictor)
	{
		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		if (!DoomerfallShots.Find(player, inflictor, gun, skill, tag) || skill != SkillPistols) return null;
		return gun;
	}

	// DRLA's Scout damage multiplier for a gun, from the comment above each DRLA weapon's Fire state
	// (tools/pistols/scout_scale.py lists them). Stock Doom's Pistol counts as DRLA's Pistol, which replaces it with the
	// same shot and fire rate. A parent class's entry counts for a subclass. 0 for a gun not listed.
	static int ScoutOf(class<Weapon> gun)
	{
		static const String names[] = {
			"Pistol", "RLPistol", "RLCombatPistol", "RLHandcannon", "RLMarksmanPistol", "RLBlaster", "RLNuclearPlasmaPistol",
			"RLUzi", "RLHuntingRevolver", "RLPP7", "RLSilencedPistol", "RLShredderPistol", "RLSpeedloaderPistol",
			"RLNuclearPlasmaRevolver", "RLHighPowerPistol", "RLHighPowerCombatPistol", "RLHighPowerHandcannon",
			"RLHighPowerMarksmanPistol", "RLHighPowerBlaster", "RLHighPowerNuclearPlasmaPistol", "RLHighPowerHuntingRevolver",
			"RLHighPowerPP7", "RLHighPowerUzi", "RLStormPistol", "RLStormCombatPistol", "RLStormHandcannon",
			"RLStormMarksmanPistol", "RLStormBlaster", "RLStormNuclearPlasmaPistol", "RLStormUzi", "RLPlasmaPistol",
			"RLPlasmaCombatPistol", "RLPlasmaHandcannon", "RLPlasmaMarksmanPistol", "RLPlasmaUzi", "RLOverchargedBlaster",
			"RLSuperchargedNuclearPlasmaPistol", "RLDemolitionAmmoPistol", "RLDemolitionAmmoCombatPistol",
			"RLDemolitionAmmoHandcannon", "RLDemolitionAmmoMarksmanPistol", "RLDemolitionAmmoUzi",
			"RLNanoManufactureAmmoPistol", "RLNanoManufactureAmmoCombatPistol", "RLNanoManufactureAmmoHandCannon",
			"RLNanomanufactureAmmoMarksmanPistol", "RLNanoManufactureAmmoBlaster", "RLNanoManufactureAmmoUzi",
			"RLHeavyPulseBlaster", "RLAssaultRifleUzi", "RLBurstCannonUzi", "RLLaserShotgun", "RLDeathsGaze", "RLBaronBlaster",
			"RLLonghorn", "RLAntiFreakJackal", "RLGrammatonClericBeretta", "RLHellsingARMSCasull", "RLMarathonShotguns",
			"RLMysteriousMagnum", "RLUnknownHerald"
		};
		static const int scout[] = {
			8, 8, 7, 8, 2, 8, 8,
			4, 8, 8, 8, 5, 8,
			8, 10, 9, 10,
			2, 10, 10, 10,
			10, 6, 7, 6, 7,
			2, 7, 7, 3, 8,
			7, 8, 2, 4, 8,
			8, 8, 7,
			8, 2, 4,
			8, 7, 8,
			2, 8, 4,
			8, 8, 7, 7, 8, 8,
			8, 8, 8, 8, 3,
			8, 4
		};
		for (class<Object> c = gun; c; c = c.GetParentClass())
		{
			String n = c.GetClassName();
			for (int i = 0; i < names.Size(); i++) if (n ~== names[i]) return scout[i];
		}
		return 0;
	}

	// Where a Scout multiplier sits from fast (0) to slow (1), or -1 while the scale is not set. A gun not listed sits in
	// the middle.
	static double SlowShare(int scoutMult)
	{
		int fast = Rule(ScaleFast), slow = Rule(ScaleSlow);
		if (fast <= 0 || slow <= fast) return -1;
		if (scoutMult <= 0) return 0.5;
		return clamp((scoutMult - fast) / double(slow - fast), 0., 1.);
	}

	// Both fire-rate multipliers together for a gun with this Scout multiplier.
	static double Multiplier(int scoutMult)
	{
		double t = SlowShare(scoutMult);
		if (t < 0) return 1;
		double m = 1;
		int f = Rule(SprayFastBp), s = Rule(SpraySlowBp);
		if (f > 0 && s > 0) m *= (f + (s - f) * t) / 10000.;
		f = Rule(DeadeyeFastBp);
		s = Rule(DeadeyeSlowBp);
		if (f > 0 && s > 0) m *= (f + (s - f) * t) / 10000.;
		return m;
	}

	// Carry-through and fragment hits waiting for the next tick.
	Array<int> qKind;
	Array<Actor> qFrom;     // the enemy the hit landed on (skipped by its own fragments and carry)
	Array<Actor> qShooter;
	Array<double> qX, qY, qZ, qDX, qDY, qDZ;
	Array<int> qDamage;
	Array<Name> qType;
	int dealing;            // EDeal while this handler's own damage is being dealt
	int carried;            // the damage the carry-through being dealt carries
	DoomerfallPistolTracer tracer;

	override void WorldThingDamaged(WorldEvent e)
	{
		let victim = e.Thing;
		let src = e.DamageSource;
		if (e.Damage <= 0 || !victim || victim.player || !src || !src.player || src.player.mo != src) return;
		if (dealing == DealFragment) return; // Fragments make no fragments and no carry-through.
		int burst;
		if (dealing == DealCarry) burst = carried;
		else if (FromGun(src, e.Inflictor)) burst = e.Damage;
		else return;
		bool carry = Rule(Carry) > 0 && victim.health < 0;
		bool shrapnel = Rule(Fragments) > 0 && Rule(FragmentBp) > 0;
		if (!carry && !shrapnel) return;

		// The shot's line: carried on from the carry-through, a projectile's flight, or the shooter's eye to the puff.
		Vector3 dir;
		Vector3 at = victim.pos + (0, 0, victim.height / 2);
		if (dealing == DealCarry) dir = carryDir;
		else
		{
			let inf = e.Inflictor;
			Vector3 eye = src.pos + (0, 0, src.player.viewz - src.pos.z);
			if (inf && !inf.bIsPuff && inf.Vel.Length() > 0) dir = inf.Vel;
			else if (inf && inf.bIsPuff) dir = inf.pos - eye;
			else dir = at - eye;
			if (inf) at.Z = clamp(inf.pos.Z, victim.pos.Z, victim.pos.Z + victim.height);
		}
		// Level, as Doom aims: a line that kept the shot's pitch would dive into the floor or sky a little way behind
		// the enemy, so carry-through and fragments fly flat at the hit's height.
		if (dir.XY.Length() <= 0) return;
		dir = (dir.XY.Unit(), 0);
		if (carry) Queue(DealCarry, victim, src, at, dir, -victim.health, e.DamageType);
		if (shrapnel) Queue(DealFragment, victim, src, at, dir, burst, e.DamageType);
	}
	Vector3 carryDir;

	void Queue(int kind, Actor from, Actor shooter, Vector3 at, Vector3 dir, int damage, Name type)
	{
		qKind.Push(kind);
		qFrom.Push(from);
		qShooter.Push(shooter);
		qX.Push(at.X); qY.Push(at.Y); qZ.Push(at.Z);
		qDX.Push(dir.X); qDY.Push(dir.Y); qDZ.Push(dir.Z);
		qDamage.Push(damage);
		qType.Push(type);
	}

	override void WorldTick()
	{
		// Each entry can queue more (a carry-through that kills again); all of them are dealt this tick.
		for (int i = 0; i < qKind.Size() && i < MaxSteps; i++)
		{
			let shooter = qShooter[i];
			if (!shooter || shooter.health <= 0) continue;
			Vector3 at = (qX[i], qY[i], qZ[i]), dir = (qDX[i], qDY[i], qDZ[i]);
			if (qKind[i] == DealCarry) CarryOn(qFrom[i], shooter, at, dir, qDamage[i], qType[i]);
			else Burst(qFrom[i], shooter, at, dir, qDamage[i], qType[i]);
		}
		qKind.Clear(); qFrom.Clear(); qShooter.Clear();
		qX.Clear(); qY.Clear(); qZ.Clear(); qDX.Clear(); qDY.Clear(); qDZ.Clear();
		qDamage.Clear(); qType.Clear();

		if (Actor.DD_SheetValue(SheetValid) != 1) return; // Rules come from Daggerfall's character only.
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = playeringame[i] ? players[i].mo : null;
			if (mo && mo.health > 0 && !mo.FindInventory("DoomerfallPistolsPerks")) mo.GiveInventory("DoomerfallPistolsPerks", 1);
		}
	}

	override void WorldUnloaded(WorldEvent e)
	{
		qKind.Clear(); qFrom.Clear(); qShooter.Clear();
		qX.Clear(); qY.Clear(); qZ.Clear(); qDX.Clear(); qDY.Clear(); qDZ.Clear();
		qDamage.Clear(); qType.Clear();
	}

	// The first thing this line hits that a bullet would: a live shootable actor (not the player, not skip) or a wall.
	// Where it ended goes to traceHit and traceDist (the VM cannot pass a vector by reference).
	Vector3 traceHit;
	double traceDist;
	Actor TraceFrom(Actor skip, Actor shooter, Vector3 at, Vector3 dir, double range)
	{
		if (!tracer) tracer = new("DoomerfallPistolTracer");
		tracer.skip = skip;
		tracer.shooter = shooter;
		traceHit = at + dir * range;
		traceDist = range;
		if (!tracer.Trace(at, level.PointInSector(at.XY), dir, range, 0, Line.ML_BLOCKEVERYTHING | Line.ML_BLOCKHITSCAN)) return null;
		traceHit = tracer.Results.HitPos;
		traceDist = tracer.Results.Distance;
		return tracer.Results.HitType == TRACE_HitActor ? tracer.Results.HitActor : null;
	}

	void Deal(int kind, Actor victim, Actor shooter, int damage, Name type, Vector3 at, Vector3 dir)
	{
		int was = dealing;
		Vector3 keep = carryDir;
		dealing = kind;
		carryDir = dir;
		if (kind == DealCarry) carried = damage;
		if (!victim.bNoBlood)
		{
			// A fragment's hit looks weaker than a bullet's: the smallest blood frame (damage under 9), scaled down.
			let blood = victim.SpawnBlood(at, atan2(-dir.Y, -dir.X), kind == DealFragment ? min(damage, 8) : damage);
			if (blood && kind == DealFragment) blood.Scale *= 0.6;
		}
		victim.DamageMobj(null, shooter, damage, type, DMG_THRUSTLESS | DMG_NO_ENHANCE);
		dealing = was;
		carryDir = keep;
	}

	void CarryOn(Actor from, Actor shooter, Vector3 at, Vector3 dir, int damage, Name type)
	{
		if (damage <= 0) return;
		let next = TraceFrom(from, shooter, at, dir, CarryRange);
		Vector3 hitPos = traceHit;
		Log(String.Format("carry %s -> %s damage %d dist %.0f", from ? from.GetClassName() : 'None', next ? next.GetClassName() : 'None', damage, traceDist));
		if (next) Deal(DealCarry, next, shooter, damage, type, hitPos, dir);
		else Puff(hitPos, false);
	}

	// The fragments of one hit: a V of straight lines behind the enemy, each turning to an enemy close to its path.
	void Burst(Actor from, Actor shooter, Vector3 at, Vector3 dir, int hit, Name type)
	{
		int n = Rule(Fragments);
		int damage = max(1, int(round(hit * Rule(FragmentBp) / 10000.)));
		double turn = Rule(FragmentTurnCdeg) / 100.;
		if (from && dir.XY.Length() > 0) at += (dir.XY.Unit() * from.radius, 0); // out of the far side of the enemy
		double yaw = atan2(dir.Y, dir.X), pitch = -asin(clamp(dir.Z, -1., 1.));

		// Enemies a fragment could lock on to: once per burst, those within the lock-on angle of the V (no range limit,
		// so every live monster on the map is looked at; the angle test is cheap).
		Array<Actor> near;
		double half = n > 1 ? FragmentV / 2 : 0;
		if (turn > 0)
		{
			let it = ThinkerIterator.Create("Actor", Thinker.STAT_DEFAULT);
			Actor a;
			while (a = Actor(it.Next()))
			{
				if (a == from || !a.bIsMonster || a.bFriendly || !a.bShootable || a.health <= 0 || a.player) continue;
				Vector2 to = a.pos.XY - at.XY;
				if (abs(Actor.DeltaAngle(yaw, atan2(to.Y, to.X))) <= half + turn) near.Push(a);
			}
		}

		for (int k = 0; k < n; k++)
		{
			double a = n > 1 ? yaw - half + k * FragmentV / (n - 1) : yaw;
			Vector3 fdir = (cos(a) * cos(pitch), sin(a) * cos(pitch), -sin(pitch));
			let victim = TraceFrom(from, shooter, at, fdir, FragmentRange);
			Vector3 hitPos = traceHit;
			double dist = traceDist;
			bool turned = false;
			// The nearest enemy within the lock-on angle that a fragment could reach, if nearer than the straight hit.
			for (int j = 0; j < near.Size(); j++)
			{
				let c = near[j];
				if (!c || c.health <= 0) continue;
				// Within the lock-on angle across the floor (Doom aims up and down by itself), then straight at its middle.
				Vector3 to = c.pos + (0, 0, c.height / 2) - at;
				double d = to.Length();
				if (d <= 0 || d > FragmentRange || d >= dist || abs(Actor.DeltaAngle(a, atan2(to.Y, to.X))) > turn) continue;
				if (TraceFrom(from, shooter, at, to.Unit(), d + c.radius) != c) continue;
				victim = c;
				hitPos = traceHit;
				dist = d;
				fdir = to.Unit();
				turned = true;
			}
			Streak(at, fdir, dist);
			Log(String.Format("fragment %s -> %s damage %d of %d%s", from ? from.GetClassName() : 'None', victim ? victim.GetClassName() : 'None', damage, hit, turned ? " turned" : ""));
			if (victim) Deal(DealFragment, victim, shooter, damage, type, hitPos, fdir);
			else Puff(hitPos, true);
		}
	}

	// What a player sees: a few fast sparks along a fragment's line, and a puff where a line ends on a wall (half size for
	// a fragment).
	static void Streak(Vector3 at, Vector3 dir, double dist)
	{
		FSpawnParticleParams p;
		p.color1 = "FFD070";
		p.style = STYLE_Add;
		p.flags = SPF_FULLBRIGHT;
		p.size = 3;
		p.startalpha = 1;
		double speed = 32;
		p.lifetime = max(1, int(dist / speed));
		p.fadestep = -1;
		p.vel = dir * speed;
		for (int i = 0; i < 3; i++)
		{
			p.pos = at + dir * (i * speed / 3);
			level.SpawnParticle(p);
		}
	}

	static void Puff(Vector3 at, bool fragment)
	{
		Actor.Spawn(fragment ? "DoomerfallFragmentPuff" : "BulletPuff", at);
	}
}

// A fragment's wall hit: Doom's bullet puff at half size, so it reads as weaker than a bullet.
class DoomerfallFragmentPuff : BulletPuff
{
	Default
	{
		Scale 0.5;
	}
}

// Carry-through and fragment lines: stop at walls (as a bullet, two-sided lines block only when flagged) and at live
// shootable actors other than the player and the enemy the line starts in.
class DoomerfallPistolTracer : LineTracer
{
	Actor skip, shooter;

	override ETraceStatus TraceCallback()
	{
		if (Results.HitType == TRACE_HitActor)
		{
			let a = Results.HitActor;
			if (a == skip || a == shooter || a.player || !a.bShootable || a.health <= 0) return TRACE_Skip;
		}
		return TRACE_Stop;
	}
}

// On the player while Daggerfall's character is loaded: the fire-rate multipliers, the bonus pool and faster reloads.
class DoomerfallPistolsPerks : Inventory
{
	double pool;
	Array<class<Weapon> > scoutGun;
	Array<int> scoutMult;
	int poolAmmo;      // the held pistol's ammo last tic: a drop is a shot, which spends the pool
	Weapon poolGun;
	Array<Actor> flying;    // projectiles carrying the pool their shot spent ...
	Array<int> flyingBonus; // ... this much (0 once a hit took it)
	Array<int> flyingIdle;  // tics since it stopped being a missile

	Weapon trackedGun;
	State lastState;
	int lastTics;
	bool reloading, readyLastTic;
	double cutCarry;
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
		pool = DoomerfallPistols.Rule(DoomerfallPistols.Pool);
	}

	int ScoutOf(class<Weapon> gun)
	{
		int i = scoutGun.Find(gun);
		if (i < scoutGun.Size()) return scoutMult[i];
		int m = DoomerfallPistols.ScoutOf(gun);
		scoutGun.Push(gun);
		scoutMult.Push(m);
		return m;
	}

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		// Active: source is the actor being hit. The player's own pistol hits on others only, not carry or fragments.
		if (passive || damage <= 0 || !owner || source == owner) return;
		let h = DoomerfallPistols(StaticEventHandler.Find("DoomerfallPistols"));
		if (!h || h.dealing != DoomerfallPistols.DealNone) return;
		let gun = DoomerfallPistols.FromGun(owner, inflictor);
		if (!gun) return;
		int scout = ScoutOf(gun);
		double m = DoomerfallPistols.Multiplier(scout);
		// A bullet (puff) or a projectile hitting inside the firing action takes the live pool. A projectile in flight takes
		// what its shot spent (once: its first hit), never the pool that refilled after it was fired.
		int bonus = 0;
		bool live = inflictor.bIsPuff || inflictor.GetAge() == 0;
		int k = live ? flying.Size() : flying.Find(inflictor);
		if (live) bonus = int(pool);
		else if (k < flying.Size()) { bonus = flyingBonus[k]; flyingBonus[k] = 0; }
		if (m == 1 && bonus <= 0) return;
		// The pool is flat, added after the multipliers (Deadeye does not multiply it, owner 2026-11-27).
		newdamage = max(1, int(round(damage * m))) + bonus;
		if (live) pool -= bonus;
		DoomerfallPistols.Log(String.Format("hit %s with %s: %d -> %d (x%.3f scout %d, pool +%d)", source ? source.GetClassName() : 'None',
			inflictor.GetClassName(), damage, newdamage, m, scout, bonus));
	}

	// Runs after the player's weapon frames moved this tic, so a frame entered this tic still has all its tics.
	override void DoEffect()
	{
		Super.DoEffect();
		int most = DoomerfallPistols.Rule(DoomerfallPistols.Pool);
		int ms = DoomerfallPistols.Rule(DoomerfallPistols.PoolRefillMs);
		// A shot from the held pistol (its ammo dropped) spends what its hits did not: a miss wastes the pool. This runs
		// after the weapon fired this tic, so a bullet's hit has already taken it.
		let held = owner && owner.player ? owner.player.ReadyWeapon : null;
		int ammoNow = DoomerfallPistols.IsPistol(held) ? AmmoNow(held) : 0;
		// A projectile pistol's shot carries what it spent to its first hit (CarryPool); a bullet that missed wastes it.
		for (int i = flying.Size() - 1; i >= 0; i--)
		{
			let f = flying[i];
			if (f && (f.bMissile || ++flyingIdle[i] < TICRATE) && flyingBonus[i] > 0) continue;
			flying.Delete(i); flyingBonus.Delete(i); flyingIdle.Delete(i);
		}
		if (held == poolGun && ammoNow < poolAmmo && pool >= 1)
		{
			let shot = CarryPool(int(pool));
			DoomerfallPistols.Log(String.Format("shot %s spent pool %d%s", held.GetClassName(), int(pool),
				shot ? " carried by " .. shot.GetClassName() : ""));
			pool = 0;
		}
		poolGun = DoomerfallPistols.IsPistol(held) ? held : null;
		poolAmmo = ammoNow;
		if (most <= 0) pool = 0;
		else if (pool < most) pool = min(most, pool + (ms > 0 ? most * 1000. / (ms * TICRATE) : most));

		let p = owner ? owner.player : null;
		let w = p ? p.ReadyWeapon : null;
		let psp = p ? p.FindPSprite(PSP_WEAPON) : null;
		int cut = DoomerfallPistols.Rule(DoomerfallPistols.ReloadBp);
		bool hasReload = w && w.FindState("Reload") != null;
		if (!psp || cut <= 0 || !hasReload || !DoomerfallPistols.IsPistol(w) || p.PendingWeapon != WP_NOCHANGE || w != trackedGun)
		{
			trackedGun = (psp && hasReload && DoomerfallPistols.IsPistol(w) && p.PendingWeapon == WP_NOCHANGE) ? w : null;
			reloading = false;
			readyLastTic = p && (p.WeaponState & WF_WEAPONREADY);
			lastState = psp ? psp.CurState : null;
			lastTics = psp ? psp.Tics : 0;
			lastAmmo = AmmoNow(w);
			return;
		}

		int ammo = AmmoNow(w);
		bool shot = ammo < lastAmmo;
		lastAmmo = ammo;
		bool entered = psp.CurState != lastState || psp.Tics > lastTics;
		bool magEmpty = w.AmmoType1 && w.AmmoType2 && owner.CountInv(w.AmmoType1) < w.AmmoUse1;
		bool wasReady = readyLastTic;
		readyLastTic = p.WeaponState & WF_WEAPONREADY;
		if (p.WeaponState & WF_WEAPONREADY) reloading = false;
		else if (shot)
		{
			// The frames after a shot are a reload only when DRLA's autoreload takes over after the magazine ran dry.
			let autoOption = CVar.GetCVar("DRLA_autoreload", p);
			reloading = magEmpty && autoOption && autoOption.GetBool();
			entered = false; // Not the frame that fired.
			cutCarry = 0;
		}
		else if (entered && (psp.CurState == w.FindState("Fire") || psp.CurState == w.FindState("Hold")))
			reloading = false;
		// A reload starts only as the gun leaves its ready state without firing: the reload key or a pull on an empty
		// magazine (DRLA's Fire goes to Reload).
		else if (!reloading && wasReady && ((p.cmd.buttons & BT_RELOAD) || magEmpty))
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
			DoomerfallPistols.Log(String.Format("reload %s frame %d -> %d tics", w.GetClassName(), before, psp.Tics));
		}
		lastState = psp.CurState;
		lastTics = psp.Tics;
	}

	// The projectile the player's pistol fired this tic, if any, takes the spent pool with it to its first hit (up to a
	// second after it stops flying: a delayed explosion still counts; a miss loses it).
	Actor CarryPool(int bonus)
	{
		let it = ThinkerIterator.Create("Actor", Thinker.STAT_DEFAULT);
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (!a.bMissile || a.target != owner || a.GetAge() > 0 || flying.Find(a) < flying.Size()) continue;
			flying.Push(a); flyingBonus.Push(bonus); flyingIdle.Push(0);
			return a;
		}
		return null;
	}

	int AmmoNow(Weapon w)
	{
		return (w && w.AmmoType1) ? owner.CountInv(w.AmmoType1) : 0;
	}
}
