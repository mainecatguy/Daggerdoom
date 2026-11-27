version "4.10"

// Test harness for the Energy Weapons perks (tools/energy/energy_test.py). Not part of the game.
// Burn rule sets (card 08) wait 140 tics after the last shot so every burn has paid out. The last set, "stress", burns
// a dense 20 x 20 pack (EnTestMonster, 20 units apart) and fires bursts into it (see Stress).
// For each rule set and gun it asks the fake Daggerfall peer for the rules ("ENTEST want <cfg>"), waits until Doom reads
// them, selects the gun, puts the player back at the start and places:
//   target   a big shootable post 96 units ahead, in the line of fire (the hits land here);
//   near     two test monsters by the target (46 units to its side, and 36 behind and 30 to the side; edges inside the
//            64 splash radius);
//   far      one test monster 96 units to the side of the target (edge 88 away, outside the radius, in sight).
// Then it fires the gun a few times and logs every bit of damage and every projectile the player's gun spawned.

class EnTestTarget : Actor
{
	Default { Health 1000000; Radius 16; Height 56; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class EnTestMonster : Actor
{
	Default { Monster; Health 1000000; Radius 8; Height 40; +NOBLOOD +DONTTHRUST -COUNTKILL }
	States { Spawn: TROO A -1; Stop; }
}

class EnPerkTest : EventHandler
{
	Array<String> cfgs, guns;
	int step, gun, phase, wait, t, shots;
	Vector3 start;
	bool startSet;
	Actor target, near1, near2, far;

	override void OnRegister()
	{
		static const String c[] = { "off", "dmg", "splash", "speed25", "speed", "burn25", "burn50", "burn75", "burn100", "stress" };
		for (int i = 0; i < c.Size(); i++) cfgs.Push(c[i]);
		static const String g[] = { "PlasmaRifle", "BFG9000", "RLPlasmaRifle", "RLLaserRifle" };
		for (int i = 0; i < g.Size(); i++) { class<Actor> kk = g[i]; if (kk) guns.Push(g[i]); }
	}

	bool Arrived(String c)
	{
		int d = Actor.DD_SheetValue(173), s = Actor.DD_SheetValue(174), r = Actor.DD_SheetValue(175), v = Actor.DD_SheetValue(176);
		if (c == "off" && Actor.DD_SheetValue(2) == -1) return true;
		if (c == "off" && !(d == 0 && s == 0 && r == 0 && v == 0)) return false;
		if (c == "dmg") return d == 5000 && s == 0 && v == 0;
		if (c == "splash") return d == 0 && s == 2000 && r == 64 && v == 0;
		int b = Actor.DD_SheetValue(177), cv = Actor.DD_SheetValue(178), bb = Actor.DD_SheetValue(179), br = Actor.DD_SheetValue(180);
		bool noburn = b == 0 && cv == 0 && bb == 0 && br == 0;
		if (c == "off") return noburn;
		if (c == "speed25") return d == 0 && s == 0 && v == 1500 && noburn;
		if (c == "speed") return d == 0 && s == 0 && v == 6000 && noburn;
		bool plain = d == 0 && s == 0 && v == 0;
		if (c == "burn25") return plain && b == 5000 && cv == 0 && bb == 0;
		if (c == "burn50") return plain && b == 10000 && cv == 2000 && bb == 0;
		if (c == "burn75") return plain && b == 12500 && cv == 4000 && bb == 0;
		return plain && b == 15000 && cv == 4000 && bb == 4000 && br == 128; // burn100, stress
	}

	void Fill(PlayerInfo p, Weapon w)
	{
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = r.MaxAmount; }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = max(m.MaxAmount, 1); }
	}

	String Who(Actor a)
	{
		if (!a) return "none";
		if (a == target) return "target";
		if (a == near1) return "near1";
		if (a == near2) return "near2";
		if (a == far) return "far";
		if (a.player) return "player";
		return a.GetClassName();
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (phase < 3 || phase >= 10) return;
		Console.Printf("ENTEST dmg %s %d by %s flags %d", Who(e.Thing), e.Damage, e.Inflictor ? e.Inflictor.GetClassName() : 'None', e.DamageFlags);
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		let a = e.Thing;
		PlayerInfo p = players[consoleplayer];
		if (phase < 3 || phase >= 10 || !a || !a.bMissile || a.target != p.mo) return;
		let tag = DoomerfallShotTag.Of(a);
		Console.Printf("ENTEST missile %s vel %.3f speed %.3f default %.3f gen %d", a.GetClassName(), a.vel.Length(), a.Speed, a.default.Speed,
			tag ? tag.generation : -1);
	}

	override void WorldThingDestroyed(WorldEvent e)
	{
		let a = e.Thing;
		PlayerInfo p = players[consoleplayer];
		if (phase < 3 || phase >= 10 || !a || !a.default.bMissile || a.target != p.mo) return;
		Console.Printf("ENTEST gone %s at %.0f %.0f %.0f from player %.0f target at %.0f %.0f %.0f", a.GetClassName(), a.pos.x, a.pos.y, a.pos.z,
			a.Distance2D(p.mo), target ? target.pos.x : 0, target ? target.pos.y : 0, target ? target.pos.z : 0);
	}

	Actor Put(class<Actor> k, Vector3 pos)
	{
		let a = Actor.Spawn(k, pos);
		if (a) { a.angle = 180; Console.Printf("ENTEST put %s fits %d", k.GetClassName(), a.TestMobjLocation()); }
		return a;
	}

	void Clear()
	{
		if (target) target.Destroy();
		if (near1) near1.Destroy();
		if (near2) near2.Destroy();
		if (far) far.Destroy();
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		p.cheats |= CF_BUDDHA;
		if (step > 0 && Actor.DD_SheetValue(2) != 1) step = cfgs.Size(); // no Daggerfall character: only "off" runs
		if (step >= cfgs.Size())
		{
			if (phase != 99) { phase = 99; Console.Printf("ENTEST done"); }
			return;
		}
		String c = cfgs[step];
		switch (phase)
		{
		case 0:
			if (gun >= guns.Size()) { gun = 0; step++; break; }
			Console.Printf("ENTEST want %s", c);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(c)) { phase = c == "stress" ? 10 : 2; wait = 0; }
			else if (++wait > 350) { Console.Printf("ENTEST timeout sheet %s", c); step++; phase = 0; }
			break;
		case 2:
		{
			class<Weapon> k = guns[gun];
			mo.GiveInventory(k, 1);
			let w = Weapon(mo.FindInventory(k));
			if (p.ReadyWeapon != w) { p.PendingWeapon = w; if (++wait > 400) { Console.Printf("ENTEST noselect %s", guns[gun]); gun++; phase = 0; } break; }
			if (!(p.WeaponState & WF_WEAPONREADY)) break;
			Fill(p, w);
			if (!startSet) { start = mo.pos; startSet = true; }
			mo.SetOrigin(start, false); mo.vel = (0, 0, 0); mo.angle = 0; mo.pitch = 0;
			target = Put("EnTestTarget", mo.Vec3Angle(96, 0)); // a wall about 135 units ahead of the E1M1 start stops balls
			near1 = Put("EnTestMonster", target.Vec3Offset(0, 46, 0));
			near2 = Put("EnTestMonster", target.Vec3Offset(36, 30, 0)); // behind and beside: a wall is 40 units south
			far = Put("EnTestMonster", target.Vec3Offset(0, 96, 0));
			Console.Printf("ENTEST sight near1 %d near2 %d far %d", target.CheckSight(near1), target.CheckSight(near2), target.CheckSight(far));
			Console.Printf("ENTEST case %s %s slot=%d", c, guns[gun], DoomerfallWeaponCategory.SkillSlotOf(w));
			phase = 3; t = 0; shots = 0;
			break;
		}
		case 3: // a few shots
		{
			let w = p.ReadyWeapon;
			if (w) Fill(p, w);
			if (p.WeaponState & WF_WEAPONREADY)
			{
				if (shots >= (guns[gun] == "BFG9000" ? 1 : 4)) { phase = 4; t = 0; break; }
				mo.SetOrigin(start, false); mo.angle = 0; mo.pitch = 0;
				mo.FireWeapon(null); shots++;
				Console.Printf("ENTEST fire %d tic %d", shots, level.maptime);
			}
			else if (++t > 300) { Console.Printf("ENTEST nofire %s", guns[gun]); phase = 4; t = 0; }
			break;
		}
		case 4:
			if (++t < (c.Left(4) == "burn" ? 140 : 70)) break;
			Console.Printf("ENTEST end %s %s", c, guns[gun]);
			Clear();
			gun++; phase = 0;
			break;
		default:
			if (Stress(p)) { step++; phase = 0; }
			break;
		}
	}

	// Stress: 400 EnTestMonsters 20 units apart (each burst reaches over 100 of them), all burning 300. Then for 6 s,
	// a BFG-sized volley (40 direct hits of 200 on random pack members) every 35 tics, and one plasma-sized hit (40) every
	// 3 tics, through DoomerfallEnergyBurn.Hit with the burn100 rules: each hit converts and bursts. Logs the time each
	// volley takes and the longest gap between tics. Perk logging is turned off first (it is not part of normal play).
	Array<Actor> pack;
	double lastTic, maxGap, maxVolley, maxSingle;
	int bursts;
	bool Stress(PlayerInfo p)
	{
		let mo = p.mo;
		double now = MSTimeF();
		if (phase == 10)
		{
			let log = CVar.FindCVar("dd_perklog");
			if (log) log.SetBool(false);
			mo.SetOrigin(start, false); mo.angle = 0;
			for (int i = 0; i < 400; i++)
			{
				let m = Actor.Spawn("EnTestMonster", mo.Vec3Offset(48 + (i % 20) * 20, ((i / 20) - 10) * 20, 0), NO_REPLACE);
				if (!m) continue;
				pack.Push(m);
				DoomerfallBurn.Apply(m, 300, mo);
			}
			Console.Printf("ENTEST stress pack %d burning %d", pack.Size(), Count());
			phase = 11; t = 0; lastTic = now;
			return false;
		}
		if (t > 5) maxGap = max(maxGap, now - lastTic);
		lastTic = now;
		t++;
		if (t <= 210)
		{
			int n = t % 35 == 0 ? 40 : t % 3 == 0 ? 1 : 0;
			double t0 = MSTimeF();
			for (int k = 0; k < n; k++)
			{
				let m = pack[Random[EnTest](0, pack.Size() - 1)];
				if (m && m.health > 0) { DoomerfallEnergyBurn.Hit(m, mo, n > 1 ? 200 : 40); bursts++; }
			}
			double took = MSTimeF() - t0;
			if (n > 1) { maxVolley = max(maxVolley, took); Console.Printf("ENTEST stress volley tic %d hits %d ms %.3f burning %d", t, n, took, Count()); }
			else if (n == 1) maxSingle = max(maxSingle, took);
			return false;
		}
		Console.Printf("ENTEST stress end hits %d max volley ms %.3f max single ms %.3f max tic gap ms %.1f burning %d",
			bursts, maxVolley, maxSingle, maxGap, Count());
		for (int i = 0; i < pack.Size(); i++) if (pack[i]) pack[i].Destroy();
		pack.Clear();
		return true;
	}

	int Count()
	{
		int n = 0;
		for (int i = 0; i < pack.Size(); i++) if (pack[i] && DoomerfallBurn.Burning(pack[i])) n++;
		return n;
	}
}
