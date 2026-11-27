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

	override void OnRegister() { lastStr = -2; lastSpd = -2; }

	override void WorldTick()
	{
		let p = players[consoleplayer];
		let mo = p.mo;
		if (!mo) return;
		if (!haveHome) { home = mo.Pos; homeAngle = mo.Angle; haveHome = true; }
		int s = Actor.DD_SheetStat(0), v = Actor.DD_SheetStat(6);
		if (s != lastStr || v != lastSpd) { lastStr = s; lastSpd = v; stable = 0; measured = false; moveTimer = 0; return; }
		if (measured) return;
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
