// Weapon categories for Doomerfall's gun skills (work/backlog/skills-in-doom.md), so later perk cards know which
// Daggerfall skill a gun belongs to. Works for stock Doom and for DRLA, and without DRLA.
//
// Precedence when signs overlap (the proposal's lean, not yet an owner decision):
//   Melee > Explosive > Energy > Shotgun > Precision > Automatic > Pistol.
// So DRLA's Autoshotgun (shotgun and rapid-fire tokens) is a Shotgun, and a cell-fed shotgun or Plasma Rifle is
// Energy rather than Shotgun or Automatic.
//
// Signs used:
//   - Melee: the MELEEWEAPON flag, stock Fist and Chainsaw, or DRLA's RLMeleeTypeWeapon token.
//   - Explosive / Energy: the gun's ammo (either ammo type, since DRLA guns load a magazine from reserve ammo)
//     is or descends from RocketAmmo / Cell. DRLA has no explosive token.
//   - Shotgun, Precision, Automatic, Pistol: stock Shotgun and SuperShotgun, Chaingun, Pistol, or DRLA's
//     RLShotgunTypeWeapon, RLSingleShotRifleTypeWeapon, RLRapidfireTypeWeapon, RLPistolTypeWeapon tokens.
// Pistols (owner, 2026-11-26): stock Pistol and DRLA's pistol-token guns; no rifle is a pistol. No DRLA rifle carries
// the pistol token (checked in GameMods/ExtractedData), and rifles with DRLA's rifle token are Precision, which has
// no skill yet (backlog: Rifles). Pistol-token guns that also carry shotgun or rapid-fire tokens, or use cells, take
// the category ahead of Pistol in the precedence above (Storm pistols, Uzis, plasma pistols).
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
		}
		return -1;
	}

	clearscope static String Label(int category)
	{
		static const String names[] = { "other", "melee", "pistol", "shotgun", "automatic", "precision", "explosive", "energy" };
		return category >= 0 && category <= Energy ? names[category] : "other";
	}

	clearscope static int Of(Weapon w)
	{
		if (!w) return Other;
		let owner = w.Owner;
		bool held = owner && owner.player && owner.player.ReadyWeapon == w;
		if (w.bMeleeWeapon || w is "Fist" || w is "Chainsaw" || (held && HasToken(owner, "RLMeleeTypeWeapon"))) return Melee;
		if (AmmoIs(w, "RocketAmmo")) return Explosive;
		if (AmmoIs(w, "Cell")) return Energy;
		if (w is "Shotgun" || w is "SuperShotgun" || (held && HasToken(owner, "RLShotgunTypeWeapon"))) return Shotgun;
		if (held && HasToken(owner, "RLSingleShotRifleTypeWeapon")) return Precision;
		if (w is "Chaingun" || (held && HasToken(owner, "RLRapidfireTypeWeapon"))) return Automatic;
		if (w is "Pistol" || (held && HasToken(owner, "RLPistolTypeWeapon"))) return Pistol;
		return Other;
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

	private clearscope static bool AmmoIs(Weapon w, String base)
	{
		class<Inventory> b = base;
		if (!b) return false;
		return (w.AmmoType1 && GetDefaultByType(w.AmmoType1) is b) || (w.AmmoType2 && GetDefaultByType(w.AmmoType2) is b);
	}
}
