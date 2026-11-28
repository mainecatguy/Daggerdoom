version "4.10"

// Paired-run harness for the Automatics perks (tools/automatics/automatics_paired.py). Not part of the game.
// Every cycle it holds DRLA's Chaingun (the stock Chaingun without DRLA), puts a fresh target in front of the player,
// holds the trigger for 72 tics, then hits the target once for 100 from nowhere, and logs what Daggerfall's sheet said.

class AutoPairTarget : Actor
{
	Default { Health 1000000; Radius 40; Height 64; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class AutoPairHarness : EventHandler
{
	int t, shots, hits, ammoStart, cycle;
	Actor target;

	int AmmoNow(PlayerInfo p)
	{
		let w = p.ReadyWeapon;
		if (!w || !w.AmmoType1) return -1;
		let a = p.mo.FindInventory(w.AmmoType1);
		return a ? a.Amount : 0;
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || mo.health <= 0 || level.maptime < 140 || Actor.DD_SheetValue(2) != 1) return;
		String gunName = "RLChaingun";
		class<Weapon> k = gunName;
		if (!k) k = "Chaingun";
		let w = p.ReadyWeapon;
		if (!w || !(w is k))
		{
			if (!mo.FindInventory(k)) mo.GiveInventory(k, 1);
			p.PendingWeapon = Weapon(mo.FindInventory(k));
			return;
		}
		if (!target)
		{
			if (!(p.WeaponState & WF_WEAPONREADY)) return;
			if (w.AmmoType2) { mo.GiveInventory(w.AmmoType2, 1); mo.FindInventory(w.AmmoType2).Amount = 300; }
			let m = mo.FindInventory(w.AmmoType1);
			if (!m) { mo.GiveInventory(w.AmmoType1, 1); m = mo.FindInventory(w.AmmoType1); }
			m.Amount = w.AmmoType2 ? m.MaxAmount : 300;
			mo.pitch = 0;
			target = Actor.Spawn("AutoPairTarget", mo.Vec3Angle(120, mo.angle, 0));
			t = 0; shots = 0; hits = 0; ammoStart = AmmoNow(p); cycle++;
			Console.Printf("PAIRED start %d skill=%d dmg=%d burstbp=%d burstn=%d per=%d sunder=%d/%d", cycle, Actor.DD_SheetSkill(5),
				DoomerfallRules.Get(0), DoomerfallRules.Get(1), DoomerfallRules.Get(2), DoomerfallRules.Get(4),
				DoomerfallRules.Get(5), DoomerfallRules.Get(6));
			return;
		}
		if (t < 72)
		{
			p.attackdown = true;
			if (p.WeaponState & WF_WEAPONREADY)
			{
				int before = AmmoNow(p), hp = target.health;
				Console.Printf("AUTOTEST fire");
				mo.FireWeapon(null);
				shots++;
				if (hp != target.health) hits++;
				Console.Printf("PAIRED shot %d n=%d ammo=%d->%d lost=%d", cycle, shots, before, AmmoNow(p), hp - target.health);
			}
		}
		else p.attackdown = false;
		if (++t == 90)
		{
			int hp = target.health;
			target.DamageMobj(null, null, 100, 'None');
			Console.Printf("PAIRED end %d skill=%d shots=%d hits=%d ammo=%d->%d probe=%d", cycle, Actor.DD_SheetSkill(5), shots, hits,
				ammoStart, AmmoNow(p), hp - target.health);
			target.Destroy();
			target = null;
		}
	}
}
