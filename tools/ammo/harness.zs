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
	const CHANGERUN = @CHANGERUN@; // The change run: the change ammo key, the automatic change, and the magazine unload.
	const MATERIALRUN = @MATERIALRUN@; // The material run: an Iron and a Daedric copy of one gun scale damage by their material.
	const SIZERUN = @SIZERUN@; // The sizes run: each pickup size, and monster drops, give Doom's amounts in both games.
	const SHOPRUN = @SHOPRUN@; // The shop run: Daggerfall buys a general store's ammo (-dfshopammotest), Doom fires it.
	const SAVED = 10;
	vector3 dropSpot;
	Actor lookItem;
	Array<Inventory> sized;
	Array<String> sizedWhat;
	Array<Actor> victims;
	int touchIndex;
	int shopClip, shopCell, buttons;

	// A spot whose seeded roll (DoomerfallAmmoTiers.Convert) gives this tier, and no jackpot.
	vector3 SpotFor(int type, int want, int k)
	{
		let p = players[0].mo;
		int lvl = DoomerfallAmmoTiers.Get().areaLevel;
		for (int j = 0; j < 2000; j++)
		{
			vector3 at = p.pos + (96 + k * 48, (j % 40) * 16 - 320, (j / 40) * 16);
			int seed = DoomerfallAmmoTiers.Seed(at, type);
			if (DoomerfallAmmoTiers.Unit(seed, 1) < DoomerfallAmmoTiers.JackpotChance) continue;
			if (DoomerfallAmmoTiers.RollTier(lvl, DoomerfallAmmoTiers.Unit(seed, 3), DoomerfallAmmoTiers.Unit(seed, 4)) == want) return at;
		}
		return (0, 0, 0);
	}

	static Inventory PickupNear(vector3 at, double range, Array<Inventory> skip)
	{
		Actor mo;
		Inventory best = null;
		double bestD = range;
		let it = ThinkerIterator.Create("DoomerfallAmmoPickup");
		while (mo = Actor(it.Next()))
		{
			let inv = Inventory(mo);
			if (inv.Owner || skip.Find(inv) != skip.Size()) continue;
			double d = (mo.pos.xy - at.xy).Length();
			if (d < bestD) { bestD = d; best = inv; }
		}
		return best;
	}

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
	void Hit(String label, int damage = 10)
	{
		let p = players[0].mo;
		let w = players[0].ReadyWeapon;
		String ammo = "none";
		if (w) { ammo = ReserveOf(w.AmmoType1); if (ammo == "none") ammo = ReserveOf(w.AmmoType2); }
		let t = Actor.Spawn("Cyberdemon", p.Vec3Angle(200, p.angle), NO_REPLACE);
		if (!t) { Console.Printf("AMHIT %s no target", label); return; }
		int before = t.health;
		t.DamageMobj(null, p, damage, 'None');
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

	void Magazine(String why)
	{
		Console.Printf("AMMAG %s RLPistolClip=%d ready=%s", why, players[0].mo.CountInv("RLPistolClip"), players[0].ReadyWeapon ? String.Format("%s", players[0].ReadyWeapon.GetClassName()) : "none");
	}

	// One line per change of what the ready gun is doing after a change ammo key: its state (reload, down, up, ready,
	// other), whether it can fire, its magazine, and its reserve. ammo.py checks that the new tier fires only after it.
	String watched;
	void Watch(String label)
	{
		let w = players[0].ReadyWeapon;
		let psp = players[0].FindPSprite(PSP_WEAPON);
		String st = "none", mag = "none", reserve = "none";
		int magCount = -1;
		if (w && psp)
		{
			st = "other";
			State reload = w.FindState("Reload");
			if (reload && Actor.InStateSequence(psp.CurState, reload)) st = "reload";
			else if (Actor.InStateSequence(psp.CurState, w.GetDownState())) st = "down";
			else if (Actor.InStateSequence(psp.CurState, w.GetUpState())) st = "up";
			else if (Actor.InStateSequence(psp.CurState, w.GetReadyState())) st = "ready";
			reserve = ReserveOf(w.AmmoType1);
			if (reserve == "none") reserve = ReserveOf(w.AmmoType2);
			if (w.AmmoType1 && ReserveOf(w.AmmoType1) == "none") { mag = w.AmmoType1.GetClassName(); magCount = players[0].mo.CountInv(w.AmmoType1); }
		}
		class<Inventory> rc = reserve;
		String line = String.Format("%s gun=%s state=%s fire=%d mag=%d reserve=%s:%d", label, w ? String.Format("%s", w.GetClassName()) : "none", st,
			(players[0].WeaponState & WF_WEAPONREADY) ? 1 : 0, magCount, reserve, rc ? players[0].mo.CountInv(rc) : -1);
		if (line == watched) return;
		watched = line;
		Console.Printf("AMRELOAD %s tic=%d", line, timer);
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
		// Holding fire: the player's own fire routine, as the attack button calls it, each tic the gun is ready.
		if (SHOPRUN && buttons && (players[0].WeaponState & WF_WEAPONREADY) && PlayerPawn(players[0].mo)) PlayerPawn(players[0].mo).FireWeapon(null);
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
			if (CHANGERUN) phase = 50;
			if (MATERIALRUN) phase = 80;
			if (SIZERUN) phase = 90;
			if (SHOPRUN) phase = 110;
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
		case 44: // Meanwhile a Regular, then a Silver clip lies just ahead, out of touch reach, for the look label ("look:" in the log).
			if (timer == 20 || timer == 70)
			{
				if (lookItem) lookItem.Destroy();
				lookItem = Actor.Spawn(timer == 20 ? "DFAmmo_Clip_0" : "DFAmmo_Clip_2", p.Vec3Angle(56, p.angle), NO_REPLACE);
				Console.Printf("AMLOOK %s ahead", lookItem ? lookItem.GetClassName() : 'none');
			}
			if (timer == 120 && lookItem) lookItem.Destroy();
			if (timer == 140) { Report("after tier pickups"); phase = 7; timer = 0; }
			break;
		case 50: // Daggerfall's test hook (-dfchangeammotest) adds tiered bullets and a DRLA pistol on key 4.
			if (timer == 35 * 6) EventHandler.SendNetworkEvent("dd_hotkey:4");
			if (timer == 35 * 10) { Report("pistol up"); Magazine("pistol up"); Hit("regular"); Next(); }
			break;
		case 51: // The change ammo key: the magazine goes back to Daggerfall, and Steel loads.
			if (timer == 1) EventHandler.SendNetworkEvent("df_change_ammo");
			if (timer == 105) { Report("after change"); Magazine("after change"); Hit("steel"); Next(); }
			break;
		case 52: // Spend every loaded round, the magazine the change's reload filled included: the next tier (Silver) loads by itself.
			if (timer == 1) { p.TakeInventory("Clip", p.CountInv("Clip")); p.TakeInventory("RLPistolClip", p.CountInv("RLPistolClip")); }
			if (timer == 140) { Report("after running dry"); Magazine("after running dry"); Hit("automatic"); Next(); }
			break;
		case 53: // Each gun remembers its own tier: the starting gun on key 2 loads its own (Regular, or no bullets at all).
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:2");
			if (timer == 175) { Report("starting gun"); Hit("other gun"); Next(); }
			break;
		case 54: // Back to the pistol on key 4: Silver again.
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:4");
			if (timer == 175) { Report("pistol again"); Magazine("pistol again"); Hit("pistol again"); Next(); }
			break;
		// The material run (-dfmaterialtest): Daggerfall adds an Iron Shotgun on key 3 and a Daedric one on key 4, and gives
		// shells a stand-in +25%. Hits are 1000, so the bridge's integer damage shows the ratio exactly.
		case 80:
			if (timer == 35 * 4) Hit("start gun", 1000); // DRLA X's starting gun, often the Blaster (no reserve ammo): its own material.
			if (timer == 35 * 5) EventHandler.SendNetworkEvent("dd_hotkey:3");
			if (timer == 35 * 12) { Hit("iron", 1000); Next(); } // Waits are long: a busy machine runs Daggerfall at about 1 fps.
			break;
		case 81:
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:4");
			if (timer == 245) { Hit("daedric", 1000); Next(); }
			break;
		case 82:
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:3");
			if (timer == 245) { Hit("iron again", 1000); Next(); }
			break;
		case 83: // Fists have no material: no bonus at all.
			if (timer == 1) SelectMelee(p);
			if (timer == 105) { Hit("melee", 1000); phase = 85; timer = 0; }
			break;
		case 85: // An Ebony Blaster: no reserve ammo, but a gun, so it gets its material bonus.
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:5");
			if (timer == 245) { Hit("blaster", 1000); phase = 84; timer = 0; }
			break;
		case 84:
			if (timer == 1) EventHandler.SendNetworkEvent("dd_hotkey:4");
			if (timer == 245) { Hit("daedric again", 1000); Report("daedric up"); phase = 7; timer = 0; }
			break;
		// The reload checks: each gun is raised by its hotkey, then the change ammo key; Watch logs every tic that differs.
		case 55: case 57: case 59: case 61:
		{
			static const String KEYS[] = { "dd_hotkey:5", "dd_hotkey:6", "dd_hotkey:7", "dd_hotkey:4" };
			int k = (phase - 55) / 2;
			if (timer == 1) EventHandler.SendNetworkEvent(KEYS[k]);
			if (timer == 175)
			{
				Report(String.Format("raised %s", KEYS[k]));
				watched = "";
				Watch(String.Format("change%d before", k));
				if (k == 3) { phase = 7; timer = 0; } else Next();
			}
			break;
		}
		case 56: case 58: case 60:
		{
			int k = (phase - 56) / 2;
			if (timer == 1) EventHandler.SendNetworkEvent("df_change_ammo");
			Watch(String.Format("change%d", k));
			if (timer == 175) { Report(String.Format("after change%d", k)); Next(); }
			break;
		}
		// The sizes run: plain pickups of every size, placed where they roll Regular, Silver, or Ebony (every tier gives
		// the same amount), and DRLA zombies killed for their drops. Each converted pickup is touched alone; ammo.py checks
		// Daggerfall's "picked up" line and Doom's counter against Doom's amounts.
		case 90:
		{
			let tiers = DoomerfallAmmoTiers.Get();
			if (timer > LIMIT) { Finish("no area level"); break; }
			if (!tiers || tiers.areaLevel < 0 || timer < 35) break;
			// Every size at Regular, two at Silver, and every size again at Ebony, the highest tier an area level 1 rolls.
			static const String PLAIN[] = { "Clip", "ClipBox", "Shell", "ShellBox", "RocketAmmo", "RocketBox", "Cell", "CellPack", "ClipBox", "RocketAmmo",
				"Clip", "ClipBox", "Shell", "ShellBox", "RocketAmmo", "RocketBox", "Cell", "CellPack" };
			static const int TYPES[] = { 0, 0, 1, 1, 2, 2, 3, 3, 0, 2, 0, 0, 1, 1, 2, 2, 3, 3 };
			static const int WANT[] = { 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 8, 8, 8, 8, 8, 8, 8, 8 };
			for (int k = 0; k < PLAIN.Size(); k++)
			{
				vector3 at = SpotFor(TYPES[k], WANT[k], k);
				if (at == (0, 0, 0)) { Console.Printf("AMSIZE no spot for %s tier %d", PLAIN[k], WANT[k]); continue; }
				Actor.Spawn(PLAIN[k], at, NO_REPLACE);
				sized.Push(null);
				sizedWhat.Push(String.Format("%s %.0f %.0f %.0f", PLAIN[k], at.x, at.y, at.z));
			}
			// Drops: these script-spawned zombies count as summoned, and summoned monsters drop nothing (owner rule,
			// dd_lootrng.cpp), so every size is also tossed as Doom's drop code does it (TOSSED, set before the converter
			// judges it a tic later), at Regular and at Ebony.
			for (int k = 0; k < 16; k++)
			{
				int j = k % 8, want = k < 8 ? 0 : 8;
				vector3 at = SpotFor(TYPES[j], want, PLAIN.Size() + k);
				if (at == (0, 0, 0)) { Console.Printf("AMSIZE no spot for tossed %s tier %d", PLAIN[j], want); continue; }
				let t = Inventory(Actor.Spawn(PLAIN[j], at, NO_REPLACE));
				if (t) t.bTOSSED = true;
				sized.Push(null);
				sizedWhat.Push(String.Format("%s %.0f %.0f %.0f tossed", PLAIN[j], at.x, at.y, at.z));
			}
			for (int i = 0; i < 10; i++)
			{
				// Eight stock Zombiemen (their clip drop goes through DRLA's RLClipSpawner), two of DRLA's replacements.
				// Spaced so each drop lands nearest its own corpse.
				let z = Actor.Spawn("Zombieman", p.pos + (-200 - i * 96, 0, 0), i < 8 ? NO_REPLACE : ALLOW_REPLACE);
				if (z) victims.Push(z);
			}
			Console.Printf("AMSIZE level %d, %d plain pickups, %d zombies (%s)", tiers.areaLevel, sizedWhat.Size(), victims.Size(),
				victims.Size() ? String.Format("%s", victims[0].GetClassName()) : "none");
			Next();
			break;
		}
		case 91: // Find what each plain pickup became, then kill the zombies.
		{
			if (timer < 5) break;
			Array<Inventory> none;
			for (int k = 0; k < sizedWhat.Size(); k++)
			{
				Array<String> f;
				sizedWhat[k].Split(f, " ");
				sized[k] = PickupNear((f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble()), 24, none);
				let s = DoomerfallAmmoPickup(sized[k]);
				Console.Printf(f.Size() > 4 ? "AMSIZE dropped by Toss_%s -> %s tier %d amount %d type %d" : "AMSIZE placed %s -> %s tier %d amount %d type %d", f[0], s ? String.Format("%s", s.GetClassName()) : "none", s ? s.tier : -1, s ? s.Amount : 0, s ? s.ammoType : -1);
			}
			// DRLA replaces Zombieman with a spawner that removes itself: kill the monsters standing where they spawned.
			Array<Actor> spots;
			spots.Move(victims);
			Actor mo;
			let it = ThinkerIterator.Create("Actor");
			while (mo = Actor(it.Next()))
			{
				if (!mo.bISMONSTER || mo.player || mo.health <= 0) continue;
				for (int i = 0; i < 10; i++)
					if ((mo.pos.xy - (p.pos.xy + (-200 - i * 96, 0))).Length() < 24) { victims.Push(mo); break; }
			}
			Console.Printf("AMSIZE killing %d monsters (%s)", victims.Size(), victims.Size() ? String.Format("%s", victims[0].GetClassName()) : "none");
			for (int i = 0; i < victims.Size(); i++)
				victims[i].DamageMobj(null, null, 100000, 'None');
			Next();
			break;
		}
		case 92: // The drops: any tiered pickup near a corpse.
		{
			if (timer < 175) break;
			for (int i = 0; i < victims.Size(); i++)
			{
				Console.Printf("AMSIZE victim %d: %s", i, victims[i] ? String.Format("%s health %d at %.0f %.0f %.0f floor %.0f", victims[i].GetClassName(), victims[i].health, victims[i].pos.x, victims[i].pos.y, victims[i].pos.z, victims[i].floorz) : "gone");
				if (!victims[i]) continue;
				Inventory d;
				while (d = PickupNear(victims[i].pos, 44, sized))
				{
					let s = DoomerfallAmmoPickup(d);
					sized.Push(d);
					sizedWhat.Push("drop");
					Console.Printf("AMSIZE dropped by %s -> %s tier %d amount %d type %d", victims[i].GetClassName(), d.GetClassName(), s.tier, d.Amount, s.ammoType);
				}
			}
			Report("before touches");
			touchIndex = 0;
			Next();
			break;
		}
		case 93: // Touch one pickup every 70 tics, so each round trip through Daggerfall shows on its own.
			if (timer % 70 != 1) break;
			if (touchIndex > 0) Report(String.Format("after touch %d", touchIndex - 1));
			if (touchIndex >= sized.Size()) { phase = 7; timer = 0; break; }
			{
				let s = DoomerfallAmmoPickup(sized[touchIndex]);
				if (s) { Console.Printf("AMTOUCH %d %s tier %d amount %d type %d", touchIndex, s.GetClassName(), s.tier, s.Amount, s.ammoType); s.Touch(p); }
				else Console.Printf("AMTOUCH %d none", touchIndex);
			}
			touchIndex++;
			break;
		case 110: // Wait for Daggerfall's purchase of a general store's bullets and cells to reach Doom's counters.
			if (timer == 1) { shopClip = p.CountInv("Clip"); shopCell = p.CountInv("Cell"); Report("before shop purchase"); }
			if (timer > LIMIT) { Report("shop purchase never arrived"); phase = 7; timer = 0; break; }
			if (timer % 35 == 0) Report("waiting for shop purchase");
			// The purchase may land before this phase starts; the player starts with 60 bullets and no cells.
			if (p.CountInv("Clip") > 60 && p.CountInv("Cell") >= 20) { Report("after shop purchase"); Next(); }
			break;
		case 111: // Fire the bought bullets from a chaingun, then the bought cells from a plasma rifle, holding fire.
		case 112:
		{
			String gun = phase == 111 ? "Chaingun" : "PlasmaRifle";
			String ammo = phase == 111 ? "Clip" : "Cell";
			if (timer == 1)
			{
				p.GiveInventory(gun, 1);
				let w = Weapon(p.FindInventory(gun));
				if (w) players[0].PendingWeapon = w;
				Console.Printf("AMSHOP select %s: %s", gun, w ? "given" : "MISSING");
			}
			if (timer == 70) { shopClip = p.CountInv(ammo); Console.Printf("AMSHOP fire %s ready=%s %s=%d", gun, players[0].ReadyWeapon ? String.Format("%s", players[0].ReadyWeapon.GetClassName()) : "none", ammo, shopClip); buttons = BT_ATTACK; }
			if (timer == 140)
			{
				buttons = 0;
				int left = p.CountInv(ammo);
				Console.Printf("AMSHOP fired %s: %s %d -> %d, %s", gun, ammo, shopClip, left, left < shopClip ? "spent" : "NOT SPENT");
				Report(String.Format("after firing %s", gun));
				if (phase == 112) { phase = 7; timer = 0; } else Next();
			}
			break;
		}
		case SAVED:
			if (timer > 35 * 8) Finish("saved");
			break;
		case 20: // Loaded: give Doom's report time to reach Daggerfall.
			if (EQUIPRUN && timer == 105) { Hit("loaded"); Report("loaded"); }
			if (CHANGERUN && timer == 105) { Hit("loaded"); Report("loaded"); Magazine("loaded"); }
			if (MATERIALRUN && timer == 105) { Hit("loaded", 1000); Report("loaded"); }
			if (TIERRUN && timer == 35) TierCensus("after load", DoomerfallAmmoTiers.Get().areaLevel);
			if (TIERRUN && timer == 35 * 19) TierCensus("end of load run", DoomerfallAmmoTiers.Get().areaLevel);
			if (timer == 35 * (EQUIPRUN || CHANGERUN || MATERIALRUN ? 6 : 20)) Finish("loaded"); // Long enough for Daggerfall's hook, window test included, to run again.
			break;
		}
	}
}
