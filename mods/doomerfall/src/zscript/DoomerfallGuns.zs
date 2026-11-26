// Weapon hotkeys. Daggerfall holds every gun the player owns and the hotkey table. Doom holds only the active gun.
// The engine (dd_items.cpp) turns Daggerfall's bridge events into these network events, and this handler's
// "dfg_out:" events back into bridge events. Nothing here runs unless Daggerfall sends a gun event.
//
//   dfg_state:<request>:<amount>:<class>  one state line of the gun the next dfg_equip gives
//   dfg_equip:<request>:<flags>:<pickup>  take every gun and give this one; flags 1 keep the ready gun, 2 give nothing
//   dfg_drop:<request>:<flags>:<pickup>   Daggerfall's inventory window dropped this Doom item: spawn its pickup in front
//                                         of the player, carrying the gun's dfg_state lines (flags 0x200: the gun Doom
//                                         holds, whose live state goes instead); answers dfg_out:dropped
//
// A gun's state is its per-class inventory, every item named <Weapon>... (DRLA's RL<Weapon>Clip magazine,
// <Weapon>ModLimit, and its mods). It leaves Doom with the gun and comes back with it, so swapping never reloads.
class DoomerfallGuns : EventHandler
{
	const FlagAdopt = 1;
	const FlagClear = 2;
	const FlagSelect = 3;
	const Taken = 0;   // DFB_ITEM_TAKEN
	const Refused = 4; // DFB_ITEM_REFUSED

	Array<String> stateNames;
	Array<int> stateAmounts;
	int stateRequest;

	// Items leave the player only by Daggerfall's inventory window. Doom's drops are blocked in d_net.cpp, and DRLA's
	// "Drop Item" key (Zoom: guns, the Technician's scrap, mod packs, armor) in g_game.cpp. M's backpack toss ("use
	// RLSpecialItemDropper") fails here: the dropper is kept at 0.
	override void WorldTick()
	{
		static const String dropper[] = { "RLSpecialItemDropper" };
		class<Inventory> c = dropper[0];
		if (c && consoleplayer >= 0 && players[consoleplayer].mo) players[consoleplayer].mo.TakeInventory(c, 999);
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(4) != "dfg_" || e.Name.Left(8) == "dfg_out:") return;
		Array<String> f;
		e.Name.Split(f, ":");
		let mo = players[e.Player].mo;
		if (f[0] == "dfg_state" && f.Size() >= 4)
		{
			int request = f[1].ToInt();
			if (request != stateRequest) { stateNames.Clear(); stateAmounts.Clear(); stateRequest = request; }
			stateNames.Push(f[3]);
			stateAmounts.Push(f[2].ToInt());
		}
		else if (f[0] == "dfg_equip" && f.Size() >= 4) Equip(mo, f[1].ToInt(), f[2].ToInt(), f[3]);
		else if (f[0] == "dfg_drop" && f.Size() >= 4) Drop(mo, f[1].ToInt(), f[2].ToInt(), f[3]);
	}

	// A DRLA gun with any mod on it drops as its ...PickupModded class, which shows the mods and hands them over.
	static bool Modded(Array<String> names, Array<int> amounts)
	{
		static const String mods[] = { "ModLimit", "PowerMod", "BulkMod", "AgilityMod", "TechnicalMod", "SniperMod", "FirestormMod", "NanoMod", "DemonArtifacts" };
		for (int j = 0; j < names.Size(); j++)
			for (int m = 0; m < mods.Size(); m++)
				if (amounts[j] > 0 && EndsWith(names[j], mods[m])) return true;
		return false;
	}

	void Drop(PlayerPawn mo, int request, int flags, String cls)
	{
		Array<String> names;
		Array<int> amounts;
		if (request == stateRequest)
		{
			names.Copy(stateNames);
			amounts.Copy(stateAmounts);
		}
		stateNames.Clear();
		stateAmounts.Clear();
		stateRequest = 0;
		if (!mo || mo.health <= 0)
		{
			Tell("dropped", request, Refused, cls);
			return;
		}
		// The gun in Doom's hands: its live magazine and mods, and it leaves the hands.
		class<Weapon> wcls = WeaponFor(cls);
		let held = (flags & 0x200) && wcls ? Weapon(mo.FindInventory(wcls)) : null;
		if (held)
		{
			// Daggerfall's material line stays (DoomerfallGunMaterial); the gun's live state replaces the rest.
			int material = names.Find("DoomerfallGunMaterial");
			int materialAmount = material < names.Size() ? amounts[material] : 0;
			names.Clear();
			amounts.Clear();
			if (materialAmount > 0) { names.Push("DoomerfallGunMaterial"); amounts.Push(materialAmount); }
			String n = held.GetClassName();
			Array<Inventory> extras;
			for (Inventory i = mo.Inv; i; i = i.Inv)
			{
				if (i is "Weapon") continue;
				String name = i.GetClassName();
				if (name.Length() <= n.Length() || name.Left(n.Length()) != n || EndsWith(name, "TypeWeapon")) continue;
				extras.Push(i);
			}
			for (int j = 0; j < extras.Size(); j++)
			{
				let x = extras[j];
				if (!x) continue;
				String name = x.GetClassName();
				if (x.Amount > 0 && !EndsWith(name, "Selected")) { names.Push(name); amounts.Push(x.Amount); }
				mo.TakeInventory((class<Inventory>)(x.GetClass()), 0x7fffffff);
			}
			if (mo.player && mo.player.ReadyWeapon == held)
			{
				String deselectName = "RLDeselectionFunction";
				class<Inventory> deselect = deselectName;
				if (deselect) mo.GiveInventory(deselect, 1);
			}
			mo.TakeInventory((class<Inventory>)(held.GetClass()), 0x7fffffff);
		}
		String spawnName = cls;
		if (EndsWith(spawnName, "Modded")) spawnName = spawnName.Left(spawnName.Length() - 6);
		if (Modded(names, amounts))
		{
			class<Actor> modded = spawnName .. "Modded";
			if (modded) spawnName = spawnName .. "Modded";
		}
		class<Actor> spawnCls = spawnName;
		Actor pickup = spawnCls ? Actor.Spawn(spawnCls, mo.Vec3Angle(24, mo.angle, 32)) : null;
		if (!pickup)
		{
			Tell("dropped", request, Refused, cls);
			return;
		}
		pickup.bDropped = true;
		pickup.angle = mo.angle;
		pickup.vel = (Actor.AngleToVector(mo.angle, 4), 2) + mo.vel;
		for (int j = 0; j < names.Size(); j++)
		{
			class<Inventory> c = names[j];
			if (!c || amounts[j] <= 0) continue;
			let inv = pickup.GiveInventoryType(c);
			if (inv) inv.Amount = amounts[j];
		}
		Console.Printf("dfg drop: %s as %s carrying %d state lines%s", cls, spawnName, names.Size(), held ? " (from Doom's hands)" : "");
		Tell("dropped", request, Taken, spawnName);
	}

	static void Tell(String word, int request, int status, String cls)
	{
		EventHandler.SendNetworkEvent(String.Format("dfg_out:%s:%d:%d:%s", word, request, status, cls));
	}

	static bool EndsWith(String s, String tail)
	{
		return s.Length() >= tail.Length() && s.Mid(s.Length() - tail.Length()) == tail;
	}

	// The weapon a world pickup gives: the pickup itself (stock Doom), or DRLA's RL<Weapon>Pickup[Modded] naming.
	static class<Weapon> WeaponFor(String pickup)
	{
		class<Actor> c = pickup;
		class<Weapon> w = (class<Weapon>)(c);
		if (w) return w;
		String base = pickup;
		if (EndsWith(base, "PickupModded")) base = base.Left(base.Length() - 12);
		else if (EndsWith(base, "Pickup")) base = base.Left(base.Length() - 6);
		else return null;
		c = base;
		return (class<Weapon>)(c);
	}

	// The world pickup Daggerfall names a held gun by, or "" for a weapon that is not a gun Daggerfall can hold
	// (fists and other weapons with no pickup and no world sprite stay in Doom).
	static String PickupFor(Weapon w)
	{
		String n = w.GetClassName();
		class<Actor> p = n .. "Pickup";
		if (p) return n .. "Pickup";
		let def = GetDefaultByType((class<Actor>)(w.GetClass()));
		State s = def.SpawnState;
		if (s && s.sprite != Actor.GetSpriteIndex('TNT1')) return n;
		return "";
	}

	static void SetAmount(Actor mo, class<Inventory> c, int amount)
	{
		if (!c) return;
		if (amount <= 0) { mo.TakeInventory(c, 0x7fffffff); return; }
		let item = mo.FindInventory(c);
		if (!item)
		{
			mo.GiveInventory(c, 1);
			item = mo.FindInventory(c);
			if (!item) return;
		}
		item.Amount = amount;
	}

	// Takes one gun and its state away, reporting both to Daggerfall.
	static void Stash(Actor mo, Weapon w, int request, bool wasReady)
	{
		String n = w.GetClassName();
		Array<Inventory> extras;
		for (Inventory i = mo.Inv; i; i = i.Inv)
		{
			if (i is "Weapon") continue;
			String name = i.GetClassName();
			if (name.Length() <= n.Length() || name.Left(n.Length()) != n) continue;
			if (EndsWith(name, "TypeWeapon")) continue; // DRLA's weapon family token, shared by every pistol and so on.
			extras.Push(i);
		}
		for (int j = 0; j < extras.Size(); j++)
		{
			let x = extras[j];
			if (!x) continue;
			String name = x.GetClassName();
			if (x.Amount > 0 && !EndsWith(name, "Selected")) Tell("state", request, x.Amount, name);
			mo.TakeInventory((class<Inventory>)(x.GetClass()), 0x7fffffff);
		}
		if (wasReady)
		{
			String deselectName = "RLDeselectionFunction"; // What DRLA runs when a weapon is lowered. Looked up at run time.
			class<Inventory> deselect = deselectName;
			if (deselect) mo.GiveInventory(deselect, 1);
		}
		String pickup = PickupFor(w);
		mo.TakeInventory((class<Inventory>)(w.GetClass()), 0x7fffffff);
		Tell("stashed", request, 0, pickup);
	}

	void Equip(PlayerPawn mo, int request, int flags, String pickup)
	{
		class<Weapon> want = null;
		if (flags == 0 || flags == FlagSelect) want = WeaponFor(pickup);
		if (!mo || !mo.player || mo.health <= 0 || ((flags == 0 || flags == FlagSelect) && !want))
		{
			Tell("done", request, Refused, pickup);
			return;
		}
		Weapon ready = mo.player.ReadyWeapon;
		if (flags == FlagSelect)
		{
			// The active gun is already here, perhaps lowered for the fists. Raise it.
			class<Weapon> held = WeaponFor(pickup);
			let w = held ? Weapon(mo.FindInventory(held)) : null;
			if (w && w != ready) mo.player.PendingWeapon = w;
			Tell("done", request, w ? Taken : Refused, pickup);
			return;
		}
		Array<Weapon> guns;
		for (Inventory i = mo.Inv; i; i = i.Inv)
		{
			let w = Weapon(i);
			if (w && PickupFor(w) != "") guns.Push(w);
		}
		bool kept = false;
		for (int j = 0; j < guns.Size(); j++)
		{
			let w = guns[j];
			if (!w) continue;
			if (flags == FlagAdopt && !kept && w == ready)
			{
				kept = true;
				Tell("kept", request, 0, PickupFor(w));
				continue;
			}
			Stash(mo, w, request, w == ready);
		}
		bool ok = flags != 0;
		if (want)
		{
			// Giving a weapon also gives its ammo. Put the ammo back as it was.
			let def = GetDefaultByType(want);
			class<Inventory> a1 = def.AmmoType1, a2 = def.AmmoType2;
			int n1 = a1 ? mo.CountInv(a1) : 0, n2 = a2 ? mo.CountInv(a2) : 0;
			mo.GiveInventory(want, 1);
			SetAmount(mo, a1, n1);
			if (a2 != a1) SetAmount(mo, a2, n2);
			if (request == stateRequest)
				for (int j = 0; j < stateNames.Size(); j++)
				{
					class<Inventory> c = stateNames[j];
					SetAmount(mo, c, stateAmounts[j]);
				}
			let w = Weapon(mo.FindInventory(want));
			if (w)
			{
				ok = true;
				mo.player.PendingWeapon = w;
				if (!mo.player.ReadyWeapon) mo.BringUpWeapon();
			}
		}
		// DRLA counts carried weapons. Doom now carries only the active gun.
		String limitName = "RLWeaponLimit"; // Looked up at run time: only DRLA has it.
		class<Inventory> limit = limitName;
		if (limit)
		{
			int held = 0;
			for (Inventory i = mo.Inv; i; i = i.Inv)
			{
				let w = Weapon(i);
				if (w && PickupFor(w) != "") held++;
			}
			SetAmount(mo, limit, held);
		}
		stateNames.Clear();
		stateAmounts.Clear();
		stateRequest = 0;
		Tell("done", request, ok ? Taken : Refused, pickup);
	}
}

// The Daggerfall material of a gun dropped from Daggerfall's inventory, carried by its pickup as material + 1, so taking
// it back gives the same material and the look label can show it (dd_items.cpp, dd_look.cpp). Only Daggerfall sets it.
class DoomerfallGunMaterial : Inventory
{
	Default
	{
		Inventory.MaxAmount 16;
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
	}
}
