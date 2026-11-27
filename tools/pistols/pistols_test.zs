version "4.10"

// Test harness for the Pistols perks (tools/pistols/pistols_test.py). Not part of the game.
// For each rule set it asks the fake Daggerfall peer for that sheet ("PISTTEST want <cfg>"), waits until Doom reads it,
// then for each sample gun:
//   fire sets (off, spray, mult, reload, reload60, pool): 5 shots at a close target that never moves, logging each
//     shot's hits, damage and the tics from the trigger until the gun is ready again; then, for a gun with a magazine,
//     a reload from an empty magazine, timed the same way.
//   line sets (carry, frag, turn, carryfrag): one shot at target A 64 units ahead. When A is first hit, the harness
//     places the other targets along the shot's real line (the perk deals carry-through and fragments a tick later):
//       carry      A (20 health) and B (30 health) die, C (huge) behind them takes what is left.
//       frag       A huge; B straight behind (the middle fragment), C on the +15 degree fork (a side fragment).
//       turn       A huge; D 4 degrees off the middle line (the middle fragment turns to it), E 7.5 degrees off both
//                  the middle and the side lines (outside the 5 degree turn: nothing hits it).
//       carryfrag  A (20 health) dies; B (huge) straight behind takes the carry-through and A's middle fragment.
//     Each target logs what it lost.

class PistTestWall : Actor // Damage only: never moves.
{
	Default { Health 1000000; Radius 20; Height 56; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY +ISMONSTER }
	States { Spawn: PLAY A -1; Stop; Death: PLAY H 4; PLAY N -1; Stop; }
}

class PistTestThin : PistTestWall { Default { Radius 4; } } // for angle tests: a box this thin is hit only near its line

class PistPerkTest : EventHandler
{
	Array<String> cfgs;
	Array<String> guns;
	int cfg, gun, phase, wait, shot, fireTic, hits, lost;
	Weapon heldGun;
	Actor target;
	Array<Actor> extra;     // B, C, D, E
	Array<String> extraName;
	Array<int> extraLost;
	Vector3 spot;
	double dirAngle;
	bool spotFound, placed;

	override void OnRegister()
	{
		static const String c[] = { "off", "spray", "mult", "reload", "reload60", "pool", "carry", "frag", "turn", "carryfrag" };
		static const String g[] = { "Pistol", "RLPistol", "RLHandcannon", "RLMarksmanPistol" };
		for (int i = 0; i < c.Size(); i++) cfgs.Push(c[i]);
		for (int i = 0; i < g.Size(); i++) { class<Actor> k = g[i]; if (k) guns.Push(g[i]); else Console.Printf("PISTTEST absent %s", g[i]); }
	}

	static bool Want(int idx, int v) { return Actor.DD_SheetValue(idx) == v; }

	// Sheet values 173..185 for each rule set; must match RULES in pistols_test.py.
	static int RuleOf(String c, int idx)
	{
		bool rate = c == "spray" || c == "mult";
		if (idx == 173) return rate ? 10 : 0;
		if (idx == 174) return rate ? 30 : 0;
		if (idx == 175) return rate ? 25000 : 0;
		if (idx == 176) return rate ? 15000 : 0;
		if (idx == 177) return c == "mult" ? 15000 : 0;
		if (idx == 178) return c == "mult" ? 30000 : 0;
		if (idx == 179) return c == "reload" ? 2000 : c == "reload60" ? 6000 : 0;
		if (idx == 180) return c == "carry" || c == "carryfrag" ? 1 : 0;
		bool pool = c == "pool" || c == "carry" || c == "carryfrag";
		if (idx == 181) return pool ? 100 : 0;
		if (idx == 182) return pool ? 500 : 0;
		bool frag = c == "frag" || c == "turn" || c == "carryfrag";
		if (idx == 183) return frag ? 3 : 0;
		if (idx == 184) return frag ? 3300 : 0;
		if (idx == 185) return frag ? 5 : 0;
		return 0;
	}

	bool Arrived(String c)
	{
		if (c == "off" && Actor.DD_SheetValue(2) == -1) return true;
		for (int i = 173; i <= 185; i++) if (!Want(i, RuleOf(c, i))) return false;
		return true;
	}

	bool LineSet(String c) { return c == "carry" || c == "frag" || c == "turn" || c == "carryfrag"; }

	void Fill(PlayerInfo p, Weapon w)
	{
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = r.MaxAmount; }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = w.AmmoType2 ? m.MaxAmount : 50; }
	}

	Actor Put(Vector3 at, double health, class<Actor> k = "PistTestWall")
	{
		let a = Actor.Spawn(k, at);
		if (a) { a.health = int(health); a.SetOrigin(at, false); }
		return a;
	}

	void AddExtra(String name, Vector3 center, double health, class<Actor> k = "PistTestWall")
	{
		let a = Put(center - (0, 0, 28), health, k);
		extra.Push(a); extraName.Push(name); extraLost.Push(0);
		Console.Printf("PISTTEST placed %s at %.0f %.0f %.0f", name, center.X, center.Y, center.Z);
	}

	// The perk's own line: from A's centre at the puff's height, level, along the shooter's eye to the puff.
	void PlaceFollowers(String c, Actor a, Actor puff, PlayerPawn mo)
	{
		Vector3 eye = mo.pos + (0, 0, mo.player.viewz - mo.pos.z);
		Vector3 los = puff.pos - eye;
		Vector3 dir = (los.XY.Unit(), 0);
		Vector3 at = (a.pos.X, a.pos.Y, clamp(puff.pos.Z, a.pos.Z, a.pos.Z + a.height));
		Vector3 far = at + (dir.XY.Unit() * a.radius, 0);
		double yaw = atan2(dir.Y, dir.X), pitch = 0;
		Console.Printf("PISTTEST line yaw %.2f pitch %.2f", yaw, pitch);
		if (c == "carry") { AddExtra("B", at + dir * 64, 30); AddExtra("C", at + dir * 128, 1000000); }
		else if (c == "carryfrag") AddExtra("B", at + dir * 200, 1000000);
		else if (c == "frag") { AddExtra("B", far + Dir(yaw, pitch) * 120, 1000000); AddExtra("C", far + Dir(yaw + 15, pitch) * 140, 1000000); }
		else if (c == "turn") { AddExtra("D", far + Dir(yaw + 4, pitch) * 150, 1000000, "PistTestThin"); AddExtra("E", far + Dir(yaw - 7.5, pitch) * 180, 1000000, "PistTestThin"); }
	}

	static Vector3 Dir(double yaw, double pitch) { return (cos(yaw) * cos(pitch), sin(yaw) * cos(pitch), -sin(pitch)); }

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.DamageSource || !e.DamageSource.player) return;
		String c = cfg < cfgs.Size() ? cfgs[cfg] : "";
		if (target && e.Thing == target)
		{
			hits++; lost += e.Damage;
			Console.Printf("PISTTEST damage A %d inflictor %s health %d", e.Damage, e.Inflictor ? e.Inflictor.GetClassName() : 'None', target.health);
			if (phase == 11 && !placed && e.Inflictor) { placed = true; PlaceFollowers(c, target, e.Inflictor, PlayerPawn(e.DamageSource)); }
		}
		for (int i = 0; i < extra.Size(); i++)
		{
			if (extra[i] && e.Thing == extra[i])
			{
				extraLost[i] += e.Damage;
				Console.Printf("PISTTEST damage %s %d inflictor %s health %d", extraName[i], e.Damage, e.Inflictor ? e.Inflictor.GetClassName() : 'None', extra[i].health);
			}
		}
	}

	// Looks along 8 directions from the start for the longest clear line; the player stands at the start facing it.
	void FindSpot(Actor mo)
	{
		double best = 0;
		for (int a = 0; a < 360; a += 45)
		{
			FLineTraceData d;
			mo.LineTrace(a, 2000, 0, TRF_THRUACTORS, 32, 0, 0, d);
			if (d.Distance > best) { best = d.Distance; dirAngle = a; }
		}
		spot = mo.pos;
		spotFound = best >= 450;
		Console.Printf("PISTTEST spot angle %.0f clear %.0f", dirAngle, best);
	}

	Actor Place(double dist, double health)
	{
		Vector2 xy = spot.XY + Actor.AngleToVector(dirAngle, dist);
		return Put((xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy)), health);
	}

	void Clear()
	{
		if (target) target.Destroy();
		for (int i = 0; i < extra.Size(); i++) if (extra[i]) extra[i].Destroy();
		extra.Clear(); extraName.Clear(); extraLost.Clear();
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		if (!spotFound && phase != 99) { FindSpot(mo); if (!spotFound) { Console.Printf("PISTTEST nospot"); Console.Printf("PISTTEST done"); phase = 99; } }
		if (phase == 99) return;
		if (cfg > 0 && Actor.DD_SheetValue(2) != 1) cfg = cfgs.Size(); // No Daggerfall character: only "off" runs.
		if (cfg >= cfgs.Size()) { phase = 99; Console.Printf("PISTTEST done"); return; }
		String c = cfgs[cfg];
		p.attackdown = false;
		switch (phase)
		{
		case 0:
			Console.Printf("PISTTEST want %s", c);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(c)) { gun = 0; phase = 2; }
			else if (++wait > 350) { Console.Printf("PISTTEST timeout sheet %s", c); cfg++; phase = 0; }
			break;
		case 2: // select the gun
		{
			if (gun >= guns.Size()) { cfg++; phase = 0; break; }
			class<Weapon> k = guns[gun];
			mo.GiveInventory(k, 1);
			heldGun = Weapon(mo.FindInventory(k));
			p.PendingWeapon = heldGun;
			phase = 3; wait = 0;
			break;
		}
		case 3: // ready: set up the case
			if (p.ReadyWeapon == heldGun && (p.WeaponState & WF_WEAPONREADY))
			{
				Fill(p, heldGun);
				mo.SetOrigin(spot, false); mo.vel = (0, 0, 0); mo.angle = dirAngle; mo.pitch = 0;
				int first, second;
				[first, second] = DoomerfallWeaponCategory.Both(heldGun);
				Console.Printf("PISTTEST case %s %s cat=%s slot=%d cycle=%d", c, guns[gun], DoomerfallWeaponCategory.Label(first),
					DoomerfallWeaponCategory.SkillSlotOf(heldGun), DoomerfallPistols.FireCycle(heldGun));
				bool killA = c == "carry" || c == "carryfrag";
				target = Place(64, killA ? 20 : 1000000);
				phase = LineSet(c) ? 10 : 4;
				shot = 0; fireTic = -1; hits = lost = 0; placed = false;
			}
			else if (++wait > 175) { Console.Printf("PISTTEST noselect %s %s", c, guns[gun]); gun++; phase = 2; }
			break;
		case 4: // fire sets: 5 shots
			if (fireTic >= 0 && (p.WeaponState & WF_WEAPONREADY))
			{
				Console.Printf("PISTTEST shot %s %s n=%d hits=%d lost=%d cycle=%d", c, guns[gun], shot, hits, lost, level.maptime - fireTic);
				fireTic = -1;
				if (shot >= 5) { phase = 6; break; }
			}
			if (fireTic < 0 && (p.WeaponState & WF_WEAPONREADY))
			{
				Fill(p, heldGun);
				hits = 0; lost = 0;
				Console.Printf("PISTTEST fire tic=%d", level.maptime);
				mo.FireWeapon(null);
				fireTic = level.maptime; shot++;
			}
			else if (fireTic >= 0 && level.maptime - fireTic > 300) { Console.Printf("PISTTEST stuck %s %s", c, guns[gun]); phase = 6; }
			break;
		case 6: // reload from an empty magazine (guns with one)
			if (!heldGun.AmmoType2) { phase = 8; break; }
			if (fireTic < 0)
			{
				let m = mo.FindInventory(heldGun.AmmoType1);
				if (m) m.Amount = 0;
				Console.Printf("PISTTEST reloadstart tic=%d", level.maptime);
				mo.FireWeapon(null); // An empty magazine sends DRLA's Fire to its Reload.
				fireTic = level.maptime;
			}
			else if (level.maptime > fireTic && (p.WeaponState & WF_WEAPONREADY))
			{
				let m = mo.FindInventory(heldGun.AmmoType1);
				Console.Printf("PISTTEST reload %s %s tics=%d mag=%d", c, guns[gun], level.maptime - fireTic, m ? m.Amount : -1);
				phase = 8;
			}
			else if (level.maptime - fireTic > 300) { Console.Printf("PISTTEST stuck reload %s %s", c, guns[gun]); phase = 8; }
			break;
		case 8:
			Console.Printf("PISTTEST end %s %s", c, guns[gun]);
			Clear();
			gun++; phase = 2;
			break;
		case 10: // line sets: one shot (the pool is full: nothing was fired for a while)
			if (p.WeaponState & WF_WEAPONREADY)
			{
				Console.Printf("PISTTEST fire tic=%d", level.maptime);
				phase = 11;
				mo.FireWeapon(null);
				fireTic = level.maptime;
			}
			break;
		case 11:
			if (level.maptime - fireTic >= 40)
			{
				String s = String.Format("PISTTEST line %s %s hitsA=%d lostA=%d", c, guns[gun], hits, lost);
				for (int i = 0; i < extra.Size(); i++) s.AppendFormat(" %s=%d", extraName[i], extraLost[i]);
				Console.Printf("%s", s);
				phase = 8;
			}
			break;
		}
	}
}
