// DRLA guns whose magazine empties in one shot reload by themselves. Does nothing without DRLA.
//
// DRLA already has this as its user option "1-shot weapons autoreload" (CVar DRLA_autoreload, off by default):
// 31 guns, such as the shotgun, double shotgun, super shotgun and rocket launcher, ask DRLA's DRLA_AutoReload ACS
// script after firing and jump to their Reload state when it is on. This handler turns the option on once each time
// UZDoom starts, so the player can still turn it off from DRLA's options menu for the rest of the session.
//
// Two one-shot guns never ask that script, so this handler reloads them while the option is on: when the gun sits
// in its Ready loop with an empty magazine and enough reserve ammo, it is sent to its own Reload state, as if the
// player pressed reload.
class DoomerfallReload : StaticEventHandler
{
	const OptionName = "DRLA_autoreload";

	override void OnRegister()
	{
		let option = CVar.FindCVar(OptionName); // Exists only when DRLA is loaded.
		if (option) option.SetBool(true);
	}

	// The guns DRLA's own option misses. reserveNeed is what their Reload state checks before it reloads.
	static bool Missed(Weapon w, out int reserveNeed)
	{
		String n = w.GetClassName();
		if (n == "RLBaronBlaster")
		{
			// One shot per magazine. A reload costs 100 cells, or 50 with the Fireangel perk.
			String perkName = "RLFireangelPerk";
			class<Inventory> perk = perkName;
			reserveNeed = (perk && w.owner.CountInv(perk) > 0) ? 50 : 100;
			return true;
		}
		if (n == "RLMarathonShotguns")
		{
			// Two shells per shot and per magazine. Held as a pair (with its demon artifacts) it has its own
			// left and right magazines and reload keys, which this does not touch.
			String dualName = "RLMarathonShotgunsDemonArtifacts";
			class<Inventory> dual = dualName;
			if (dual && w.owner.CountInv(dual) > 0) return false;
			reserveNeed = 2;
			return true;
		}
		return false;
	}

	override void WorldTick()
	{
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i]) continue;
			let p = players[i];
			let w = p.ReadyWeapon;
			if (!p.mo || p.mo.health <= 0 || !w || p.PendingWeapon != WP_NOCHANGE) continue;
			int reserveNeed;
			if (!Missed(w, reserveNeed)) continue;
			let option = CVar.GetCVar(OptionName, p);
			if (!option || !option.GetBool()) continue;
			if (!w.AmmoType1 || p.mo.CountInv(w.AmmoType1) >= w.AmmoUse1) continue;
			if (!w.AmmoType2 || p.mo.CountInv(w.AmmoType2) < reserveNeed) continue;
			let psp = p.FindPSprite(PSP_WEAPON);
			State ready = w.FindState("Ready");
			State reload = w.FindState("Reload");
			if (!psp || !psp.CurState || !ready || !reload || !psp.CurState.InStateSequence(ready)) continue;
			p.SetPsprite(PSP_WEAPON, reload);
		}
	}
}
