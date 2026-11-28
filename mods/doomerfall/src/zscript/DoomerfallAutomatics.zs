// The Automatics skill in Doom (work/backlog/skills-in-doom.md, Automatics). Daggerfall sends the live skill in the
// character sheet; Doom's shared rules (DoomerfallRules.zs, Auto*) turn it into the numbers below, and this applies them
// to hits from a gun whose skill is Automatics (DoomerfallWeaponCategory.SkillSlotOf), stock Doom's Chaingun or a DRLA
// rapid-fire gun. Without a Daggerfall character every rule reads off, so a Doom-only game is unchanged.
//
//   damage bonus   every hit from the gun does +x% (0 to 60%).
//   burst fire     the first n shots of a burst do +x% more (multiplies with the damage bonus). The burst restarts once
//                  the gun has not fired for the reset time (0.3 s).
//   ammo saving    one ammo per n shots, or every n-th shot free: the gun spends its ammo as usual and Doom gives back
//                  the rounds it saved, to the ammo the gun fired from (stock: the reserve, which Doom then reports to
//                  Daggerfall as usual; DRLA: the loaded magazine). The every-n-th count restarts when the gun is lowered.
//   sunder         each hit makes the enemy take +x% damage from all sources, stacking to a cap, for good
//                  (DoomerfallSunder rides on the enemy).
//   bands          by the gun's own base tics between shots (DoomerfallAutomaticBands): slow and middle guns add flat
//                  damage to each bullet before every percentage bonus, and each bullet passes through more enemies
//                  (penetration); a fast gun has a chance per shot of one extra free bullet.
//   suppression    each hit slows the enemy's movement more, up to a cap, fading after the last hit
//                  (DoomerfallSuppress rides on the enemy).
//
// A shot is a tic in which the gun spent ammo while the trigger was down, or hit something while it was down; several
// pellets or bullets in one tic are one shot.
//
// Only hits from an Automatics gun count, not whatever the player happens to hold when a hit lands. The gun comes from
// the shot's tag (DoomerfallShots.zs):
//   bullets      hitscan damage comes with its puff as the inflictor and lands in the tic it is fired, so a puff hit
//                while an Automatics gun is held came from that gun.
//   projectiles  a projectile an Automatics gun fires carries a tag naming the gun, and the burst state of its shot;
//                its hit and its splash count when it lands, even after a weapon switch or a save and load. What it
//                spawns (explosions, fragments) carries the same tag, so counts too.
// Rockets, grenades, barrels, other guns' projectiles and untagged projectiles get nothing.
// Fractional damage rounds up with the chance of the fraction, so +1% on a 5-point bullet is worth +1% on average.
//
// Penetration: after a direct hit (not splash), the bullet goes on along its line from the enemy's far side and hits
// the next enemy behind it with the hit's full damage (its damage before the first enemy's own modifiers), as Pistols'
// carry-through does: dealt with DMG_NO_ENHANCE and no inflictor, so no bonus applies twice, in the next WorldTick.
// Such a hit still counts as the gun's hit for sunder and suppression.
//
// Extra bullet: when a fast-band gun fires a shot, a roll gives one more bullet in the same tic, costing no ammo. It is
// the shot's own first bullet again: a hitscan bullet repeats that LineAttack exactly as the gun made it (seen in
// WorldHitscanPreFired: its damage roll, damage type, puff, flags, range and offsets), so every bonus applies to it as
// to the others; a projectile is spawned again (its class sets its damage) with the shot's tag, burst state and band.
// Its spread mirrors the first bullet's about the gun's aim (the player's angle and the autoaimed pitch, BulletSlope,
// taken as the shot was fired): the same spread, by the gun's own symmetric scatter.
class DoomerfallAutomatics : StaticEventHandler
{
	const SkillAutomatics = DoomerfallRules.SkillAutomatics;
	const AutoDamageBp = DoomerfallRules.AutoDamageBp;
	const AutoBurstBp = DoomerfallRules.AutoBurstBp;
	const AutoBurstShots = DoomerfallRules.AutoBurstShots;
	const AutoBurstResetMs = DoomerfallRules.AutoBurstResetMs;
	const AutoShotsPerAmmo = DoomerfallRules.AutoShotsPerAmmo;
	const AutoSunderBp = DoomerfallRules.AutoSunderBp;
	const AutoSunderMaxBp = DoomerfallRules.AutoSunderMaxBp;
	const AutoFreeEvery = DoomerfallRules.AutoFreeEvery;
	const AutoSlowDamage = DoomerfallRules.AutoSlowDamage;
	const AutoSlowPen = DoomerfallRules.AutoSlowPen;
	const AutoMidDamage = DoomerfallRules.AutoMidDamage;
	const AutoMidPen = DoomerfallRules.AutoMidPen;
	const AutoFastExtraBp = DoomerfallRules.AutoFastExtraBp;
	const AutoSuppressBp = DoomerfallRules.AutoSuppressBp;
	const AutoSuppressMaxBp = DoomerfallRules.AutoSuppressMaxBp;
	const AutoSuppressFadeMs = DoomerfallRules.AutoSuppressFadeMs;

	const PenRange = 8192.;  // as far as a hitscan bullet
	const MaxSteps = 4096;   // safety stop for one tick's penetration chains

	// A perk rule's value (DoomerfallRules.Get: Doom applies the rule to Daggerfall's character sheet), 0 if off.
	clearscope static int Rule(int index)
	{
		return DoomerfallRules.Get(index);
	}

	clearscope static bool IsAutomatic(Weapon w)
	{
		return w && DoomerfallWeaponCategory.SkillSlotOf(w) == SkillAutomatics;
	}

	// The band rules (DoomerfallAutomaticBands.EBand): flat damage per bullet and extra enemies passed through.
	static int BandDamage(int band, out int pen)
	{
		pen = 0;
		if (band == DoomerfallAutomaticBands.BandSlow) { pen = Rule(AutoSlowPen); return Rule(AutoSlowDamage); }
		if (band == DoomerfallAutomaticBands.BandMiddle) { pen = Rule(AutoMidPen); return Rule(AutoMidDamage); }
		return 0;
	}

	// damage * factor, rounding the fraction up with its chance.
	static int Scale(double damage, double factor)
	{
		double x = damage * factor;
		int whole = int(x);
		if (frandom[DoomerfallAutomatics](0, 1) < x - whole) whole++;
		return max(1, whole);
	}

	// Perk log lines: always in the log, capped unless dd_perklog is on (tests).
	int logged;
	static void Log(String msg)
	{
		let h = DoomerfallAutomatics(StaticEventHandler.Find("DoomerfallAutomatics"));
		let all = CVar.FindCVar("dd_perklog");
		if (!h || (h.logged >= 200 && !(all && all.GetBool()))) return;
		h.logged++;
		DDLog.Debug(String.Format("automatics: %s", msg));
	}

	// Whether damage through this inflictor came from an Automatics gun of this player (DoomerfallShots.Find: the shot's
	// tag, or the held gun for a bullet), and if so whether it was a burst shot and the gun's band as it fired (a
	// projectile's tag keeps it; a bullet lands in the tic it is fired, so the gun's band now). For a bullet this also
	// counts the shot.
	static bool FromGun(Actor player, Actor inflictor, out bool burst, out class<Weapon> gun, out int band)
	{
		burst = false;
		gun = null;
		band = DoomerfallAutomaticBands.BandNone;
		let perks = player ? DoomerfallAutomaticsPerks(player.FindInventory("DoomerfallAutomaticsPerks")) : null;
		int skill;
		DoomerfallShotTag tag;
		if (!perks || !DoomerfallShots.Find(player, inflictor, gun, skill, tag) || skill != SkillAutomatics) return false;
		if (tag) MarkTag(tag, perks); // a point-blank hit lands before the shot's spawn event
		burst = tag ? tag.autoBurst : perks.MarkShot();
		band = tag && tag.burstSet ? tag.autoBand : DoomerfallAutomaticBands.BandOfGun(player, gun);
		return true;
	}

	// A shot the held Automatics gun just fired counts as a shot of the burst, and its tag (DoomerfallShots, which also
	// copies it to everything the shot spawns) remembers whether it was a burst shot.
	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		if (!m) return;
		// Projectiles only: a gun's helper actors (DRLA's recoil and reload effects) are not shots.
		if (!(m.bMissile || m.default.bMissile) || !m.target || !m.target.player || m.target.player.mo != m.target) return;
		let perks = DoomerfallAutomaticsPerks(m.target.FindInventory("DoomerfallAutomaticsPerks"));
		if (!perks || !perks.TriggerDown()) return;
		let tag = DoomerfallShots.Tag(m);
		if (tag && MarkTag(tag, perks))
		{
			Log(String.Format("projectile %s from %s", m.GetClassName(), tag.gun.GetClassName()));
			if (perks.shotMissileTic != level.maptime)
			{
				perks.shotMissile = m;
				perks.shotMissileTic = level.maptime;
				perks.ExtraBullet();
			}
		}
	}

	// A bullet a player fires from an Automatics gun, before it flies: the shot's first one is what an extra bullet
	// repeats. Never stops the bullet.
	override bool WorldHitscanPreFired(WorldEvent e)
	{
		let mo = e.Thing;
		if (!mo || !mo.player || mo.player.mo != mo || e.Damage <= 0 || (e.AttackLineFlags & LAF_NOINTERACT)) return false;
		let perks = DoomerfallAutomaticsPerks(mo.FindInventory("DoomerfallAutomaticsPerks"));
		if (perks && perks.TriggerDown() && IsAutomatic(mo.player.ReadyWeapon)) perks.NoteBullet(e);
		return false;
	}

	// Decides once whether a shot the held Automatics gun fired this tic is a burst shot, and counts it.
	static bool MarkTag(DoomerfallShotTag tag, DoomerfallAutomaticsPerks perks)
	{
		if (tag.burstSet || tag.generation != 0 || tag.fireTic != level.maptime || tag.skill != SkillAutomatics || !perks.TriggerDown()) return false;
		tag.burstSet = true;
		tag.autoBurst = perks.MarkShot();
		tag.autoBand = DoomerfallAutomaticBands.BandOfGun(perks.owner, tag.gun);
		return true;
	}

	override void WorldTick()
	{
		bool valid = DoomerfallRules.HasCharacter(); // Rules come from Daggerfall's character only.
		for (int i = 0; i < MAXPLAYERS && valid; i++)
		{
			let mo = playeringame[i] ? players[i].mo : null;
			if (!mo || mo.health <= 0) continue;
			if (!mo.FindInventory("DoomerfallAutomaticsPerks")) mo.GiveInventory("DoomerfallAutomaticsPerks", 1);
		}
		// Penetration hits queued since the last tick; each can queue the next.
		for (int i = 0; i < qFrom.Size() && i < MaxSteps; i++)
		{
			let shooter = qShooter[i];
			if (shooter && shooter.health > 0) Penetrate(qFrom[i], shooter, (qX[i], qY[i], qZ[i]), (qDX[i], qDY[i], 0), qDamage[i], qLeft[i], qType[i], qGun[i]);
		}
		ClearQueue();
	}

	override void WorldUnloaded(WorldEvent e)
	{
		ClearQueue();
	}

	// Penetration hits waiting for the next tick.
	Array<Actor> qFrom, qShooter;
	Array<double> qX, qY, qZ, qDX, qDY;
	Array<int> qDamage, qLeft;
	Array<Name> qType;
	Array<String> qGun;
	bool penetrating;          // while this handler deals a penetration hit
	class<Weapon> penGun;      // that hit's gun
	DoomerfallPistolTracer tracer;

	void ClearQueue()
	{
		qFrom.Clear(); qShooter.Clear(); qX.Clear(); qY.Clear(); qZ.Clear(); qDX.Clear(); qDY.Clear();
		qDamage.Clear(); qLeft.Clear(); qType.Clear(); qGun.Clear();
	}

	void Queue(Actor from, Actor shooter, Vector3 at, Vector2 dir, int damage, int left, Name type, class<Weapon> gun)
	{
		qFrom.Push(from); qShooter.Push(shooter);
		qX.Push(at.X); qY.Push(at.Y); qZ.Push(at.Z); qDX.Push(dir.X); qDY.Push(dir.Y);
		qDamage.Push(damage); qLeft.Push(left); qType.Push(type); qGun.Push(gun.GetClassName());
	}

	// The bullet goes on from the far side of the enemy it hit, to the next live shootable thing on its line.
	void Penetrate(Actor from, Actor shooter, Vector3 at, Vector3 dir, int damage, int left, Name type, String gunName)
	{
		if (!tracer) tracer = new("DoomerfallPistolTracer");
		tracer.skip = from;
		tracer.shooter = shooter;
		Actor next = null;
		Vector3 hitPos = at + dir * PenRange;
		if (tracer.Trace(at, level.PointInSector(at.XY), dir, PenRange, 0, Line.ML_BLOCKEVERYTHING | Line.ML_BLOCKHITSCAN))
		{
			hitPos = tracer.Results.HitPos;
			if (tracer.Results.HitType == TRACE_HitActor) next = tracer.Results.HitActor;
		}
		Log(String.Format("penetrate %s -> %s damage %d left %d", from ? from.GetClassName() : 'None', next ? next.GetClassName() : 'None', damage, left - 1));
		if (!next) { Actor.Spawn("BulletPuff", hitPos); return; }
		class<Weapon> gun = gunName;
		bool was = penetrating;
		class<Weapon> wasGun = penGun;
		penetrating = true;
		penGun = gun;
		penLeft = left - 1;
		penCarry = damage;
		penAt = hitPos;
		penDir = dir.XY;
		if (!next.bNoBlood) next.SpawnBlood(hitPos, atan2(-dir.Y, -dir.X), damage);
		next.DamageMobj(null, shooter, damage, type, DMG_THRUSTLESS | DMG_NO_ENHANCE);
		penetrating = was;
		penGun = wasGun;
	}
	int penLeft, penCarry;
	Vector3 penAt;
	Vector2 penDir;

	// After the hit, so a hit does not boost itself: sunder, suppression, and penetration.
	override void WorldThingDamaged(WorldEvent e)
	{
		let victim = e.Thing;
		let src = e.DamageSource;
		if (e.Damage <= 0 || !victim || victim.player || !src || !src.player || src.player.mo != src) return;
		bool burst;
		class<Weapon> gun;
		int left, band;
		if (penetrating) { gun = penGun; left = penLeft; }
		else if (!FromGun(src, e.Inflictor, burst, gun, band)) return; // Hits from an Automatics gun only.
		else if (e.DamageFlags & DMG_EXPLOSION) left = 0;              // Splash does not pass through anything.
		else BandDamage(band, left);

		if (left > 0 && gun)
		{
			// The bullet's line: on from the last penetration, a projectile's flight, or the shooter's eye to the puff.
			Vector3 at = victim.pos + (0, 0, victim.height / 2);
			Vector3 dir;
			let inf = e.Inflictor;
			if (penetrating) { dir = (penDir, 0); at.Z = penAt.Z; }
			else
			{
				Vector3 eye = src.pos + (0, 0, src.player.viewz - src.pos.z);
				if (inf && !inf.bIsPuff && inf.Vel.Length() > 0) dir = inf.Vel;
				else if (inf && inf.bIsPuff) dir = inf.pos - eye;
				else dir = at - eye;
				if (inf) at.Z = clamp(inf.pos.Z, victim.pos.Z, victim.pos.Z + victim.height);
			}
			// Level, as Doom aims, as Pistols' carry-through does.
			if (dir.XY.Length() > 0)
			{
				let perks = DoomerfallAutomaticsPerks(src.FindInventory("DoomerfallAutomaticsPerks"));
				int damage = penetrating ? penCarry : (perks ? perks.CarriedDamage(victim, e.Damage) : e.Damage);
				Queue(victim, src, at + (dir.XY.Unit() * victim.radius, 0), dir.XY.Unit(), damage, left, e.DamageType, gun);
			}
		}

		if (victim.health <= 0) return;
		Sunder(victim);
		Suppress(victim);
	}

	static void Sunder(Actor victim)
	{
		int step = Rule(AutoSunderBp), cap = Rule(AutoSunderMaxBp);
		if (step <= 0 || cap <= 0) return;
		let s = DoomerfallSunder(victim.FindInventory("DoomerfallSunder"));
		if (!s)
		{
			victim.GiveInventory("DoomerfallSunder", 1);
			s = DoomerfallSunder(victim.FindInventory("DoomerfallSunder"));
			if (!s) return;
		}
		int before = s.bp;
		s.bp = max(s.bp, min(s.bp + step, cap)); // A lower cap later never takes stacks away.
		if (s.bp != before) Log(String.Format("sunder %s %d -> %d bp", victim.GetClassName(), before, s.bp));
	}

	static void Suppress(Actor victim)
	{
		int step = Rule(AutoSuppressBp), cap = Rule(AutoSuppressMaxBp), fade = Rule(AutoSuppressFadeMs);
		if (step <= 0 || cap <= 0 || fade <= 0 || !victim.bIsMonster) return;
		let s = DoomerfallSuppress(victim.FindInventory("DoomerfallSuppress"));
		if (!s)
		{
			victim.GiveInventory("DoomerfallSuppress", 1);
			s = DoomerfallSuppress(victim.FindInventory("DoomerfallSuppress"));
			if (!s) return;
		}
		double before = s.Current();
		s.AddHit(step / 10000., cap / 10000., max(1, fade * TICRATE / 1000));
		Log(String.Format("suppress %s %.4f -> %.4f speed %.2f of %.2f", victim.GetClassName(), before, s.Current(), victim.Speed, s.baseSpeed));
	}
}

// On the player while Daggerfall's character is loaded: counts shots, saves ammo, adds the damage bonuses, and fires
// the fast band's extra bullets.
class DoomerfallAutomaticsPerks : Inventory
{
	Weapon trackedGun;
	class<Inventory> trackedAmmo;
	int lastCount;
	int burstShots;
	int lastShotTic;
	int unitsUsed, unitsPaid, unitsPer;
	int freeShots;              // shots since the gun was raised, for the every-n-th free shot

	// The fast band's extra bullet: what this tic's shot did.
	int rolledTic;
	int bulletTic;              // the shot's first bullet (LineAttack) this tic, as the gun fired it
	double bulletAngle, bulletPitch, bulletRange, bulletZ, bulletForward, bulletSide;
	int bulletDamage, bulletFlags;
	Name bulletType;
	class<Actor> bulletPuff;
	Vector2 bulletCenter;       // the gun's aim then: angle, autoaimed pitch
	Vector2 firedAim;           // MirrorMissile's result: the aim a projectile shot was fired along
	Actor shotMissile;
	int shotMissileTic;
	bool extra;                 // while firing an extra bullet

	// The last hit's damage after this gun's bonuses, before the enemy's own modifiers (penetration carries it on).
	Actor hitVictim;
	int hitDamage, hitTic;

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
		lastShotTic = -1000;
		rolledTic = bulletTic = shotMissileTic = hitTic = -1;
	}

	bool TriggerDown()
	{
		let p = owner ? owner.player : null;
		return p && (p.attackdown || ((p.cmd.buttons | p.oldbuttons) & (BT_ATTACK | BT_ALTATTACK)));
	}

	// One shot per tic; a gap longer than the reset time starts a new burst.
	void CountShot()
	{
		int now = level.maptime;
		if (now == lastShotTic) return;
		int resetTics = max(1, DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoBurstResetMs) * TICRATE / 1000);
		if (now - lastShotTic > resetTics) burstShots = 0;
		burstShots++;
		lastShotTic = now;
	}

	// Watches the ammo the held gun fires from (AmmoType1: stock reserve or DRLA magazine). Runs every tic and again
	// at each hit, and only acts on a change, so it never counts the same rounds twice.
	void Sync()
	{
		let p = owner ? owner.player : null;
		let w = p ? p.ReadyWeapon : null;
		if (!DoomerfallAutomatics.IsAutomatic(w) || !w.AmmoType1)
		{
			trackedGun = null;
			return;
		}
		let ammo = owner.FindInventory(w.AmmoType1);
		int count = ammo ? ammo.Amount : 0;
		if (w != trackedGun || w.AmmoType1 != trackedAmmo)
		{
			trackedGun = w;
			trackedAmmo = w.AmmoType1;
			lastCount = count;
			freeShots = 0; // the gun was (re)raised
			return;
		}
		if (count < lastCount && TriggerDown()) // Not a change-ammo unload, which happens with the trigger up.
		{
			CountShot();
			SaveAmmo(ammo, lastCount - count);
		}
		lastCount = ammo ? ammo.Amount : 0;
	}

	void SaveAmmo(Inventory ammo, int used)
	{
		int per = DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoShotsPerAmmo);
		if (per != unitsPer) unitsUsed = unitsPaid = 0; // A new rule starts a new count.
		unitsPer = per;
		if (per <= 1)
		{
			// Every n-th shot free (skill 25 until 50's one per 2 replaces it).
			int every = DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoFreeEvery);
			if (every <= 1) return;
			freeShots++;
			if (freeShots % every) return;
			ammo.Amount += used;
			DoomerfallAutomatics.Log(String.Format("ammo %s used %d refunded %d (shot %d, every %d free) now %d", ammo.GetClassName(), used, used, freeShots, every, ammo.Amount));
			return;
		}
		unitsUsed += used;
		int due = (unitsUsed + per - 1) / per; // The first shot of each group of n pays.
		int refund = clamp(used - (due - unitsPaid), 0, used);
		unitsPaid = due;
		if (unitsUsed >= per * 1000) { unitsUsed -= per * 1000; unitsPaid -= 1000; }
		if (refund <= 0) return;
		ammo.Amount += refund; // At most what was just spent, so never above what the gun held.
		DoomerfallAutomatics.Log(String.Format("ammo %s used %d refunded %d (1 per %d) now %d", ammo.GetClassName(), used, refund, per, ammo.Amount));
	}

	// A shot of the held Automatics gun this tic (a bullet hit or a fired projectile): counts it if the trigger is down
	// and says whether it is one of the burst's first n shots.
	bool MarkShot()
	{
		Sync();
		if (TriggerDown()) CountShot();
		int n = DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoBurstShots);
		return n > 0 && lastShotTic == level.maptime && burstShots <= n;
	}

	void NoteBullet(WorldEvent e)
	{
		if (extra || bulletTic == level.maptime) return;
		bulletTic = level.maptime;
		bulletAngle = e.AttackAngle;
		bulletPitch = e.AttackPitch;
		bulletRange = e.AttackDistance;
		bulletDamage = e.Damage;
		bulletType = e.DamageType;
		bulletPuff = e.AttackPuffType;
		bulletFlags = e.AttackLineFlags;
		bulletZ = e.AttackZ;
		bulletForward = e.AttackOffsetForward;
		bulletSide = e.AttackOffsetSide;
		bulletCenter = (owner.angle, owner.BulletSlope()); // as A_FireBullets aims, before its spread
	}

	override void DoEffect()
	{
		Super.DoEffect();
		Sync();
		if (bulletTic == level.maptime) ExtraBullet(); // a projectile shot rolls at its spawn event (WorldThingSpawned)
	}

	// The damage a hit on this victim had after this gun's bonuses, before the victim's own modifiers.
	int CarriedDamage(Actor victim, int dealt)
	{
		return victim == hitVictim && hitTic == level.maptime ? hitDamage : dealt;
	}

	// The player's damage multipliers that come before ModifyDamage (P_DamageMobj: DamageMultiply, then Daggerfall's
	// damage bonus), so a flat bonus added here scales as if it were base damage.
	double EarlyFactor()
	{
		return owner.DamageMultiply * (1 + Actor.DD_DamageBonusBp() / 10000.);
	}

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		// Active: source is the actor being hit. The player's own hits on others only.
		if (passive || damage <= 0 || !owner || !owner.player || source == owner) return;
		bool burst;
		class<Weapon> gun;
		int band;
		if (!DoomerfallAutomatics.FromGun(owner, inflictor, burst, gun, band)) return; // Hits from an Automatics gun only.
		double early = EarlyFactor();
		int pen;
		int flat = DoomerfallAutomatics.BandDamage(band, pen);
		double factor = 1 + DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoDamageBp) / 10000.;
		if (burst) factor *= 1 + DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoBurstBp) / 10000.;
		if (factor != 1 || flat > 0)
		{
			newdamage = DoomerfallAutomatics.Scale(damage + flat * early, factor);
			DoomerfallAutomatics.Log(String.Format("hit %s with %s shot %d%s: %d -> %d (x%.4f) tic %d by %s flat %d%s", source ? source.GetClassName() : 'None',
				gun.GetClassName(), burstShots, burst ? " burst" : "", damage, newdamage, factor, level.maptime, inflictor.GetClassName(), flat, extra ? " extra" : ""));
		}
		hitVictim = source;
		hitDamage = newdamage;
		hitTic = level.maptime;
	}

	// The aim the engine gives a player's missile fired from this input angle (P_SpawnPlayerMissile, p_mobj.cpp): autoaim
	// tries the angle, then 5.625 degrees right and left, and takes the first that finds a target, with the pitch to it;
	// with free aim (autoaim 0.5 or less and freelook) only the angle itself. Returns whether it found a target; if not,
	// the input angle and the view pitch (0 without freelook).
	bool MissileAim(class<Actor> type, double input, out double an, out double pt)
	{
		static const double diffs[] = { 0, 5.625, -5.625 };
		let d = GetDefaultByType(type);
		double range = d && d.MaxTargetRange > 0 ? d.MaxTargetRange * 64 : 1024;
		bool freeaim = level.IsFreelookAllowed() && owner.player.GetAutoaim() <= 0.5;
		FTranslatedLineTarget t;
		for (int i = 0; i < 3; i++)
		{
			an = input + diffs[i];
			pt = owner.AimLineAttack(an, range, t, 0);
			if (t.linetarget) return true;
			if (freeaim) break;
		}
		an = input;
		if (!level.IsFreelookAllowed()) pt = 0;
		return false;
	}

	// The direction of a projectile shot's extra copy: the shot's own direction (yaw, pitch) mirrored about the aim the
	// engine fired it along, so its spread is the gun's own. That aim depends on how the gun fired (A_FireProjectile):
	//   no autoaim     (the weapon's NOAUTOAIM, a no-autoaim call, or autoaim found nothing): the player's angle and view
	//                  pitch; the call's angle and pitch spread are around them.
	//   autoaim        the engine's aim from the player's angle; the angle spread is added after it, the pitch is the
	//                  target's.
	//   aim at angle   (FPF_AIMATANGLE) autoaim from the player's angle plus the spread: the extra is aimed by the
	//                  engine from the player's angle minus that spread.
	// A no-autoaim call is told apart from autoaim by the pitch: autoaim's is exactly the pitch to its target.
	// The aim found is left in firedAim (the VM cannot pass a vector as an out parameter).
	String MirrorMissile(class<Actor> type, double yaw, double pitch, out double na, out double np)
	{
		static const double diffs[] = { 0, 5.625, -5.625 };
		let w = owner.player.ReadyWeapon;
		double an0, p0;
		Vector2 aim = (owner.angle, owner.pitch);
		String how = "no autoaim";
		if (!(w && w.bNoAutoaim))
		{
			if (!MissileAim(type, owner.angle, an0, p0)) how = "no target";
			else if (abs(Actor.DeltaAngle(p0, pitch)) < 0.01)
			{
				aim = (an0, p0);
				how = "autoaim";
			}
			else
			{
				for (int i = 0; i < 3; i++)
				{
					double th = yaw - diffs[i], a2, p2;
					if (!MissileAim(type, th, a2, p2) || abs(Actor.DeltaAngle(a2, yaw)) > 0.01 || abs(Actor.DeltaAngle(p2, pitch)) > 0.01) continue;
					double th2 = owner.angle - Actor.DeltaAngle(owner.angle, th);
					if (!MissileAim(type, th2, na, np)) { na = th2; np = owner.pitch; }
					firedAim = (owner.angle, p0);
					return "aim at angle";
				}
			}
		}
		firedAim = aim;
		na = aim.X - Actor.DeltaAngle(aim.X, yaw);
		np = 2 * aim.Y - pitch;
		return how;
	}

	// The fast band: once per shot, a chance of one more bullet, free. A hitscan shot rolls in the player's DoEffect,
	// after the gun fired (its first bullet is known by then). A projectile shot rolls at the first projectile's spawn
	// event: the engine sends it when the projectile first thinks (OF_JustSpawned, PostBeginPlay), after the player's
	// DoEffect and before the projectile moves.
	void ExtraBullet()
	{
		int now = level.maptime;
		if (lastShotTic != now || rolledTic == now || !TriggerDown()) return;
		rolledTic = now;
		let w = owner.player.ReadyWeapon;
		int chance = DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoFastExtraBp);
		if (chance <= 0 || !w || DoomerfallAutomaticBands.BandOf(w) != DoomerfallAutomaticBands.BandFast) return;
		if (Random[DoomerfallAutomatics](0, 9999) >= chance) return;

		extra = true;
		if (shotMissileTic == now && shotMissile)
		{
			// A projectile shot: the same projectile again, its direction mirrored about the aim it was fired along.
			let m = shotMissile;
			double speed = m.Vel.Length();
			double ma = speed > 0 ? atan2(m.Vel.Y, m.Vel.X) : m.angle;
			double mp = speed > 0 ? -atan2(m.Vel.Z, m.Vel.XY.Length()) : m.pitch;
			double na, np;
			String how = MirrorMissile(m.GetClass(), ma, mp, na, np);
			Vector2 aim = firedAim;
			let c = Actor.Spawn(m.GetClass(), m.pos, NO_REPLACE);
			if (c)
			{
				c.target = owner;
				c.tracer = m.tracer;
				c.angle = na;
				c.pitch = np;
				c.Vel = (cos(na) * cos(np), sin(na) * cos(np), -sin(np)) * speed;
				let mt = DoomerfallShotTag.Of(m), ct = DoomerfallShots.Tag(c);
				if (ct && mt) { ct.burstSet = true; ct.autoBurst = mt.autoBurst; ct.autoBand = mt.autoBand; }
				DoomerfallAutomatics.Log(String.Format("extra projectile %s from %s angle %.3f pitch %.3f (first %.3f %.3f, aim %.3f %.3f, %s) tic %d",
					c.GetClassName(), w.GetClassName(), na, np, ma, mp, aim.X, aim.Y, how, now));
				if (c.bMissile) c.CheckMissileSpawn(owner.radius);
			}
		}
		else if (bulletTic == now)
		{
			// A hitscan shot: the first bullet's LineAttack again, as the gun made it, its spread mirrored about the aim.
			double na = bulletCenter.X - Actor.DeltaAngle(bulletCenter.X, bulletAngle);
			double np = 2 * bulletCenter.Y - bulletPitch;
			FTranslatedLineTarget t;
			owner.LineAttack(na, bulletRange, np, bulletDamage, bulletType, bulletPuff, bulletFlags, t, bulletZ, bulletForward, bulletSide);
			DoomerfallAutomatics.Log(String.Format("extra bullet from %s damage %d type %s puff %s flags %d angle %.3f pitch %.3f (first %.3f %.3f, aim %.3f %.3f) tic %d",
				w.GetClassName(), bulletDamage, bulletType, bulletPuff ? bulletPuff.GetClassName() : 'None', bulletFlags, na, np, bulletAngle, bulletPitch, bulletCenter.X, bulletCenter.Y, now));
		}
		extra = false;
	}
}

// Rides on an enemy hit by an Automatics gun with the 75 perk: it takes bp/10000 more damage from every source, for
// good. Doom saves keep it with the enemy.
class DoomerfallSunder : Inventory
{
	int bp;

	Default
	{
		Inventory.MaxAmount 1;
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
	}

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		if (!passive || damage <= 0 || bp <= 0) return;
		newdamage = DoomerfallAutomatics.Scale(damage, 1 + bp / 10000.);
	}
}

// Rides on an enemy hit by an Automatics gun with the 75 perk: its movement speed (Speed, which A_Chase steps by; its
// attacks are untouched) is slowed by a fraction that fades evenly to nothing over fadeTics after the last hit. A new
// hit adds to what is left, up to the cap. If the enemy changes its own speed meanwhile, that becomes the base. Gone,
// with the speed restored, once the slow has faded.
class DoomerfallSuppress : Inventory
{
	double slow;          // the slow just after the last hit
	int hitTic, fadeTics;
	double baseSpeed, setSpeed;
	bool applied;

	Default
	{
		Inventory.MaxAmount 1;
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
	}

	double Current()
	{
		if (fadeTics <= 0) return 0;
		return slow * max(0., 1. - (level.maptime - hitTic) / double(fadeTics));
	}

	void AddHit(double step, double cap, int fade)
	{
		slow = max(Current(), min(Current() + step, cap));
		hitTic = level.maptime;
		fadeTics = fade;
		Apply();
	}

	void Apply()
	{
		if (!owner) return;
		if (!applied || owner.Speed != setSpeed) baseSpeed = owner.Speed;
		applied = true;
		double c = Current();
		if (c <= 0)
		{
			owner.Speed = baseSpeed;
			Destroy();
			return;
		}
		setSpeed = baseSpeed * (1 - c);
		owner.Speed = setSpeed;
	}

	override void DoEffect()
	{
		Super.DoEffect();
		Apply();
	}
}
