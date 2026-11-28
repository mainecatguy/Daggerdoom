// Daggerfall attributes in Doom (owner, 2026-11-26; manual.md "Attributes"). Daggerfall owns the character sheet and
// sends its live attributes; the formulas are Doom's shared rules (DoomerfallRules.zs), and this item applies them:
//   - Strength: melee damage +0% at 0 to +100% at 100. Melee means attacks made with a weapon in the Melee skill or
//     the fists (Hand-to-Hand), as DoomerfallWeaponCategory files them. What decides it is the attack that dealt the
//     damage, not what is held when it lands (see MeleeAttack).
//   - Speed: movement speed, -25% at 0, normal at 50, +25% at 100.
//   - Agility: reloads and weapon switches run up to 40% faster (x1.4 animation speed at 100), and a chance to evade
//     damage entirely, up to 15% at 100.
// Values are capped at 100 and read live on every use, so a change on the sheet applies at once.
// Without a Daggerfall character the item is never given, so stock Doom and plain WADs are unchanged.

// The player's attribute effects. Inventory hooks compose with every other damage and speed modifier (DRLA's
// included) by multiplying.
class DoomerfallAttributeEffects : Inventory
{
	// meleeTic[t % HeldTics] == t when the owner held a melee weapon or fists at the end of tic t (level.totaltime, the clock GetAge counts).
	const HeldTics = 2048; // about a minute; a projectile older than that gets no bonus
	int meleeTic[HeldTics];
	double handlingCarry; // Agility: fractional extra weapon tics owed while reloading or switching

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
	// Agility: extra speed of reloads and weapon switches, 0 (normal) to 0.4 (x1.4), and the evade chance.
	static double HandlingBonus() { return DoomerfallRules.AgilityHandlingBonus(DoomerfallRules.Stat(DoomerfallRules.StatAgility)); }
	static double EvadeChance() { return DoomerfallRules.AgilityEvadeChance(DoomerfallRules.Stat(DoomerfallRules.StatAgility)); }

	static bool HoldsMelee(Actor mo)
	{
		if (!mo || !mo.player) return false;
		int c = DoomerfallWeaponCategory.Of(mo.player.ReadyWeapon);
		return c == DoomerfallWeaponCategory.Melee || c == DoomerfallWeaponCategory.Unarmed;
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

	// Whether this hit came from a melee or fist attack:
	//   - a hitscan or rail hit the owner is making now: Doom flags every P_LineAttack and P_RailAttack hit
	//     DMG_INFLICTOR_IS_PUFF, with a puff spawned this tic as the inflictor. Fists and chainsaws (A_Punch, A_Saw,
	//     A_CustomPunch) are hitscans; DRLA's Energysaw is a rail (A_RailAttack), whose puff on a bleeding monster
	//     is plain-Spawned without ISPUFF. The hit happens while the attack runs, so the weapon held now is the one
	//     attacking. The same goes for a puff's own effect on its first tic (an exploding melee puff);
	//   - a projectile, or its splash, including splash from its death frames after Doom clears MISSILE (the class
	//     default still has it): only if a melee weapon or the fists were held on the tic it was fired, so a rocket or
	//     plasma shot that lands after a switch to fists does not count. A hitscan a projectile makes credited to the
	//     owner (A_Explode's nails) is the projectile's: its puff's DamageSource is the projectile;
	//   - anything else credited to the player never counts: no inflictor, the player as inflictor (BFG tracers,
	//     A_BFGSpray, A_Explode in a weapon state), a barrel the player set off, a spawned explosion.
	bool MeleeAttack(Actor inflictor, int flags = 0)
	{
		if (!inflictor || inflictor == owner) return false;
		if (inflictor.bIsPuff && inflictor.DamageSource && inflictor.DamageSource != owner) inflictor = inflictor.DamageSource;
		else if (inflictor.GetAge() == 0 && ((flags & DMG_INFLICTOR_IS_PUFF) || inflictor.bIsPuff)) return HoldsMelee(owner);
		if (inflictor.bMissile || inflictor.default.bMissile) return HeldMeleeAt(level.totaltime - inflictor.GetAge());
		return false;
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

	// Offensive (Strength): damage the owner deals to something else with a melee attack. On the offensive call
	// P_DamageMobj passes the target as "source".
	// Defensive (Agility): the damage is evaded entirely (damage 0, so no pain, push or Daggerfall HP loss). The owner's
	// rule is "a chance to evade damage", so any damage counts, whoever or whatever deals it. Only Doom's
	// unstoppable damage is left alone: telefrags (which free a blocked teleport destination) and DMG_FORCED.
	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags, double angle)
	{
		if (passive)
		{
			if (damage <= 0 || (flags & DMG_FORCED) || damageType == 'Telefrag') return;
			double chance = EvadeChance();
			if (chance > 0 && Random[DoomerfallEvade](0, 9999) < chance * 10000) newdamage = 0;
			return;
		}
		if (damage <= 0 || source == owner || !MeleeAttack(inflictor, flags)) return;
		double f = StrengthMeleeFactor();
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
