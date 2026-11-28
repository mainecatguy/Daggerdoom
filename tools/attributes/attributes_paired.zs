version "3.3"

// Test only, loaded by tools/attributes/attributes_paired.py as its own pk3 (never part of doomerfall.pk3).
// Whenever the Strength and Speed Doom reads from Daggerfall's sheet change and then stay put for a second, measures:
//   - melee damage: a 20-point hit from the player through P_DamageMobj, once while holding fists (Hand-to-Hand), once
//     with a chainsaw (Melee skill) and once with a pistol (control), each against a fresh dummy;
//   - movement: the player is put back at the start with no velocity, facing a fixed angle, and how far it travels in
//     12 tics of held forward input (supplied by the harness through TweakSpeeds, as MovePlayer does) is recorded, plus the factor PlayerPawn.TweakSpeeds
//     (the function Doom's movement calls) applies to a walking forward move.
// Prints one line per measurement:
//   ATTR str=<live> spd=<live> fist=<lost> saw=<lost> pistol=<lost> move=<units> tweak=<factor> item=<0|1>
// and once, the source test (SourceTest): ATTRSRC ...
class AttrDummy : Actor
{
	Default
	{
		Health 1000000;
		Radius 8;
		Height 16;
		+SHOOTABLE
		+ISMONSTER // so autoaim (A_BFGSpray's AimLineAttack) picks it
		+NOGRAVITY
		+NOBLOOD
		+NOPAIN
		+DONTTHRUST
	}
}

// A bleeding target for the real weapon test: DRLA's melee puffs and rails take their bleeding-monster paths on it.
class AttrBleeder : Actor
{
	Default
	{
		Health 1000000;
		Radius 20;
		Height 56;
		+SHOOTABLE
		+SOLID
		+ISMONSTER
		+NOGRAVITY
		+NOPAIN
		+DONTTHRUST
	}
}

// On the player, given after DoomerfallAttributeEffects so it comes first in the inventory chain: sees an attack's
// damage before Strength, and asks the effects item whether it calls the hit melee.
class AttrRawRecorder : Inventory
{
	Default { +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE Inventory.MaxAmount 1; }

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags, double angle)
	{
		if (passive || !(source is "AttrBleeder")) return;
		let h = AttrPaired(StaticEventHandler.Find("AttrPaired"));
		let fx = DoomerfallAttributeEffects(owner.FindInventory("DoomerfallAttributeEffects"));
		if (!h) return;
		h.raw = damage;
		h.rawStr = Actor.DD_SheetStat(0);
		h.rawMelee = fx && fx.MeleeAttack(inflictor, flags);
		h.rawInflictor = inflictor ? inflictor.GetClassName() : 'none';
	}
}

// Given just before the effects item is given back, so it comes right after it in the chain: the damage after the
// attribute rules and before the gun perks, which would otherwise blur the check (as in the stopped attributes card 06
// run, 9c7bbb35).
class AttrMidRecorder : Inventory
{
	Default { +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE Inventory.MaxAmount 1; }

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags, double angle)
	{
		if (passive || !(source is "AttrBleeder")) return;
		let h = AttrPaired(StaticEventHandler.Find("AttrPaired"));
		if (h) h.mid = damage;
	}
}

// On the bleeder: sees the damage after every offensive modifier, Strength included.
class AttrPostRecorder : Inventory
{
	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags, double angle)
	{
		let h = AttrPaired(StaticEventHandler.Find("AttrPaired"));
		if (passive && h) h.Landed(damage);
	}
}

class AttrPaired : StaticEventHandler
{
	// The real weapon test: each weapon's own Fire state (PlayerPawn.FireWeapon, as the fire button does) against a
	// bleeding target in front, with the weapon really switched to. melee = the weapon is in the Melee skill or fists.
	static const String WpnClass[] = { "RLFist", "RLChainsaw", "RLPiercingChainsaw", "RLDoubleChainsaw", "RLRipper", "RLPistol", "RLRailgun", "RLEnergysaw" };
	static const int WpnMelee[] = { 1, 1, 1, 1, 1, 0, 0, 1 };
	int wi, wPhase, wTics, wTries, wWait;
	bool wForced;
	Actor bleeder;
	int raw, rawStr, mid;
	bool rawMelee;
	Name rawInflictor;
	int wHits, wOk, wBoosted, wClassed, wRaw, wPost;
	Name wInflictor;

	// One hit landed on the bleeder: compare with what the raw recorder saw for the same hit.
	void Landed(int post)
	{
		if (raw < 0) return;
		int s = min(rawStr, 100);
		int boosted = s < 0 ? raw : max(1, int(raw * (1 + s / 100.0)));
		bool melee = WpnMelee[wi] != 0;
		int want = melee ? boosted : raw;
		wHits++;
		wRaw += raw;
		wPost += post;
		// Compared right after the effects item (mid). Guns: Daggerfall's test holds Agility and Luck at 50, so no
		// gun factor and no crit.
		if (mid == want) wOk++;
		if (melee && boosted > raw && mid == boosted) wBoosted++;
		if (rawMelee == melee) wClassed++;
		wInflictor = rawInflictor;
		raw = -1;
	}

	// Runs while the stats stay put and the walk test is not moving the player; Interrupt pauses it.
	void WeaponTest(PlayerInfo p)
	{
		let mo = p.mo;
		if (wi >= WpnClass.Size()) return;
		class<Weapon> wc = WpnClass[wi];
		if (!wc) { wi++; return; } // without DRLA
		let w = Weapon(mo.FindInventory(wc));
		if (!w) { mo.GiveInventory(wc, 1); w = Weapon(mo.FindInventory(wc)); }
		// Every tic: Doomerfall's ammo sync may set the count back to what Daggerfall's inventory holds.
		if (w && w.AmmoType1) mo.GiveInventory(w.AmmoType1, 9999);
		if (w && w.AmmoType2) mo.GiveInventory(w.AmmoType2, 9999);
		if (++wWait > 300) { wTries = 99; wPhase = 1; wTics = 99; } // stuck: report what there is and go on
		if (wPhase == 0)
		{
			// A DRLA gun can sit in its refire state after the harness's fire (no button is ever held), so the switch
			// never happens: then bring the next weapon up through its own Select state (which gives DRLA's type token).
			if (wWait == 150 && w && p.ReadyWeapon != w)
			{
				p.ReadyWeapon = w;
				p.PendingWeapon = WP_NOCHANGE;
				p.SetPsprite(PSP_WEAPON, w.GetUpState());
				wForced = true;
			}
			if (!Ready(p, wc) || !(p.WeaponState & WF_WEAPONREADY)) return;
			// The raw recorder must come before the effects item and the mid recorder right after it. The effects item is
			// left alone (re-giving it, as an earlier version did, made the railgun land no hit): the raw recorder goes
			// to the head of the chain (AddInventory), and the mid recorder is spliced in right behind the effects item.
			let fx = mo.FindInventory("DoomerfallAttributeEffects");
			if (!fx) return;
			if (!mo.FindInventory("AttrRawRecorder")) mo.GiveInventory("AttrRawRecorder", 1);
			if (!mo.FindInventory("AttrMidRecorder"))
			{
				mo.GiveInventory("AttrMidRecorder", 1);
				let m = mo.Inv; // just added, so at the head
				if (m is "AttrMidRecorder" && m != fx)
				{
					mo.Inv = m.Inv;
					m.Inv = fx.Inv;
					fx.Inv = m;
				}
			}
			int rawPos = -1, fxPos = -1, midPos = -1, n = 0;
			for (Inventory it = mo.Inv; it; it = it.Inv, n++)
			{
				if (it is "AttrRawRecorder") rawPos = n;
				else if (it == fx) fxPos = n;
				else if (it is "AttrMidRecorder") midPos = n;
			}
			if (!(rawPos < fxPos && midPos == fxPos + 1)) return; // order not as needed: wait (stuck check reports)
			bleeder = Actor.Spawn("AttrBleeder", mo.Vec3Angle(mo.radius + 40, mo.Angle), NO_REPLACE);
			bleeder.GiveInventory("AttrPostRecorder", 1);
			mo.Pitch = 0;
			raw = -1;
			Fire1(p);
			return;
		}
		if (++wTics < 35 || (!(p.WeaponState & WF_WEAPONREADY) && wTries < 99)) return;
		if (wHits == 0 && wTries < 4) { Fire1(p); return; } // DRLA fists may first need raising for a fight
		Console.Printf("ATTRWPN weapon=%s melee=%d hits=%d ok=%d boosted=%d classed=%d raw=%d post=%d inflictor=%s held=%s ammo=%d pending=%s wstate=%d forced=%d",
			WpnClass[wi], WpnMelee[wi], wHits, wOk, wBoosted, wClassed, wRaw, wPost, wInflictor,
			p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'none', w && w.AmmoType1 ? mo.CountInv(w.AmmoType1) : -1,
			p.PendingWeapon && p.PendingWeapon != WP_NOCHANGE ? p.PendingWeapon.GetClassName() : 'nochange', p.WeaponState, wForced);
		Interrupt();
		wi++;
		wForced = false;
		wTries = wHits = wOk = wBoosted = wClassed = wRaw = wPost = wWait = 0;
	}

	void Fire1(PlayerInfo p)
	{
		PlayerPawn(p.mo).FireWeapon(null);
		wPhase = 1;
		wTics = 0;
		wTries++;
	}

	void Interrupt()
	{
		if (bleeder) bleeder.Destroy();
		wPhase = 0;
	}

	const SettleTics = 70;
	const MoveTics = 12;

	int lastStr, lastSpd, stable, moveTimer;
	bool measured;
	Vector3 home;
	double homeAngle;
	bool haveHome;
	int fist, saw, pistol;
	int srcPhase, srcWait;
	bool srcDone;
	Actor gunRocket, meleeRocket;

	override void OnRegister() { lastStr = -2; lastSpd = -2; }

	// Once, at the first Strength above 0: the bonus must follow the attack that dealt the damage, not the weapon held
	// when it lands. Really switches to a pistol and fires (spawns) a rocket owned by the player, really switches to
	// fists and fires another, then, holding fists, hits dummies with: the gun-fired rocket (as its impact or splash
	// would), the fist-fired rocket, a barrel credited to the player, the player directly, and a pistol control.
	//   ATTRSRC str=<live> gunrocket=<lost> meleerocket=<lost> barrel=<lost> fist=<lost> pistol=<lost>
	void SourceTest(PlayerInfo p, int s)
	{
		let mo = p.mo;
		if (srcPhase == 0)
		{
			if (Ready(p, "Pistol"))
			{
				gunRocket = Fire(mo);
				srcPhase = 1;
			}
		}
		else if (srcPhase == 1)
		{
			if (Ready(p, "Fist"))
			{
				meleeRocket = Fire(mo);
				srcPhase = 2;
				srcWait = 0;
			}
		}
		else if (++srcWait > 3)
		{
			let barrel = Actor.Spawn("ExplosiveBarrel", mo.Pos + (0, 0, -1000), NO_REPLACE);
			barrel.bNoInteraction = true;
			barrel.target = mo;
			int g = HitWith(mo, gunRocket), m = HitWith(mo, meleeRocket), b = HitWith(mo, barrel), f = HitWith(mo, mo);
			int n = HitWith(mo, null), bfg = Spray(mo), pc = Hit(p, "Pistol"), punch = Punch(mo);
			int ge, gl, me, ml;
			[ge, gl] = Explode(p, gunRocket);
			[me, ml] = Explode(p, meleeRocket);
			// Reference: the same explosion with the effects item taken away (DoomerfallAttributes gives it back).
			let fx = mo.FindInventory("DoomerfallAttributeEffects");
			if (fx) fx.Destroy();
			int re, rl;
			[re, rl] = Explode(p, Fire(mo));
			Console.Printf("ATTRREF boom=%d late=%d", re, rl);
			Console.Printf("ATTRSRC str=%d gunrocket=%d meleerocket=%d barrel=%d player=%d pistol=%d held=%s punch=%d null=%d bfg=%d gunboom=%d gunlate=%d meleeboom=%d meleelate=%d",
				s, g, m, b, f, pc, p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'none', punch, n, bfg, ge, gl, me, ml);
			barrel.Destroy();
			if (gunRocket) gunRocket.Destroy();
			if (meleeRocket) meleeRocket.Destroy();
			srcDone = true;
		}
	}

	// Switches to a weapon of this class for real; true once it is up.
	bool Ready(PlayerInfo p, class<Weapon> wc)
	{
		let w = Weapon(p.mo.FindInventory(wc));
		if (!w)
		{
			p.mo.GiveInventory(wc, 1);
			w = Weapon(p.mo.FindInventory(wc));
			if (!w) return false;
		}
		if (p.ReadyWeapon != w)
		{
			if (p.PendingWeapon != w) p.PendingWeapon = w;
			return false;
		}
		return p.PendingWeapon == WP_NOCHANGE;
	}

	// A rocket the player fired this tic, frozen out of the way so it never explodes by itself.
	Actor Fire(Actor mo)
	{
		let r = Actor.Spawn("Rocket", mo.Pos + (0, 0, -1000), NO_REPLACE);
		r.bNoInteraction = true;
		r.target = mo;
		return r;
	}

	// A real 20-point hitscan punch (LineAttack, so a puff is the inflictor, as for A_Punch and A_Saw) at a dummy just
	// in front of the player, who stands where the walk test put them back. 0 if the dummy was not hit.
	int Punch(Actor mo)
	{
		let dummy = Actor.Spawn("AttrDummy", mo.Vec3Angle(mo.radius + 20, mo.Angle), NO_REPLACE);
		dummy.Height = 128;
		int before = dummy.Health;
		mo.LineAttack(mo.Angle, 64, 0, 20, 'Melee', "BulletPuff");
		int lost = before - dummy.Health;
		dummy.Destroy();
		return lost;
	}

	// A dummy where Punch puts one, for hits that need real geometry.
	Actor FrontDummy(Actor mo)
	{
		let dummy = Actor.Spawn("AttrDummy", mo.Vec3Angle(mo.radius + 20, mo.Angle), NO_REPLACE);
		dummy.Height = 128;
		return dummy;
	}

	// A real BFG tracer: A_BFGSpray from a ball the player fired, one ray of a fixed 20 at the dummy in front. Stock
	// A_BFGSpray makes the player the inflictor. The player holds fists meanwhile.
	int Spray(Actor mo)
	{
		let dummy = FrontDummy(mo);
		let ball = Actor.Spawn("BFGBall", mo.Pos + (0, 0, -1000), NO_REPLACE);
		ball.bNoInteraction = true;
		ball.target = mo;
		ball.Angle = mo.Angle;
		int before = dummy.Health;
		ball.A_BFGSpray("BFGExtra", 1, 15, 1, 1024, 32, 20); // one ray, half a degree left (0 would mean 90 degrees)
		int lost = before - dummy.Health;
		ball.Destroy();
		dummy.Destroy();
		return lost;
	}

	// A real explosion of a rocket the player fired, at a dummy in front: Doom's ExplodeMissile (its first death frame
	// runs A_Explode), then a second A_Explode as a later death frame would run it, after Doom cleared MISSILE. The
	// player is made invulnerable meanwhile so the splash does not reach Daggerfall's HP. Returns both losses.
	int, int Explode(PlayerInfo p, Actor rocket)
	{
		if (!rocket) return -1, -1;
		let mo = p.mo;
		int cheats = p.cheats;
		p.cheats |= CF_GODMODE;
		let dummy = FrontDummy(mo);
		rocket.bNoInteraction = false;
		rocket.SetOrigin(dummy.Pos + (0, 0, 32), false);
		rocket.Vel = (0, 0, 0);
		int before = dummy.Health;
		rocket.ExplodeMissile();
		int first = before - dummy.Health;
		before = dummy.Health;
		int late = -1;
		if (!rocket.bMissile) // Doom cleared it, as for every later death frame
		{
			rocket.A_Explode();
			late = before - dummy.Health;
		}
		dummy.Destroy();
		p.cheats = cheats;
		return first, late;
	}

	// Health a fresh dummy loses to a 20-point hit with this inflictor and the player as source.
	int HitWith(Actor mo, Actor inflictor)
	{
		let dummy = Actor.Spawn("AttrDummy", mo.Pos + (0, 0, -1000), NO_REPLACE);
		int before = dummy.Health;
		dummy.DamageMobj(inflictor, mo, 20, 'None');
		int lost = before - dummy.Health;
		dummy.Destroy();
		return lost;
	}

	override void WorldTick()
	{
		let p = players[consoleplayer];
		let mo = p.mo;
		if (!mo) return;
		if (!haveHome) { home = mo.Pos; homeAngle = mo.Angle; haveHome = true; }
		int s = Actor.DD_SheetStat(0), v = Actor.DD_SheetStat(6);
		if (s != lastStr || v != lastSpd) { lastStr = s; lastSpd = v; stable = 0; measured = false; moveTimer = 0; Interrupt(); return; }
		if (measured)
		{
			if (s > 0 && !srcDone) SourceTest(p, s);
			else if (s > 0 && srcDone) WeaponTest(p);
			return;
		}
		if (++stable < SettleTics) return;
		if (moveTimer == 0)
		{
			fist = Hit(p, "Fist");
			saw = Hit(p, "Chainsaw");
			pistol = Hit(p, "Pistol");
			mo.SetOrigin(home, false);
			mo.Vel = (0, 0, 0);
			mo.Angle = homeAngle;
		}
		if (++moveTimer <= MoveTics)
		{
			Walk(PlayerPawn(mo));
			return;
		}
		double moved = (mo.Pos.XY - home.XY).Length();
		double fwd, side;
		[fwd, side] = PlayerPawn(mo).TweakSpeeds(0x1900, 0); // a walking forward move
		double tweak = fwd / (PlayerPawn(mo).ForwardMove1 * 0x1900);
		let climb = DoomerfallClimb(StaticEventHandler.Find("DoomerfallClimb"));
		Console.Printf("ATTR str=%d spd=%d fist=%d saw=%d pistol=%d move=%.2f tweak=%.4f item=%d climb=%.4f", s, v, fist, saw, pistol,
			moved, tweak, mo.FindInventory("DoomerfallAttributeEffects") ? 1 : 0, climb ? climb.GroundSpeed(PlayerPawn(mo), false) : -1);
		mo.SetOrigin(home, false);
		mo.Vel = (0, 0, 0);
		measured = true;
	}

	// One tic of a walking forward move, as PlayerPawn.MovePlayer applies cmd.forwardmove on the ground. Held keys do not
	// reach a UZDoom window that is never active (quiet_run's private desktop), so the harness supplies the move.
	void Walk(PlayerPawn pp)
	{
		double fm, sm, friction, movefactor;
		[fm, sm] = pp.TweakSpeeds(0x1900, 0);
		[friction, movefactor] = pp.GetFriction();
		pp.ForwardThrust(fm * pp.Speed / 256 * movefactor, pp.Angle);
	}

	// Health a dummy loses to a real 20-point hitscan hit (Punch) while the player holds a weapon of this class. The
	// weapon is spawned loose and held for this one call only, so nothing else (Daggerfall's drawn gun, DRLA) sees a
	// switch.
	int Hit(PlayerInfo p, class<Weapon> wc)
	{
		let mo = p.mo;
		let w = Weapon(Actor.Spawn(wc, mo.Pos + (0, 0, -1000), NO_REPLACE));
		let old = p.ReadyWeapon;
		p.ReadyWeapon = w;
		int lost = Punch(mo);
		p.ReadyWeapon = old;
		if (w) w.Destroy();
		return lost;
	}
}
