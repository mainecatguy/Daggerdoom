version "4.14"

// Weapon hotkeys, on the real dungeon with DRLA. Hotkey presses go through the engine's hotkey path as
// dd_hotkey:<key>:<modifier> network events (the same SendHotkey a slot key uses). Daggerfall's -dfhotkeystest puts
// each new gun on the first free key from 3, standing in for the popup.
class HKHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 20;
	const LOADRUN = @LOADRUN@;
	const SAVED = 10; // The phase the autosave is made in. A load run that reaches it has loaded.

	int phase, timer, step, passed, failed;
	String startGun; // DRLA X picks the starting gun, so the test reads it.
	int startRounds;

	bool Has(PlayerPawn p, String cls) { class<Inventory> c = cls; return c && p.FindInventory(c) != null; }
	int Rounds(PlayerPawn p, String gun) { class<Inventory> c = gun .. "Clip"; return c ? p.CountInv(c) : -1; }
	void SetRounds(PlayerPawn p, String gun, int n) { class<Inventory> c = gun .. "Clip"; if (c) p.SetInventory(c, n); }
	bool done;
	Actor item;
	vector3 home;
	vector2 ahead;

	void Finish()
	{
		Console.Printf("HKRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("HKDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("HKCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void Next() { phase++; timer = 0; step = 0; }

	String Held(PlayerPawn p)
	{
		String s = "";
		String ready = "none";
		if (p.player.ReadyWeapon) ready = p.player.ReadyWeapon.GetClassName();
		for (Inventory i = p.Inv; i; i = i.Inv)
			if (i is "Weapon") s = s .. i.GetClassName() .. " ";
		return String.Format("weapons [%s] ready %s, %sClip %d, RLShotgunClip %d, RLWeaponLimit %d", s,
			ready, startGun, Rounds(p, startGun), p.CountInv("RLShotgunClip"), p.CountInv("RLWeaponLimit"));
	}

	void PressUse(PlayerPawn p)
	{
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	void FindClearSpot(PlayerPawn p)
	{
		home = p.pos;
		for (int a = 0; a < 360; a += 45)
		{
			FLineTraceData t;
			if (!p.LineTrace(a, 96, 0, TRF_THRUACTORS, 16, 0, 0, t) || t.HitType == TRACE_HitNone)
			{
				p.angle = a;
				break;
			}
		}
		ahead = (cos(p.angle), sin(p.angle));
		p.pitch = 0;
	}

	void GoHome(PlayerPawn p)
	{
		p.SetOrigin(home, false);
		p.vel = (0, 0, 0);
		p.angle = atan2(ahead.y, ahead.x);
		p.pitch = 0;
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

	// Presses a hotkey at tic 1 and returns true at tic 70, when the swap has had time to finish.
	bool Hotkey(int key)
	{
		if (timer == 1)
		{
			Console.Printf("HKPRESS key %d", key);
			EventHandler.SendNetworkEvent(String.Format("dd_hotkey:%d:0", key));
		}
		return timer == 70;
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
		if (LOADRUN && phase == SAVED) { phase = 20; timer = 0; passed = failed = 0; }
		if (LOADRUN && phase < SAVED) return;

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
			if (timer > LIMIT) { Report(false, "Daggerfall never listed this space"); Finish(); break; }
			if (!inside || !AnyPile() || timer < 35) break;
			RemoveMonsters();
			FindClearSpot(p);
			Next();
			break;
		case 2: // Daggerfall has adopted the starting pistol and left it in Doom as the active gun.
			if (timer < 105) break;
			if (p.player.ReadyWeapon) startGun = p.player.ReadyWeapon.GetClassName();
			Console.Printf("HKSTATE start: %s", Held(p));
			Report(startGun != "" && startGun != "RLShotgun" && p.CountInv("RLWeaponLimit") == 1, "Doom keeps its starting gun " .. startGun .. " as the only gun");
			{
				// One round short of full when the magazine holds more than one, else empty. Either way a reload would show.
				class<Inventory> c = startGun .. "Clip";
				int most = c ? GetDefaultByType(c).MaxAmount : 0;
				startRounds = most > 1 ? most - 1 : 0;
				SetRounds(p, startGun, startRounds);
			}
			Next();
			break;
		case 3: // Key 3 (the shotgun's Doom slot) has no hotkeys, so taking the shotgun puts it there and draws it at once.
			if (!Take(p, "RLShotgunPickup", 0)) break;
			Console.Printf("HKSTATE took shotgun: %s", Held(p));
			Report(!item || !item.bSPECIAL, "Use took the shotgun off the floor");
			Report(Has(p, "RLShotgun") && !Has(p, startGun) && p.CountInv("RLWeaponLimit") == 1, "key 3 was free, so the shotgun is drawn at once and the start gun put away");
			Report(Rounds(p, startGun) == 0, "the start gun's magazine left with it");
			SetRounds(p, "RLShotgun", 0); // Empty: it must still be empty when it comes back.
			Next();
			break;
		case 4: // Key 2 brings the start gun back, not reloaded.
			if (!Hotkey(2)) break;
			Console.Printf("HKSTATE key 2: %s", Held(p));
			Report(Has(p, startGun) && !Has(p, "RLShotgun"), "key 2 swaps back to the start gun");
			Report(Rounds(p, startGun) == startRounds, String.Format("the start gun's magazine is still %d", startRounds));
			Next();
			break;
		case 5: // A modded pistol. Key 2 already has a hotkey, so it only goes to Daggerfall's inventory (the test puts it on key 4).
			if (!Take(p, "RLPistolPickupModded", 1)) break;
			Console.Printf("HKSTATE took modded pistol: %s", Held(p));
			Report(Has(p, startGun) && p.CountInv("RLPistolPowerMod") == 0, "key 2 had a hotkey, so the modded pistol is not drawn and Doom gets no mods");
			Next();
			break;
		case 6: // Armor goes to Daggerfall's Weapons & Armor tab; the Python side checks the stored names.
			if (!Take(p, "GreenArmor", 0)) break;
			Next();
			break;
		case 7:
			if (!Take(p, "RLGenericArmorPickup", 0)) break;
			Next();
			break;
		case 8: // Key 4 draws the modded pistol with the mods it was found with.
			if (!Hotkey(4)) break;
			Console.Printf("HKSTATE key 4: %s, RLPistolPowerMod %d, RLPistolModLimit %d", Held(p), p.CountInv("RLPistolPowerMod"), p.CountInv("RLPistolModLimit"));
			Report(Has(p, "RLPistol") && p.CountInv("RLPistolPowerMod") == 2 && p.CountInv("RLPistolModLimit") == 2, "the modded pistol keeps its mods (power 2, limit 2)");
			Next();
			break;
		case 9:
			if (!Hotkey(3)) break;
			Console.Printf("HKSTATE key 3 again: %s", Held(p));
			Report(Has(p, "RLShotgun") && p.CountInv("RLShotgunClip") == 0 && p.CountInv("RLPistolPowerMod") == 0, "the shotgun comes back still empty, and the pistol's mods left with the pistol");
			Console.Printf("HKSAVE autosave");
			LevelLocals.MakeAutoSave();
			Next();
			break;
		case SAVED:
			if (timer > 35 * 8) Finish();
			break;
		case 20: // After the load: the shotgun is active; the pistol's magazine lives only in Daggerfall's save.
			if (timer == 70)
			{
				Console.Printf("HKSTATE after load: %s", Held(p));
				Report(Has(p, "RLShotgun") && !Has(p, startGun) && p.CountInv("RLShotgunClip") == 0, "after the load Doom holds only the shotgun, still empty");
				timer = 100;
				phase = 21;
			}
			break;
		case 21:
			if (timer == 101) { Console.Printf("HKPRESS key 2"); EventHandler.SendNetworkEvent("dd_hotkey:2:0"); }
			if (timer < 170) break;
			Console.Printf("HKSTATE after load, key 2: %s", Held(p));
			Report(Has(p, startGun) && !Has(p, "RLShotgun") && Rounds(p, startGun) == startRounds, String.Format("key 2 still draws %s, with its magazine of %d from Daggerfall's save", startGun, startRounds));
			timer = 200;
			phase = 22;
			break;
		case 22:
			if (timer == 201) { Console.Printf("HKPRESS key 4"); EventHandler.SendNetworkEvent("dd_hotkey:4:0"); }
			if (timer < 270) break;
			Console.Printf("HKSTATE after load, key 4: %s, RLPistolPowerMod %d", Held(p), p.CountInv("RLPistolPowerMod"));
			Report(Has(p, "RLPistol") && p.CountInv("RLPistolPowerMod") == 2 && p.CountInv("RLPistolModLimit") == 2, "after the load key 4 draws the modded pistol with its mods from Daggerfall's save");
			Finish();
			break;
		}
	}

	// Spawns a pickup ahead, waits for it to land, presses Use, and returns true 70 tics later. With mods, the pickup
	// carries pistol mods as its own inventory, as DRLA's GetWeaponMods gives a dropped modded gun.
	bool Take(PlayerPawn p, String cls, int mods)
	{
		switch (step)
		{
		case 0:
			GoHome(p);
			item = Actor.Spawn(cls, (home.xy + ahead * 48, home.z), NO_REPLACE);
			if (item && mods) { item.SetInventory("RLPistolPowerMod", 2); item.SetInventory("RLPistolModLimit", 2); }
			Console.Printf("HKSPAWN %s", cls);
			timer = 0;
			step = 1;
			break;
		case 1: // DRLA items only become pickups after landing.
			if (!item) { Report(false, cls .. " vanished at spawn"); Finish(); break; }
			if (item.bSPECIAL && timer > 8) { GoHome(p); timer = 0; step = 2; }
			else if (timer > 70) { Report(false, cls .. " never became a pickup"); Finish(); }
			break;
		case 2:
			if (timer == 3) PressUse(p);
			if (timer >= 70) return true;
			break;
		}
		return false;
	}
}
