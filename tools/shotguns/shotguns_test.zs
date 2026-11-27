version "4.10"

// Test harness for the Shotguns perks (tools/shotguns/shotguns_test.py). Not part of the game.
// For each rule set it asks the fake Daggerfall peer for that sheet ("SHOTTEST want <cfg>"), waits until Doom reads it,
// then for each sample gun:
//   fire sets (off, dmg, reload, p50, p100): 5 shots at a close target that never moves, logging each shot's hits,
//     damage and the tics from the shot until the gun is ready again; then, for a gun with a magazine, a reload from
//     an empty magazine, timed the same way.
//   knock sets (knock, knock100, collide): the player stands 64 units from a target that stands 40 units from a wall
//     (collide: a second target between it and the wall) and fires once; the harness logs how far the target moved,
//     whether it staggered and what it lost. Then the same with a 10x heavier target.

class ShotTestWall : Actor // Damage only: never moves.
{
	Default { Health 1000000; Radius 20; Height 56; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class ShotTestMonster : Actor
{
	Default { Health 1000000; Radius 20; Height 56; Mass 100; +SHOOTABLE +SOLID +NOBLOOD }
	States { Spawn: PLAY A -1; Stop; Pain: PLAY G 8; Goto Spawn; }
}

class ShotTestHeavy : ShotTestMonster { Default { Mass 1000; } }

class ShotPerkTest : EventHandler
{
	Array<String> cfgs;
	Array<String> guns;
	int cfg, gun, phase, wait, t, shot, fireTic, hits, lost, lost2, sub;
	bool painSeen;
	Weapon heldGun;
	Actor target, target2;
	Vector3 spot;
	double dirAngle;
	bool spotFound;

	override void OnRegister()
	{
		static const String c[] = { "off", "dmg", "reload", "p50", "p100", "knock", "knock100", "collide" };
		static const String g[] = { "Shotgun", "RLShotgun", "RLDoubleShotgun", "RLAssaultShotgun", "RLAutoshotgun" };
		for (int i = 0; i < c.Size(); i++) cfgs.Push(c[i]);
		for (int i = 0; i < g.Size(); i++) { class<Actor> k = g[i]; if (k) guns.Push(g[i]); else Console.Printf("SHOTTEST absent %s", g[i]); }
	}

	static bool Want(int idx, int v) { return Actor.DD_SheetValue(idx) == v; }

	bool Arrived(String c)
	{
		int d = 0, r = 0, p = 0, k = 0, s = 0, o = 0;
		if (c == "dmg") d = 7500;
		else if (c == "reload") r = 3500;
		else if (c == "p50") p = 5000;
		else if (c == "p100") p = 10000;
		else if (c == "knock") { k = 10000; s = 200; }
		else if (c == "knock100") { p = 10000; k = 20000; s = 400; }
		else if (c == "collide") { k = 10000; s = 200; o = 200; }
		if (c == "off" && Actor.DD_SheetValue(2) == -1) return true;
		return Want(162, d) && Want(163, r) && Want(164, p) && Want(165, k) && Want(166, s) && Want(167, o);
	}

	bool KnockSet(String c) { return c == "knock" || c == "knock100" || c == "collide"; }

	void Fill(PlayerInfo p, Weapon w)
	{
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = r.MaxAmount; }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = w.AmmoType2 ? m.MaxAmount : 50; }
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.DamageSource || !e.DamageSource.player) return;
		if (target && e.Thing == target) { hits++; lost += e.Damage; }
		if (target2 && e.Thing == target2 && !e.Inflictor) lost2 += e.Damage; // Collision damage only, not a stray pellet.
	}

	// A spot 124 units from a one-sided wall with a clear line to it, from the start: the player stands there facing the
	// wall; targets go 64 units ahead.
	void FindSpot(Actor mo)
	{
		for (int a = 0; a < 360 && !spotFound; a += 45)
		{
			FLineTraceData d;
			if (!mo.LineTrace(a, 1500, 0, TRF_THRUACTORS, 8, 0, 0, d) || d.HitType != TRACE_HitWall || !d.HitLine) continue;
			if (d.Distance < 200 || (d.HitLine.flags & Line.ML_TWOSIDED)) continue;
			Vector2 back = Actor.AngleToVector(a, d.Distance - 124);
			Vector2 xy = mo.pos.XY + back;
			spot = (xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy));
			dirAngle = a;
			spotFound = true;
			Console.Printf("SHOTTEST spot angle %d wall %.0f", a, d.Distance);
		}
	}

	Actor Place(class<Actor> k, double dist)
	{
		Vector2 xy = spot.XY + Actor.AngleToVector(dirAngle, dist);
		return Actor.Spawn(k, (xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy)));
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		if (!spotFound) { FindSpot(mo); if (!spotFound) { Console.Printf("SHOTTEST nospot"); Console.Printf("SHOTTEST done"); spotFound = true; cfg = 99; } }
		if (cfg > 0 && Actor.DD_SheetValue(2) != 1) cfg = cfgs.Size(); // No Daggerfall character: only "off" runs.
		if (cfg >= cfgs.Size()) { if (phase != 99) { phase = 99; Console.Printf("SHOTTEST done"); } return; }
		String c = cfgs[cfg];
		p.attackdown = false;
		switch (phase)
		{
		case 0:
			Console.Printf("SHOTTEST want %s", c);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(c)) { gun = 0; phase = 2; }
			else if (++wait > 350) { Console.Printf("SHOTTEST timeout sheet %s", c); cfg++; phase = 0; }
			break;
		case 2: // select the gun
		{
			if (gun >= guns.Size()) { cfg++; phase = 0; break; }
			class<Weapon> k = guns[gun];
			mo.GiveInventory(k, 1);
			heldGun = Weapon(mo.FindInventory(k));
			p.PendingWeapon = heldGun;
			phase = 3; wait = 0; sub = 0;
			break;
		}
		case 3: // ready: set up the case
			if (p.ReadyWeapon == heldGun && (p.WeaponState & WF_WEAPONREADY))
			{
				Fill(p, heldGun);
				mo.SetOrigin(spot, false); mo.vel = (0, 0, 0); mo.angle = dirAngle; mo.pitch = 0;
				int first, second;
				[first, second] = DoomerfallWeaponCategory.Both(heldGun);
				Console.Printf("SHOTTEST case %s %s cat=%s slot=%d sub=%d", c, guns[gun], DoomerfallWeaponCategory.Label(first), DoomerfallWeaponCategory.SkillSlotOf(heldGun), sub);
				if (KnockSet(c))
				{
					target = Place(sub ? "ShotTestHeavy" : "ShotTestMonster", 64);
					if (c == "collide") target2 = Place("ShotTestMonster", 114);
					phase = 10;
				}
				else { target = Place("ShotTestWall", 64); phase = 4; }
				shot = 0; t = 0; fireTic = -1; hits = lost = lost2 = 0; painSeen = false;
			}
			else if (++wait > 175) { Console.Printf("SHOTTEST noselect %s %s", c, guns[gun]); gun++; phase = 2; }
			break;
		case 4: // fire sets: 5 shots
			if (fireTic >= 0 && (p.WeaponState & WF_WEAPONREADY))
			{
				Console.Printf("SHOTTEST shot %s %s n=%d hits=%d lost=%d cycle=%d", c, guns[gun], shot, hits, lost, level.maptime - fireTic);
				fireTic = -1;
				if (shot >= 5) { phase = 6; break; }
			}
			if (fireTic < 0 && (p.WeaponState & WF_WEAPONREADY))
			{
				Fill(p, heldGun);
				hits = 0; lost = 0;
				Console.Printf("SHOTTEST fire tic=%d", level.maptime);
				mo.FireWeapon(null);
				fireTic = level.maptime; shot++;
			}
			else if (fireTic >= 0 && level.maptime - fireTic > 300) { Console.Printf("SHOTTEST stuck %s %s", c, guns[gun]); phase = 6; }
			break;
		case 6: // reload from an empty magazine (guns with one)
			if (!heldGun.AmmoType2) { phase = 8; break; }
			if (fireTic < 0)
			{
				let m = mo.FindInventory(heldGun.AmmoType1);
				if (m) m.Amount = 0;
				Console.Printf("SHOTTEST reloadstart tic=%d", level.maptime);
				mo.FireWeapon(null); // An empty magazine sends DRLA's Fire to its Reload.
				fireTic = level.maptime;
			}
			else if (level.maptime > fireTic && (p.WeaponState & WF_WEAPONREADY))
			{
				let m = mo.FindInventory(heldGun.AmmoType1);
				Console.Printf("SHOTTEST reload %s %s tics=%d mag=%d", c, guns[gun], level.maptime - fireTic, m ? m.Amount : -1);
				phase = 8;
			}
			else if (level.maptime - fireTic > 300) { Console.Printf("SHOTTEST stuck reload %s %s", c, guns[gun]); phase = 8; }
			break;
		case 8:
			Console.Printf("SHOTTEST end %s %s", c, guns[gun]);
			if (target) target.Destroy();
			if (target2) target2.Destroy();
			gun++; phase = 2;
			break;
		case 10: // knock sets: one shot
			if (p.WeaponState & WF_WEAPONREADY)
			{
				Console.Printf("SHOTTEST fire tic=%d", level.maptime);
				spotStart = target.pos;
				mo.FireWeapon(null);
				fireTic = level.maptime;
				phase = 11;
			}
			break;
		case 11:
			if (target.InStateSequence(target.CurState, target.FindState("Pain"))) painSeen = true;
			if (level.maptime - fireTic >= 45)
			{
				Console.Printf("SHOTTEST knock %s %s sub=%d moved=%.1f pain=%d hits=%d lost=%d lost2=%d", c, guns[gun], sub, (target.pos.XY - spotStart.XY).Length(), painSeen, hits, lost, lost2);
				target.Destroy(); if (target2) target2.Destroy();
				if (++sub < 2) { phase = 3; wait = 0; } else { gun++; phase = 2; }
			}
			break;
		}
	}
	Vector3 spotStart;
}
