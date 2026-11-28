version "4.10"

// Test harness for Automatics bands, free shots, suppression and the 100 stack (tools/automatics/bands_test.py). Not
// part of the game. For each case it asks the fake Daggerfall peer for a rule set ("BANDTEST want <cfg>"), selects the
// gun, puts target A in front of the player and target B straight behind A, and pulls the trigger for a while, logging
// the shots (tics in which the gun's ammo dropped), ammo, and each target's hits and damage.

class BandTestTarget : Actor
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

// A monster (suppression slows monsters) that stands still: its Speed is what A_Chase would step by.
class BandTestMonster : BandTestTarget
{
	Default
	{
		Speed 8;
		+ISMONSTER
	}
}

class BandTest : EventHandler
{
	Array<String> cfgs, guns;
	Array<int> lengths;
	Array<double> pitches, sides;
	Array<Actor> hitBy; // the distinct things (bullet puffs, projectiles) that damaged A this case
	bool reported;
	int c, phase, wait, t, shots, ammoStart, prevAmmo, hitsA, lostA, hitsB, lostB, endTic, hitTics, lastHitTic;
	Actor a, b;

	void Add(String cfg, String gun, int len, double pitch = 0, double side = 0)
	{
		class<Actor> k = gun;
		if (!k) { Console.Printf("BANDTEST absent %s", gun); return; }
		cfgs.Push(cfg); guns.Push(gun); lengths.Push(len); pitches.Push(pitch); sides.Push(side);
	}

	// Every bullet a player fires, as the gun made it (to compare an extra bullet with the shot's own).
	override bool WorldHitscanPreFired(WorldEvent e)
	{
		if (e.Thing && e.Thing.player)
			Console.Printf("BANDTEST bullet tic %d damage %d type %s puff %s flags %d angle %.3f pitch %.3f", level.maptime, e.Damage, e.DamageType,
				e.AttackPuffType ? e.AttackPuffType.GetClassName() : 'None', e.AttackLineFlags, e.AttackAngle, e.AttackPitch);
		return false;
	}

	// The band of a carried gun as it fires now: by its firing mode (count of the mode item) and alternate fire.
	void Report(Actor mo, String gun, String mode, int count, bool alt)
	{
		class<Weapon> k = gun;
		if (!k) { Console.Printf("BANDTEST absent %s", gun); return; }
		mo.GiveInventory(k, 1);
		let w = Weapon(mo.FindInventory(k));
		if (!w) { Console.Printf("BANDTEST absent %s", gun); return; }
		if (mode != "")
		{
			class<Inventory> mk = mode;
			mo.TakeInventory(mk, 1000);
			if (count > 0) mo.GiveInventory(mk, count);
		}
		bool was = w.bAltFire;
		w.bAltFire = alt;
		Console.Printf("BANDTEST report %s %d %d band=%d tics=%d", gun, count, alt, DoomerfallAutomaticBands.BandOf(w), DoomerfallAutomaticBands.TicsOf(k, mo, alt));
		w.bAltFire = was;
	}

	// A target 260 (else 200) away in the open, the player turned `side` degrees right of it, where autoaim's straight
	// probe misses it and its +5.625 degree probe finds it (P_SpawnPlayerMissile tries 0, +5.625, -5.625).
	Actor PlaceAside(Actor mo, class<Actor> tk, double side)
	{
		for (int d = 260; d >= 200; d -= 60)
		{
			for (double th = 0; th < 360; th += 15)
			{
				let t = Actor.Spawn(tk, mo.Vec3Angle(d, th));
				if (!t) continue;
				FTranslatedLineTarget lt0, lt1;
				mo.angle = th - side;
				mo.AimLineAttack(mo.angle, 1024, lt0, 0);
				mo.AimLineAttack(mo.angle + 5.625, 1024, lt1, 0);
				if (t.TestMobjLocation() && mo.CheckSight(t) && lt0.linetarget != t && lt1.linetarget == t) return t;
				t.Destroy();
			}
		}
		mo.angle = -side;
		return Actor.Spawn(tk, mo.Vec3Angle(260, 0));
	}

	override void OnRegister()
	{
		Add("off", "Chaingun", 60);
		Add("off", "RLBattleRifle", 60);
		Add("bands", "Chaingun", 60);
		Add("bands", "RLBattleRifle", 60);
		Add("bands", "RLUzi", 60);
		Add("bands", "RLThompson", 700);
		Add("bands", "RLMinigun", 300);
		Add("extra100", "RLThompson", 80);
		Add("extra100", "RLThompson", 80, -5); // looking 5 degrees up: autoaim lowers the shot onto A
		// A fast-band projectile gun (bands_test.dec), the player turned 12 degrees right of A (260 away, 40 radius: 8.7
		// degrees either side): only autoaim's +5.625 probe finds it.
		Add("extra100", "BandTestProjectileUzi", 60, 0, 12);
		Add("extra100", "BandTestProjectileUzi", 60, -5, 12);
		Add("extra100", "BandTestNoAimUzi", 60, -5, 12); // no autoaim: shots fly along the view, up and to the right of A
		Add("free3", "Chaingun", 90);
		Add("free3", "RLBattleRifle", 90);
		Add("big", "Chaingun", 90);
		Add("suppress", "Chaingun", 60);
	}

	// The sheet values that show a rule set has arrived (DFB_SHEET_AUTO_*, bridge/doomerfall_bridge.h).
	bool Arrived(String cfg)
	{
		int slowd = Actor.DD_SheetValue(195), fast = Actor.DD_SheetValue(199), free = Actor.DD_SheetValue(194);
		int sunder = Actor.DD_SheetValue(160), sup = Actor.DD_SheetValue(200);
		if (cfg == "off") return slowd == 0 && fast == 0 && free == 0 && sunder == 0 && sup == 0;
		if (cfg == "bands") return slowd == 25 && fast == 1000;
		if (cfg == "extra100") return slowd == 0 && fast == 10000;
		if (cfg == "free3") return free == 3 && slowd == 0;
		if (cfg == "big") return sunder == 200 && Actor.DD_SheetValue(159) == 4;
		return sup == 500 && sunder == 0;
	}

	int AmmoNow(PlayerInfo p)
	{
		let w = p.ReadyWeapon;
		if (!w || !w.AmmoType1) return -1;
		let m = p.mo.FindInventory(w.AmmoType1);
		return m ? m.Amount : 0;
	}

	void Fill(PlayerInfo p, bool lowOnly)
	{
		let w = p.ReadyWeapon;
		if (!w) return;
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = 300; }
		if (!w.AmmoType1) return;
		p.mo.GiveInventory(w.AmmoType1, 1);
		let m = p.mo.FindInventory(w.AmmoType1);
		if (!m) return;
		int full = w.AmmoType2 ? max(m.MaxAmount, 1) : 300; // stock: the reserve is the ammo it fires
		if (!lowOnly || m.Amount < 6) m.Amount = full;
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.DamageSource || !e.DamageSource.player) return;
		if (a && e.Thing == a && e.Inflictor && hitBy.Find(e.Inflictor) == hitBy.Size()) hitBy.Push(e.Inflictor);
		if (a && e.Thing == a) { hitsA++; lostA += e.Damage; if (lastHitTic != level.maptime) { hitTics++; lastHitTic = level.maptime; } }
		if (b && e.Thing == b) { hitsB++; lostB += e.Damage; }
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		if (!reported)
		{
			reported = true;
			for (int i = 0; i < 3; i++) Report(mo, "RLGrammatonClericBeretta", "RLGrammatonClericBerettaMode", i, false);
			Report(mo, "RLGrammatonClericBeretta", "RLGrammatonClericBerettaMode", 2, true); // its AltFire only switches mode
			Report(mo, "RLWidowmakerSMG", "", 0, false);
			Report(mo, "RLWidowmakerSMG", "", 0, true);
			Report(mo, "RLStormUzi", "", 0, false);
			Report(mo, "RLSussGun", "", 0, false);
			Report(mo, "RLNuclearOnslaught", "", 0, false);
			Report(mo, "RLHurricaneCannon", "", 0, false);
		}
		if (c >= cfgs.Size()) { if (phase != 99) { phase = 99; Console.Printf("BANDTEST done"); } return; }
		String cfg = cfgs[c], gun = guns[c];
		switch (phase)
		{
		case 0:
			Console.Printf("BANDTEST want %s", cfg);
			phase = 1; wait = 0;
			break;
		case 1:
			if (Arrived(cfg)) phase = 2;
			else if (++wait > 350) { Console.Printf("BANDTEST timeout sheet %s valid %d fmt %d 195=%d 199=%d", cfg, Actor.DD_SheetValue(2), Actor.DD_SheetValue(0), Actor.DD_SheetValue(195), Actor.DD_SheetValue(199)); c++; phase = 0; }
			break;
		case 2:
		{
			class<Weapon> k = gun;
			mo.GiveInventory(k, 1);
			let w = Weapon(mo.FindInventory(k));
			if (w) p.PendingWeapon = w;
			phase = 3; wait = 0;
			break;
		}
		case 3:
		{
			let w = p.ReadyWeapon;
			if (w && w.GetClassName() == gun && (p.WeaponState & WF_WEAPONREADY))
			{
				Fill(p, false);
				mo.angle = 0; mo.pitch = pitches[c];
				mo.vel = (0, 0, 0);
				class<Actor> tk = cfg == "suppress" ? "BandTestMonster" : "BandTestTarget";
				hitBy.Clear();
				a = sides[c] ? PlaceAside(mo, tk, sides[c]) : Actor.Spawn(tk, mo.Vec3Angle(120, 0));
				b = cfg == "suppress" || sides[c] ? null : Actor.Spawn("BandTestTarget", mo.Vec3Angle(260, 0));
				if (sides[c] && (!a.TestMobjLocation() || !mo.CheckSight(a))) Console.Printf("BANDTEST target blocked %s %s fits %d sight %d at %.0f %.0f", cfg, gun, a.TestMobjLocation(), mo.CheckSight(a), a.pos.x, a.pos.y);
				hitsA = lostA = hitsB = lostB = hitTics = 0; lastHitTic = -1;
				t = 0; shots = 0; ammoStart = AmmoNow(p); prevAmmo = ammoStart; endTic = -1;
				Console.Printf("BANDTEST case %s %s band=%d tics=%d slot=%d pitch=%.1f angle=%.1f", cfg, gun, DoomerfallAutomaticBands.BandOf(w),
					DoomerfallAutomaticBands.TicsOf(w.GetClass(), mo, w.bAltFire), DoomerfallWeaponCategory.SkillSlotOf(w), mo.pitch, mo.angle);
				phase = 4;
			}
			else if (++wait > 175) { Console.Printf("BANDTEST noselect %s %s", cfg, gun); c++; phase = 0; }
			break;
		}
		case 4:
		{
			bool refill = cfg == "bands" || cfg == "extra100" || cfg == "suppress";
			int now = AmmoNow(p);
			bool shot = now < prevAmmo; // fired in P_PlayerThink this tic (a refund comes later, in DoEffect)
			if (t < lengths[c])
			{
				p.attackdown = true;
				if (p.WeaponState & WF_WEAPONREADY)
				{
					int before = AmmoNow(p);
					mo.FireWeapon(null);
					if (AmmoNow(p) < before) shot = true;
				}
			}
			else p.attackdown = false;
			if (shot) { shots++; Console.Printf("BANDTEST shot %d tic %d", shots, level.maptime); }
			if (refill) Fill(p, true);
			prevAmmo = AmmoNow(p);
			if (cfg == "suppress" && a) Console.Printf("BANDTEST speed tic %d %.4f", level.maptime, a.Speed);
			int tail = cfg == "suppress" ? 200 : sides[c] ? 40 : 20; // projectiles fly 300 units to A
			if (++t >= lengths[c] + tail) phase = 5;
			break;
		}
		case 5:
		{
			Console.Printf("BANDTEST end %s %s shots=%d hittics=%d ammo=%d->%d hitsA=%d lostA=%d hitsB=%d lostB=%d hitby=%d", cfg, gun, shots, hitTics, ammoStart, AmmoNow(p), hitsA, lostA, hitsB, lostB, hitBy.Size());
			if (cfg == "big")
			{
				int hp = a.health;
				a.DamageMobj(null, null, 100, 'None');
				Console.Printf("BANDTEST probe %s %s hit=%d", cfg, gun, hp - a.health);
			}
			if (a) a.Destroy();
			if (b) b.Destroy();
			a = b = null;
			if (c + 1 < cfgs.Size() && cfgs[c + 1] == cfg) { c++; phase = 2; }
			else { c++; phase = 0; }
			break;
		}
		}
	}
}
