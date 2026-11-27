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
		+NOGRAVITY
		+NOBLOOD
		+NOPAIN
		+DONTTHRUST
	}
}

class AttrPaired : StaticEventHandler
{
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
			Console.Printf("ATTRSRC str=%d gunrocket=%d meleerocket=%d barrel=%d fist=%d pistol=%d held=%s punch=%d", s, g, m, b, f,
				Hit(p, "Pistol"), p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'none', Punch(mo));
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
		if (s != lastStr || v != lastSpd) { lastStr = s; lastSpd = v; stable = 0; measured = false; moveTimer = 0; return; }
		if (measured)
		{
			if (s > 0 && !srcDone) SourceTest(p, s);
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
		Console.Printf("ATTR str=%d spd=%d fist=%d saw=%d pistol=%d move=%.2f tweak=%.4f item=%d", s, v, fist, saw, pistol,
			moved, tweak, mo.FindInventory("DoomerfallAttributeEffects") ? 1 : 0);
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

	// Health a fresh dummy loses to a 20-point player hit while the player holds a weapon of this class. The weapon is
	// spawned loose and held for this one call only, so nothing else (Daggerfall's drawn gun, DRLA) sees a switch.
	int Hit(PlayerInfo p, class<Weapon> wc)
	{
		let mo = p.mo;
		let w = Weapon(Actor.Spawn(wc, mo.Pos + (0, 0, -1000), NO_REPLACE));
		let dummy = Actor.Spawn("AttrDummy", mo.Pos + (0, 0, -1000), NO_REPLACE);
		let old = p.ReadyWeapon;
		p.ReadyWeapon = w;
		int before = dummy.Health;
		dummy.DamageMobj(mo, mo, 20, 'Melee');
		int lost = before - dummy.Health;
		p.ReadyWeapon = old;
		dummy.Destroy();
		if (w) w.Destroy();
		return lost;
	}
}
