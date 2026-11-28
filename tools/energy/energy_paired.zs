version "4.10"

// Paired-run harness for the Energy Weapons perks (tools/energy/energy_paired.py). Not part of the game.
// Every cycle: the player stands at the start with DRLA's Plasma Rifle (the stock one without DRLA), faces the first
// direction with room, a fresh target stands 128 units ahead and a test monster 40 units beside it (inside the splash
// radius); the player fires 3 shots and 45 tics after the first the harness logs what Daggerfall's sheet said, the projectiles'
// speed and what the target and its neighbour lost.

class EnPairTarget : Actor
{
	Default { Health 1000000; Radius 16; Height 56; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class EnPairMonster : Actor
{
	Default { Monster; Health 1000000; Radius 8; Height 40; +NOBLOOD +DONTTHRUST -COUNTKILL }
	States { Spawn: TROO A -1; Stop; }
}

class EnPairHarness : EventHandler
{
	int t, cycle, shots, lost, nearLost, missiles;
	double speedSum, defSpeed;
	Actor target, near;
	Vector3 start;
	bool startSet;
	double dir;

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.DamageSource || !e.DamageSource.player) return;
		if (target && e.Thing == target) lost += e.Damage;
		if (near && e.Thing == near) nearLost += e.Damage;
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		let a = e.Thing;
		let mo = players[consoleplayer].mo;
		if (!target || !a || !a.bMissile || a.target != mo) return;
		missiles++; speedSum += a.vel.Length(); defSpeed = a.default.Speed;
	}

	// Kill the city's attackers so only the harness's actors are around.
	void Quiet(Actor mo)
	{
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next())) if (a.bIsMonster && a != target && a != near && !(a is "EnPairMonster") && a.health > 0) a.Destroy();
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || mo.health <= 0 || level.maptime < 140 || Actor.DD_SheetValue(2) != 1) return;
		p.cheats |= CF_BUDDHA;
		String gunName = "RLPlasmaRifle";
		class<Weapon> k = gunName;
		if (!k) k = "PlasmaRifle";
		let w = p.ReadyWeapon;
		if (!w || !(w is k))
		{
			if (!mo.FindInventory(k)) mo.GiveInventory(k, 1);
			p.PendingWeapon = Weapon(mo.FindInventory(k));
			return;
		}
		if (w.AmmoType2) { mo.GiveInventory(w.AmmoType2, 1); mo.FindInventory(w.AmmoType2).Amount = 50; }
		let m = mo.FindInventory(w.AmmoType1);
		if (!m) { mo.GiveInventory(w.AmmoType1, 1); m = mo.FindInventory(w.AmmoType1); }
		m.Amount = max(m.MaxAmount, 50);
		if (!startSet) { start = mo.pos; startSet = true; }
		if (!target)
		{
			if (!(p.WeaponState & WF_WEAPONREADY)) return;
			Quiet(mo);
			mo.SetOrigin(start, false); mo.vel = (0, 0, 0); mo.pitch = 0;
			for (int i = 0; i < 12 && !target; i++)
			{
				double a = dir + i * 30;
				let tg = Actor.Spawn("EnPairTarget", mo.Vec3Angle(128, a));
				let nb = Actor.Spawn("EnPairMonster", tg.Vec3Angle(40, a + 90));
				if (tg.TestMobjLocation() && nb.TestMobjLocation() && mo.CheckSight(tg) && tg.CheckSight(nb) && abs(tg.pos.z - mo.pos.z) < 8)
				{ target = tg; near = nb; dir = a; }
				else { tg.Destroy(); nb.Destroy(); }
			}
			if (!target) { Console.Printf("PAIRED nospot"); return; }
			mo.angle = dir;
			t = 0; lost = 0; nearLost = 0; shots = 0; missiles = 0; speedSum = 0; cycle++;
			Console.Printf("PAIRED start %d skill=%d dmg=%d splash=%d radius=%d speed=%d burn=%d convert=%d burst=%d burstradius=%d", cycle,
				Actor.DD_SheetSkill(9), DoomerfallRules.Get(18), DoomerfallRules.Get(19), DoomerfallRules.Get(20), DoomerfallRules.Get(21),
				DoomerfallRules.Get(22), DoomerfallRules.Get(23), DoomerfallRules.Get(24), DoomerfallRules.Get(25));
			return;
		}
		t++;
		if (shots < 3 && (p.WeaponState & WF_WEAPONREADY)) { mo.SetOrigin(start, false); mo.angle = dir; mo.pitch = 0; mo.FireWeapon(null); shots++; }
		if (t == 45)
		{
			Console.Printf("PAIRED end %d skill=%d shots=%d lost=%d near=%d missiles=%d vel=%.3f default=%.3f", cycle, Actor.DD_SheetSkill(9), shots,
				lost, nearLost, missiles, missiles ? speedSum / missiles : 0, defSpeed);
			target.Destroy(); near.Destroy();
			target = null; near = null;
		}
	}
}
