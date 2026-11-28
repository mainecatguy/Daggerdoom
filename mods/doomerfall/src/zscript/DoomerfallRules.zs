// The one place where Doom applies Daggerfall's rules to Daggerfall's character sheet (owner, 2026-11-27, Q&A item 45:
// "daggerfall transfer its character sheet to Doom and allow Doom to apply the rules based on that character sheet";
// architecture.md, "Character sheet and rules").
//
// In:  the character sheet Daggerfall sends over the bridge (bridge/doomerfall_bridge.h DFB_SHEET_*), read through
//      Actor.DD_SheetStat / DD_SheetSkill / DD_SheetSkillBase / DD_SheetValue. Each reads -1 without a Daggerfall
//      character, and then every rule here reads "no change", so stock Doom and plain WADs are unchanged.
// Out: rule values and factors. The systems that act on them (DoomerfallAttributes.zs, DoomerfallJump.zs and the gun
//      skill perks DoomerfallAutomatics.zs, DoomerfallExplosives.zs, DoomerfallShotguns.zs, DoomerfallEnergy.zs,
//      DoomerfallPistols.zs) hold
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
	const SkillPistols = 7;
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

	// Attribute rework (owner, 2026-11-27: gamedesign/decisions/20261127-attribute-rework-owner.md). The damage factors
	// multiply with each other and with every other damage modifier (damagestacking 01 reviews that).
	// Strength: melee damage +0% at 0 to +100% at 100.
	clearscope static double StrengthMeleeFactor(int v) { return v < 0 ? 1.0 : 1.0 + v / 100.0; }
	// Strength: shotguns, explosives and automatics -20% at 0, normal at 50, +20% at 100.
	clearscope static double StrengthGunFactor(int v) { return v < 0 ? 1.0 : 0.8 + clamp(v, 0, 100) * 0.004; }
	// Speed: movement -25% at 0, normal at 50, +25% at 100.
	clearscope static double SpeedFactor(int v) { return v < 0 ? 1.0 : 0.75 + v / 200.0; }
	// Agility: every firearm -10% at 0, normal at 50, +10% at 100; rifles and pistols (rifleOrPistol) get another
	// -10% to +10% on the same line, added to the first (so -20% to +20%).
	clearscope static double AgilityGunFactor(int v, bool rifleOrPistol)
	{
		return v < 0 ? 1.0 : 1.0 + (clamp(v, 0, 100) - 50) * (rifleOrPistol ? 0.004 : 0.002);
	}
	// Agility: reloads and weapon switches up to 40% faster (0 to 0.4 extra speed), linear from 0 at Agility 0. The old
	// chance to evade damage is gone (owner, 2026-11-27).
	const AgilityMaxHandling = 0.40;
	clearscope static double AgilityHandlingBonus(int v) { return v <= 0 ? 0.0 : AgilityMaxHandling * v / 100.0; }
	// Luck: a super crit of LuckCritFactor x the damage, 0% at 50 and below, +0.1% per point above (5% at 100).
	const LuckCritFactor = 5;
	clearscope static double LuckCritChance(int v) { return v <= 50 ? 0.0 : min(v - 50, 50) * 0.001; }
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
		AutoSunderBp,        // 75: each hit makes the enemy take this much more damage from all sources (1%; 2% at 100) ...
		AutoSunderMaxBp,     // ... permanently, up to this much (15%; 30% at 100, the total, not added to 75's)
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
		// Pistols. Fast and slow pistols are DRLA's Scout definition: the gun's Scout damage multiplier (DoomerfallPistols
		// ScoutOf), fast at PistScaleFast and slow at PistScaleSlow; each fire-rate multiplier goes linearly between them.
		PistSprayFastBp,     // 25: damage multiplier for the fastest pistols (x2.5) ...
		PistSpraySlowBp,     // ... and for the slowest (x1.5)
		PistDeadeyeFastBp,   // 75: Deadeye multiplier for the fastest pistols (x1.5) ...
		PistDeadeyeSlowBp,   // ... and for the slowest (x3); multiplies with the 25 one, not the pool
		PistScaleFast,       // the Scout multiplier that counts as the fastest pistol (3) ...
		PistScaleSlow,       // ... and as the slowest (8)
		PistReloadBp,        // reloads take this much less time: 20% at 25, 40% at 50, 60% at 75
		PistCarry,           // 50: 1, a killing hit's leftover damage carries on to the next enemy behind
		PistPool,            // 50: bonus damage pool spent by each pistol shot ...
		PistPoolRefillMs,    // ... refilling from empty in this long
		PistFragments,       // 100: each pistol hit bursts into this many fragments behind the enemy ...
		PistFragmentBp,      // ... each dealing this much of the hit's damage ...
		PistFragmentTurnCdeg,// ... locking on to an enemy within this many 1/100ths of a degree of its path
		// More Automatics (skillperks 09; gamedesign/decisions/20261127-automatics-tuning-owner.md). Added after the
		// Pistols rules so the test harnesses' sheet slots (155 + rule) keep their places. A gun's band is its own base
		// tics between shots (DoomerfallAutomaticBands: 4+ slow, 3 middle, 1-2 fast).
		AutoFreeEvery,       // 25-49: every this many-th shot spends no ammo (3); 0 from 50, so it never stacks with AutoShotsPerAmmo
		AutoSlowDamage,      // 50: slow band, each bullet gets this much base damage (25) ...
		AutoSlowPen,         // ... and passes through this many more enemies (1)
		AutoMidDamage,       // 50: middle band, the same two (7 ...
		AutoMidPen,          // ... and 1)
		AutoFastExtraBp,     // 50: fast band, each shot's chance of one extra free bullet (10%)
		AutoSuppressBp,      // 75: each hit slows the enemy's movement by this much more (5%) ...
		AutoSuppressMaxBp,   // ... up to this much (40%) ...
		AutoSuppressFadeMs,  // ... fading evenly to nothing over this long after the last hit (5 s)
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
		if (rule <= EnergyBurstRadius) return SkillEnergy;
		if (rule <= PistFragmentTurnCdeg) return SkillPistols;
		return SkillAutomatics;
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
		case AutoSunderBp:       return skill >= 100 ? 200 : skill >= 75 ? 100 : 0;
		case AutoSunderMaxBp:    return skill >= 100 ? 3000 : skill >= 75 ? 1500 : 0;

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

		case PistSprayFastBp:    return skill >= 25 ? 25000 : 0;
		case PistSpraySlowBp:    return skill >= 25 ? 15000 : 0;
		case PistDeadeyeFastBp:  return skill >= 75 ? 15000 : 0;
		case PistDeadeyeSlowBp:  return skill >= 75 ? 30000 : 0;
		case PistScaleFast:      return skill >= 25 ? 3 : 0;
		case PistScaleSlow:      return skill >= 25 ? 8 : 0;
		case PistReloadBp:       return 2000 * min(perk, 3);
		case PistCarry:          return skill >= 50 ? 1 : 0;
		case PistPool:           return skill >= 50 ? 100 : 0;
		case PistPoolRefillMs:   return skill >= 50 ? 500 : 0;
		case PistFragments:      return skill >= 100 ? 3 : 0;
		case PistFragmentBp:     return skill >= 100 ? 3300 : 0;
		case PistFragmentTurnCdeg: return skill >= 100 ? 250 : 0;

		case AutoFreeEvery:      return skill >= 25 && skill < 50 ? 3 : 0;
		case AutoSlowDamage:     return skill >= 50 ? 25 : 0;
		case AutoSlowPen:        return skill >= 50 ? 1 : 0;
		case AutoMidDamage:      return skill >= 50 ? 7 : 0;
		case AutoMidPen:         return skill >= 50 ? 1 : 0;
		case AutoFastExtraBp:    return skill >= 50 ? 1000 : 0;
		case AutoSuppressBp:     return skill >= 75 ? 500 : 0;
		case AutoSuppressMaxBp:  return skill >= 75 ? 4000 : 0;
		case AutoSuppressFadeMs: return skill >= 75 ? 5000 : 0;
		}
		return 0;
	}
}
