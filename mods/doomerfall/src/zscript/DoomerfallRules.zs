// The one place where Doom applies Daggerfall's rules to Daggerfall's character sheet (owner, 2026-11-27, Q&A item 45:
// "daggerfall transfer its character sheet to Doom and allow Doom to apply the rules based on that character sheet";
// architecture.md, "Character sheet and rules").
//
// In:  the character sheet Daggerfall sends over the bridge (bridge/doomerfall_bridge.h DFB_SHEET_*), read through
//      Actor.DD_SheetStat / DD_SheetSkill / DD_SheetSkillBase / DD_SheetValue. Each reads -1 without a Daggerfall
//      character, and then every rule here reads "no change", so stock Doom and plain WADs are unchanged.
// Out: rule values and factors. The systems that act on them (DoomerfallAttributes.zs, DoomerfallJump.zs and the gun
//      skill perks DoomerfallAutomatics.zs, DoomerfallExplosives.zs, DoomerfallShotguns.zs, DoomerfallEnergy.zs) hold
//      no rule numbers of their own.
//
// A new perk or attribute adds its formula here, reading the sheet value it depends on, and its system asks for it.
// Daggerfall's own moddable formulas (FormulaHelper, for example the climbing chances) stay in Daggerfall, which sends
// their results in the sheet, so formula mods keep working.
class DoomerfallRules : StaticEventHandler
{
	// Character sheet: DFB_SHEET_VALID, DFCareer.Stats, DFCareer.Skills (bridge/doomerfall_bridge.h).
	const SheetValid = 2;
	const StatStrength = 0;
	const StatAgility = 3;
	const StatSpeed = 6;
	const StatLuck = 7;
	const SkillJumping = 3;
	const SkillShotguns = 4;
	const SkillAutomatics = 5;
	const SkillExplosives = 6;
	const SkillEnergy = 9;

	// ---- Sheet reads ----

	// Whether the sheet describes Daggerfall's current, fully loaded character.
	clearscope static bool HasCharacter() { return Actor.DD_SheetValue(SheetValid) == 1; }

	// A live attribute capped at 100, or -1 without a Daggerfall character.
	clearscope static int Stat(int stat)
	{
		int v = Actor.DD_SheetStat(stat);
		return v < 0 ? -1 : min(v, 100);
	}

	// ---- Attributes (owner, 2026-11-26; manual.md "Attributes"). Each takes Stat(): 0..100, or -1 (no change). ----

	// Strength: melee damage +0% at 0 to +100% at 100.
	clearscope static double StrengthMeleeFactor(int v) { return v < 0 ? 1.0 : 1.0 + v / 100.0; }
	// Speed: movement -25% at 0, normal at 50, +25% at 100.
	clearscope static double SpeedFactor(int v) { return v < 0 ? 1.0 : 0.75 + v / 200.0; }
	// Agility: reloads and weapon switches up to 40% faster (0 to 0.4 extra speed), and a chance to evade damage
	// entirely, up to 15%. Linear from 0 at Agility 0.
	const AgilityMaxHandling = 0.40;
	const AgilityMaxEvade = 0.15;
	clearscope static double AgilityHandlingBonus(int v) { return v <= 0 ? 0.0 : AgilityMaxHandling * v / 100.0; }
	clearscope static double AgilityEvadeChance(int v) { return v <= 0 ? 0.0 : AgilityMaxEvade * v / 100.0; }
	// Luck (owner, 2026-11-27): each monster death drops ammo with a Luck / 2 percent chance (0% to 50%; above 100
	// counts as 100). roll is 0..1 (DoomerfallAmmoTiers hashes it from the monster's loot seed).
	clearscope static bool LuckAmmoDrop(int luck, double roll) { return luck > 0 && roll * 200 < min(luck, 100); }

	// ---- Jumping skill and falling damage (work/backlog/skills-in-doom.md; the skillperks jumping card) ----
	// The Jumping value is the permanent (base) skill, which perks follow (DD_SheetSkillBase).

	// Jump height multiplier: +1% per point to +100% at 100, plus 25% from 25 on.
	clearscope static double JumpHeightFactor(int s)
	{
		s = clamp(s, 0, 100);
		return 1.0 + s / 100.0 + (s >= 25 ? 0.25 : 0.0);
	}
	// Extra jumps in mid-air: one at 50, two at 100.
	clearscope static int AirJumps(int s) { return s >= 100 ? 2 : s >= 50 ? 1 : 0; }
	// No falling damage from 75. Below 75 Jumping does not reduce it (the owner has not chosen a curve yet).
	clearscope static bool FallImmune(int s) { return s >= 75; }

	// Daggerfall's falling damage (PlayerHealth.ApplyPlayerFallDamage): every metre past 5 costs 5 HP.
	const UnitsPerMetre = 30.0;    // Doom maps are Daggerfall's layout at 75%, and Daggerfall has 40 units per metre
	const FallThreshold = 5.0;     // metres of fall that do no damage
	const FallHPPerMetre = 5.0;    // HP per metre past the threshold
	clearscope static int FallDamage(double units)
	{
		double metres = units / UnitsPerMetre;
		return metres > FallThreshold ? int(FallHPPerMetre * (metres - FallThreshold)) : 0;
	}

	// ---- Gun skill perks (work/backlog/skills-in-doom.md and the perks cards), from the live skill, so a drained or
	// fortified skill counts, as the gun's skill choice does (DoomerfallWeaponCategory.SkillSlotOf). Get(rule) is a
	// rule's value, 0 meaning off; damage and other bonuses are in 1/10000ths (bp). ----
	enum ERule
	{
		// Automatics
		AutoDamageBp,        // damage bonus, +0% to +60% by skill
		AutoBurstBp,         // 25: burst fire, this much more damage ...
		AutoBurstShots,      // ... on the first this many shots of a burst ...
		AutoBurstResetMs,    // ... which restarts this long after the last shot
		AutoShotsPerAmmo,    // one ammo per this many shots: 2 at 50, 4 at 100; 1 or 0 is normal use
		AutoSunderBp,        // 75: each hit makes the enemy take this much more damage from all sources ...
		AutoSunderMaxBp,     // ... permanently, up to this much
		// Explosives
		ExplDamageBp,        // damage bonus, +0% to +60% by skill
		ExplSelfCutBp,       // the player's own splash damage is cut by this much: 95% at 25, 99% at 75
		ExplDirectBp,        // 50: more damage to the enemy a shot hits directly (amount open, so 0)
		ExplChainBp,         // 100: an enemy the explosives kill explodes for this much of its maximum health ...
		ExplChainRadius,     // ... in this radius (map units, a Doom rocket's, an engineering pick)
		// Shotguns
		ShotDamageBp,        // damage bonus, +0% to +75% by skill
		ShotReloadBp,        // 25: reloads take this much less time (35%; 100's amount is open, so it stays)
		ShotPelletBp,        // this many more pellets per shot: +50% at 50, +100% at 100
		ShotKnockBp,         // 75: knockback strength, 10000 = the 75 perk's, 2x at 100
		ShotSlamDamage,      // most extra damage an enemy knocked into a wall takes: 200 at 75, 400 at 100
		ShotCollideDamage,   // most damage a knocked enemy and what it hits each take (open, so 0)
		// Energy Weapons
		EnergyDamageBp,      // damage bonus, +0% to +50% by skill
		EnergySplashBp,      // 25: a hit that is not an explosion also deals this much of its damage ...
		EnergySplashRadius,  // ... to every other enemy within this many map units
		EnergySpeedBp,       // the guns' projectiles fly this much faster: 15% at each of 25, 50, 75 and 100
		EnergyBurnBp,        // a direct hit sets the enemy burning for this much of its damage over 3 s
		EnergyConvertBp,     // a direct hit first turns this much of the enemy's burn into instant damage
		EnergyBurstBp,       // 100: that converted damage bursts out, setting enemies nearby burning for this ...
		EnergyBurstRadius,   // ... much of it, within this many map units
		RuleCount
	};

	// Set only by test harnesses under tools/ (a hand-picked rule set in place of the character's), and used only when
	// the game was started with +set dd_ruletest 1.
	bool testRules;
	int testRule[RuleCount];

	// A perk rule's value for the current character, or 0 (off) without one.
	clearscope static int Get(int rule)
	{
		let h = dd_ruletest ? DoomerfallRules(StaticEventHandler.Find("DoomerfallRules")) : null;
		if (h && h.testRules) return rule >= 0 && rule < RuleCount ? h.testRule[rule] : 0;
		int skill = Actor.DD_SheetSkill(SkillOf(rule));
		return skill < 0 ? 0 : Compute(rule, skill);
	}

	clearscope static int SkillOf(int rule)
	{
		if (rule <= AutoSunderMaxBp) return SkillAutomatics;
		if (rule <= ExplChainRadius) return SkillExplosives;
		if (rule <= ShotCollideDamage) return SkillShotguns;
		return SkillEnergy;
	}

	// The rules themselves, from the skill's value.
	clearscope static int Compute(int rule, int skill)
	{
		int s = clamp(skill, 0, 100);
		int perk = s / 25; // 0..4: the perks reached at 25, 50, 75 and 100
		switch (rule)
		{
		case AutoDamageBp:       return 6000 * s / 100;
		case AutoBurstBp:        return skill >= 25 ? 3000 : 0;
		case AutoBurstShots:     return skill >= 25 ? 3 : 0;
		case AutoBurstResetMs:   return skill >= 25 ? 300 : 0;
		case AutoShotsPerAmmo:   return skill >= 100 ? 4 : skill >= 50 ? 2 : 1;
		case AutoSunderBp:       return skill >= 75 ? 100 : 0;
		case AutoSunderMaxBp:    return skill >= 75 ? 1500 : 0;

		case ExplDamageBp:       return 6000 * s / 100;
		case ExplSelfCutBp:      return skill >= 75 ? 9900 : skill >= 25 ? 9500 : 0;
		case ExplDirectBp:       return 0; // 50: the owner has not set the amount
		case ExplChainBp:        return skill >= 100 ? 2500 : 0;
		case ExplChainRadius:    return skill >= 100 ? 128 : 0;

		case ShotDamageBp:       return 7500 * s / 100;
		case ShotReloadBp:       return skill >= 25 ? 3500 : 0;
		case ShotPelletBp:       return skill >= 100 ? 10000 : skill >= 50 ? 5000 : 0;
		case ShotKnockBp:        return skill >= 100 ? 20000 : skill >= 75 ? 10000 : 0;
		case ShotSlamDamage:     return skill >= 100 ? 400 : skill >= 75 ? 200 : 0;
		case ShotCollideDamage:  return 0; // open: owner tentative 200 at 75, 400 at 100

		case EnergyDamageBp:     return 5000 * s / 100;
		case EnergySplashBp:     return skill >= 25 ? 2000 : 0;
		case EnergySplashRadius: return skill >= 25 ? 64 : 0;
		case EnergySpeedBp:      return 1500 * perk;
		case EnergyBurnBp:       return perk >= 4 ? 15000 : perk == 3 ? 12500 : perk == 2 ? 10000 : perk == 1 ? 5000 : 0;
		case EnergyConvertBp:    return perk >= 3 ? 4000 : perk == 2 ? 2000 : 0;
		case EnergyBurstBp:      return perk >= 4 ? 4000 : 0;
		case EnergyBurstRadius:  return perk >= 4 ? 128 : 0;
		}
		return 0;
	}
}
