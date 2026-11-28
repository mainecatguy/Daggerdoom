version "4.10"

// Test harness for the exact "which gun fired this" hook (UZDoom/src/dd_shotsource.cpp, used by
// mods/doomerfall/src/zscript/DoomerfallShots.zs), driven by tools/gunsource/gunsource_test.py. Not part of the game.
//
// Each case: gun A fires, its shot is held still in the middle of a pack of targets, right where gun B's bomb will
// throw its fragments. The player switches to gun B and fires into the same pack. B's bomb bursts beside A's bomb, so
// B's fragments appear next to A's bomb, far nearer it than B's own blast: the old nearest-tagged-thing rule would give
// them gun A. Then A's shot is let go and bursts in the pack while B's spawns still fly. Every actor spawned during a
// case is logged with the tag it carries (GUNSRC spawned), so an untagged spawn shows up; every tag the mod makes is
// logged ("shots: tag ... by fired|child|carried|near"); every hit on a target logs the tag behind it.
//
// Families (the last letter of each class names its gun): bomb -> blast + two side fragments; fragment -> blast;
// blast (not a missile) -> spark, spawned WITHOUT SXF_TRANSFERPOINTERS so its target is the blast, not the player;
// spark -> ember. Gun C fires a bullet whose puff spawns the fragment (an untagged intermediary: the puff). Gun D
// spawns a helper actor next to the player, and the helper launches the bomb a few tics later (another intermediary).

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

class GunSrc play
{
	// Spawns "GunSrc<kind><family>" from a: the family is the last letter of a's class name.
	static void Kid(Actor a, String kind, double x, double y, double vx, double vy, double vz = 0, int flags = 0)
	{
		String n = a.GetClassName();
		String cls = "GunSrc" .. kind .. n.Mid(n.Length() - 1);
		class<Actor> k = cls;
		a.A_SpawnItemEx(k, x, y, 0, vx, vy, vz, 0, SXF_NOCHECKPOSITION | flags);
	}
}

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
class GunSrcGunB : GunSrcGunA { States { Fire: MISG B 8 A_FireProjectile("GunSrcBombB"); MISG B 6; Goto Ready; } }
class GunSrcGunC : GunSrcGunA { States { Fire: MISG B 8 A_FireBullets(0, 0, 1, 1, "GunSrcPuffC", FBF_NORANDOM); MISG B 6; Goto Ready; } }
class GunSrcGunD : GunSrcGunA { States { Fire: MISG B 8 A_SpawnItemEx("GunSrcHelperD", 24, 0, 32, 0, 0, 0, 0, SXF_NOCHECKPOSITION); MISG B 6; Goto Ready; } }

class GunSrcBomb : Actor // not a Rocket: a Rocket's smoke trail would be one class under both guns
{
	Default { Projectile; Radius 11; Height 8; Speed 20; Damage 5; }
	States
	{
	Spawn: MISL A -1 Bright; Stop;
	Death:
		MISL B 0 { GunSrc.Kid(self, "Blast", 0, 0, 0, 0); }
		MISL B 0 { GunSrc.Kid(self, "Frag", -8, 40, 0, 6); }
		MISL B 0 { GunSrc.Kid(self, "Frag", -8, -40, 0, -6); }
		MISL B 8 Bright A_Explode(20, 64);
		MISL CD 6 Bright;
		Stop;
	}
}
class GunSrcBombA : GunSrcBomb {}
class GunSrcBombB : GunSrcBomb {}
class GunSrcBombD : GunSrcBomb {}

class GunSrcFrag : Actor
{
	Default { Projectile; Radius 4; Height 4; Speed 6; Damage 3; }
	States
	{
	Spawn: BAL1 AB 10; Goto Death; // bursts by itself after 20 tics if it hits nothing
	Death:
		BAL1 C 0 { GunSrc.Kid(self, "Blast", 0, 0, 0, 0, 0, SXF_TRANSFERPOINTERS); }
		BAL1 CDE 4;
		Stop;
	}
}
class GunSrcFragA : GunSrcFrag {}
class GunSrcFragB : GunSrcFrag {}
class GunSrcFragC : GunSrcFrag {}
class GunSrcFragD : GunSrcFrag {}

class GunSrcBlast : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY }
	States
	{
	Spawn:
		MISL B 2;
		MISL C 0 { GunSrc.Kid(self, "Spark", 0, 0, 0, 0, 2); } // no SXF_TRANSFERPOINTERS: the spark targets this blast
		MISL C 4 A_Explode(10, 96);
		Stop;
	}
}
class GunSrcBlastA : GunSrcBlast {}
class GunSrcBlastB : GunSrcBlast {}
class GunSrcBlastC : GunSrcBlast {}
class GunSrcBlastD : GunSrcBlast {}

class GunSrcSpark : Actor
{
	Default { Projectile; Radius 2; Height 2; Speed 2; Damage 0; }
	States
	{
	Spawn: BAL1 A 8; Goto Death;
	Death:
		BAL1 C 0 { GunSrc.Kid(self, "Ember", 0, 0, 0, 0); }
		BAL1 C 2;
		Stop;
	}
}
class GunSrcSparkA : GunSrcSpark {}
class GunSrcSparkB : GunSrcSpark {}
class GunSrcSparkC : GunSrcSpark {}
class GunSrcSparkD : GunSrcSpark {}

class GunSrcEmber : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY }
	States { Spawn: BAL1 DE 3; Stop; }
}
class GunSrcEmberA : GunSrcEmber {}
class GunSrcEmberB : GunSrcEmber {}
class GunSrcEmberC : GunSrcEmber {}
class GunSrcEmberD : GunSrcEmber {}

class GunSrcPuffC : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY +PUFFONACTORS +ALWAYSPUFF }
	States
	{
	Spawn:
		PUFF A 1 Bright;
		PUFF A 0 { GunSrc.Kid(self, "Frag", 0, 0, -4, 0); }
		PUFF BCD 4;
		Stop;
	}
}

class GunSrcHelperD : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY }
	States
	{
	Spawn:
		TNT1 A 3;
		TNT1 A 0 { GunSrc.Kid(self, "Bomb", 0, 0, 20, 0); }
		TNT1 A 2;
		Stop;
	}
}

class GunSourceTest : EventHandler
{
	Array<String> gunA, gunB;
	Array<Actor> frozen, targets;
	Array<double> fvx, fvy, fvz;
	Array<int> serials; // every actor spawned in this case, and the root gun of each (WorldThingSpawned)
	Array<String> roots;
	int cur, phase, wait, t, seenA;
	bool freezing;
	Vector3 start;

	override void OnRegister()
	{
		gunA.Push("GunSrcGunA"); gunB.Push("GunSrcGunB");
		gunA.Push("GunSrcGunC"); gunB.Push("GunSrcGunD");
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
		let p = players[consoleplayer];
		if (!m || !p.mo || phase < 1 || phase > 4 || m is "Inventory" || m is "GunSrcTarget" || m.bIsMonster || m.player) return;
		DoomerfallShots.Tag(m); // tag it now if DoomerfallShots has not yet; safe to repeat
		let tag = DoomerfallShotTag.Of(m);
		// Ground truth from the engine's spawn chain, not from the mod: the gun held when the player's own action
		// spawned this actor's first ancestor ("other" when the chain does not reach the player in this case).
		int from = m.DD_SpawnedBy();
		String root = "other";
		if (from && from == p.mo.DD_SpawnSerial()) root = Held();
		else if (from) { int at = serials.Find(from); if (at < serials.Size()) root = roots[at]; }
		serials.Push(m.DD_SpawnSerial()); roots.Push(root);
		Console.Printf("GUNSRC spawned %s gun=%s gen=%d carrier=%d missile=%d puff=%d root=%s", m.GetClassName(), tag && tag.gun ? tag.gun.GetClassName() : 'None',
			tag ? tag.generation : -9, tag ? tag.carrier : 0, m.bMissile || m.default.bMissile, m.bIsPuff, root);
		if (phase != 1 || !tag || !tag.gun || tag.gun.GetClassName() != gunA[cur]) return;
		seenA++;
		if (!freezing || !m.bMissile) return;
		frozen.Push(m); fvx.Push(m.vel.x); fvy.Push(m.vel.y); fvz.Push(m.vel.z);
		m.vel = (0, 0, 0);
		m.bNoGravity = true;
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		// Every hit on a target, whoever Doom names as its source (a puff's or a helper's spawns name the puff or the
		// helper): the tag behind it, for the player.
		if (!e.Thing || !(e.Thing is "GunSrcTarget")) return;
		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		bool found = DoomerfallShots.Find(players[consoleplayer].mo, e.Inflictor, gun, skill, tag);
		Console.Printf("GUNSRC hit inf=%s found=%d gen=%d gun=%s held=%s tic=%d src=%s", e.Inflictor ? e.Inflictor.GetClassName() : 'None',
			found, tag ? tag.generation : -1, gun ? gun.GetClassName() : 'None', Held(), level.maptime, e.DamageSource ? e.DamageSource.GetClassName() : 'None');
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
		targets.Clear(); frozen.Clear(); fvx.Clear(); fvy.Clear(); fvz.Clear(); serials.Clear(); roots.Clear();
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
