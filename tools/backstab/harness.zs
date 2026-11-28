version "4.14"

// Backstabbing test (backstab.py), where the test town's map starts. It spawns a stock ZombieMan (huge health, so it
// never dies) in front of the player, facing away, and hits it as the player in set states, each step in its own tic.
// Each step prints BSHIT <name> <base damage> <health lost> before <state> after <state>, where a state is
// no-target / target-player / target-other, with "+heard" when the monster has heard the player (LastHeard):
//   unaware      no target, nothing heard: the backstab element applies
//   alerted      target set to the player: none
//   volley       no target, three hits in one tic (as a shotgun's pellets): all three get it, one sneak hit
//   infight      target set to another monster: it has noticed someone, so none
//   hitscan      no target, a real hitscan shot (LineAttack) from the player: the backstab element applies
//   heardbefore  it heard the player make a noise 50 tics earlier (more than an attack's second) and has no target:
//                alerted, so none
//   heardtwice   heard the player 50 tics earlier, then the attack's own noise in the same tic as the hit: still none
//   ownnoise     nothing heard before; the attack's own noise in the same tic as the hit (a gun alerts as it fires):
//                the backstab element applies
//   ownflight    the attack's own noise 6 tics before the hit (a bullet's wind-up, a rocket's flight): it applies
// For the hearing steps the monster is held in its idle frame (it cannot look and take a target), so LastHeard is the
// only thing that differs; the noise is the player's own SoundAlert, as a gun's.
// Then BSPHASE fire: the runner holds +attack for a moment with the player's real gun aimed at it (idle, nothing heard,
// free to react); BSHIT fire reports the health it lost. BSDONE ends the route.
class BSHarness : StaticEventHandler
{
	const BASE = 100;
	int wait, step, timer, delay;
	bool started, done;
	Actor mon, other;
	double aim;
	vector2 spot;

	// Back on its spot, idle, facing away, with no target and nothing heard. hold: stays in its idle frame, so it never
	// looks (and never takes a target from what it hears).
	void Reset(bool hold = false)
	{
		mon.SetOrigin((spot, mon.floorz), false);
		mon.SetZ(mon.floorz);
		mon.vel = (0, 0, 0);
		mon.angle = aim;
		mon.target = null;
		mon.LastHeard = null;
		mon.lastenemy = null;
		mon.SetState(mon.SpawnState); // idle again: a chasing monster with no target looks all around at once
		if (hold) mon.tics = -1;
	}

	String Seen(PlayerPawn p)
	{
		String s = mon.target == p ? "target-player" : mon.target ? "target-other" : "no-target";
		return mon.LastHeard == p ? s .. "+heard" : s;
	}

	void Hit(String name, PlayerPawn p, int count = 1)
	{
		String was = Seen(p);
		int before = mon.health;
		for (int i = 0; i < count; i++) mon.DamageMobj(p, p, BASE, 'None');
		Console.Printf("BSHIT %s %d %d before %s after %s", name, BASE * count, before - mon.health, was, Seen(p));
	}

	// An open direction from the player: a 300 unit trace at mid height that hits nothing.
	double OpenAngle(PlayerPawn p)
	{
		for (int i = 0; i < 32; i++)
		{
			double a = p.angle + i * 360. / 32;
			FLineTraceData t;
			if (!p.LineTrace(a, 300, 0, 0, 32, data: t)) return a;
		}
		return p.angle;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE;
		if (!started)
		{
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { wait = 0; return; }
			if (++wait < 35 * 6) return; // Daggerfall sets the test skill a second after the game starts
			started = true;
			aim = OpenAngle(p);
			p.angle = aim;
			p.pitch = 0;
			p.vel = (0, 0, 0);
			vector2 dir = (cos(aim), sin(aim));
			mon = Actor.Spawn("ZombieMan", (p.pos.xy + dir * 160, p.floorz));
			other = Actor.Spawn("ZombieMan", (p.pos.xy - dir * 600, p.floorz));
			if (!mon || !other) { Console.Printf("BSERROR spawn failed"); done = true; return; }
			spot = mon.pos.xy;
			mon.health = 1000000;
			other.health = 1000000;
			other.bDormant = true;
			Reset();
			delay = 10;
			Console.Printf("BSSTART angle %.1f mon %s", aim, mon.GetClassName());
			return;
		}
		if (++timer < delay) return;
		timer = 0;
		delay = 10;
		p.angle = aim;
		p.pitch = 0;
		switch (step++)
		{
		case 0: Reset(); Hit("unaware", p); break;
		case 1: mon.target = p; Hit("alerted", p); break;
		case 2: Reset(); Hit("volley", p, 3); break;
		case 3: Reset(); mon.target = other; Hit("infight", p); break;
		case 4:
		{
			Reset();
			String was = Seen(p);
			int before = mon.health;
			p.LineAttack(aim, 1024, 0, 20, 'Hitscan', "BulletPuff");
			Console.Printf("BSHIT hitscan 20 %d before %s after %s", before - mon.health, was, Seen(p));
			break;
		}
		case 5: Reset(true); p.SoundAlert(p); delay = 50; break;               // an earlier noise
		case 6: Hit("heardbefore", p); break;
		case 7: Reset(true); p.SoundAlert(p); delay = 50; break;               // an earlier noise
		case 8: p.SoundAlert(p); Hit("heardtwice", p); break;                   // then the attack's own
		case 9: Reset(true); p.SoundAlert(p); Hit("ownnoise", p); break;
		case 10: Reset(true); p.SoundAlert(p); delay = 6; break;
		case 11: Hit("ownflight", p); break;
		case 12: Reset(); timer = -60; wait = mon.health; Console.Printf("BSPHASE fire %s", Seen(p)); break;
		case 13: Console.Printf("BSHIT fire 0 %d before - after %s", wait - mon.health, Seen(p)); break;
		default: Console.Printf("BSDONE"); done = true; break;
		}
	}
}
