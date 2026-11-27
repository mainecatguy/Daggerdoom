version "4.10"

// Test harness for the Automatics perks (tools/automatics/automatics_test.py). Not part of the game.
// For each rule set it asks the fake Daggerfall peer for that sheet ("AUTOTEST want <cfg>"), waits until Doom reads it,
// then for each sample gun: selects it, fills its ammo, puts a target in front of the player and pulls the trigger in a
// fixed pattern, logging each shot's ammo and the target's health loss.

class AutoTestTarget : Actor
{
	Default
	{
		Health 1000000;
		Radius 40;
		Height 64;
		+SHOOTABLE
		+SOLID
		+NOBLOOD
		+DONTTHRUST
		+NOGRAVITY
	}
	States { Spawn: PLAY A -1; Stop; }
}

class AutoPerkTest : EventHandler
{
	// DFB_SHEET_AUTO_* (bridge/doomerfall_bridge.h)
	const IDX_DAMAGE = 155;
	const IDX_BURSTSHOTS = 157;
	const IDX_PERAMMO = 159;
	const IDX_SUNDER = 160;

	Array<String> cfgs;
	Array<String> guns;
	int cfg, gun, phase, wait, t, shots, lastShotTic, burstIndex, ammoStart, targetHits, targetLost, hitTics, lastHitTic;
	bool holdMode, decided; // held: the run started with +attack, so the trigger is really down (DRLA spin-up guns)
	Weapon heldGun;
	Actor target;

	override void OnRegister()
	{
		static const String c[] = { "off", "dmg", "burst", "ammo2", "ammo4", "sunder", "full" };
		static const String g[] = { "Chaingun", "RLChaingun", "RLBattleRifle", "RLUzi", "RLMinigun" };
		for (int i = 0; i < c.Size(); i++) cfgs.Push(c[i]);
		for (int i = 0; i < g.Size(); i++) { class<Actor> k = g[i]; if (k) guns.Push(g[i]); else Console.Printf("AUTOTEST absent %s", g[i]); }
	}

	// The sheet values that show a rule set has arrived.
	bool Arrived(String c)
	{
		int d = Actor.DD_SheetValue(IDX_DAMAGE), b = Actor.DD_SheetValue(IDX_BURSTSHOTS), a = Actor.DD_SheetValue(IDX_PERAMMO), s = Actor.DD_SheetValue(IDX_SUNDER);
		if (c == "off") return (d == 0 && b == 0 && a == 1 && s == 0) || Actor.DD_SheetValue(2) == -1;
		if (c == "dmg") return d == 6000 && b == 0 && a == 1 && s == 0;
		if (c == "burst") return d == 0 && b == 3 && a == 1 && s == 0;
		if (c == "ammo2") return d == 0 && b == 0 && a == 2 && s == 0;
		if (c == "ammo4") return d == 0 && b == 0 && a == 4 && s == 0;
		if (c == "sunder") return d == 0 && b == 0 && a == 1 && s == 100;
		return d == 6000 && b == 3 && a == 4 && s == 100; // full: skill 100
	}

	// Trigger pattern: true while the trigger is held at tic t of the case.
	bool Held(String c, int tt)
	{
		if (c == "burst") return tt < 40 || (tt >= 60 && tt < 100) || (tt >= 103 && tt < 123);
		return tt < 70;
	}

	int CaseLength(String c) { return c == "burst" ? 130 : 75; }

	int AmmoNow(PlayerInfo p, Weapon w = null)
	{
		if (!w) w = p.ReadyWeapon;
		if (!w || !w.AmmoType1) return -1;
		let a = p.mo.FindInventory(w.AmmoType1);
		return a ? a.Amount : 0;
	}

	void Fill(PlayerInfo p, Weapon w = null)
	{
		if (!w) w = p.ReadyWeapon;
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = 300; }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = max(m.MaxAmount, 1); }
		if (w.AmmoType1 && !w.AmmoType2) { let m = p.mo.FindInventory(w.AmmoType1); m.Amount = 300; } // stock: reserve is the ammo it fires
	}

	// DRLA guns spawn recoil and reload helper actors (not projectiles) aimed at the player while firing: they must
	// never count as shots. Logged so the test knows they really appeared.
	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		if (!m) return;
		String n = m.GetClassName();
		if (!m.bMissile && m.target && m.target.player && n.IndexOf("Recoil") >= 0)
			Console.Printf("AUTOTEST helper %s trigger=%d", m.GetClassName(), m.target.player.attackdown);
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (e.Thing && e.Thing.player) Console.Printf("AUTOTEST player hurt %d by %s tic %d", e.Damage, e.Inflictor ? e.Inflictor.GetClassName() : 'None', level.maptime);
		if (e.Thing && e.Thing is "AutoTestTarget" && e.Thing != target) Console.Printf("AUTOTEST stray target hit");
		if (target && e.Thing == target && e.DamageSource && e.DamageSource.player)
		{
			targetHits++; targetLost += e.Damage;
			if (level.maptime != lastHitTic) { hitTics++; lastHitTic = level.maptime; }
		}
	}

	// +attack mode: the gun fires by itself once raised. Target and ammo are ready before it is selected; switching to
	// the fist ends the case. Shots are counted as tics in which the target was hit.
	void HeldTick(PlayerInfo p)
	{
		let mo = p.mo;
		if (cfg > 0 && Actor.DD_SheetValue(2) != 1) cfg = cfgs.Size();
		if (cfg >= cfgs.Size()) { if (phase != 99) { phase = 99; Console.Printf("AUTOTEST done"); } return; }
		String c = cfgs[cfg];
		switch (phase)
		{
		case 0: if (!(p.cmd.buttons & BT_ATTACK)) break; Console.Printf("AUTOTEST want %s", c); phase = 1; wait = 0; break; // after +wait ... +attack
		case 1:
			if (Arrived(c)) { gun = 0; phase = 2; }
			else if (++wait > 350) { Console.Printf("AUTOTEST timeout sheet %s", c); cfg++; phase = 0; }
			break;
		case 2:
		{
			if (gun >= guns.Size()) { cfg++; phase = 0; break; }
			if (p.ReadyWeapon && p.ReadyWeapon.GetClassName() == guns[gun]) break;
			class<Weapon> k = guns[gun];
			mo.GiveInventory(k, 1);
			heldGun = Weapon(mo.FindInventory(k));
			Fill(p, heldGun);
			mo.angle = 0; mo.pitch = 0;
			target = Actor.Spawn("AutoTestTarget", mo.Vec3Angle(120, 0));
			targetHits = 0; targetLost = 0; hitTics = 0; lastHitTic = -1;
			ammoStart = AmmoNow(p, heldGun);
			int first, second;
			[first, second] = DoomerfallWeaponCategory.Both(heldGun);
			Console.Printf("AUTOTEST case %s %s cat=%s slot=%d", c, guns[gun], DoomerfallWeaponCategory.Label(first), DoomerfallWeaponCategory.SkillSlotOf(heldGun));
			p.PendingWeapon = heldGun;
			t = 0; phase = 4;
			break;
		}
		case 4:
			if (p.ReadyWeapon == heldGun && ++t == (c == "burst" ? 40 : 70))
			{
				p.PendingWeapon = Weapon(mo.FindInventory("Fist"));
				if (!p.PendingWeapon) { mo.GiveInventory("Fist", 1); p.PendingWeapon = Weapon(mo.FindInventory("Fist")); }
				phase = 5; wait = 0;
			}
			else if (++wait > 600) { Console.Printf("AUTOTEST noselect %s %s", c, guns[gun]); phase = 5; }
			break;
		case 5:
			if (p.ReadyWeapon != heldGun && ++wait > 20)
			{
				Console.Printf("AUTOTEST end %s %s shots=%d ammo=%d->%d hits=%d lost=%d", c, guns[gun], hitTics, ammoStart, AmmoNow(p, heldGun), targetHits, targetLost);
				int hp = target.health;
				target.DamageMobj(null, null, 100, 'None');
				let fresh = Actor.Spawn("AutoTestTarget", mo.Vec3Angle(400, 180));
				int fh = fresh.health;
				fresh.DamageMobj(null, null, 100, 'None');
				Console.Printf("AUTOTEST probe %s %s hit=%d fresh=%d", c, guns[gun], hp - target.health, fh - fresh.health);
				target.Destroy(); fresh.Destroy(); target = null;
				gun++; phase = 2;
			}
			break;
		}
	}

	// Which gun caused a hit (rule set "full" still loaded), with the stock Chaingun held:
	//   earlier   a projectile fired before the trigger was pulled lands while the Chaingun is held and the trigger is
	//             down: no perks. (A rocket would do, but in E1M1 a step stops rockets fired from the start.)
	//   barrel    a barrel the player blew up hits the target: no perks.
	//   fragment  a player-owned projectile spawned out in the world: no perks.
	//   own       a projectile fired with the Chaingun (trigger down), landing after a switch to the fist: perks.
	int src;
	Vector3 srcStart;
	bool srcStartSet;
	bool SourceTick(PlayerInfo p)
	{
		static const String names[] = { "earlier", "barrel", "fragment", "own", "close" };
		let mo = p.mo;
		if (phase == 90) // hold the Chaingun
		{
			mo.GiveInventory("Chaingun", 1);
			let w = Weapon(mo.FindInventory("Chaingun"));
			if (p.ReadyWeapon != w) { p.PendingWeapon = w; return true; }
			if (!(p.WeaponState & WF_WEAPONREADY) || ++wait < 10) return true;
			wait = 0;
			if (src >= names.Size()) return false;
			if (!srcStartSet) { srcStart = mo.pos; srcStartSet = true; }
			mo.SetOrigin(srcStart, false); mo.vel = (0, 0, 0); // blasts push the player; E1M1 has a step ~130 units east
			mo.angle = 0; mo.pitch = 0;
			target = Actor.Spawn("AutoTestTarget", mo.Vec3Angle(names[src] == "close" ? 60 : 110, 0)); // close: point blank
			targetHits = 0; targetLost = 0;
			Console.Printf("AUTOTEST src %s begin", names[src]);
			phase = 91; t = 0;
			return true;
		}
		String n = names[src];
		bool down = n == "earlier" ? t >= 3 : n == "own" ? t < 3 : true;
		p.attackdown = down;
		if (t == 0)
		{
			if (n == "earlier") mo.SpawnPlayerMissile("PlasmaBall");
			else if (n == "own" || n == "close") mo.SpawnPlayerMissile("PlasmaBall");
			else if (n == "barrel")
			{
				let b = Actor.Spawn("ExplosiveBarrel", target.Vec3Offset(40, 50, 0));
				b.DamageMobj(null, mo, 1000, 'None');
			}
			else
			{
				let m = Actor.Spawn("PlasmaBall", target.Vec3Offset(60, 0, 16));
				m.target = mo;
				m.vel = (-m.Speed, 0, 0);
			}
		}
		if (n == "own" && t == 3) { mo.GiveInventory("Fist", 1); p.PendingWeapon = Weapon(mo.FindInventory("Fist")); }
		if (++t >= 60)
		{
			p.attackdown = false;
			Console.Printf("AUTOTEST src %s end hits=%d lost=%d held=%s", n, targetHits, targetLost, p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'None');
			target.Destroy(); target = null;
			src++; phase = 90;
		}
		return true;
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		if (!decided)
		{
			decided = true;
			let hc = CVar.FindCVar("autotest_hold");
			holdMode = hc && hc.GetBool();
			if (holdMode) { guns.Clear(); static const String hg[] = { "RLChaingun", "RLMinigun" }; for (int i = 0; i < hg.Size(); i++) { class<Actor> k = hg[i]; if (k) guns.Push(hg[i]); } }
		}
		if (holdMode) { HeldTick(p); return; }
		if (cfg > 0 && Actor.DD_SheetValue(2) != 1) cfg = cfgs.Size(); // No Daggerfall character: only "off" runs.
		if (cfg >= cfgs.Size())
		{
			if (phase < 90 && Actor.DD_SheetValue(2) == 1) { phase = 90; src = 0; t = 0; }
			if (phase >= 90 && phase < 99 && SourceTick(p)) return;
			if (phase != 99) { phase = 99; Console.Printf("AUTOTEST done"); }
			return;
		}
		String c = cfgs[cfg];
		switch (phase)
		{
		case 0: // ask for the rule set
			Console.Printf("AUTOTEST want %s", c);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(c)) { gun = 0; phase = 2; }
			else if (++wait > 350) { Console.Printf("AUTOTEST timeout sheet %s", c); cfg++; phase = 0; }
			break;
		case 2: // select the gun
		{
			if (gun >= guns.Size()) { cfg++; phase = 0; break; }
			class<Weapon> k = guns[gun];
			mo.GiveInventory(k, 1);
			let w = Weapon(mo.FindInventory(k));
			if (w) p.PendingWeapon = w;
			phase = 3; wait = 0;
			break;
		}
		case 3:
		{
			let w = p.ReadyWeapon;
			if (w && w.GetClassName() == guns[gun] && (p.WeaponState & WF_WEAPONREADY))
			{
				Fill(p);
				int first, second;
				[first, second] = DoomerfallWeaponCategory.Both(w);
				Console.Printf("AUTOTEST case %s %s cat=%s slot=%d", c, guns[gun], DoomerfallWeaponCategory.Label(first), DoomerfallWeaponCategory.SkillSlotOf(w));
				mo.angle = 0; mo.pitch = 0;
				target = Actor.Spawn("AutoTestTarget", mo.Vec3Angle(120, 0));
				targetHits = 0; targetLost = 0; hitTics = 0; lastHitTic = -1;
				t = 0; shots = 0; lastShotTic = -1000; burstIndex = 0; ammoStart = AmmoNow(p);
				phase = 4;
			}
			else if (++wait > 175) { Console.Printf("AUTOTEST noselect %s %s", c, guns[gun]); gun++; phase = 2; }
			break;
		}
		case 4: // fire
		{
			let w = p.ReadyWeapon;
			if (Held(c, t))
			{
				p.attackdown = true;
				if (p.WeaponState & WF_WEAPONREADY)
				{
					int before = AmmoNow(p), hp = target.health;
					Console.Printf("AUTOTEST fire");
					mo.FireWeapon(null);
					int after = AmmoNow(p);
					if (after < before || hp != target.health)
					{
						if (level.maptime - lastShotTic > 10) burstIndex = 0; // 0.3 s
						burstIndex++; shots++; lastShotTic = level.maptime;
					}
					Console.Printf("AUTOTEST shot %s %s n=%d burst=%d tic=%d ammo=%d->%d lost=%d", c, guns[gun], shots, burstIndex, level.maptime, before, after, hp - target.health);
				}
			}
			else p.attackdown = false;
			if (++t >= CaseLength(c)) phase = 5;
			break;
		}
		case 5: // after the refunds of the last tic
		{
			// Shots: tics in which the target was hit (a stock Chaingun pull fires in two tics; DRLA's spin-up guns fire
			// a short string per pull, in tics after the pull).
			Console.Printf("AUTOTEST end %s %s shots=%d ammo=%d->%d hits=%d lost=%d", c, guns[gun], hitTics, ammoStart, AmmoNow(p), targetHits, targetLost);
			// Damage from another source: the shot target, and a fresh one nobody shot.
			int hp = target.health;
			target.DamageMobj(null, null, 100, 'None');
			let fresh = Actor.Spawn("AutoTestTarget", mo.Vec3Angle(400, 180));
			int fh = fresh.health;
			fresh.DamageMobj(null, null, 100, 'None');
			Console.Printf("AUTOTEST probe %s %s hit=%d fresh=%d", c, guns[gun], hp - target.health, fh - fresh.health);
			target.Destroy(); fresh.Destroy();
			gun++; phase = 2;
			break;
		}
		}
	}
}
