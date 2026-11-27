// The Automatics skill in Doom (work/backlog/skills-in-doom.md, Automatics). Daggerfall decides the rules from the
// live skill and sends them in the character sheet (DFB_SHEET_AUTO_*, DoomerfallAutomaticsRules.cs); Doom applies them
// to hits from a gun whose skill is Automatics (DoomerfallWeaponCategory.SkillSlotOf), stock Doom's Chaingun or a DRLA
// rapid-fire gun. Without a Daggerfall character every rule reads off, so a Doom-only game is unchanged.
//
//   damage bonus   every hit from the gun does +x% (0 to 60%).
//   burst fire     the first n shots of a burst do +x% more (multiplies with the damage bonus). The burst restarts once
//                  the gun has not fired for the reset time (0.3 s).
//   ammo saving    one ammo per n shots: the gun spends its ammo as usual and Doom gives back the rounds it saved, to
//                  the ammo the gun fired from (stock: the reserve, which Doom then reports to Daggerfall as usual;
//                  DRLA: the loaded magazine).
//   sunder         each hit makes the enemy take +x% damage from all sources, stacking to a cap, for good
//                  (DoomerfallSunder rides on the enemy).
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
class DoomerfallAutomatics : StaticEventHandler
{
	// DFB_SHEET_* indices; must match bridge/doomerfall_bridge.h.
	const SheetValid = 2;
	const SkillAutomatics = 5;
	const AutoDamageBp = 155;
	const AutoBurstBp = 156;
	const AutoBurstShots = 157;
	const AutoBurstResetMs = 158;
	const AutoShotsPerAmmo = 159;
	const AutoSunderBp = 160;
	const AutoSunderMaxBp = 161;

	// A rule's value from Daggerfall, or 0 without a character.
	clearscope static int Rule(int index)
	{
		return max(0, Actor.DD_SheetValue(index));
	}

	clearscope static bool IsAutomatic(Weapon w)
	{
		return w && DoomerfallWeaponCategory.SkillSlotOf(w) == SkillAutomatics;
	}

	// damage * factor, rounding the fraction up with its chance.
	static int Scale(int damage, double factor)
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
	// tag, or the held gun for a bullet), and if so whether it was a burst shot. For a bullet this also counts the shot.
	static bool FromGun(Actor player, Actor inflictor, out bool burst, out Name gun)
	{
		burst = false;
		gun = 'None';
		let perks = player ? DoomerfallAutomaticsPerks(player.FindInventory("DoomerfallAutomaticsPerks")) : null;
		class<Weapon> wc;
		int skill;
		DoomerfallShotTag tag;
		if (!perks || !DoomerfallShots.Find(player, inflictor, wc, skill, tag) || skill != SkillAutomatics) return false;
		gun = wc.GetClassName();
		burst = tag ? tag.autoBurst : perks.MarkShot();
		return true;
	}

	// A shot the held Automatics gun just fired counts as a shot of the burst, and its tag (DoomerfallShots, which also
	// copies it to everything the shot spawns) remembers whether it was a burst shot.
	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		// Projectiles only: a gun's helper actors (DRLA's recoil and reload effects) are not shots.
		if (!m || !m.bMissile || !m.target || !m.target.player || m.target.player.mo != m.target) return;
		let perks = DoomerfallAutomaticsPerks(m.target.FindInventory("DoomerfallAutomaticsPerks"));
		if (!perks || !perks.TriggerDown()) return;
		let tag = DoomerfallShots.Tag(m);
		if (!tag || tag.generation != 0 || tag.fireTic != level.maptime || tag.skill != SkillAutomatics) return;
		tag.autoBurst = perks.MarkShot();
		Log(String.Format("projectile %s from %s", m.GetClassName(), tag.gun.GetClassName()));
	}

	override void WorldTick()
	{
		if (Actor.DD_SheetValue(SheetValid) != 1) return; // Rules come from Daggerfall's character only.
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = playeringame[i] ? players[i].mo : null;
			if (mo && mo.health > 0 && !mo.FindInventory("DoomerfallAutomaticsPerks")) mo.GiveInventory("DoomerfallAutomaticsPerks", 1);
		}
	}

	// Sunder: after the hit, so a hit does not boost itself.
	override void WorldThingDamaged(WorldEvent e)
	{
		let victim = e.Thing;
		let src = e.DamageSource;
		if (e.Damage <= 0 || !victim || victim.player || victim.health <= 0 || !src || !src.player || src.player.mo != src) return;
		int step = Rule(AutoSunderBp), cap = Rule(AutoSunderMaxBp);
		if (step <= 0 || cap <= 0) return;
		bool burst;
		Name gun;
		if (!FromGun(src, e.Inflictor, burst, gun)) return; // Hits from an Automatics gun only.
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
}

// On the player while Daggerfall's character is loaded: counts shots, saves ammo, and adds the damage bonuses.
class DoomerfallAutomaticsPerks : Inventory
{
	Weapon trackedGun;
	class<Inventory> trackedAmmo;
	int lastCount;
	int burstShots;
	int lastShotTic;
	int unitsUsed, unitsPaid, unitsPer;

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
		if (per <= 1) return;
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

	override void DoEffect()
	{
		Super.DoEffect();
		Sync();
	}

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		// Active: source is the actor being hit. The player's own hits on others only.
		if (passive || damage <= 0 || !owner || !owner.player || source == owner) return;
		bool burst;
		Name gun;
		if (!DoomerfallAutomatics.FromGun(owner, inflictor, burst, gun)) return; // Hits from an Automatics gun only.
		double factor = 1 + DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoDamageBp) / 10000.;
		if (burst) factor *= 1 + DoomerfallAutomatics.Rule(DoomerfallAutomatics.AutoBurstBp) / 10000.;
		if (factor == 1) return;
		newdamage = DoomerfallAutomatics.Scale(damage, factor);
		DoomerfallAutomatics.Log(String.Format("hit %s with %s shot %d%s: %d -> %d (x%.4f) tic %d by %s", source ? source.GetClassName() : 'None',
			gun, burstShots, burst ? " burst" : "", damage, newdamage, factor, level.maptime, inflictor.GetClassName()));
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
