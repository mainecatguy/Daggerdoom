version "4.10"

// Test harness for the owner's perk numbers (tools/perknumbers/perknumbers_test.py). Not part of the game.
// Unlike the per-skill tests, the fake Daggerfall peer sends a real character sheet (skills and attributes) and no
// hand-picked rule set, so Doom's own rules (DoomerfallRules.Compute) turn the skill into the numbers under test.
// For each case it asks for a sheet ("PNTEST want <cfg>"), waits until Doom reads it, and runs one shot:
//   shot   (e49, e50)    a rocket at a target 100 units ahead: the direct hit's factor and the splash's.
//   chain  (e100)        a 1000-health monster (1 left) 100 units north dies to the rocket; dummies behind it at known
//                        distances log what Inpulsa's blast does to each. Every attribute is 100, so any bonus that
//                        leaked onto the blast would show.
//   slam   (s74, s75, s100) the player faces a wall 124 units away; a 100-mass target stands 4 units from it, is hit
//                        by one shotgun blast and slams into the wall in its first tic of flight.

class PNTarget : Actor
{
	Default { Health 1000000; Radius 40; Height 64; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class PNChainMonster : Actor
{
	Default { Monster; Health 1000; Radius 8; Height 40; +NOBLOOD +DONTTHRUST -COUNTKILL -SOLID }
	States { Spawn: TROO A -1; Stop; Death: TROO IJKL 5; TROO M -1; Stop; }
}

// Not a monster, so it never chains; it never dies and never moves.
class PNDummy : Actor
{
	Default { Health 1000000; Radius 16; Height 56; +SHOOTABLE -SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}
class PNDummyBig : PNDummy { Default { Radius 50; } }

class PNSlamTarget : Actor
{
	Default { Health 1000000; Radius 40; Height 56; Mass 100; +SHOOTABLE +SOLID +NOBLOOD +NOPAIN }
	States { Spawn: PLAY A -1; Stop; }
}

class PNTest : EventHandler
{
	Array<String> cfgs, kinds, guns;
	int step, gun, phase, wait, t;
	Vector3 start, spot;
	double dirAngle;
	bool startSet, spotFound;
	Actor target;
	Array<Actor> things;
	int targetLost;

	override void OnRegister()
	{
		static const String c[] = { "e49", "e50", "e100", "s74", "s75", "s100" };
		static const String k[] = { "shot", "shot", "chain", "slam", "slam", "slam" };
		for (int i = 0; i < c.Size(); i++) { cfgs.Push(c[i]); kinds.Push(k[i]); }
	}

	// The sheet the peer writes for each case: Explosives, Shotguns, and every attribute.
	static int, int, int Sheet(String c)
	{
		if (c == "e49") return 49, 0, 50;
		if (c == "e50") return 50, 0, 50;
		if (c == "e100") return 100, 0, 100;
		if (c == "s74") return 0, 74, 50;
		if (c == "s75") return 0, 75, 50;
		return 0, 100, 50; // s100
	}

	bool Arrived(String c)
	{
		int e, s, a;
		[e, s, a] = Sheet(c);
		return DoomerfallRules.HasCharacter() && Actor.DD_SheetSkill(DoomerfallRules.SkillExplosives) == e
			&& Actor.DD_SheetSkill(DoomerfallRules.SkillShotguns) == s && Actor.DD_SheetStat(DoomerfallRules.StatLuck) == a;
	}

	// The gun for a case: the first of these the game has.
	String GunFor(String kind)
	{
		static const String rockets[] = { "RLRocketLauncher", "RocketLauncher" };
		static const String shotguns[] = { "RLDoubleShotgun", "Shotgun" };
		for (int i = 0; i < 2; i++)
		{
			String n = kind == "slam" ? shotguns[i] : rockets[i];
			class<Actor> k = n;
			if (k) return n;
		}
		return "";
	}

	void Fill(PlayerInfo p, Weapon w)
	{
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = r.MaxAmount; }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = max(m.MaxAmount, 1); }
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (phase != 4) return;
		String inf = e.Inflictor ? e.Inflictor.GetClassName() : 'None';
		if (target && e.Thing == target) { targetLost += e.Damage; Console.Printf("PNTEST target lost %d by %s", e.Damage, inf); }
		if (e.Thing is "PNDummy" && e.Inflictor is "DoomerfallChainBlast")
		{
			// Doom's radius damage distance (P_RadiusAttack, square pattern): the larger of |dx| and |dy|, less the radius.
			Vector2 d = e.Inflictor.Vec2To(e.Thing);
			double len = max(0., max(abs(d.x), abs(d.y)) - e.Thing.radius);
			bool inZ = e.Inflictor.pos.z >= e.Thing.pos.z && e.Inflictor.pos.z < e.Thing.pos.z + e.Thing.height;
			Console.Printf("PNTEST blasthit len %.4f inz %d dmg %d", len, inZ, e.Damage);
		}
		if (e.Thing && e.Thing.health <= 0 && !e.Thing.player) Console.Printf("PNTEST killed %s by %s", e.Thing.GetClassName(), inf);
	}

	void FindSpot(Actor mo)
	{
		for (int a = 0; a < 360 && !spotFound; a += 45)
		{
			FLineTraceData d;
			if (!mo.LineTrace(a, 1500, 0, TRF_THRUACTORS, 8, 0, 0, d) || d.HitType != TRACE_HitWall || !d.HitLine) continue;
			if (d.Distance < 200 || (d.HitLine.flags & Line.ML_TWOSIDED)) continue;
			Vector2 xy = mo.pos.XY + Actor.AngleToVector(a, d.Distance - 124);
			spot = (xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy));
			dirAngle = a;
			spotFound = true;
			Console.Printf("PNTEST spot angle %d wall %.0f", a, d.Distance);
		}
	}

	Actor Dummy(class<Actor> k, Actor centre, double dx, double dy, double len)
	{
		let m = Actor.Spawn(k, (centre.pos.x + dx, centre.pos.y + dy, centre.pos.z));
		if (!m) return null;
		things.Push(m);
		Console.Printf("PNTEST dummy len %.0f fits %d sight %d", len, m.TestMobjLocation(), m.CheckSight(centre));
		return m;
	}

	void Place(PlayerInfo p, String kind)
	{
		let mo = p.mo;
		if (mo.RadiusDamageFactor != 1) mo.RadiusDamageFactor = 1; // a DRLA Demolitionist: splash-immune
		things.Clear();
		target = null;
		targetLost = 0;
		if (kind == "shot") target = Actor.Spawn("PNTarget", mo.Vec3Angle(100, 0));
		else if (kind == "chain")
		{
			// North, into E1M1's open start room. A is the nearest thing on the rocket's path, so the rocket hits it.
			mo.angle = 90;
			let a = Actor.Spawn("PNChainMonster", mo.Vec3Angle(100, 90));
			a.health = 1; things.Push(a);
			// Distances from the blast (at A's centre) to each dummy's edge, all behind A. 0: a big dummy whose box
			// reaches A's centre; 140 is out of reach. Actors never block radius damage or its sight check.
			Dummy("PNDummyBig", a, 0, 50, 0);
			static const int lens[] = { 32, 64, 96, 112, 140 };
			for (int i = 0; i < lens.Size(); i++) Dummy("PNDummy", a, 0, 16 + lens[i], lens[i]);
		}
		else // slam: the player at the spot facing the wall; the target 4 units from it
		{
			mo.SetOrigin(spot, false); mo.angle = dirAngle;
			Vector2 xy = spot.XY + Actor.AngleToVector(dirAngle, 124 - 40 - 4);
			target = Actor.Spawn("PNSlamTarget", (xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy)));
			Console.Printf("PNTEST slam target fits %d", target.TestMobjLocation());
		}
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		p.cheats |= CF_BUDDHA;
		if (!startSet) { start = mo.pos; startSet = true; FindSpot(mo); mo.SetOrigin(start, false); }
		if (step > 0 && !DoomerfallRules.HasCharacter()) step = cfgs.Size(); // no Daggerfall character
		if (step >= cfgs.Size())
		{
			if (phase != 99) { phase = 99; Console.Printf("PNTEST done"); }
			return;
		}
		String c = cfgs[step], kind = kinds[step];
		switch (phase)
		{
		case 0:
			Console.Printf("PNTEST want %s", c);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(c)) { phase = 2; wait = 0; }
			else if (++wait > 350)
			{
				Console.Printf("PNTEST timeout sheet %s valid %d expl %d shot %d luck %d", c, Actor.DD_SheetValue(2),
					Actor.DD_SheetSkill(DoomerfallRules.SkillExplosives), Actor.DD_SheetSkill(DoomerfallRules.SkillShotguns), Actor.DD_SheetStat(DoomerfallRules.StatLuck));
				step++; phase = 0;
			}
			break;
		case 2:
		{
			String n = GunFor(kind);
			if (n == "" || (kind == "slam" && !spotFound)) { Console.Printf("PNTEST skip %s no gun or wall", c); step++; phase = 0; break; }
			class<Weapon> k = n;
			mo.GiveInventory(k, 1);
			let w = Weapon(mo.FindInventory(k));
			if (p.ReadyWeapon != w) { p.PendingWeapon = w; if (++wait > 400) { Console.Printf("PNTEST noselect %s", n); step++; phase = 0; } break; }
			if (!(p.WeaponState & WF_WEAPONREADY)) break;
			Fill(p, w);
			mo.SetOrigin(start, false); mo.vel = (0, 0, 0); mo.angle = 0; mo.pitch = 0;
			Console.Printf("PNTEST case %s %s %s slot=%d", c, kind, n, DoomerfallWeaponCategory.SkillSlotOf(w));
			Place(p, kind);
			phase = 3; t = 0;
			break;
		}
		case 3:
			p.attackdown = true;
			if (p.WeaponState & WF_WEAPONREADY) { mo.FireWeapon(null); phase = 4; t = 0; }
			else if (++t > 100) { Console.Printf("PNTEST nofire %s", c); phase = 4; t = 0; }
			break;
		case 4:
			p.attackdown = false;
			if (++t < 45) break;
			Console.Printf("PNTEST end %s %s lost=%d", c, kind, targetLost);
			if (target) target.Destroy();
			for (int i = 0; i < things.Size(); i++) if (things[i]) things[i].Destroy();
			things.Clear(); target = null;
			step++; phase = 0;
			break;
		}
	}
}
