version "4.14"

// Gun ammo route (tools/location_record/gunammo.py). Owner rule (2026-11-24): guns never give ammo, whatever their
// source, on a first take or a retake. In town, with Daggerfall's -dfgundroptest hook, this prints the player's Doom ammo
// for the gun's types (LRAMMO) at every step:
//   map take:      a gun pickup placed in front of the player (not dropped), taken with Use;
//   path 1 x3:     Daggerfall's inventory window drops the gun (the hook), the pickup is taken back with Use;
//   path 2 x3:     DRLA's own weapon drop (the held gun's WeaponDropConfirm state), taken back (DRLA runs only);
//   path 3 x3:     Doom's weapdrop (DropInventory of the ready weapon), taken back;
//   monster take:  a ShotgunGuy is killed and the gun it drops is taken with Use.
// Ammo for those types must not change on any take. A retake needs the gun held again: Daggerfall's hotkeys draw a newly
// taken gun when its key is free; if no shotgun is held when a drop path starts, the route says so and moves on.
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, tries, cycle, path;
}

class MDHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 25;
	bool done, drla;
	// DRLA can swap the player's class ("Player swapped to Portia"); a copy of the route state survives it.
	int kPhase, kTimer, kTries, kCycle, kPath;
	Array<String> paths;	// the drop paths this run takes, in order (@PATHS@)
	MDState cur;
	String mapGun, weaponName, clipName;
	Actor victim;

	override void OnRegister()
	{
		drla = "@SET@" ~== "drla";
		mapGun = drla ? "RLShotgunPickup" : "Shotgun";
		weaponName = drla ? "RLShotgun" : "Shotgun";
		clipName = drla ? "RLShotgunClip" : "";
		String list = "@PATHS@";
		list.Split(paths, " ", TOK_SKIPEMPTY);
	}

	void Finish(String why) { Console.Printf("MDDONE %s", why); done = true; }
	void Fail(String why) { Console.Printf("MDFAIL %s", why); Finish("failed"); }
	void Next(MDState st, int phase) { st.phase = phase; st.timer = 0; st.tries = 0; }
	// Path 1 is steps 2-3, path 2 steps 4-5, path 3 steps 6-7; after the last path, the monster's drop (step 8).
	void NextPath(MDState st, int index) { st.path = index; st.cycle = 0; Next(st, index < paths.Size() ? paths[index].ToInt() * 2 : 8); }

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
			if (kPhase > 0) { st.phase = kPhase; st.timer = kTimer; st.tries = kTries; st.cycle = kCycle; st.path = kPath; Console.Printf("MDSTATUS route state carried over at step %d", st.phase); }
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
			NextPath(st, 0);
			break;
		case 2: // Path 1: Daggerfall's hook drops the gun about 6 s after it is in the inventory.
			if (FindGun(p) && st.tries == 0) { st.tries = 1; st.timer = 0; }
			if (st.tries == 1 && st.timer > 35 * 2) { Ammo(p, String.Format("p1 drop %d", st.cycle + 1)); Next(st, 3); break; }
			if (st.tries == 0 && st.timer > 35 * 20) { Console.Printf("LRSTEP path 1: Daggerfall did not drop the gun"); NextPath(st, st.path + 1); }
			break;
		case 3:
			Take(p, st, FindGun(p));
			if (st.timer < 35 * 6) break;
			Ammo(p, String.Format("p1 retake %d", ++st.cycle));
			if (st.cycle < 3) Next(st, 2);
			else NextPath(st, st.path + 1);
			break;
		case 4: // Path 2: DRLA's weapon drop of the held gun.
		case 6: // Path 3: Doom's weapdrop.
			if (!HoldsGun(p))
			{
				// Daggerfall draws a taken gun only when its key is free; otherwise press the shotgun's key, 3.
				if (st.timer == 35 || st.timer == 35 * 6) { EventHandler.SendNetworkEvent("dd_hotkey:3"); Console.Printf("LRSTEP pressed hotkey 3"); }
				if (st.timer > 35 * 12) { Ammo(p, "no gun held"); Console.Printf("LRSTEP path %d: no %s held to drop", st.phase == 4 ? 2 : 3, weaponName); NextPath(st, st.path + 1); }
				break;
			}
			if (st.timer < 35 * 2) break;
			if (st.phase == 4)
			{
				let w = p.player.ReadyWeapon;
				State s = w.FindState("WeaponDropConfirm");
				if (s) p.player.SetPsprite(PSP_WEAPON, s);
				else Console.Printf("LRSTEP %s has no WeaponDropConfirm", w.GetClassName());
			}
			else p.DropInventory(p.player.ReadyWeapon);
			Next(st, st.phase + 1);
			break;
		case 5:
		case 7:
			if (st.timer == 35 * 2)
			{
				Ammo(p, String.Format("p%d drop %d", st.phase == 5 ? 2 : 3, st.cycle + 1));
				if (HoldsGun(p) && !FindGun(p))
				{
					Console.Printf("LRSTEP path %d: nothing was dropped (DRLA guns are +INVENTORY.UNDROPPABLE)", st.phase == 5 ? 2 : 3);
					NextPath(st, st.path + 1);
					break;
				}
			}
			if (st.timer < 35 * 2) break;
			if (st.timer == 35 * 2) { st.tries = 0; }
			{
				int t = st.timer - 35 * 2;
				let gun = FindGun(p);
				if (gun && (t == 10 || t == 45))
				{
					vector2 back = Actor.AngleToVector(p.AngleTo(gun) + 180, 40);
					p.SetOrigin((gun.pos.xy + back, gun.floorz), false);
					p.vel = (0, 0, 0);
					p.angle = p.AngleTo(gun);
					p.pitch = 25;
					EventHandler.SendNetworkEvent("df_interact");
				}
				if (t < 35 * 6) break;
			}
			Ammo(p, String.Format("p%d retake %d", st.phase == 5 ? 2 : 3, ++st.cycle));
			if (st.cycle < 3) Next(st, st.phase - 1);
			else NextPath(st, st.path + 1);
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
		kPhase = st.phase; kTimer = st.timer; kTries = st.tries; kCycle = st.cycle; kPath = st.path;
	}
}
