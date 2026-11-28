version "4.10"

// Test harness for the Explosives perks (tools/explosives/explosives_test.py). Not part of the game.
// For each case it asks the fake Daggerfall peer for a rule set ("EXPTEST want <cfg>"), waits until Doom reads it,
// selects the gun, puts the player back at the start, places targets and fires one shot, then logs what everyone lost.
//   shot        a target 100 units ahead: the rocket hits it directly and its splash reaches the player.
//   pointblank  a target touching the player: the rocket explodes in its own spawn check.
//   switch      as shot, but the rocket is slowed to a crawl and the player switches to another gun while it flies:
//               the hit must still count for the launcher (the shared shot tag, DoomerfallShots).
//   chain       monster A (1000 max health, 1 left) ahead, B (same) beside it, and a stock DoomImp (1 left) beside B:
//               the rocket kills A, A's blast kills B, B's blast kills the imp.
//   pack        a grid of up to 400 test monsters (4000 max health, 130 left), the rocket kills the first, and the chain
//               runs through the pack; logs each tic's wall time while it runs.

class ExpTestTarget : Actor
{
	Default { Health 1000000; Radius 40; Height 64; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class ExpTestMonster : Actor
{
	Default { Monster; Health 1000; Radius 8; Height 40; +NOBLOOD +DONTTHRUST -COUNTKILL -SOLID } // not solid, so a dense pack fits
	States
	{
	Spawn: TROO A -1; Stop;
	Death: TROO IJKL 5; TROO M -1; Stop;
	}
}

class ExpPackMonster : ExpTestMonster { Default { Health 4000; } }

class ExpPerkTest : EventHandler
{
	Array<String> cfgs, kinds, guns;
	int step, gun, phase, wait, t;
	Vector3 start;
	bool startSet, packDone;
	Actor target;
	Array<Actor> pack;
	int targetLost, targetHits, playerLost, blastHurtPlayer;
	double lastTick, worstGap;
	int packTics;

	override void OnRegister()
	{
		static const String c[] = { "off", "dmg", "self25", "self75", "direct", "self25", "dmg", "chain", "chain" };
		static const String k[] = { "shot", "shot", "shot", "shot", "shot", "pointblank", "switch", "chain", "pack" };
		for (int i = 0; i < c.Size(); i++) { cfgs.Push(c[i]); kinds.Push(k[i]); }
		static const String g[] = { "RocketLauncher", "RLRocketLauncher" };
		for (int i = 0; i < g.Size(); i++) { class<Actor> kk = g[i]; if (kk) guns.Push(g[i]); }
	}

	bool Arrived(String c)
	{
		int d = Actor.DD_SheetValue(162), s = Actor.DD_SheetValue(163), x = Actor.DD_SheetValue(164), ch = Actor.DD_SheetValue(165);
		if (c == "off") return (d == 0 && s == 0 && x == 0 && ch == 0) || Actor.DD_SheetValue(2) == -1;
		if (c == "dmg") return d == 6000 && s == 0 && x == 0 && ch == 0;
		if (c == "self25") return d == 0 && s == 9500 && x == 0 && ch == 0;
		if (c == "self75") return d == 0 && s == 9900 && x == 0 && ch == 0;
		if (c == "direct") return d == 0 && s == 0 && x == 5000 && ch == 0;
		return d == 0 && s == 0 && x == 0 && ch == 2500 && Actor.DD_SheetValue(166) == 128; // chain
	}

	void Fill(PlayerInfo p, Weapon w)
	{
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = r.MaxAmount; }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = max(m.MaxAmount, 1); }
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		String inf = e.Inflictor ? e.Inflictor.GetClassName() : 'None';
		if (e.Thing && e.Thing.player)
		{
			Console.Printf("EXPTEST player hurt %d by %s tic %d flags %d type %s tagged %d", e.Damage, inf, level.maptime, e.DamageFlags, e.DamageType,
				DoomerfallShotTag.Of(e.Inflictor) != null);
			if (e.Inflictor is "DoomerfallChainBlast") blastHurtPlayer++;
			else if (phase == 4) playerLost += e.Damage;
		}
		if (target && e.Thing == target)
		{
			targetHits++; targetLost += e.Damage;
			let held = players[consoleplayer].ReadyWeapon;
			Console.Printf("EXPTEST target hit held %s slot %d", held ? held.GetClassName() : 'None', held ? DoomerfallWeaponCategory.SkillSlotOf(held) : -1);
		}
		if (phase == 4 && kinds[step] == "pack") return; // a kill line per monster would cost more than the chain
		if (e.Thing && e.Thing.health <= 0 && !e.Thing.player)
			Console.Printf("EXPTEST killed %s by %s tic %d", e.Thing.GetClassName(), inf, level.maptime);
	}

	Actor Monster(class<Actor> k, Vector3 pos)
	{
		let m = Actor.Spawn(k, pos);
		if (m) { m.health = 1; m.angle = 180; pack.Push(m); }
		return m;
	}

	// DRLA can hand the player armor, which absorbs or (fire-weak armor) adds to a hit after the perk changed it. Take
	// it away so what the player loses is what the perk let through.
	void StripArmor(Actor mo)
	{
		Array<Inventory> gone;
		for (let i = mo.Inv; i; i = i.Inv)
		{
			String n = i.GetClassName();
			if (i is "BasicArmor") { if (i.Amount > 0) Console.Printf("EXPTEST armor %s %d", n, i.Amount); i.Amount = 0; }
			else if ((i is "Armor" || i is "Powerup" || n.IndexOf("Armor") >= 0) && !(i is "Weapon")) gone.Push(i);
		}
		for (int k = 0; k < gone.Size(); k++) { Console.Printf("EXPTEST armor %s", gone[k].GetClassName()); gone[k].Destroy(); }
		String inv = "";
		for (let i = mo.Inv; i; i = i.Inv) if (!(i is "Weapon") && !(i is "Ammo")) inv = inv .. " " .. i.GetClassName();
		Console.Printf("EXPTEST inv fire100=%d dmgfactor=%.2f%s", mo.ApplyDamageFactor('Fire', 100), mo.DamageFactor, inv);
	}

	// The switch case: slow the player's rocket to a crawl as it spawns and put another gun up before it lands.
	override void WorldThingSpawned(WorldEvent e)
	{
		let a = e.Thing;
		PlayerInfo p = players[consoleplayer];
		if (phase != 4 || step >= kinds.Size() || kinds[step] != "switch" || !a || !a.bMissile || a.target != p.mo) return;
		a.vel *= 0.02;
		Console.Printf("EXPTEST slowed %s", a.GetClassName());
		if (p.PendingWeapon == WP_NOCHANGE) SlowAndSwitch(p);
	}

	void SlowAndSwitch(PlayerInfo p)
	{
		for (let i = p.mo.Inv; i; i = i.Inv)
		{
			let w = Weapon(i);
			if (w && w != p.ReadyWeapon && DoomerfallWeaponCategory.SkillSlotOf(w) != 6) { p.PendingWeapon = w; Console.Printf("EXPTEST switch to %s", w.GetClassName()); break; }
		}
	}

	void Place(PlayerInfo p, String kind)
	{
		let mo = p.mo;
		StripArmor(mo);
		pack.Clear();
		target = null;
		if (kind == "shot" || kind == "switch") target = Actor.Spawn("ExpTestTarget", mo.Vec3Angle(100, 0));
		else if (kind == "pointblank") target = Actor.Spawn("ExpTestTarget", mo.Vec3Angle(57, 0));
		else if (kind == "chain")
		{
			// B is too far for the rocket's splash to kill (50 left) but close enough for A's blast; the imp (20 left) is
			// out of reach of both and only B's blast reaches it.
			let a = Monster("ExpTestMonster", mo.Vec3Angle(100, 0));
			let b = Monster("ExpTestMonster", a.Vec3Offset(0, 100, 0));
			let imp = Monster("DoomImp", a.Vec3Offset(0, 200, 0));
			b.health = 50; imp.health = 20;
			Console.Printf("EXPTEST chain fits a=%d b=%d imp=%d sight ab=%d bi=%d", a.TestMobjLocation(), b.TestMobjLocation(), imp.TestMobjLocation(), a.CheckSight(b), b.CheckSight(imp));
		}
		else // pack: a grid ahead and to the left, only where a monster fits and can see the first one
		{
			// Pack monsters have 4000 maximum health and 130 left, so a stock rocket's splash (at most 128) cannot kill
			// them but the blasts (1000, 500, 250, ... at the centre) can: the chain has to carry through the pack.
			let first = Monster("ExpPackMonster", mo.Vec3Angle(100, 0));
			for (int i = 0; i < 40 && pack.Size() < 400; i++)
				for (int j = -20; j < 20 && pack.Size() < 400; j++)
				{
					if (i == 0 && j == 0) continue;
					Vector3 pos = first.Vec3Offset(i * 12, j * 12, 0);
					let m = Actor.Spawn("ExpPackMonster", pos);
					if (!m.TestMobjLocation() || m.Distance2D(mo) < 80 || !m.CheckSight(first)) { m.Destroy(); continue; }
					m.health = 130; pack.Push(m);
				}
			Console.Printf("EXPTEST pack size %d", pack.Size());
		}
		targetLost = 0; targetHits = 0; playerLost = 0; blastHurtPlayer = 0;
	}

	override void WorldTick()
	{
		PerkRuleFeed.Sync();
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		p.cheats |= CF_BUDDHA;
		double now = MSTimeF();
		if (phase == 4 && kinds[step] == "pack" && lastTick > 0)
		{
			worstGap = max(worstGap, now - lastTick);
			if (now - lastTick > 40) Console.Printf("EXPTEST slow tic %d gap %.1f ms", level.maptime, now - lastTick);
		}
		lastTick = now;
		if (step > 0 && Actor.DD_SheetValue(2) != 1) step = cfgs.Size(); // no Daggerfall character: only "off" runs
		if (step >= cfgs.Size())
		{
			if (phase != 99) { phase = 99; Console.Printf("EXPTEST done"); }
			return;
		}
		String c = cfgs[step], kind = kinds[step];
		switch (phase)
		{
		case 0:
			if (gun >= guns.Size()) { gun = 0; step++; break; }
			if (kind == "pack" && gun > 0) { gun++; break; } // one pack per run, with the first gun
			Console.Printf("EXPTEST want %s", c);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(c)) phase = 2;
			else if (++wait > 350) { Console.Printf("EXPTEST timeout sheet %s", c); step++; phase = 0; }
			break;
		case 2:
		{
			class<Weapon> k = guns[gun];
			mo.GiveInventory(k, 1);
			let w = Weapon(mo.FindInventory(k));
			if (p.ReadyWeapon != w) { p.PendingWeapon = w; if (++wait > 400) { Console.Printf("EXPTEST noselect %s", guns[gun]); gun++; phase = 0; } break; }
			if (!(p.WeaponState & WF_WEAPONREADY)) break;
			Fill(p, w);
			if (!startSet) { start = mo.pos; startSet = true; }
			mo.SetOrigin(start, false); mo.vel = (0, 0, 0); mo.angle = 0; mo.pitch = 0;
			int first, second;
			[first, second] = DoomerfallWeaponCategory.Both(w);
			Place(p, kind);
			Console.Printf("EXPTEST case %s %s %s cat=%s slot=%d", c, kind, guns[gun], DoomerfallWeaponCategory.Label(first), DoomerfallWeaponCategory.SkillSlotOf(w));
			phase = 3; t = 0; worstGap = 0; packTics = 0;
			break;
		}
		case 3: // one shot
			p.attackdown = true;
			if (p.WeaponState & WF_WEAPONREADY) { Console.Printf("EXPTEST fire tic %d at %.0f %.0f %.0f health %d buddha %d", level.maptime, mo.pos.x, mo.pos.y, mo.pos.z, mo.health, (p.cheats & CF_BUDDHA) != 0); mo.FireWeapon(null); phase = 4; t = 0; }
			else if (++t > 100) { Console.Printf("EXPTEST nofire %s", guns[gun]); phase = 4; t = 0; }
			break;
		case 4:
			p.attackdown = false;
			if (++t < (kind == "pack" ? 140 : kind == "switch" ? 150 : 45)) break;
			int dead = 0;
			for (int i = 0; i < pack.Size(); i++) if (pack[i] && pack[i].health <= 0) dead++;
			Console.Printf("EXPTEST end %s %s %s target=%d/%d player=%d blasthurt=%d dead=%d/%d gap=%.1f", c, kind, guns[gun],
				targetHits, targetLost, playerLost, blastHurtPlayer, dead, pack.Size(), worstGap);
			if (target) target.Destroy();
			for (int i = 0; i < pack.Size(); i++) if (pack[i]) pack[i].Destroy();
			pack.Clear(); target = null;
			gun++; phase = 0;
			break;
		}
	}
}

// Daggerfall sends the character sheet and Doom applies the rules (DoomerfallRules.zs), so a real character's perk rules
// come from its skill. This test's fake Daggerfall instead writes a hand-picked rule set in the sheet's reserved perk
// slots (155-180, in DoomerfallRules order); this hands that set to Doom's rules each tic, before the playsim uses them.
class PerkRuleFeed play
{
	static void Sync()
	{
		let r = DoomerfallRules(StaticEventHandler.Find("DoomerfallRules"));
		if (!r) return;
		r.testRules = Actor.DD_SheetValue(2) == 1; // no Daggerfall character: the rules read off, as in a real game
		for (int i = 0; i < DoomerfallRules.RuleCount; i++) r.testRule[i] = max(0, Actor.DD_SheetValue(155 + i));
	}
}
