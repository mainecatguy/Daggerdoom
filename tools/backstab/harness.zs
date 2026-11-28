version "4.14"

// Backstabbing test (backstab.py), where the test town's map starts. It spawns a stock ZombieMan (huge health, so it
// never dies) in front of the player, facing away, and hits it as the player in set states, one step per 10 tics so
// every step is its own tic. Each step prints BSHIT <name> <base damage> <health lost> <target state after>:
//   unaware   no target, nothing heard: the backstab element applies
//   alerted   target set to the player: none
//   volley    no target, three hits in one tic (as a shotgun's pellets): all three get it, one sneak hit
//   heard     no target, but it heard the player (LastHeard) and has not looked yet: still unaware (see dd_backstab.cpp)
//   infight   target set to another monster: it has noticed someone, so none
//   hitscan   no target, a real hitscan shot (LineAttack) from the player: the backstab element applies
// Then BSPHASE fire: the runner holds +attack for a moment with the player's real gun aimed at it (no target first);
// BSHIT fire reports the health it lost. BSDONE ends the route.
class BSHarness : StaticEventHandler
{
	const BASE = 100;
	int wait, step, timer;
	bool started, done;
	Actor mon, other;
	double aim;

	vector2 spot;

	// Back on its spot, idle, facing away, with no target and nothing heard.
	void Reset()
	{
		mon.SetOrigin((spot, mon.floorz), false);
		mon.SetZ(mon.floorz);
		mon.vel = (0, 0, 0);
		mon.angle = aim;
		mon.target = null;
		mon.LastHeard = null;
		mon.lastenemy = null;
		mon.SetState(mon.SpawnState); // idle again: a chasing monster with no target looks all around at once
	}

	String Seen(PlayerPawn p)
	{
		return mon.target == p ? "target-player" : mon.target ? "target-other" : "no-target";
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
			Console.Printf("BSSTART angle %.1f mon %s", aim, mon.GetClassName());
			return;
		}
		if (++timer < 10) return;
		timer = 0;
		p.angle = aim;
		p.pitch = 0;
		switch (step++)
		{
		case 0: Reset(); Hit("unaware", p); break;
		case 1: mon.target = p; Hit("alerted", p); break;
		case 2: Reset(); Hit("volley", p, 3); break;
		case 3: Reset(); mon.LastHeard = p; Hit("heard", p); break;
		case 4: Reset(); mon.target = other; Hit("infight", p); break;
		case 5:
		{
			Reset();
			String was = Seen(p);
			int before = mon.health;
			p.LineAttack(aim, 1024, 0, 20, 'Hitscan', "BulletPuff");
			Console.Printf("BSHIT hitscan 20 %d before %s after %s", before - mon.health, was, Seen(p));
			break;
		}
		case 6: Reset(); timer = -60; wait = mon.health; Console.Printf("BSPHASE fire %s", Seen(p)); break;
		case 7: Console.Printf("BSHIT fire 0 %d before - after %s", wait - mon.health, Seen(p)); break;
		default: Console.Printf("BSDONE"); done = true; break;
		}
	}
}
