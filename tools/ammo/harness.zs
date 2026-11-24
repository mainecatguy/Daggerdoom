version "4.14"

// Reserve ammo in Daggerfall's inventory. The take run enters Privateer's Hold, picks up a box of bullets by touch,
// spends 5 bullets, waits for Daggerfall's test hook (-dfammotest) to drop 7 bullets and add 20 shells on its side,
// then autosaves. The load run loads that save in fresh copies of both games and reports the counts again.
class AMHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const String AMMO[] = { "Clip", "Shell", "RocketAmmo", "Cell" };
	const LIMIT = 35 * 20;
	const LOADRUN = @LOADRUN@;
	const EQUIPRUN = @EQUIPRUN@; // The equip run: guns equipped from Daggerfall set the damage bonus of their loaded ammo.
	const TIERRUN = @TIERRUN@; // The tiers run: tiered drops roll with the area level, and tiered pickups reach Daggerfall.
	const SAVED = 10;
	vector3 dropSpot;

	int phase, timer, startClip, startShell;
	bool done, sawShells, windowDrop, windowBack;

	// Shells arrive with Daggerfall's first change, the bullets go to 0 with its window drop, and come back with its pickup.
	void WatchDaggerfall(Actor p)
	{
		if (!sawShells && p.CountInv("Shell") > 0) { sawShells = true; Report("Daggerfall's change arrived"); }
		if (sawShells && !windowDrop && p.CountInv("Clip") == 0) { windowDrop = true; Report("bullets dropped in Daggerfall's window"); }
		if (windowDrop && !windowBack && p.CountInv("Clip") > 0) { windowBack = true; Report("bullets taken back in Daggerfall's window"); }
	}

	void Finish(String why)
	{
		Report("final");
		Console.Printf("AMDONE %s", why);
		done = true;
	}

	void Next() { phase++; timer = 0; }

	void Report(String why)
	{
		let p = players[0].mo;
		String line = "AMCOUNT " .. why;
		for (int i = 0; i < AMMO.Size(); i++)
			line = line .. " " .. AMMO[i] .. "=" .. p.CountInv(AMMO[i]);
		Console.Printf("%s", line);
	}

	static String ReserveOf(class<Inventory> c)
	{
		if (!c) return "none";
		let def = GetDefaultByType(c);
		if (def is "Clip") return "Clip";
		if (def is "Shell") return "Shell";
		if (def is "RocketAmmo") return "RocketAmmo";
		if (def is "Cell") return "Cell";
		return "none";
	}

	// Hurts a fresh stock Cyberdemon for 10 with the player as the source, as a shot does, and reports the health lost.
	// Daggerfall's damage bonus (from the ready gun's loaded ammo) scales it in Doom.
	void Hit(String label)
	{
		let p = players[0].mo;
		let w = players[0].ReadyWeapon;
		String ammo = "none";
		if (w) { ammo = ReserveOf(w.AmmoType1); if (ammo == "none") ammo = ReserveOf(w.AmmoType2); }
		let t = Actor.Spawn("Cyberdemon", p.Vec3Angle(200, p.angle), NO_REPLACE);
		if (!t) { Console.Printf("AMHIT %s no target", label); return; }
		int before = t.health;
		t.DamageMobj(null, p, 10, 'None');
		int lost = before - t.health;
		t.Destroy();
		Console.Printf("AMHIT %s weapon=%s ammo=%s lost=%d", label, w ? w.GetClassName() : 'none', ammo, lost);
	}

	// Lowers the gun for a weapon that uses no ammo, such as fists.
	void SelectMelee(Actor p)
	{
		for (Inventory i = p.Inv; i; i = i.Inv)
		{
			let w = Weapon(i);
			if (w && !w.AmmoType1 && !w.AmmoType2) { players[0].PendingWeapon = w; Console.Printf("AMNOTE melee %s", w.GetClassName()); return; }
		}
		p.GiveInventory("Fist", 1);
		let f = Weapon(p.FindInventory("Fist"));
		if (f) players[0].PendingWeapon = f;
		Console.Printf("AMNOTE melee Fist given");
	}

	void TierCensus(String why, int areaLevel)
	{
		int counts[10];
		for (int i = 0; i < 10; i++) counts[i] = 0;
		int plain = 0;
		Actor mo;
		let it = ThinkerIterator.Create("Inventory");
		while (mo = Actor(it.Next()))
		{
			let inv = Inventory(mo);
			if (inv.Owner) continue;
			let tiered = DoomerfallAmmoPickup(mo);
			if (tiered) counts[tiered.tier]++;
			else if (DoomerfallAmmoTiers.PlainType(mo) >= 0) plain++;
		}
		String line = String.Format("AMTIERS %s level=%d plain=%d", why, areaLevel, plain);
		for (int i = 0; i < 10; i++) line = line .. String.Format(" t%d=%d", i, counts[i]);
		Console.Printf("%s", line);
	}

	// The roll's odds at the owner's table levels, from 100000 draws each, and the jackpot share of the seed hash.
	void RollStats()
	{
		static const int LEVELS[] = { 1, 10, 20, 30 };
		for (int l = 0; l < LEVELS.Size(); l++)
		{
			int counts[10];
			for (int i = 0; i < 10; i++) counts[i] = 0;
			for (int n = 0; n < 100000; n++)
				counts[DoomerfallAmmoTiers.RollTier(LEVELS[l], DoomerfallAmmoTiers.Unit(n, 3), DoomerfallAmmoTiers.Unit(n, 4))]++;
			Console.Printf("AMODDS level %d Regular %.1f%% Silver %.1f%% Adamantium %.1f%% Ebony %.1f%% Daedric %.2f%%", LEVELS[l],
				counts[0] / 1000.0, counts[2] / 1000.0, counts[5] / 1000.0, counts[8] / 1000.0, counts[9] / 1000.0);
		}
		int jackpots = 0;
		for (int n = 0; n < 100000; n++) if (DoomerfallAmmoTiers.Unit(n * 7 + 1, 1) < DoomerfallAmmoTiers.JackpotChance) jackpots++;
		Console.Printf("AMODDS jackpot %.2f%%", jackpots / 1000.0);
	}

	bool AnyPile()
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		return it.Next() != null;
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (LOADRUN && phase == SAVED) { phase = 20; timer = 0; Report("loaded"); }
		if (LOADRUN && phase < SAVED) return;
		if (!LOADRUN && !EQUIPRUN && phase < SAVED) WatchDaggerfall(p);

		switch (phase)
		{
		case 0: // Enter the dungeon by the test door hook.
			if (inside) { Next(); break; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			Next();
			break;
		case 1: // Daggerfall's pile list shows it is ready in this space.
			if (timer > LIMIT) { Finish("Daggerfall never listed this space"); break; }
			if (!inside || !AnyPile() || timer < 35) break;
			RemoveMonsters();
			startClip = p.CountInv("Clip");
			startShell = p.CountInv("Shell");
			Report("start");
			Next();
			if (EQUIPRUN) phase = 30; // No break inside this constant if: one with a break crashed UZDoom's compiler.
			if (TIERRUN) phase = 40;
			break;
		case 2: // A box of bullets by touch. Stock ClipBox, not DRLA's spawner, so the amount is known.
		{
			// Two boxes, so Daggerfall's hook (60 bullets) runs whatever gun DRLA X started the player with.
			for (int i = 0; i < 2; i++)
			{
				let box = Inventory(Actor.Spawn("ClipBox", p.pos, NO_REPLACE));
				if (box) box.Touch(p);
			}
			Report("after ClipBox");
			Next();
			break;
		}
		case 3: // Spend 5 bullets, as firing would.
			if (timer < 35) break;
			p.TakeInventory("Clip", 5);
			Report("after spending 5");
			Next();
			break;
		case 4: // Daggerfall's test hook drops 7 bullets and adds 20 shells on its side, then drops all bullets and 5
			// shells through its inventory window and takes them back from the pile. It may run before the boxes if
			// Doom started with 60 or more bullets, so the steps are watched from the start (WatchDaggerfall).
			if (timer % 35 == 0) Report("waiting");
			if (windowBack) { Report("after Daggerfall's window test"); phase = 7; timer = 0; }
			else if (timer > LIMIT) { Report("Daggerfall's window test never finished"); phase = 7; timer = 0; }
			break;
		case 7:
			if (timer < 70) break;
			Report("before save");
			Console.Printf("AMSAVE autosave");
			LevelLocals.MakeAutoSave();
			phase = SAVED;
			timer = 0;
			break;
		case 30: // Daggerfall adopts the starting gun onto key 2 and its test hook adds a shotgun on key 3.
			if (timer == 35 * 5) { Hit("start gun"); Report("start gun"); Next(); }
			break;
		case 31:
			if (timer == 1) SelectMelee(p);
			if (timer == 105) { Hit("melee"); Next(); }
			break;
		case 32: // Daggerfall's hotkey raises the starting gun again (DFB_GUN_SELECT).
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:2");
			if (timer == 105) { Hit("hotkey 2"); Next(); }
			break;
		case 33: // Daggerfall's hotkey equips the shotgun it holds (DFB_GUN_GIVE).
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:3");
			if (timer == 140) { Hit("hotkey 3"); Report("shotgun equipped"); Next(); }
			break;
		case 34: // Spend 3 shells, as firing would, then save.
			if (timer == 1) p.TakeInventory("Shell", 3);
			if (timer == 70) { Report("after spending 3 shells"); phase = 7; timer = 0; }
			break;
		case 40: // The area level arrives, and every placed ammo pickup has rolled a tier.
		{
			let tiers = DoomerfallAmmoTiers.Get();
			if (timer > LIMIT) { Finish("no area level"); break; }
			if (!tiers || tiers.areaLevel < 0 || timer < 35) break;
			TierCensus("placed", tiers.areaLevel);
			RollStats();
			Next();
			break;
		}
		case 41: // A plain box of bullets dropped away from the player becomes one tiered drop. A grid of boxes shows jackpots.
			dropSpot = p.Vec3Angle(160, p.angle);
			Actor.Spawn("ClipBox", dropSpot, NO_REPLACE);
			for (int i = 0; i < 300; i++)
				Actor.Spawn("ClipBox", p.pos + (4000 + (i % 20) * 40, 4000 + (i / 20) * 40, 0), NO_REPLACE);
			Next();
			break;
		case 42:
		{
			if (timer < 5) break;
			Actor near = null, plain = null;
			Actor mo;
			let it = ThinkerIterator.Create("Inventory");
			while (mo = Actor(it.Next()))
			{
				if (Inventory(mo).Owner || (mo.pos.xy - dropSpot.xy).Length() > 32) continue;
				if (mo is "DoomerfallAmmoPickup") near = mo; else if (mo is "ClipBox") plain = mo;
			}
			Console.Printf("AMTIER drop %s amount %d, plain box left: %s", near ? String.Format("%s", near.GetClassName()) : "none", near ? Inventory(near).Amount : 0, plain ? "yes" : "no");
			TierCensus("after drops", DoomerfallAmmoTiers.Get().areaLevel);
			Next();
			break;
		}
		case 43: // Touch Silver bullets, Regular bullets, and Daedric shells. Only Regular (the loaded tier) reaches Doom.
		{
			static const String TOUCH[] = { "DFAmmo_Clip_2", "DFAmmo_Clip_0", "DFAmmo_Shell_9" };
			Report("before tier pickups");
			for (int i = 0; i < TOUCH.Size(); i++)
			{
				let item = Inventory(Actor.Spawn(TOUCH[i], p.pos, NO_REPLACE));
				if (item) { Console.Printf("AMTIER touch %s x%d", TOUCH[i], item.Amount); item.Touch(p); }
			}
			Next();
			break;
		}
		case 44:
			if (timer == 140) { Report("after tier pickups"); phase = 7; timer = 0; }
			break;
		case SAVED:
			if (timer > 35 * 8) Finish("saved");
			break;
		case 20: // Loaded: give Doom's report time to reach Daggerfall.
			if (EQUIPRUN && timer == 105) { Hit("loaded"); Report("loaded"); }
			if (TIERRUN && timer == 35) TierCensus("after load", DoomerfallAmmoTiers.Get().areaLevel);
			if (TIERRUN && timer == 35 * 19) TierCensus("end of load run", DoomerfallAmmoTiers.Get().areaLevel);
			if (timer == 35 * (EQUIPRUN ? 6 : 20)) Finish("loaded"); // Long enough for Daggerfall's hook, window test included, to run again.
			break;
		}
	}
}
