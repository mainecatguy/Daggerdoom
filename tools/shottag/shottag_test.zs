version "4.10"

// Test harness for shot tags (mods/doomerfall/src/zscript/DoomerfallShots.zs), driven by tools/shottag/shottag_test.py.
// Not part of the game. For each case: hold the gun, fire one shot at a target, hold every projectile the shot makes
// still until the player has switched to the fist, then let them fly. Every hit on the target logs the tag behind it
// (DoomerfallShots.Find) and the gun held at that moment. shottest_mode "save" freezes a rocket after the switch and
// autosaves; "load" (the save loaded) lets it fly and logs the same.

class ShotTestTarget : Actor
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

// Stand-ins for a mod's shrapnel rocket, for stock Doom: the bomb's death spawns a separate explosion actor and two
// fragments, and each fragment's death spawns another explosion (generation 2).
class ShotTestBomb : Rocket
{
	States
	{
	Death:
		MISL B 0 A_SpawnItemEx("ShotTestBlast", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 0 A_SpawnItemEx("ShotTestFrag", -4, 0, 0, 8, 0, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 0 A_SpawnItemEx("ShotTestFrag", -4, 8, 0, 8, 0, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 8 Bright A_Explode(20, 64);
		MISL CD 6 Bright;
		Stop;
	}
}

class ShotTestFrag : Actor
{
	Default
	{
		Projectile;
		Radius 4;
		Height 4;
		Speed 8;
		Damage 3;
	}
	States
	{
	Spawn:
		BAL1 A -1;
		Stop;
	Death:
		BAL1 C 0 A_SpawnItemEx("ShotTestBlast", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION | SXF_TRANSFERPOINTERS);
		BAL1 CDE 4;
		Stop;
	}
}

class ShotTestBlast : Actor
{
	Default
	{
		+NOBLOCKMAP
		+NOGRAVITY
	}
	States
	{
	Spawn:
		MISL B 2;
		MISL C 4 A_Explode(10, 96);
		Stop;
	}
}

class ShotTagTest : EventHandler
{
	Array<String> guns, shells;
	Array<Actor> frozen;
	Array<double> fvx, fvy, fvz;
	String mode;
	int cur, phase, wait, t, saveWait, shotSeen;
	bool freezing, decided;
	transient bool live; // false again after a save loads
	Vector3 start;
	Actor target;

	override void OnRegister()
	{
		// gun, and the projectile the harness fires for it ("" = the gun fires its own). "close": the target stands at
		// point blank, so the shot hits inside the firing action; nothing is held still and the gun stays up.
		static const String g[] = { "RocketLauncher", "RocketLauncher", "RocketLauncher", "RocketLauncher", "BFG9000",
			"RLRocketLauncher", "RLRocketLauncher", "RLClusterBombLauncher", "RLShrapnelCannon" };
		static const String s[] = { "", "ShotTestBomb", "close", "ShotTestBomb+close", "", "", "close", "", "" };
		bool drla = Has("RLRocketLauncher");
		for (int i = 0; i < g.Size(); i++)
		{
			class<Actor> k = g[i];
			if (!k || (i < 5) == drla) continue; // each run: its own guns only
			guns.Push(g[i]);
			shells.Push(s[i]);
		}
	}

	static bool Has(String n) { class<Actor> k = n; return k != null; }

	String Held()
	{
		let p = players[consoleplayer];
		return p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'None';
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		if (!m || !m.target || !m.target.player) return;
		if (phase == 1 && (m.bMissile || m.default.bMissile)) shotSeen++;
		if (!freezing || !m.bMissile) return;
		frozen.Push(m); fvx.Push(m.vel.x); fvy.Push(m.vel.y); fvz.Push(m.vel.z);
		m.vel = (0, 0, 0);
		m.bNoGravity = true;
	}

	void Release()
	{
		for (int i = 0; i < frozen.Size(); i++)
		{
			let m = frozen[i];
			if (!m) continue;
			m.bNoGravity = m.default.bNoGravity;
			m.vel = (fvx[i], fvy[i], fvz[i]);
		}
		Console.Printf("SHOTTEST release n=%d held=%s", frozen.Size(), Held());
		frozen.Clear(); fvx.Clear(); fvy.Clear(); fvz.Clear();
		freezing = false;
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!target || e.Thing != target || !e.DamageSource || !e.DamageSource.player) return;
		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		bool found = DoomerfallShots.Find(e.DamageSource, e.Inflictor, gun, skill, tag);
		Console.Printf("SHOTTEST hit inf=%s found=%d gen=%d gun=%s skill=%d held=%s dmg=%d tic=%d", e.Inflictor ? e.Inflictor.GetClassName() : 'None',
			found, tag ? tag.generation : -1, gun ? gun.GetClassName() : 'None', skill, Held(), e.Damage, level.maptime);
	}

	void Loaded()
	{
		mode = "load";
		Console.Printf("SHOTTEST loaded held=%s", Held());
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (!a.bMissile || !a.target || !a.target.player) continue;
			let tag = DoomerfallShotTag.Of(a);
			Console.Printf("SHOTTEST inflight %s tag=%s gen=%d", a.GetClassName(), tag && tag.gun ? tag.gun.GetClassName() : 'None', tag ? tag.generation : -1);
		}
	}

	void Fill(PlayerInfo p, Weapon w)
	{
		if (w.AmmoType2) { p.mo.GiveInventory(w.AmmoType2, 1); let r = p.mo.FindInventory(w.AmmoType2); if (r) r.Amount = max(r.MaxAmount, 50); }
		if (w.AmmoType1) { p.mo.GiveInventory(w.AmmoType1, 1); let m = p.mo.FindInventory(w.AmmoType1); if (m) m.Amount = max(m.MaxAmount, 1); }
		if (w.AmmoType1 && !w.AmmoType2) { let m = p.mo.FindInventory(w.AmmoType1); m.Amount = max(m.MaxAmount, 50); } // a BFG must not run dry and switch guns
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		if (!decided)
		{
			decided = true;
			if (mode != "load") { let c = CVar.FindCVar("shottest_mode"); mode = c ? c.GetString() : ""; }
			if (mode == "save")
			{
				String g = Has("RLRocketLauncher") ? "RLRocketLauncher" : "RocketLauncher";
				guns.Clear(); shells.Clear(); guns.Push(g); shells.Push("");
			}
			Console.Printf("SHOTTEST start mode=%s cases=%d", mode, guns.Size());
		}
		if (mode == "idle") return; // waiting for the console to load the save
		p.cheats |= CF_GODMODE;
		if (phase == 5 && !live) { Loaded(); Release(); phase = 3; t = 0; }
		live = true;
		if (Actor.DD_SheetValue(2) != 1) { if (++wait > 700) { Console.Printf("SHOTTEST nosheet"); Console.Printf("AUTOTEST done"); wait = -100000; } return; }
		if (cur >= guns.Size()) { if (phase != 99) { phase = 99; Console.Printf("AUTOTEST done"); } return; }
		switch (phase)
		{
		case 0: // hold the gun
		{
			class<Weapon> k = guns[cur];
			mo.GiveInventory(k, 1);
			let w = Weapon(mo.FindInventory(k));
			if (!w) { Console.Printf("SHOTTEST nogun %s", guns[cur]); cur++; break; }
			Fill(p, w);
			if (p.ReadyWeapon != w) { p.PendingWeapon = w; if (++wait > 350) { Console.Printf("SHOTTEST noselect %s", guns[cur]); cur++; wait = 0; } break; }
			if (!(p.WeaponState & WF_WEAPONREADY) || ++wait < 10) break;
			wait = 0;
			if (start == (0, 0, 0)) start = mo.pos;
			mo.SetOrigin(start, false); mo.vel = (0, 0, 0); mo.angle = 0; mo.pitch = 0;
			bool close = shells[cur].IndexOf("close") >= 0;
			target = Actor.Spawn("ShotTestTarget", mo.Vec3Angle(close ? 60 : 110, 0));
			Console.Printf("SHOTTEST case %s %s", guns[cur], shells[cur]);
			freezing = !close; phase = 1; t = 0; shotSeen = 0;
			break;
		}
		case 1: // one shot, then switch to the fist
			if (shotSeen == 0)
			{
				p.attackdown = true;
				String proj = shells[cur];
				int plus = proj.IndexOf("+");
				if (plus >= 0) proj = proj.Left(plus);
				if (proj == "close") proj = "";
				if (proj != "") { if (t == 0) mo.SpawnPlayerMissile(proj); }
				else if (p.WeaponState & WF_WEAPONREADY) mo.FireWeapon(null);
				if (++t > 120) { Console.Printf("SHOTTEST noshot %s", guns[cur]); Release(); phase = 3; t = 0; }
				break;
			}
			p.attackdown = false;
			if (!freezing) { phase = 3; t = 0; break; } // point blank: already landed, the gun stays up
			mo.GiveInventory("Fist", 1);
			p.PendingWeapon = Weapon(mo.FindInventory("Fist"));
			phase = 2; wait = 0;
			break;
		case 2: // let the shot fly once the fist is up
			if (!p.ReadyWeapon || !(p.ReadyWeapon is "Fist") || !(p.WeaponState & WF_WEAPONREADY))
			{
				if (++wait > 350) { Console.Printf("SHOTTEST nofist"); Release(); phase = 3; t = 0; }
				break;
			}
			if (mode == "save") { phase = 5; saveWait = 0; level.MakeAutoSave(); Console.Printf("SHOTTEST saving frozen=%d", frozen.Size()); break; }
			Release(); phase = 3; t = 0;
			break;
		case 3:
			if (++t >= 140)
			{
				Console.Printf("SHOTTEST end %s", guns[cur]);
				if (target) target.Destroy();
				target = null; cur++; phase = 0; wait = 0;
			}
			break;
		case 5: // the save holds this phase: the save run stops here, the load run lets the shot fly (above)
			if (++saveWait > 35) { Console.Printf("SHOTTEST saved"); Console.Printf("AUTOTEST done"); phase = 99; }
			break;
		}
	}
}
