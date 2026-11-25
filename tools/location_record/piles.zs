version "4.14"

// Location record route for dropped piles and dropped Doom items (tools/location_record/piles.py), with DRLA loaded and
// Daggerfall's -dfpilestest hook, which does the dropping as the inventory window would.
// Route "first": in town, Daggerfall drops a pile; step out of town, warp 300 tiles away (more than two map pixels, so
// Daggerfall wipes its scene cache), warp back and walk into town again. Enter Privateer's Hold, clear it; Daggerfall
// drops a pile and a modded DRLA shotgun (its own Doom pickup); print the pickup; leave and return; print it again,
// take it with Use, let the hotkeys draw it and print the drawn gun's mods; leave and save in town. Monsters die by fire,
// plain deaths, barrels and gibbing; corpses are counted (LRCORPSES, LRLOOK) at leaving, on return and after the load.
// Route "load": load that save in town and wait there, then enter the dungeon and wait (Daggerfall logs the piles).
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer, tries;
	vector3 street;
	int wildTileX, wildTileY;
}

class MDHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 25;
	const HALF = 12288;
	const SPACING = 192;
	const STEPOUT = 20000;
	bool done, loadRoute;
	// DRLA can swap the player's class ("Player swapped to Portia"), dropping the old pawn's inventory: a copy of the route state
	int kPhase, kTimer, kTries, kWildX, kWildY;
	MDState cur;	// the swap may also hand the new pawn a fresh MDState of its own
	vector3 kStreet;

	override void OnRegister() { loadRoute = "@ROUTE@" ~== "load"; }

	void Finish(String why) { Console.Printf("MDDONE %s", why); done = true; }
	void Fail(String why) { Console.Printf("MDFAIL %s", why); Finish("failed"); }

	static bool InTown() { return level.MapName ~== "@TOWN@"; }
	static bool InWild() { return level.MapName ~== "DDOVER01"; }
	static bool Inside() { return level.MapName ~== "MAP01"; }

	static vector2 ToWorld(vector2 v)
	{
		return (CVar.FindCVar("dd_tm_originx").GetInt() * SPACING + HALF + v.x, CVar.FindCVar("dd_tm_originy").GetInt() * SPACING + HALF + v.y);
	}

	static void Place(PlayerPawn p, vector3 at, double yaw)
	{
		p.SetOrigin(at, false);
		p.vel = (0, 0, 0);
		p.angle = yaw;
		p.pitch = 0;
	}

	static void Warp(int x, int y)
	{
		CVar.FindCVar("dd_tm_warp").SetString(String.Format("%d %d", x, y));
		Console.Printf("LRWARP %d %d", x, y);
	}

	void Next(MDState st, int phase) { st.phase = phase; st.timer = 0; st.tries = 0; }

	static void KillAll(PlayerPawn p)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		int n = 0;
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && mo.health > 0 && !mo.player) { mo.DamageMobj(p, p, mo.health + 1000, 'None', DMG_FORCED); n++; }
		if (n) Console.Printf("LRKILLED %d", n);
	}

	// Kills the living monsters three ways, as play would: a third by fire (DRLA's burning corpses), a third by an
	// ordinary death, and the rest by barrels set off beside them (explosions, and XDeath for those close enough).
	static void MixedKill(PlayerPawn p)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		Array<Actor> blast;
		int fire = 0, plain = 0;
		while (mo = Actor(it.Next()))
		{
			if (!mo.bISMONSTER || mo.health <= 0 || mo.player) continue;
			int n = fire + plain + blast.Size();
			if (n % 3 == 0) { mo.DamageMobj(p, p, mo.health + 1, 'Fire', DMG_FORCED); fire++; }
			else if (n % 3 == 1) { mo.DamageMobj(p, p, mo.health + 1, 'None', DMG_FORCED); plain++; }
			else blast.Push(mo);
		}
		int barrels = 0;
		for (int i = 0; i < blast.Size(); i += 4)
		{
			let b = Actor.Spawn("ExplosiveBarrel", blast[i].pos);
			if (b) { b.DamageMobj(p, p, 1000, 'None', DMG_FORCED); barrels++; }
		}
		Console.Printf("LRMIXED fire %d plain %d near barrels %d (%d barrels)", fire, plain, blast.Size(), barrels);
	}

	// Corpses in the map: all, those showing nothing (TNT1), and those showing their spawn frame (a lost corpse look).
	static void CountCorpses(String when)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		int dead = 0, alive = 0, hidden = 0, standing = 0, looks = 0;
		int tnt = Actor.GetSpriteIndex("TNT1");
		Array<String> keys;
		Array<int> counts;
		while (mo = Actor(it.Next()))
		{
			if (!mo.bISMONSTER || mo.player) continue;
			if (mo.health > 0) { alive++; continue; }
			dead++;
			looks += (mo.sprite * 64 + mo.frame) % 9973;
			String key = String.Format("%s %s %d", mo.GetClassName(), mo.sprite == tnt ? "TNT1" : "spr" .. mo.sprite, mo.frame);
			int at = keys.Find(key);
			if (at == keys.Size()) { keys.Push(key); counts.Push(1); } else counts[at]++;
			if (mo.sprite == tnt) hidden++;
			else if (mo.SpawnState && mo.sprite == mo.SpawnState.sprite && mo.frame == mo.SpawnState.Frame) standing++;
		}
		Console.Printf("LRCORPSES %s dead %d alive %d hidden %d standing %d, sum of sprite frames %d", when, dead, alive, hidden, standing, looks);
		for (int i = 0; i < keys.Size(); i++) Console.Printf("LRLOOK %s %s x%d", when, keys[i], counts[i]);
	}

	static Inventory FindGun()
	{
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next()))
			if (!inv.Owner && inv.GetClassName() == "RLShotgunPickupModded" || !inv.Owner && inv.GetClassName() == "RLShotgunPickup") return inv;
		return null;
	}

	static void PrintGun(String when, Inventory gun)
	{
		if (!gun) { Console.Printf("LRGUN %s none", when); return; }
		String carried = "";
		for (Inventory i = gun.Inv; i; i = i.Inv) carried = carried .. String.Format(" %s=%d", i.GetClassName(), i.Amount);
		Console.Printf("LRGUN %s %s at %d,%d,%d dropped %d carries%s", when, gun.GetClassName(), int(gun.pos.x), int(gun.pos.y), int(gun.pos.z), gun.bDROPPED, carried);
	}

	void GoToExit(PlayerPawn p)
	{
		Place(p, (EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), atan2(-EXITDATA[4], -EXITDATA[3]));
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
			if (kPhase > 0)
			{
				st.phase = kPhase; st.timer = kTimer; st.tries = kTries; st.street = kStreet;
				st.wildTileX = kWildX; st.wildTileY = kWildY;
				Console.Printf("MDSTATUS the player pawn changed; route state carried over at step %d", st.phase);
			}
		}
		if (!st) return;
		if (loadRoute && st.phase >= 20 && st.phase < 40) Next(st, 40);	// the save carries the first route's state
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		st.timer++;
		if (level.maptime % 350 == 1) Console.Printf("MDSTATUS step %d, timer %d, map %s", st.phase, st.timer, level.MapName);
		bool ready = level.maptime >= 8 && CVar.FindCVar("dd_sync_df_phase").GetInt() == 3 && CVar.FindCVar("dd_ui_test_hold").GetInt() == 0;
		switch (st.phase)
		{
		case 0: // In town: Daggerfall drops its pile after a few seconds in play.
			if (!InTown() || !ready) break;
			if (st.timer < 35 * 16) break;
			st.street = p.pos;
			Console.Printf("LRTOWN pile dropped at the street, leaving town");
			Next(st, 1);
			break;
		case 1: // Step out of town to the south.
			if (InWild()) { p.SetOrigin((p.pos.xy, p.floorz), false); p.vel = (0, 0, 0); Next(st, 2); break; }
			if (st.timer % 20 == 5) { st.tries++; Place(p, (st.street.x, st.street.y - STEPOUT * st.tries, st.street.z), 0); }
			if (st.tries > 6) Fail("could not leave town");
			break;
		case 2: // In the wilderness: warp far away.
			if (!InWild() || st.timer < 35) break;
			{
				vector2 w = ToWorld(p.pos.xy);
				st.wildTileX = int(w.x / SPACING);
				st.wildTileY = int(w.y / SPACING);
			}
			Warp(st.wildTileX + 300, st.wildTileY);
			Next(st, 3);
			break;
		case 3: // Far away: wait, then warp back.
			if (!InWild() || st.timer < 35 * 4) break;
			Warp(st.wildTileX, st.wildTileY);
			Next(st, 4);
			break;
		case 4: // Back: walk north into town, then to the street, and wait there.
			if (InTown())
			{
				if (st.tries == 0) { Place(p, st.street, 0); st.tries = 1; st.timer = 0; Console.Printf("LRTOWN back at the street"); }
				if (st.timer > 35 * 6) Next(st, 5);
				break;
			}
			if (!InWild() || st.timer < 70) break;
			p.SetOrigin((p.pos.x, p.pos.y + 120, p.pos.z), true);
			p.SetZ(p.floorz);
			p.vel = (0, 0, 0);
			if (st.timer > LIMIT * 2) Fail("could not walk back into town");
			break;
		case 5: // Use the dungeon door.
		case 7:
			if (Inside()) { Next(st, st.phase + 1); break; }
			if (!InTown() || !ready) break;
			Place(p, (door.xy + normal * 48, door.z), atan2(-normal.y, -normal.x));
			if (st.timer == 50 || st.timer % 175 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (st.timer > LIMIT) Fail("no entry");
			break;
		case 6: // Inside: clear it, wait for Daggerfall's drops, print the dropped gun, leave.
			if (!Inside()) break;
			if (st.timer == 35 * 3) MixedKill(p);
			if (st.timer > 35 * 8) KillAll(p);
			if (st.timer < 35 * 14) break;
			PrintGun("dropped", FindGun());
			CountCorpses("leaving");
			GoToExit(p);
			Next(st, 20);
			break;
		case 20: // Leave.
			p.vel = (0, 0, 0);
			if (st.timer == 5 || st.timer % 70 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (InTown()) Next(st, 7);
			else if (st.timer > LIMIT) Fail("exit did not work");
			break;
		case 8: // Back inside: print the gun, stand before it and press Use.
			if (!Inside()) break;
			if (st.timer == 35 * 4) CountCorpses("returned");
			if (st.timer > 35 * 4) KillAll(p);
			if (st.timer < 35 * 5) break;
			{
				let gun = FindGun();
				PrintGun("returned", gun);
				if (!gun) { Fail("the dropped gun did not come back"); break; }
				vector2 back = Actor.AngleToVector(p.AngleTo(gun) + 180, 40);
				Place(p, (gun.pos.xy + back, gun.pos.z), p.AngleTo(gun));
				p.pitch = 20;
			}
			Next(st, 9);
			break;
		case 9:
			if (st.timer == 10 || st.timer == 45) EventHandler.SendNetworkEvent("df_interact");
			if (st.timer < 35 * 4) break;
			{
				let w = p.player.ReadyWeapon;
				Console.Printf("LRDRAWN ready %s pending %s shotgun %d power %d modlimit %d clip %d, pickup left %s", w ? w.GetClassName() : 'none',
					p.player.PendingWeapon ? p.player.PendingWeapon.GetClassName() : 'none', p.CountInv("RLShotgun"), p.CountInv("RLShotgunPowerMod"),
					p.CountInv("RLShotgunModLimit"), p.CountInv("RLShotgunClip"), FindGun() ? "yes" : "no");
			}
			GoToExit(p);
			Next(st, 21);
			break;
		case 21: // Leave, and save in town.
			p.vel = (0, 0, 0);
			if (!InTown())
			{
				if (st.timer == 5 || st.timer % 70 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
				if (st.timer > LIMIT) Fail("exit did not work");
				break;
			}
			if (st.tries == 0) { st.tries = 1; st.timer = 0; }
			if (st.timer == 35 * 4) { Console.Printf("MDSAVE outside"); level.MakeAutoSave(); }
			if (st.timer > 35 * 7) Finish("passed");
			break;
		case 40: // Loaded in town: wait for Daggerfall to put the town pile back, then enter the dungeon.
			if (!InTown() || !ready || st.timer < 35 * 8) break;
			Console.Printf("LRTOWN loaded, entering the dungeon");
			Next(st, 41);
			break;
		case 41:
			if (Inside()) { Next(st, 42); break; }
			Place(p, (door.xy + normal * 48, door.z), atan2(-normal.y, -normal.x));
			if (st.timer == 50 || st.timer % 175 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (st.timer > LIMIT) Fail("no entry after the load");
			break;
		case 42:
			if (st.timer == 35 * 5) { PrintGun("loaded", FindGun()); CountCorpses("loaded"); }
			if (st.timer > 35 * 8) Finish("passed");
			break;
		}
		kPhase = st.phase; kTimer = st.timer; kTries = st.tries; kStreet = st.street; kWildX = st.wildTileX; kWildY = st.wildTileY;
	}
}
