// Agility in Doom (owner, 2026-11-26; manual.md "Attributes"). Daggerfall owns the character sheet and sends its live
// attributes (Actor.DD_SheetStat, -1 without a Daggerfall character); Doom applies Agility here: reloads and weapon
// switches run up to 40% faster (x1.4 animation speed at 100). Agility's firearm damage is DoomerfallAttributes'. The
// old dodge chance is gone (owner, 2026-11-27: gamedesign/decisions/20261127-attribute-rework-owner.md).
// Linear from 0 at Agility 0; values are clamped to 0..100 and read live, so a change on the sheet applies at once.
// Without a Daggerfall character the item is never given, so stock Doom and plain WADs are unchanged.

class DoomerfallAgilityEffects : Inventory
{
	const AgilityStat = 3;           // DFCareer.Stats.Agility
	const MaxHandlingBonus = 0.40;   // reload and switch speed at 100

	double handlingCarry; // fractional extra weapon tics owed while reloading or switching

	Default
	{
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
		Inventory.MaxAmount 1;
	}

	// Live Agility as 0..100, or -1 without a Daggerfall character.
	static int Live()
	{
		int v = Actor.DD_SheetStat(AgilityStat);
		return v < 0 ? -1 : min(v, 100);
	}

	// Extra speed of reloads and weapon switches: 0 (normal) to 0.4 (x1.4).
	static double HandlingBonus()
	{
		int v = Live();
		return v <= 0 ? 0.0 : MaxHandlingBonus * v / 100.0;
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
}

// Gives each player the Agility item while Daggerfall has a character. One native call per tic.
class DoomerfallAgility : EventHandler
{
	override void WorldTick()
	{
		if (Actor.DD_SheetStat(DoomerfallAgilityEffects.AgilityStat) < 0) return;
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = players[i].mo;
			if (playeringame[i] && mo && !mo.FindInventory("DoomerfallAgilityEffects")) mo.GiveInventory("DoomerfallAgilityEffects", 1);
		}
	}
}
