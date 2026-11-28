// Daggerfall attributes in Doom (owner, 2026-11-26 and 2026-11-27; gamedesign/decisions/20261127-attribute-rework-owner.md;
// manual.md "Attributes"). Daggerfall owns the character sheet and sends its live attributes; the formulas are Doom's
// shared rules (DoomerfallRules.zs), and this item applies them:
//   - Strength: melee damage +1% per point (+0% at 0, double at 100). Shotguns, explosives and automatics: -20% at 0,
//     normal at 50, +20% at 100.
//   - Agility: every firearm -10% at 0, normal at 50, +10% at 100; rifles and pistols get another -10% to +10% on the
//     same line, added to the first (so -20% to +20%). Reloads and weapon switches run up to 40% faster (x1.4
//     animation speed at 100). The old dodge chance is gone (owner, 2026-11-27).
//   - Luck: a 5x super crit on the player's hits, 0% at 50 and below, +0.1% per point above (5% at 100). Each direct
//     hit (hitscan, rail, projectile impact, each pellet) rolls once; an explosion rolls once per blast, and a lucky
//     blast crits everything it hits. Damage over time (burns, dealt with DMG_DD_DEALT) never reaches ModifyDamage's
//     offensive call (p_interaction.cpp), so it never rolls. Luck's ammo drops are DoomerfallAmmo's.
//   - Speed: movement speed, -25% at 0, normal at 50, +25% at 100.
// Melee means attacks made with a weapon in the Melee skill or the fists (Hand-to-Hand); a firearm is any other weapon
// of the player's. The types are DoomerfallWeaponCategory's two categories (a weapon with two gets what each allows)
// and DoomerfallRifleTag's rifles. What decides is the attack that dealt the damage, not what is held when it lands
// (AttackKind). The factors multiply with each other and with every other damage modifier.
// Values are capped at 100 and read live on every use, so a change on the sheet applies at once.
// Without a Daggerfall character the item is never given, so stock Doom and plain WADs are unchanged.

class DoomerfallAttributeEffects : Inventory
{
	// meleeTic[t % HeldTics] == t when the owner held a melee weapon or fists at the end of tic t (level.totaltime, the clock GetAge counts).
	const HeldTics = 2048; // about a minute; a projectile older than that gets no bonus
	int meleeTic[HeldTics];
	double handlingCarry; // Agility: fractional extra weapon tics owed while reloading or switching

	// Luck's last blast: one roll per exploding actor per tic.
	Actor blastInflictor;
	int blastTic;
	bool blastLucky;

	Default
	{
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
		Inventory.MaxAmount 1;
	}

	// 1.0 for no change.
	static double StrengthMeleeFactor() { return DoomerfallRules.StrengthMeleeFactor(DoomerfallRules.Stat(DoomerfallRules.StatStrength)); }
	static double SpeedFactor() { return DoomerfallRules.SpeedFactor(DoomerfallRules.Stat(DoomerfallRules.StatSpeed)); }
	// Agility: extra speed of reloads and weapon switches, 0 (normal) to 0.4 (x1.4).
	static double HandlingBonus() { return DoomerfallRules.AgilityHandlingBonus(DoomerfallRules.Stat(DoomerfallRules.StatAgility)); }

	static bool IsMeleeCategory(int c)
	{
		return c == DoomerfallWeaponCategory.Melee || c == DoomerfallWeaponCategory.Unarmed;
	}

	static bool IsStrengthGunCategory(int c)
	{
		return c == DoomerfallWeaponCategory.Shotgun || c == DoomerfallWeaponCategory.Explosive || c == DoomerfallWeaponCategory.Automatic;
	}

	// Strength and Agility's factor for a hit of this kind by a weapon of these categories (first, second) and class.
	static double AttackFactor(int kind, int first, int second, class<Weapon> gun)
	{
		if (kind == AttackMelee) return StrengthMeleeFactor();
		if (kind != AttackGun) return 1.0;
		double f = 1.0;
		if (IsStrengthGunCategory(first) || IsStrengthGunCategory(second))
			f *= DoomerfallRules.StrengthGunFactor(DoomerfallRules.Stat(DoomerfallRules.StatStrength));
		bool rp = first == DoomerfallWeaponCategory.Pistol || second == DoomerfallWeaponCategory.Pistol || DoomerfallRifleTag.IsRifleClass(gun);
		f *= DoomerfallRules.AgilityGunFactor(DoomerfallRules.Stat(DoomerfallRules.StatAgility), rp);
		return f;
	}

	static bool HoldsMelee(Actor mo)
	{
		if (!mo || !mo.player) return false;
		return IsMeleeCategory(DoomerfallWeaponCategory.Of(mo.player.ReadyWeapon));
	}

	// Called once per tic by DoomerfallAttributes, after the players have acted.
	void RecordHeld()
	{
		int t = level.totaltime;
		meleeTic[t % HeldTics] = HoldsMelee(owner) ? t : -1;
	}

	bool HeldMeleeAt(int t)
	{
		return t > 0 && level.totaltime - t < HeldTics && meleeTic[t % HeldTics] == t;
	}

	enum EAttackKind { AttackNone, AttackMelee, AttackGun }

	static int KindOfCategory(int c)
	{
		return IsMeleeCategory(c) ? AttackMelee : AttackGun;
	}

	// What dealt this hit, decided by the attack, not by what is held when it lands, with the attacking weapon's two
	// categories and class (Other, Other, null when unknown). In order:
	//   - the player as inflictor: only a BFG ball's spray, which DoomerfallShots traces to the exploding ball's tag
	//     (A_BFGSpray); anything else (A_Explode in a weapon state) is neither;
	//   - Energy Weapons' perk splash is neither (it is already a share of a boosted hit);
	//   - a puff whose DamageSource is a shot (A_Explode's nails) stands for that shot;
	//   - a hitscan or rail hit the owner is making now: Doom flags every P_LineAttack and P_RailAttack hit
	//     DMG_INFLICTOR_IS_PUFF, with a puff spawned this tic as the inflictor. A rail's puff on a bleeding monster is
	//     plain-Spawned without ISPUFF (DRLA's Energysaw, laser rails), so the flag decides, not the puff's flag. The hit
	//     happens while the attack runs, so the weapon held now is the one attacking. The same goes for a puff's own
	//     effect on its first tic (an exploding puff). A puff dealing damage later is neither;
	//   - a shot DoomerfallShots tagged with the gun that fired it (every projectile a gun fires and everything it
	//     spawns, even after a switch): that gun's categories;
	//   - an untagged projectile or its splash (including death-frame splash after Doom clears MISSILE): melee only if
	//     a melee weapon or the fists were held on the tic it was fired; otherwise neither;
	//   - anything else (no inflictor, a barrel the player set off, a spawned explosion) is neither.
	int, int, int, class<Weapon> AttackKind(Actor inflictor, int flags = 0)
	{
		int no = DoomerfallWeaponCategory.Other;
		if (!inflictor || !owner || !owner.player) return AttackNone, no, no, null;
		DoomerfallShotTag tag = null;
		if (inflictor == owner)
		{
			class<Weapon> gun;
			int skill;
			if (!DoomerfallShots.Find(owner, inflictor, gun, skill, tag) || !tag) return AttackNone, no, no, null;
			return KindOfCategory(tag.category), tag.category, tag.second, tag.gun;
		}
		if (inflictor is "DoomerfallEnergySplash") return AttackNone, no, no, null;
		if (inflictor.bIsPuff && inflictor.DamageSource && inflictor.DamageSource != owner) inflictor = inflictor.DamageSource;
		else if (inflictor.GetAge() == 0 && ((flags & DMG_INFLICTOR_IS_PUFF) || inflictor.bIsPuff))
		{
			let w = owner.player.ReadyWeapon;
			if (!w) return AttackNone, no, no, null;
			int first, second;
			[first, second] = DoomerfallWeaponCategory.Both(w);
			return KindOfCategory(first), first, second, w.GetClass();
		}
		else if (inflictor.bIsPuff) return AttackNone, no, no, null;
		tag = DoomerfallShotTag.Of(inflictor);
		if (!tag && inflictor.GetAge() == 0) tag = DoomerfallShots.Tag(inflictor); // a point-blank hit before its spawn event
		if (tag && tag.shooter == owner) return KindOfCategory(tag.category), tag.category, tag.second, tag.gun;
		if ((inflictor.bMissile || inflictor.default.bMissile) && HeldMeleeAt(level.totaltime - inflictor.GetAge()))
			return AttackMelee, DoomerfallWeaponCategory.Melee, no, null;
		return AttackNone, no, no, null;
	}

	// Strength's melee hits.
	bool MeleeAttack(Actor inflictor, int flags = 0)
	{
		int kind = AttackKind(inflictor, flags);
		return kind == AttackMelee;
	}

	// A blast Luck may roll for: the exploding actor is in its Death, XDeath or Crash states (a shot exploding, as
	// ExplodeMissile puts it there). Lingering fire (DRLA's napalm and plasma ground fire) explodes again and again
	// from its Spawn loop, so it is damage over time and never rolls; nor do explosion actors that blast from Spawn.
	static bool ShotBlast(Actor a)
	{
		if (!a || !a.CurState) return false;
		return InSeq(a, a.FindState("Death")) || InSeq(a, a.FindState("XDeath")) || InSeq(a, a.FindState("Crash"));
	}

	static bool InSeq(Actor a, State s)
	{
		return s && a.InStateSequence(a.CurState, s);
	}

	// Luck: whether this hit is a super crit. An explosion (DMG_EXPLOSION, one P_RadiusAttack) rolls once per exploding
	// actor per tic, so all its targets share the roll.
	bool LuckyHit(Actor inflictor, int flags)
	{
		double chance = DoomerfallRules.LuckCritChance(DoomerfallRules.Stat(DoomerfallRules.StatLuck));
		if (chance <= 0) return false;
		if (flags & DMG_EXPLOSION)
		{
			if (!ShotBlast(inflictor)) return false; // ground fire and other lingering explosions: damage over time
			if (inflictor == blastInflictor && level.maptime == blastTic) return blastLucky;
			blastInflictor = inflictor;
			blastTic = level.maptime;
			blastLucky = Random[DoomerfallLuck](0, 9999) < chance * 10000;
			return blastLucky;
		}
		return Random[DoomerfallLuck](0, 9999) < chance * 10000;
	}

	// Reload states: DRLA names them Reload, ReloadWorking, ReloadFinish2, FancyReload, GrenadeReload, ZoomInReload and
	// so on. Ready loops that only allow or forbid reloading (ReadyReload, ReadyNoReload, NoReloadLoop) are not reloads.
	static bool IsReloadLabel(String label)
	{
		label = label.MakeLower();
		return label.IndexOf("reload") >= 0 && label.IndexOf("noreload") < 0 && label.IndexOf("ready") != 0;
	}

	// Weapon switch states: Select and Deselect (stock), SelectLoop, DeselectLoop, SelectSetWeapon (DRLA).
	static bool IsSwitchLabel(String label)
	{
		label = label.MakeLower();
		return label.IndexOf("select") == 0 || label.IndexOf("deselect") == 0;
	}

	// 1 reloading, 2 switching, 0 neither, judged from the label the weapon's current state sits under.
	static int Handling(PSprite psp)
	{
		if (!psp || !psp.CurState) return 0;
		String label = Actor.DD_StateLabel(psp.CurState);
		if (IsReloadLabel(label)) return 1;
		if (IsSwitchLabel(label)) return 2;
		return 0;
	}

	// One extra weapon tic, as PowerDoubleFiringSpeed does it (PSprite.Tick): a state with tics left loses one, a state
	// on its last tic moves on to the next one now, running its action (A_Raise and A_Lower included).
	static void ExtraTic(PSprite psp)
	{
		if (psp.Tics > 1) psp.Tics--;
		else if (psp.Tics == 1 && psp.Caller) psp.SetState(psp.CurState.NextState);
	}

	// Agility: reloads and weapon switches run faster.
	override void DoEffect()
	{
		Super.DoEffect();
		let p = owner ? owner.player : null;
		if (!p || p.mo != owner || owner.health <= 0 || !p.ReadyWeapon) { handlingCarry = 0; return; }
		let psp = p.FindPSprite(PSP_WEAPON);
		double bonus = HandlingBonus();
		if (bonus <= 0) { handlingCarry = 0; return; }
		if (!Handling(psp)) return; // the carry is kept, so short switches average out to the full bonus
		handlingCarry += bonus;
		if (handlingCarry < 1) return;
		handlingCarry -= 1;
		ExtraTic(psp);
	}

	override double GetSpeedFactor()
	{
		return SpeedFactor();
	}

	// Offensive only: damage the owner deals to something else. On the offensive call P_DamageMobj passes the target as
	// "source".
	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags, double angle)
	{
		if (passive || damage <= 0 || source == owner) return;
		int kind, first, second;
		class<Weapon> gun;
		[kind, first, second, gun] = AttackKind(inflictor, flags);
		if (kind == AttackNone) return;
		double f = AttackFactor(kind, first, second, gun);
		if (LuckyHit(inflictor, flags)) f *= DoomerfallRules.LuckCritFactor;
		if (f != 1.0) newdamage = max(1, int(damage * f));
	}
}

// Gives each player the effects item while Daggerfall has a character, and records each tic whether a melee weapon
// was held. Cheap: one native call and one inventory lookup per player per tic.
class DoomerfallAttributes : EventHandler
{
	override void WorldTick()
	{
		if (DoomerfallRules.Stat(DoomerfallRules.StatStrength) < 0) return;
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = players[i].mo;
			if (!playeringame[i] || !mo) continue;
			let fx = DoomerfallAttributeEffects(mo.FindInventory("DoomerfallAttributeEffects"));
			if (!fx)
			{
				mo.GiveInventory("DoomerfallAttributeEffects", 1);
				fx = DoomerfallAttributeEffects(mo.FindInventory("DoomerfallAttributeEffects"));
			}
			if (fx) fx.RecordHeld();
		}
	}
}
