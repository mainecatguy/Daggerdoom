version "4.14"

// The loaded ammo's tinted HUD icon and the change notice (card ammoicon), in a paired run. Once Daggerfall is ready and
// the starting gun's ammo is shown, touches a Silver and a Daedric pickup of the gun's ammo type (they go to Daggerfall's
// inventory through dfa_take), then presses the change ammo key three times: Regular -> Silver -> Daedric -> Regular.
// After each press it reports the loaded ammo and the icon the status bar draws for the reserve item.
class AIHarness : EventHandler
{
	static const String RESERVES[] = { "Clip", "Shell", "RocketAmmo", "Cell" };
	static const String TYPENAMES[] = { "Clip", "Shell", "Rocket", "Cell" };
	const PRESSCOUNT = 3;
	int phase, timer, presses, type;
	bool done;

	void Report(String why)
	{
		let tiers = DoomerfallAmmoTiers.Get();
		let p = players[0].mo;
		String icons = "";
		for (int t = 0; t < RESERVES.Size(); t++)
		{
			let inv = p.FindInventory(RESERVES[t]);
			icons = icons .. " " .. RESERVES[t] .. "=" .. (inv ? String.Format("%s/%d", TexMan.GetName(inv.Icon), inv.Amount) : "none");
		}
		// The status bar draws an item's Icon whenever it is valid (shared_sbar.cpp GetInventoryIcon).
		let w = players[0].ReadyWeapon;
		Console.Printf("AIREPORT %s loaded=\"%s\" tier=%d type=%d weapon=%s icons:%s", why, tiers.loadedName, tiers.loadedTier,
			tiers.loadedType, w ? w.GetClassName() : 'none', icons);
	}

	void Finish(String why)
	{
		Console.Printf("AIDONE %s", why);
		done = true;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		let tiers = DoomerfallAmmoTiers.Get();
		timer++;
		switch (phase)
		{
		case 0: // Daggerfall's rules have arrived and the starting gun's loaded ammo is shown.
			if (timer > 35 * 90) { Finish("never ready"); break; }
			if (!tiers || !tiers.rules || tiers.loadedTier < 0 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3 || timer < 35 * 3) break;
			type = tiers.loadedType;
			Report("start");
			for (int i = 0; i < 2; i++)
			{
				let pickup = Inventory(Actor.Spawn(String.Format("DFAmmo_%s_%d", TYPENAMES[type], i == 0 ? 2 : 9), p.pos, NO_REPLACE));
				if (pickup) pickup.Touch(p);
			}
			Console.Printf("AINOTE touched Silver and Daedric %s", RESERVES[type]);
			phase = 1;
			timer = 0;
			break;
		case 1: // The change ammo key every 7 seconds, with a report 4 seconds after each press.
			if (timer == 35 * 3) { presses++; Console.Printf("AINOTE press %d", presses); EventHandler.SendNetworkEvent("df_change_ammo"); }
			if (timer == 35 * 7)
			{
				Report(String.Format("press %d", presses));
				timer = 0;
				if (presses == PRESSCOUNT) Finish("done");
			}
			break;
		}
	}
}
