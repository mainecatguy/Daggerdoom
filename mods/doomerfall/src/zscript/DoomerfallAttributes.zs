// Daggerfall attributes in Doom (owner, 2026-11-26; manual.md "Attributes"). Daggerfall owns the character sheet and
// sends its live attributes (Actor.DD_SheetStat, -1 without a Daggerfall character); Doom applies them here:
//   - Strength: melee damage +0% at 0 to +100% at 100. Melee means attacks made with a weapon in the Melee skill or
//     the fists (Hand-to-Hand), as DoomerfallWeaponCategory files them. What decides it is the attack that dealt the
//     damage, not what is held when it lands (see MeleeAttack).
//   - Speed: movement speed, -25% at 0, normal at 50, +25% at 100.
// Values are clamped to 0..100 and read live on every use, so a change on the sheet applies at once.
// Without a Daggerfall character the item is never given, so stock Doom and plain WADs are unchanged.

// The player's attribute effects. Inventory hooks compose with every other damage and speed modifier (DRLA's
// included) by multiplying.
class DoomerfallAttributeEffects : Inventory
{
	// meleeTic[t % HeldTics] == t when the owner held a melee weapon or fists at the end of tic t (level.totaltime, the clock GetAge counts).
	const HeldTics = 2048; // about a minute; a projectile older than that gets no bonus
	int meleeTic[HeldTics];

	Default
	{
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
		Inventory.MaxAmount 1;
	}

	// A live attribute as 0..100, or -1 without a Daggerfall character.
	static int Live(int stat)
	{
		int v = Actor.DD_SheetStat(stat);
		return v < 0 ? -1 : min(v, 100);
	}

	// 1.0 for no change.
	static double StrengthMeleeFactor()
	{
		int v = Live(0);
		return v < 0 ? 1.0 : 1.0 + v / 100.0;
	}

	static double SpeedFactor()
	{
		int v = Live(6);
		return v < 0 ? 1.0 : 0.75 + v / 200.0;
	}

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
	//   - the owner hit directly (A_Punch-style damage with the player as inflictor), or through a puff a hitscan
	//     attack spawned this tic (fist and chainsaw hits): both happen while the attack runs, so the weapon held
	//     now is the one attacking;
	//   - a projectile, or the splash of one (its inflictor is the projectile): only if a melee weapon or the fists
	//     were held on the tic it was fired, so a rocket or plasma shot that lands after a switch to fists does not count;
	//   - anything else credited to the player (a barrel the player set off, a spawned explosion): never.
	bool MeleeAttack(Actor inflictor)
	{
		if (!inflictor || inflictor == owner) return HoldsMelee(owner);
		if (inflictor.bIsPuff && inflictor.GetAge() == 0) return HoldsMelee(owner);
		if (inflictor.bMissile) return HeldMeleeAt(level.totaltime - inflictor.GetAge());
		return false;
	}

	override double GetSpeedFactor()
	{
		return SpeedFactor();
	}

	// Offensive only: damage the owner deals to something else with a melee attack. On the offensive call
	// P_DamageMobj passes the target as "source".
	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags, double angle)
	{
		if (passive || damage <= 0 || source == owner || !MeleeAttack(inflictor)) return;
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
		if (Actor.DD_SheetStat(0) < 0) return;
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
