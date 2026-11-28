version "4.10"

// Paired-run harness for the Pistols perks (tools/pistols/pistols_paired.py). Not part of the game.
// Finds the longest clear line from the start, then every cycle: the player stands at the start facing along it with
// DRLA's Pistol (the stock Pistol without DRLA), target A (20 health) stands 64 units ahead, the player fires once, and
// when A is first hit the harness puts B (huge) 200 units straight behind A and C (huge) on the +15 degree fork
// 140 units from A's far side (the perk deals carry-through and fragments a tick later). 40 tics later it logs what
// Daggerfall's sheet said and what each target lost. Map monsters are removed so Daggerfall's real HP is not at risk.

class PistPairTarget : Actor
{
	Default { Health 1000000; Radius 20; Height 56; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY +ISMONSTER }
	States { Spawn: PLAY A -1; Stop; Death: PLAY H 4; PLAY N -1; Stop; }
}

class PistPairHarness : EventHandler
{
	int t, cycle, lostA, lostB, lostC, hitA;
	bool found, placed, fired;
	Actor a, b, c;
	Vector3 spot;
	double dir;

	int anyHits;
	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.DamageSource || !e.DamageSource.player) return;
		anyHits++;
		if (a && e.Thing == a)
		{
			lostA += e.Damage;
			if (!hitA) hitA = e.Damage;
			if (!placed && e.Inflictor) { placed = true; Followers(e.Inflictor, PlayerPawn(e.DamageSource)); }
		}
		if (b && e.Thing == b) lostB += e.Damage;
		if (c && e.Thing == c) lostC += e.Damage;
	}

	Actor Put(Vector3 center)
	{
		let x = Actor.Spawn("PistPairTarget", center - (0, 0, 28));
		if (x) x.SetOrigin(center - (0, 0, 28), false);
		return x;
	}

	// The perk's line: from A's centre at the puff's height, level, along the shooter's eye to the puff.
	void Followers(Actor puff, PlayerPawn mo)
	{
		Vector3 eye = mo.pos + (0, 0, mo.player.viewz - mo.pos.z);
		Vector3 los = puff.pos - eye;
		Vector3 d = (los.XY.Unit(), 0);
		Vector3 at = (a.pos.X, a.pos.Y, clamp(puff.pos.Z, a.pos.Z, a.pos.Z + a.height));
		Vector3 far = at + d * a.radius;
		double yaw = atan2(d.Y, d.X) + 15;
		b = Put(at + d * 200);
		c = Put(far + (cos(yaw), sin(yaw), 0) * 140);
	}

	bool FindLine(Actor mo)
	{
		double best = 0;
		for (int ang = 0; ang < 360; ang += 30)
		{
			FLineTraceData d;
			mo.LineTrace(ang, 2000, 0, TRF_THRUACTORS, 32, 0, 0, d);
			if (d.Distance > best) { best = d.Distance; dir = ang; }
		}
		spot = mo.pos;
		Console.Printf("PAIRED spot angle %.0f clear %.0f", dir, best);
		return best >= 450;
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || mo.health <= 0 || level.maptime < 140 || Actor.DD_SheetValue(2) != 1) return;
		if (!found)
		{
			let it = ThinkerIterator.Create("Actor");
			Actor m;
			while (m = Actor(it.Next())) if (m.bIsMonster && !(m is "PistPairTarget") && !m.player) m.Destroy();
			found = FindLine(mo);
			if (!found) { Console.Printf("PAIRED nospot"); return; }
		}
		class<Weapon> k = "RLPistol";
		if (!k) k = "Pistol";
		let w = p.ReadyWeapon;
		if (!w || !(w is k))
		{
			if (!mo.FindInventory(k)) mo.GiveInventory(k, 1);
			p.PendingWeapon = Weapon(mo.FindInventory(k));
			return;
		}
		p.attackdown = false;
		if (!a)
		{
			if (!(p.WeaponState & WF_WEAPONREADY)) return;
			if (w.AmmoType2) { mo.GiveInventory(w.AmmoType2, 1); mo.FindInventory(w.AmmoType2).Amount = 50; }
			let m = mo.FindInventory(w.AmmoType1);
			if (!m) { mo.GiveInventory(w.AmmoType1, 1); m = mo.FindInventory(w.AmmoType1); }
			m.Amount = w.AmmoType2 ? m.MaxAmount : 50;
			mo.SetOrigin(spot, false); mo.vel = (0, 0, 0); mo.angle = dir; mo.pitch = 0;
			Vector2 xy = spot.XY + Actor.AngleToVector(dir, 64);
			a = Actor.Spawn("PistPairTarget", (xy.X, xy.Y, mo.pos.z)); // the player's height: the map's floors can be 3D models
			a.health = 20;
			t = 0; lostA = lostB = lostC = hitA = 0; placed = fired = false; cycle++;
			String s = String.Format("PAIRED start %d skill=%d rules", cycle, Actor.DD_SheetSkill(7));
			for (int i = 181; i <= 193; i++) s.AppendFormat(" %d", Actor.DD_SheetValue(i));
			Console.Printf("%s", s);
			return;
		}
		if (t >= 2 && !fired && (p.WeaponState & WF_WEAPONREADY))
		{
			fired = true;
			mo.FireWeapon(null);
			Console.Printf("PAIRED fire %s mag %d reserve %d ready %d dist %.0f z %.0f/%.0f angle %.0f", w.GetClassName(), w.AmmoType1 ? mo.CountInv(w.AmmoType1) : -1,
				w.AmmoType2 ? mo.CountInv(w.AmmoType2) : -1, (p.WeaponState & WF_WEAPONREADY) != 0, a.Distance2D(mo), a.pos.z, mo.pos.z, mo.angle);
		}
		if (t == 20) Console.Printf("PAIRED after mag %d hits %d a %d", w.AmmoType1 ? mo.CountInv(w.AmmoType1) : -1, anyHits, a.health);
		if (++t == 42)
		{
			Console.Printf("PAIRED end %d skill=%d hitA=%d lostA=%d lostB=%d lostC=%d", cycle, Actor.DD_SheetSkill(7), hitA, lostA, lostB, lostC);
			a.Destroy(); a = null;
			if (b) b.Destroy();
			if (c) c.Destroy();
		}
	}
}
