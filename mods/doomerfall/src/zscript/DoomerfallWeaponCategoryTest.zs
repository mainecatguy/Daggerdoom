// Test hook: with +set dd_weaponcat_test 1, gives the player each sample gun in turn, waits until it is held, and
// prints "WEAPCAT <class> <category> <skill slot>" lines, ending with "WEAPCAT done".
// tools/weapon_category/run_weaponcat_test.py runs it with and without DRLA and checks the output.
class DoomerfallWeaponCategoryTest : StaticEventHandler
{
	static const String samples[] = {
		"Fist", "Chainsaw", "Pistol", "Shotgun", "SuperShotgun", "Chaingun", "RocketLauncher", "PlasmaRifle", "BFG9000",
		"RLPistol", "RLShotgun", "RLCombatShotgun", "RLDoubleShotgun", "RLAutoshotgun", "RLChaingun", "RLMinigun",
		"RLRocketLauncher", "RLMissileLauncher", "RLGrenadeLauncher", "RLPlasmaRifle", "RLPlasmaPistol", "RLLaserRifle",
		"RLRailgun", "RLUzi", "RLChainsaw", "RLBFG9000"
	};
	const SampleCount = 26;
	const WaitTics = 70;

	int next, wait;
	bool active, finished;

	override void WorldLoaded(WorldEvent e)
	{
		let flag = CVar.FindCVar("dd_weaponcat_test");
		active = flag && flag.GetBool() && !finished;
		next = 0;
		wait = 0;
	}

	override void WorldTick()
	{
		if (!active || finished) return;
		let p = players[consoleplayer];
		if (!p.mo) return;
		if (wait > 0)
		{
			wait--;
			if (wait > 0 && p.ReadyWeapon && p.ReadyWeapon.GetClassName() == samples[next] && p.PendingWeapon == WP_NOCHANGE && wait < WaitTics - 35)
				wait = 0; // Held and settled: DRLA's Select state has given its tokens.
			if (wait > 0) return;
			Report(p, samples[next]);
			next++;
		}
		while (next < SampleCount)
		{
			class<Weapon> c = samples[next];
			if (!c) { Console.Printf("WEAPCAT %s absent", samples[next]); next++; continue; }
			p.mo.GiveInventory(c, 1);
			let w = Weapon(p.mo.FindInventory(c));
			if (!w) { Console.Printf("WEAPCAT %s not-given", samples[next]); next++; continue; }
			p.PendingWeapon = w;
			wait = WaitTics;
			return;
		}
		finished = true;
		Console.Printf("WEAPCAT done");
	}

	void Report(PlayerInfo p, String wanted)
	{
		let held = p.ReadyWeapon;
		String heldName = held ? String.Format("%s", held.GetClassName()) : "none";
		int cat = DoomerfallWeaponCategory.OfHeld(p);
		Console.Printf("WEAPCAT %s %s %d held=%s", wanted, DoomerfallWeaponCategory.Label(cat), DoomerfallWeaponCategory.SkillSlot(cat), heldName);
	}
}
