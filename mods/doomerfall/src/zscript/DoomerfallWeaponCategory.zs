// Weapon categories for Doomerfall's gun skills (work/backlog/skills-in-doom.md), so later perk cards know which
// Daggerfall skill a gun belongs to. Works for stock Doom and for DRLA, and without DRLA.
//
// Precedence when signs overlap:
//   Unarmed > Melee > Pistol > Explosive > Energy > Shotgun > Precision > Automatic.
// Pistol second follows the Pistols goal (owner, 2026-11-26: DRLA's pistol-type guns are pistols), so pistol-token
// Uzis, Storm (shotgun-token) pistols and cell-fed pistols are Pistols. The order of the rest is the proposal's
// lean, not yet an owner decision: DRLA's Autoshotgun (shotgun and rapid-fire tokens) is a Shotgun, and a cell-fed
// shotgun or Plasma Rifle is Energy rather than Shotgun or Automatic.
//
// Signs used:
//   - Unarmed: stock Fist and DRLA's RLFist (which replaces it). Hand-to-Hand governs the fist, not Melee
//     (work/backlog/skills-in-doom.md), so Unarmed maps to Daggerfall's Hand-to-Hand skill (slot 30).
//   - Melee: the MELEEWEAPON flag, stock Chainsaw, DRLA's RLMeleeTypeWeapon token (chainsaws, Energysaw, Ripper),
//     or DRLA's Dragonslayer sword (it has neither the flag nor the token).
//   - Explosive / Energy: the gun's ammo (either ammo type, since DRLA guns load a magazine from reserve ammo)
//     is or descends from RocketAmmo / Cell. DRLA has no explosive or energy token. Energy also takes the DRLA energy
//     guns that recharge instead of using cells (IsEnergyGun's list: the Nuclear family, BFG Infinity, Lightweaver,
//     the nano-shrapnel Plasma Shotgun (Plasma damage), and the nano-manufacture Laser Rifle, Plasma Rifle and
//     Tristar Blaster), and the self-charging energy pistols (Pistol first, Energy second; see Both).
//   - Shotgun, Precision, Automatic, Pistol: stock Shotgun and SuperShotgun, Chaingun, Pistol, or DRLA's
//     RLShotgunTypeWeapon, RLSingleShotRifleTypeWeapon, RLRapidfireTypeWeapon, RLPistolTypeWeapon tokens.
// Pistols (owner, 2026-11-26): stock Pistol and DRLA's pistol-token guns; no rifle is a pistol. No DRLA rifle carries
// the pistol token (checked in GameMods/ExtractedData).
// Rifles (owner, 2026-11-26: "all ballistic semi-automatic weapons that are not explosives, energy weapons, shotguns
// or pistols") is skill slot 8, but no category maps to it yet. Precision (DRLA's single-shot rifle token) is not a
// clean rifle list: the Assault Rifle Chaingun, Assault Rifle Minigun and Autocannon carry it but are Automatics by
// the owner's rule (IsOwnerAutomatic, checked where the token would make them Precision), and the Sniper Rifle
// lacks it. Doomerfall's own rifle tag (DoomerfallRifleTag.IsRifle) says which
// guns are rifles; it changes no category or skill yet.
// DRLA gives its tokens only while the gun is held (the gun's Select state gives them, lowering takes them), so a
// DRLA gun that is not the held one is known by ammo only and may read as Other until it is selected.
class DoomerfallWeaponCategory abstract
{
	enum ECategory
	{
		Other,
		Melee,
		Pistol,
		Shotgun,
		Automatic,
		Precision,
		Explosive,
		Energy,
		Unarmed, // Appended so the other values keep their numbers.
	}


	// The Daggerfall skill slot (DFCareer.Skills, DFB_SHEET_SKILLS_BASE index) for a category, or -1 when the
	// category has no Doomerfall skill yet. Must match DFB_SKILL_* in bridge/doomerfall_bridge.h.
	clearscope static int SkillSlot(int category)
	{
		switch (category)
		{
			case Shotgun: return 4;
			case Automatic: return 5;
			case Explosive: return 6;
			case Pistol: return 7;
			case Energy: return 9;
			case Melee: return 10;
			case Unarmed: return 30; // Hand-to-Hand
		}
		return -1;
	}

	clearscope static String Label(int category)
	{
		static const String names[] = { "other", "melee", "pistol", "shotgun", "automatic", "precision", "explosive", "energy", "unarmed" };
		return category >= 0 && category <= Unarmed ? names[category] : "other";
	}

	// A weapon's first category, by the precedence above.
	clearscope static int Of(Weapon w)
	{
		int first, second;
		[first, second] = Both(w);
		return first;
	}

	// A weapon's two categories: its first, and a second one (or Other) where it truly fits two skills. Owner,
	// 2026-11-26 (gamedesign/decisions/20261126-two-skill-weapons-owner.md): the pairs are a Pistol or Shotgun that is
	// also an Energy Weapon. An energy pistol is Pistol then Energy; an energy shotgun (cell-fed, or on the recharging
	// list) is Energy then Shotgun. Other overlaps (a Storm pistol's shotgun token, the Autoshotgun's rapid-fire token,
	// a missile pistol's rockets) stay one category, as before. Stock Doom has no such gun, but a mod's cell-fed
	// subclass of Pistol, Shotgun or SuperShotgun gets both without DRLA.
	clearscope static int, int Both(Weapon w)
	{
		if (!w) return Other, Other;
		let owner = w.Owner;
		int tokens = 0;
		if (owner && owner.player && owner.player.ReadyWeapon == w)
		{
			if (HasToken(owner, "RLPistolTypeWeapon")) tokens |= TokPistol;
			if (HasToken(owner, "RLShotgunTypeWeapon")) tokens |= TokShotgun;
			if (HasToken(owner, "RLSingleShotRifleTypeWeapon")) tokens |= TokSingleShotRifle;
			if (HasToken(owner, "RLRapidfireTypeWeapon")) tokens |= TokRapidfire;
			if (HasToken(owner, "RLMeleeTypeWeapon")) tokens |= TokMelee;
		}
		int first, second; // ZScript passes on only the first value of "return BothWithTokens(...)".
		[first, second] = BothWithTokens(w, tokens);
		return first, second;
	}

	// Both's answer for a gun class that need not be held or even exist, as a gun in Daggerfall's inventory: the same
	// rules, with DRLA's tokens read from DoomerfallWeaponTokens (what each gun's Select state gives) instead of the
	// player's inventory. tools/weapon_types/run_weapontypes_test.py checks it gives Both's answer for every held gun.
	clearscope static int, int BothOfClass(class<Weapon> wc)
	{
		if (!wc) return Other, Other;
		int first, second;
		[first, second] = BothWithTokens(GetDefaultByType(wc), DoomerfallWeaponTokens.Of(wc));
		return first, second;
	}

	// DRLA's type tokens as bits (DoomerfallWeaponTokens and tools/weapon_types/derive_weapon_tokens.py use them).
	const TokPistol = 1;
	const TokShotgun = 2;
	const TokSingleShotRifle = 4;
	const TokRapidfire = 8;
	const TokMelee = 16;

	// The rules of Both, for a weapon (or a weapon class's defaults) and the DRLA tokens it gives while held.
	private clearscope static int, int BothWithTokens(readonly<Weapon> w, int tokens)
	{
		if (w is "Fist" || IsClass(w, "RLFist")) return Unarmed, Other;
		if (w.bMeleeWeapon || w is "Chainsaw" || IsClass(w, "RLDragonslayer") || (tokens & TokMelee)) return Melee, Other;
		// ZScript names are case-insensitive: these must not be called energy or shotgun, or they hide the enum values.
		bool isEnergy = AmmoIs(w, "Cell") || IsEnergyGun(w);
		if (w is "Pistol" || (tokens & TokPistol)) return Pistol, isEnergy ? Energy : Other;
		if (AmmoIs(w, "RocketAmmo")) return Explosive, Other;
		bool isShotgun = w is "Shotgun" || w is "SuperShotgun" || (tokens & TokShotgun);
		if (isEnergy) return Energy, isShotgun ? Shotgun : Other;
		if (isShotgun) return Shotgun, Other;
		if ((tokens & TokSingleShotRifle) && !IsOwnerAutomatic(w)) return Precision, Other;
		if (IsOwnerAutomatic(w)) return Automatic, Other;
		if (w is "Chaingun" || (tokens & TokRapidfire)) return Automatic, Other;
		return Other, Other;
	}

	// The Daggerfall skill slot a weapon uses, or -1. A weapon in two skills uses whichever of the two is higher in
	// Daggerfall's live character sheet, never both (manual.md, "Weapons that belong to two skills"); on a tie, or
	// without Daggerfall (a Doom-only game), it uses its first category's skill. Anything that reads a weapon's skill
	// should call this rather than SkillSlot(Of(w)).
	clearscope static int SkillSlotOf(Weapon w)
	{
		int first, second;
		[first, second] = Both(w);
		int a = SkillSlot(first), b = SkillSlot(second);
		if (b < 0) return a;
		if (a < 0) return b;
		return Actor.DD_SheetSkill(b) > Actor.DD_SheetSkill(a) ? b : a;
	}

	// The category of the player's held gun, or Other.
	clearscope static int OfHeld(PlayerInfo p)
	{
		return p ? Of(p.ReadyWeapon) : Other;
	}

	private clearscope static bool HasToken(Actor owner, String token)
	{
		class<Inventory> c = token; // Looked up at run time, so this works without DRLA loaded.
		return c && owner.FindInventory(c);
	}

	private clearscope static bool IsClass(readonly<Weapon> w, String name)
	{
		class<Actor> c = name; // Null when that mod is not loaded.
		return c && w is c;
	}

	// DRLA guns with the single-shot rifle token that the owner ruled Automatics (2026-11-26: "Those all sound like
	// automatics"). Looked up at run time, so this list does nothing without DRLA.
	private clearscope static bool IsOwnerAutomatic(readonly<Weapon> w)
	{
		return IsClass(w, "RLAssaultRifleChaingun") || IsClass(w, "RLAssaultRifleMinigun") || IsClass(w, "RLAutocannon");
	}

	private clearscope static bool IsEnergyGun(readonly<Weapon> w)
	{
		// DRLA energy guns with no Cell ammo (they recharge or make their own ammo), from GameMods/ExtractedData.
		// Looked up at run time, so this list does nothing without DRLA.
		static const String energyGuns[] = {
			"RLNuclearPlasmaRifle", "RLNuclearPlasmaRifleMkII", "RLNuclearPlasmaShotgun", "RLNuclearBFG9000",
			"RLNuclearVBFG9000", "RLNuclearBiggestFuckingGun", "RLNuclearOnslaught", "RLHighPowerNuclearBFG9000",
			"RLHighPowerNuclearPlasmaRifle", "RLAssaultRifleNuclearPlasmaRifle", "RLBurstCannonNuclearPlasmaRifle",
			"RLBFGInfinity", "RLNanoManufactureAmmoLaserRifle", "RLNanoManufactureAmmoPlasmaRifle",
			"RLNanoManufactureAmmoTristarBlaster", "RLLightweaver", "RLNanoShrapnelPlasmaShotgun",
			// Self-charging energy pistols (laser or plasma, no cells). Their pistol token makes them Pistol first.
			"RLBlaster", "RLNuclearPlasmaPistol", "RLHighPowerBlaster", "RLHighPowerNuclearPlasmaPistol",
			"RLNuclearPlasmaRevolver", "RLOverchargedBlaster", "RLStormBlaster", "RLStormNuclearPlasmaPistol",
			"RLSuperchargedNuclearPlasmaPistol", "RLNanoManufactureAmmoBlaster", "RLHeavyPulseBlaster"
		};
		for (int i = 0; i < energyGuns.Size(); i++)
			if (IsClass(w, energyGuns[i])) return true;
		return false;
	}

	private clearscope static bool AmmoIs(readonly<Weapon> w, String base)
	{
		class<Inventory> b = base;
		if (!b) return false;
		return (w.AmmoType1 && GetDefaultByType(w.AmmoType1) is b) || (w.AmmoType2 && GetDefaultByType(w.AmmoType2) is b);
	}
}
