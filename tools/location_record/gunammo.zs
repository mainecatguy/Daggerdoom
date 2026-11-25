version "4.14"

// Gun ammo route (tools/location_record/gunammo.py). Owner rules (2026-11-24): guns never give ammo, whatever their
// source, on a first take or a retake; and a gun leaves the player only by Daggerfall's inventory window (Doom's
// weapdrop, invdrop and drop and DRLA's own weapon drop are blocked). In town, with Daggerfall's -dfgundroptest hook,
// this prints the player's Doom ammo for the gun's types (LRAMMO) at every step:
//   map take:      a gun pickup placed in front of the player (not dropped), taken with Use;
//   window x3:     Daggerfall's inventory window drops the gun (the hook), the pickup is taken back with Use;
//   blocked drops: on DRLA runs a mod pack readied for dropping and the backpack toss, while weapdrop, invdrop and a Zoom
//                  press (DRLA's Drop Item) run every second all run long (gunammo.py); the gun must stay held
//                  with nothing on the ground;
//   monster take:  a ShotgunGuy is killed and the gun it drops is taken with Use.
// Ammo for those types must not change on any take, and Daggerfall's Doom item count (df "doom items N") must rise
// only on the map and monster takes.
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, tries, cycle;
}

class MDHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 25;
	bool done, drla;
	// DRLA can swap the player's class ("Player swapped to Portia"); a copy of the route state survives it.
	int kPhase, kTimer, kTries, kCycle;
	MDState cur;
	String mapGun, weaponName, clipName;
	Actor victim;

	override void OnRegister()
	{
		drla = "@SET@" ~== "drla";
		mapGun = drla ? "RLShotgunPickup" : "Shotgun";
		weaponName = drla ? "RLShotgun" : "Shotgun";
		clipName = drla ? "RLShotgunClip" : "";
	}

	// The drop controls must be gone from the menus (Doomerfall.zs hides them once the menus exist).
	ui int menuTicks;
	override void UiTick()
	{
		if (++menuTicks == 105) Console.Printf("LRSTEP menus: InventoryControlsMenu %s; DRLAControlsMenu %s", Controls('InventoryControlsMenu', 'weapdrop', 'invdrop'), Controls('DRLAControlsMenu', '+zoom', 'rl_specialitemdropper'));
	}

	static ui String Controls(Name menu, Name a, Name b)
	{
		let d = OptionMenuDescriptor(MenuDescriptor.GetDescriptor(menu));
		if (!d) return "absent";
		int all = 0, drops = 0;
		for (int i = 0; i < d.mItems.Size(); i++)
			if (d.mItems[i] is "OptionMenuItemControlBase") { all++; if (d.mItems[i].GetAction() == a || d.mItems[i].GetAction() == b) drops++; }
		return String.Format("%d controls, %d drop controls", all, drops);
	}

	void Finish(String why) { Console.Printf("MDDONE %s", why); done = true; }
	void Fail(String why) { Console.Printf("MDFAIL %s", why); Finish("failed"); }
	void Next(MDState st, int phase) { st.phase = phase; st.timer = 0; st.tries = 0; }

	static bool InTown() { return level.MapName ~== "@TOWN@"; }

	bool IsGunPickup(Inventory inv)
	{
		if (!inv || inv.Owner) return false;
		String n = inv.GetClassName();
		return n == mapGun || n == "RLShotgunPickupModded" || n == "RLShotgunPickup" || n == "Shotgun" || n == "RLShotgun";
	}

	Inventory FindGun(PlayerPawn p)
	{
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv, best;
		double bestd = 600;
		while (inv = Inventory(it.Next()))
			if (IsGunPickup(inv) && p.Distance3D(inv) < bestd) { best = inv; bestd = p.Distance3D(inv); }
		return best;
	}

	void Ammo(PlayerPawn p, String when)
	{
		let w = p.player.ReadyWeapon;
		String clip = clipName != "" ? String.Format(" %s %d", clipName, p.CountInv(clipName)) : "";
		Console.Printf("LRAMMO %-16s Shell %d%s | ready %s, %s held %d", when, p.CountInv("Shell"), clip, w ? w.GetClassName() : 'none', weaponName, p.CountInv(weaponName));
	}

	bool HoldsGun(PlayerPawn p)
	{
		let w = p.player.ReadyWeapon;
		let pending = p.player.PendingWeapon;
		return w && w.GetClassName() == weaponName && (pending == null || pending == WP_NOCHANGE);
	}

	// Stands before the pickup, looks at it and presses Use (DD_UsePress through the harness's df_interact).
	void Take(PlayerPawn p, MDState st, Inventory gun)
	{
		if (gun && (st.timer == 10 || st.timer == 45))
		{
			vector2 back = Actor.AngleToVector(p.AngleTo(gun) + 180, 40);
			p.SetOrigin((gun.pos.xy + back, gun.floorz), false);
			p.vel = (0, 0, 0);
			p.angle = p.AngleTo(gun);
			p.pitch = 25;
			EventHandler.SendNetworkEvent("df_interact");
		}
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = MDState(p.FindInventory("MDState"));
		if (!st) st = MDState(p.GiveInventoryType("MDState"));
		if (st && st != cur)
		{
			cur = st;
			if (kPhase > 0) { st.phase = kPhase; st.timer = kTimer; st.tries = kTries; st.cycle = kCycle; Console.Printf("MDSTATUS route state carried over at step %d", st.phase); }
		}
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		st.timer++;
		if (level.maptime % 350 == 1) Console.Printf("MDSTATUS step %d cycle %d, timer %d, map %s", st.phase, st.cycle, st.timer, level.MapName);
		bool ready = level.maptime >= 8 && CVar.FindCVar("dd_sync_df_phase").GetInt() == 3 && CVar.FindCVar("dd_ui_test_hold").GetInt() == 0;
		vector3 ahead = p.Vec3Angle(80, p.angle, 0);
		switch (st.phase)
		{
		case 0: // In town, settled: place the "map" gun and take it.
			if (!InTown() || !ready || st.timer < 35 * 14) break;
			Ammo(p, "start");
			{
				let g = Actor.Spawn(mapGun, (ahead.xy, p.floorz));
				Console.Printf("LRSTEP placed %s (dropped %d)", g ? g.GetClassName() : 'none', g ? g.bDROPPED : 0);
			}
			Next(st, 1);
			break;
		case 1:
			Take(p, st, FindGun(p));
			if (st.timer < 35 * 5) break;
			Ammo(p, "map take");
			if (FindGun(p)) Console.Printf("LRSTEP the map gun was not taken");
			Next(st, 2);
			break;
		case 2: // Daggerfall's inventory window: its hook drops the gun about 6 s after it is in the inventory.
			if (FindGun(p) && st.tries == 0) { st.tries = 1; st.timer = 0; }
			if (st.tries == 1 && st.timer > 35 * 2) { Ammo(p, String.Format("window drop %d", st.cycle + 1)); Next(st, 3); break; }
			if (st.tries == 0 && st.timer > 35 * 20) { Console.Printf("LRSTEP Daggerfall did not drop the gun"); Next(st, 4); }
			break;
		case 3:
			Take(p, st, FindGun(p));
			if (st.timer < 35 * 6) break;
			Ammo(p, String.Format("window retake %d", ++st.cycle));
			Next(st, st.cycle < 3 ? 2 : 4);
			break;
		case 4: // Blocked drops: weapdrop, invdrop and a Zoom press (DRLA's Drop Item) run every second all along.
			if (!HoldsGun(p))
			{
				// Daggerfall draws a taken gun only when its key is free; otherwise press the shotgun's key, 3.
				if (st.timer == 35 || st.timer == 35 * 6) { EventHandler.SendNetworkEvent("dd_hotkey:3"); Console.Printf("LRSTEP pressed hotkey 3"); }
				if (st.timer > 35 * 12) { Ammo(p, "no gun held"); Console.Printf("LRSTEP no %s held to drop", weaponName); Next(st, 8); }
				break;
			}
			if (drla && st.tries == 0)
			{
				// A power mod pack, used once: DRLA then drops it on the next Drop Item (Zoom) press.
				String pack = "RLPowerModItem";
				p.GiveInventory(pack, 1);
				let m = p.FindInventory(pack);
				if (m) p.UseInventory(m); // its Use state ends in Fail (the pack is kept) after setting RLUsePowerMod
				String chosen = "RLUsePowerMod";
				Console.Printf("LRSTEP mod pack selected for dropping: RLUsePowerMod %d", p.CountInv(chosen));
			}
			if (drla && st.tries == 70)
			{
				// DRLA's backpack toss (M runs "use RLSpecialItemDropper"), wearing a combat backpack (BPACK_COMBAT 1).
				String token = "RLCombatBackpackToken", type = "RLBackpackType", dropper = "RLSpecialItemDropper";
				p.GiveInventory(token, 1);
				p.SetInventory(type, 1);
				let d = p.FindInventory(dropper);
				Console.Printf("LRSTEP backpack toss: use %s", d && p.UseInventory(d) ? "succeeded" : "failed");
			}
			if (++st.tries < 35 * 4) break;
			Ammo(p, "blocked drops");
			Console.Printf("LRSTEP blocked drops: %s held %d, on the ground %s", weaponName, p.CountInv(weaponName), FindGun(p) ? "a gun" : "nothing");
			if (drla)
			{
				int packs = 0;
				let it = ThinkerIterator.Create("Inventory");
				Inventory inv;
				while (inv = Inventory(it.Next())) { String n = inv.GetClassName(); if (!inv.Owner && n.IndexOf("Backpack") >= 0) packs++; }
				String token = "RLCombatBackpackToken";
				Console.Printf("LRSTEP backpack toss blocked check: backpack worn %d, backpacks on the ground %d", p.CountInv(token), packs);
				int mods = 0;
				let ai = ThinkerIterator.Create("Actor");
				Actor a;
				while (a = Actor(ai.Next())) { String n = a.GetClassName(); if (n.IndexOf("PowerMod") >= 0 && !(a is "Inventory" && Inventory(a).Owner)) mods++; }
				String pack = "RLPowerModItem";
				Console.Printf("LRSTEP mod pack drop blocked check: packs held %d, power mods on the ground %d", p.CountInv(pack), mods);
			}
			Next(st, 8);
			break;
		case 8: // A monster's drop.
			if (st.timer == 5)
			{
				vector3 at = p.Vec3Angle(160, p.angle, 0);
				let m = Actor.Spawn("ShotgunGuy", (at.xy, p.floorz), ALLOW_REPLACE);
				Console.Printf("LRSTEP spawned %s", m ? m.GetClassName() : 'none');
			}
			if (st.timer == 20) // DRLA spawns its monster through a spawner: kill the monster nearest the spot.
			{
				vector3 at = p.Vec3Angle(160, p.angle, 0);
				let it = ThinkerIterator.Create("Actor");
				Actor mo;
				double best = 300;
				while (mo = Actor(it.Next()))
					if (mo.bISMONSTER && mo.health > 0 && !mo.player && (mo.pos.xy - at.xy).Length() < best) { victim = mo; best = (mo.pos.xy - at.xy).Length(); }
				Console.Printf("LRSTEP killing %s", victim ? victim.GetClassName() : 'none');
				if (victim) victim.DamageMobj(p, p, victim.health + 1, 'None', DMG_FORCED);
			}
			if (st.timer == 35 * 3 && !FindGun(p) && victim)
			{
				// Its drop list rolled no gun: drop one from the corpse the way a death's drop does.
				victim.A_DropItem(mapGun, -1, 256);
				Console.Printf("LRSTEP the monster's own drops held no gun; A_DropItem(%s) from its corpse", mapGun);
			}
			if (st.timer == 35 * 4)
			{
				let gun = FindGun(p);
				Console.Printf("LRSTEP monster drop: %s (dropped %d)", gun ? gun.GetClassName() : 'none', gun ? gun.bDROPPED : 0);
				Ammo(p, "monster drop");
				if (!gun) { Finish("passed"); break; }
				Next(st, 9);
			}
			break;
		case 9:
			Take(p, st, FindGun(p));
			if (st.timer < 35 * 5) break;
			Ammo(p, "monster take");
			Finish("passed");
			break;
		}
		kPhase = st.phase; kTimer = st.timer; kTries = st.tries; kCycle = st.cycle;
	}
}
