version "4.10"

// Test harness for the exact "which gun fired this" hook (UZDoom/src/dd_shotsource.cpp, used by
// mods/doomerfall/src/zscript/DoomerfallShots.zs), driven by tools/gunsource/gunsource_test.py. Not part of the game.
//
// Each case: gun A fires a bomb, which is held still in the middle of a pack of targets, right where gun B's bomb will
// throw its fragments. The player switches to gun B and fires into the same pack. B's bomb bursts beside A's bomb, so
// B's fragments appear next to A's bomb, far nearer it than B's own blast: the old nearest-tagged-thing rule would give
// them gun A. Then A's bomb is let go and bursts in the pack while B's fragments still fly. Every tag the mod makes is
// logged ("shots: tag ... by fired|child|near"), and every hit on a target logs the tag behind it.

class GunSrcTarget : Actor
{
	Default
	{
		Health 1000000;
		Radius 20;
		Height 56;
		+SHOOTABLE
		+SOLID
		+NOBLOOD
		+DONTTHRUST
		+NOGRAVITY
	}
	States { Spawn: PLAY A -1; Stop; }
}

// Two guns with their own families of shots: bomb -> blast + two side fragments -> each fragment's blast.
class GunSrcGunA : Weapon
{
	Default { Weapon.SelectionOrder 9000; Weapon.AmmoUse 0; +WEAPON.AMMO_OPTIONAL +WEAPON.NOAUTOFIRE }
	States
	{
	Ready: MISG A 1 A_WeaponReady; Loop;
	Deselect: MISG A 1 A_Lower(12); Loop;
	Select: MISG A 1 A_Raise(12); Loop;
	Fire: MISG B 8 A_FireProjectile("GunSrcBombA"); MISG B 6; Goto Ready;
	}
}

class GunSrcGunB : GunSrcGunA
{
	States { Fire: MISG B 8 A_FireProjectile("GunSrcBombB"); MISG B 6; Goto Ready; }
}

class GunSrcBombA : Rocket
{
	Default { Speed 20; Damage 5; }
	States
	{
	Death:
		MISL B 0 A_SpawnItemEx("GunSrcBlastA", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 0 A_SpawnItemEx("GunSrcFragA", -8, 40, 0, 0, 6, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 0 A_SpawnItemEx("GunSrcFragA", -8, -40, 0, 0, -6, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 8 Bright A_Explode(20, 64);
		MISL CD 6 Bright;
		Stop;
	}
}

class GunSrcBombB : GunSrcBombA
{
	States
	{
	Death:
		MISL B 0 A_SpawnItemEx("GunSrcBlastB", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 0 A_SpawnItemEx("GunSrcFragB", -8, 40, 0, 0, 6, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 0 A_SpawnItemEx("GunSrcFragB", -8, -40, 0, 0, -6, 0, 0, SXF_NOCHECKPOSITION);
		MISL B 8 Bright A_Explode(20, 64);
		MISL CD 6 Bright;
		Stop;
	}
}

class GunSrcFragA : Actor
{
	Default { Projectile; Radius 4; Height 4; Speed 6; Damage 3; }
	States
	{
	Spawn: BAL1 AB 10; Goto Death; // bursts by itself after 20 tics if it hits nothing
	Death:
		BAL1 C 0 A_SpawnItemEx("GunSrcBlastA", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION | SXF_TRANSFERPOINTERS);
		BAL1 CDE 4;
		Stop;
	}
}

class GunSrcFragB : GunSrcFragA
{
	States
	{
	Spawn: BAL1 AB 10; Goto Death; // its own, or the Goto would take GunSrcFragA's Death
	Death:
		BAL1 C 0 A_SpawnItemEx("GunSrcBlastB", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION | SXF_TRANSFERPOINTERS);
		BAL1 CDE 4;
		Stop;
	}
}

class GunSrcBlastA : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY }
	States { Spawn: MISL B 2; MISL C 4 A_Explode(10, 96); Stop; }
}

class GunSrcBlastB : GunSrcBlastA {}

class GunSourceTest : EventHandler
{
	Array<String> gunA, gunB;
	Array<Actor> frozen, targets;
	Array<double> fvx, fvy, fvz;
	int cur, phase, wait, t, seenA;
	bool freezing;
	Vector3 start;

	override void OnRegister()
	{
		gunA.Push("GunSrcGunA"); gunB.Push("GunSrcGunB");
		String n = "RLClusterBombLauncher";
		class<Actor> k = n;
		if (k) { gunA.Push("RLClusterBombLauncher"); gunB.Push("RLRocketLauncher"); }
	}

	String Held()
	{
		let p = players[consoleplayer];
		return p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'None';
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		if (!m || !m.target || !m.target.player || !m.bMissile) return;
		if (phase == 1) seenA++;
		if (!freezing) return;
		frozen.Push(m); fvx.Push(m.vel.x); fvy.Push(m.vel.y); fvz.Push(m.vel.z);
		m.vel = (0, 0, 0);
		m.bNoGravity = true;
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.Thing || !(e.Thing is "GunSrcTarget") || !e.DamageSource || !e.DamageSource.player) return;
		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		bool found = DoomerfallShots.Find(e.DamageSource, e.Inflictor, gun, skill, tag);
		Console.Printf("GUNSRC hit inf=%s found=%d gen=%d gun=%s held=%s tic=%d", e.Inflictor ? e.Inflictor.GetClassName() : 'None',
			found, tag ? tag.generation : -1, gun ? gun.GetClassName() : 'None', Held(), level.maptime);
	}

	void Fill(PlayerInfo p, Weapon w)
	{
		Class<Ammo> types[2] = { w.AmmoType1, w.AmmoType2 };
		for (int i = 0; i < 2; i++)
		{
			if (!types[i]) continue;
			p.mo.GiveInventory(types[i], 1);
			let a = p.mo.FindInventory(types[i]);
			if (a) a.Amount = max(a.MaxAmount, 50);
		}
	}

	// Selects gun k; true once it is up and ready.
	bool Hold(PlayerInfo p, String k)
	{
		class<Weapon> c = k;
		p.mo.GiveInventory(c, 1);
		let w = Weapon(p.mo.FindInventory(c));
		if (!w) { Console.Printf("GUNSRC nogun %s", k); return false; }
		Fill(p, w);
		if (p.ReadyWeapon != w) { p.PendingWeapon = w; return false; }
		return (p.WeaponState & WF_WEAPONREADY) != 0;
	}

	void Fire(PlayerInfo p)
	{
		p.attackdown = true;
		if (p.WeaponState & WF_WEAPONREADY) p.mo.FireWeapon(null);
	}

	void EndCase()
	{
		for (int i = 0; i < targets.Size(); i++) if (targets[i]) targets[i].Destroy();
		targets.Clear(); frozen.Clear(); fvx.Clear(); fvy.Clear(); fvz.Clear();
		Console.Printf("GUNSRC end %s %s", gunA[cur], gunB[cur]);
		cur++; phase = 0; wait = 0; t = 0;
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || level.maptime < 20) return;
		p.cheats |= CF_GODMODE;
		if (Actor.DD_SheetValue(2) != 1) { if (++wait > 700) { Console.Printf("GUNSRC nosheet"); Console.Printf("AUTOTEST done"); wait = -100000; } return; }
		if (cur >= gunA.Size()) { if (phase != 99) { phase = 99; Console.Printf("AUTOTEST done"); } return; }
		if (++wait > 1200) { Console.Printf("GUNSRC stuck phase %d", phase); EndCase(); return; }
		switch (phase)
		{
		case 0: // gun A up: set the scene and fire A
			if (!Hold(p, gunA[cur])) break;
			if (start == (0, 0, 0)) start = mo.pos;
			mo.SetOrigin(start, false); mo.vel = (0, 0, 0); mo.angle = 0; mo.pitch = 0;
			for (int i = -1; i <= 1; i++) targets.Push(Actor.Spawn("GunSrcTarget", mo.Vec3Offset(160, 48 * i, 0)));
			Console.Printf("GUNSRC case %s %s", gunA[cur], gunB[cur]);
			freezing = true; seenA = 0; phase = 1; t = 0;
			break;
		case 1: // A's shot held still beside B's line of fire, where B's fragments will appear
			if (!seenA) { Fire(p); if (++t > 120) { Console.Printf("GUNSRC noshot %s", gunA[cur]); EndCase(); } break; }
			p.attackdown = false;
			freezing = false;
			for (int i = 0; i < frozen.Size(); i++)
				if (frozen[i]) frozen[i].SetOrigin(mo.Vec3Offset(125, 40, frozen[i].pos.z - mo.pos.z), false);
			Console.Printf("GUNSRC held %d of %s", frozen.Size(), gunA[cur]);
			phase = 2; t = 0;
			break;
		case 2: // gun B up and fired into the pack
			if (t == 0 && !Hold(p, gunB[cur])) break;
			Fire(p);
			if (++t == 1) Console.Printf("GUNSRC fire %s held=%s", gunB[cur], Held());
			if (t >= 12) { p.attackdown = false; phase = 3; t = 0; }
			break;
		case 3: // B's fragments are flying: let A's shot go
			if (++t < 4) break;
			for (int i = 0; i < frozen.Size(); i++)
				if (frozen[i]) { frozen[i].bNoGravity = frozen[i].default.bNoGravity; frozen[i].vel = (fvx[i], fvy[i], fvz[i]); }
			Console.Printf("GUNSRC release %d held=%s", frozen.Size(), Held());
			phase = 4; t = 0;
			break;
		case 4:
			if (++t >= 140) EndCase();
			break;
		}
	}
}
