version "4.10"

// Paired-run harness for the Shotguns perks (tools/shotguns/shotguns_paired.py). Not part of the game.
// Finds a wall near the start (a ray 30 units up, above monster step height, stops on it), then every cycle: the player
// stands 124 units from the wall facing it with DRLA's Double Shotgun (the stock Shotgun without DRLA), a fresh target
// stands 64 units ahead (40 from the wall), the player fires once, and 45 tics later the harness logs what Daggerfall's
// sheet said and what happened to the target.

class ShotPairTarget : Actor
{
	Default { Health 1000000; Radius 20; Height 56; Mass 100; +SHOOTABLE +SOLID +NOBLOOD }
	States { Spawn: PLAY A -1; Stop; Pain: PLAY G 8; Goto Spawn; }
}

class ShotPairHarness : EventHandler
{
	int t, cycle, lost;
	bool pain, found, atSpot;
	int settle;
	Actor target;
	Vector3 spot, start;
	double dir;

	override void WorldThingDamaged(WorldEvent e)
	{
		if (target && e.Thing == target && e.DamageSource && e.DamageSource.player) lost += e.Damage;
	}

	// The start may be out on open terrain and the town walls may be invisible blocking lines, so walk a target-sized
	// probe with real movement from points on rings around the start until a line (not an actor) stops it after at
	// least 120 units of flat walking. The probe's last place is about 20 units from that wall.
	bool Find(Actor mo, int far = 8192)
	{
		let probe = Actor.Spawn("ShotPairTarget", mo.pos);
		probe.bSolid = false; probe.bShootable = false;
		bool ok = false;
		for (int r = 0; r <= far && !ok; r += 1024)
		{
			for (int b = 0; b < 360 && !ok; b += (r ? 30 : 360))
			{
				Vector2 from = mo.pos.XY + Actor.AngleToVector(b, r);
				if (!level.IsPointInLevel((from.X, from.Y, 0))) continue;
				for (int i = 0; i < 12 && !ok; i++)
				{
					double a = dir + i * 30; // The last wall's direction first.
					probe.SetOrigin((from.X, from.Y, level.PointInSector(from).floorplane.ZatPoint(from)), false);
					double z0 = probe.pos.z;
					Vector2 step = Actor.AngleToVector(a, 8);
					for (int s = 0; s < 80; s++)
					{
						if (probe.TryMove(probe.pos.XY + step, 1)) { probe.SetZ(probe.floorz); if (abs(probe.pos.z - z0) > 12) break; continue; }
						if (!probe.BlockingLine || probe.BlockingMobj || s < (far ? 15 : 8)) break;
						Vector2 xy = probe.pos.XY - Actor.AngleToVector(a, 84);
						spot = (xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy));
						dir = a;
						ok = true;
						Console.Printf("PAIRED spot ring %d bearing %d angle %.0f walked %d at %.0f %.0f", r, b, a, s * 8, xy.X, xy.Y);
						break;
					}
				}
			}
		}
		probe.Destroy();
		return ok;
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || mo.health <= 0 || level.maptime < 140 || Actor.DD_SheetValue(2) != 1) return;
		if (!found) // The town loads at run time: try once a second for a minute.
		{
			if (level.maptime % 35) return;
			found = Find(mo);
			if (!found && level.maptime > 2240) Console.Printf("PAIRED nospot");
			if (!found) return;
		}
		String gunName = "RLDoubleShotgun";
		class<Weapon> k = gunName;
		if (!k) k = "Shotgun";
		let w = p.ReadyWeapon;
		if (!w || !(w is k))
		{
			if (!mo.FindInventory(k)) mo.GiveInventory(k, 1);
			p.PendingWeapon = Weapon(mo.FindInventory(k));
			return;
		}
		p.attackdown = false;
		if (!target)
		{
			if (!(p.WeaponState & WF_WEAPONREADY)) return;
			// Moving far makes the overworld treadmill shift the map, so go there, let it settle, and find the wall again
			// from where the player stands.
			if (!atSpot) { mo.SetOrigin(spot, false); mo.vel = (0, 0, 0); atSpot = true; settle = 0; return; }
			if (++settle < 20) return;
			if (!Find(mo, 0)) { Console.Printf("PAIRED lost the wall"); found = atSpot = false; return; }
			if (w.AmmoType2) { mo.GiveInventory(w.AmmoType2, 1); mo.FindInventory(w.AmmoType2).Amount = 50; }
			let m = mo.FindInventory(w.AmmoType1);
			if (!m) { mo.GiveInventory(w.AmmoType1, 1); m = mo.FindInventory(w.AmmoType1); }
			m.Amount = w.AmmoType2 ? m.MaxAmount : 50;
			mo.SetOrigin(spot, false); mo.vel = (0, 0, 0); mo.angle = dir; mo.pitch = 0;
			Vector2 xy = spot.XY + Actor.AngleToVector(dir, 64);
			target = Actor.Spawn("ShotPairTarget", (xy.X, xy.Y, level.PointInSector(xy).floorplane.ZatPoint(xy)));
			start = (target.Distance2D(mo), 0, 0);
			t = 0; lost = 0; pain = false; cycle++;
			Console.Printf("PAIRED start %d skill=%d dmg=%d reload=%d pellets=%d knock=%d slam=%d collide=%d", cycle, Actor.DD_SheetSkill(4),
				Actor.DD_SheetValue(162), Actor.DD_SheetValue(163), Actor.DD_SheetValue(164), Actor.DD_SheetValue(165),
				Actor.DD_SheetValue(166), Actor.DD_SheetValue(167));
			return;
		}
		if (t == 2) mo.FireWeapon(null);
		if (target.InStateSequence(target.CurState, target.FindState("Pain"))) pain = true;
		if (++t == 48)
		{
			Console.Printf("PAIRED end %d skill=%d moved=%.1f pain=%d lost=%d", cycle, Actor.DD_SheetSkill(4), target.Distance2D(mo) - start.x, pain, lost);
			target.Destroy();
			target = null;
		}
	}
}
