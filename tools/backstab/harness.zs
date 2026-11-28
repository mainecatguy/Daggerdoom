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
// Hearing steps. An "attack" here holds the player's weapon out of its ready state (Busy), as firing does; the noise is
// the player's own SoundAlert, as a gun's. The monster is held in its idle frame, so it cannot look and take a target
// (like an ambush monster that cannot see the player) and LastHeard is the only thing that differs:
//   silentafter  an earlier attack with a noise (5 tics), the weapon ready for 15 tics, then a new attack that makes no
//                noise hits it, 20 tics after that noise: alerted, none
//   heardtwice   the same, but the new attack makes its own noise in the hit's tic: still alerted, none
//   ownnoise     one attack: its noise and its hit in the same tic: the backstab element applies
//   ownflight    one attack: its noise 6 tics before its hit: it applies
//   windup       one attack with two noises, 20 tics apart (a wind-up, then firing), hit 2 tics after the second: applies
//   noattack     an attack with a noise ends, then a hit 2 tics later while the weapon is ready (no attack): none
// Then BSPHASE fire: the runner holds +attack for a moment with the player's real gun aimed at it (idle, nothing heard,
// free to react); BSHIT fire reports the health it lost. Then spread: two unaware monsters hit A, B, A in one tic (a
// blast's pellets over both): all three hits get it, two sneak hits; BSSPREAD B <B's loss>.
// Then BSPHASE minigun: the player gets DRLA's Assault Minigun (a wind-up weapon: an alert at the wind-up, about 20 tics
// of spin, another alert as it starts firing), the monster is held idle, and the runner holds +attack: its first bullet
// must be a sneak hit although the monster first heard the wind-up. BSHIT minigun reports. BSDONE ends the route.
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

	// An attack: the weapon held out of its ready state (as when it fires), or back to its ready loop.
	void Busy(bool on)
	{
		let psp = players[0].FindPSprite(PSP_WEAPON);
		if (!psp) return;
		if (on)
		{
			players[0].WeaponState &= ~(WF_WEAPONREADY | WF_WEAPONREADYALT);
			psp.tics = -1;
		}
		else psp.tics = 1;
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
		if (step != 24 || timer > -45) p.angle = aim; // b2b: turned away for its first 15 tics
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
		// silentafter
		case 5: Reset(true); Busy(true); p.SoundAlert(p); delay = 5; break;
		case 6: Busy(false); delay = 15; break;
		case 7: Busy(true); Hit("silentafter", p); Busy(false); break;
		// heardtwice
		case 8: Reset(true); Busy(true); p.SoundAlert(p); delay = 5; break;
		case 9: Busy(false); delay = 15; break;
		case 10: Busy(true); p.SoundAlert(p); Hit("heardtwice", p); Busy(false); break;
		// ownnoise
		case 11: Reset(true); Busy(true); p.SoundAlert(p); Hit("ownnoise", p); Busy(false); break;
		// ownflight
		case 12: Reset(true); Busy(true); p.SoundAlert(p); delay = 6; break;
		case 13: Hit("ownflight", p); Busy(false); break;
		// windup
		case 14: Reset(true); Busy(true); p.SoundAlert(p); delay = 20; break;
		case 15: p.SoundAlert(p); delay = 2; break;
		case 16: Hit("windup", p); Busy(false); break;
		// noattack
		case 17: Reset(true); Busy(true); p.SoundAlert(p); delay = 5; break;
		case 18: Busy(false); delay = 2; break;
		case 19: Hit("noattack", p); break;
		// the player's real gun
		case 20: Reset(); timer = -60; wait = mon.health; Console.Printf("BSPHASE fire %s", Seen(p)); break;
		case 21: Console.Printf("BSHIT fire 0 %d before - after %s", wait - mon.health, Seen(p)); break;
		case 22:
		{
			Reset();
			other.bDormant = false;
			other.target = null; other.LastHeard = null; other.lastenemy = null;
			String was = Seen(p);
			int a = mon.health, b = other.health;
			mon.DamageMobj(p, p, BASE, 'None');
			other.DamageMobj(p, p, BASE, 'None');
			mon.DamageMobj(p, p, BASE, 'None');
			other.bDormant = true;
			Console.Printf("BSHIT spread %d %d before %s after %s", 2 * BASE, a - mon.health, was, Seen(p));
			Console.Printf("BSSPREAD B %d", b - other.health);
			break;
		}
		// back to back: the real gun, one click aimed away (it hears it), then turned to it and a second click
		case 23:
			Reset(true);
			{ let w = players[0].ReadyWeapon; if (w && w.Ammo1) w.Ammo1.Amount = max(w.Ammo1.Amount, w.Ammo1.MaxAmount); } // a full magazine
			p.angle = aim + 90;
			timer = -60;
			wait = mon.health;
			Console.Printf("BSPHASE b2b %s", Seen(p));
			break;
		case 24: Console.Printf("BSHIT b2b 0 %d before - after %s", wait - mon.health, Seen(p)); break;
		// DRLA's wind-up minigun
		case 25:
		{
			Name gunName = 'RLAssaultRifleMinigun';
			Class<Actor> gun = gunName;
			if (!gun) { Console.Printf("BSNOTE no DRLA minigun"); step = 28; break; }
			p.GiveInventory("RLAssaultRifleMinigun", 1);
			p.GiveInventory("RLAssaultRifleMinigunClip", 200);
			p.A_SelectWeapon("RLAssaultRifleMinigun");
			delay = 70;
			break;
		}
		case 26:
			Reset(true);
			timer = -70;
			wait = mon.health;
			Console.Printf("BSPHASE minigun %s weapon %s", Seen(p), players[0].ReadyWeapon ? players[0].ReadyWeapon.GetClassName() : 'none');
			break;
		case 27: Console.Printf("BSHIT minigun 0 %d before - after %s", wait - mon.health, Seen(p)); break;
		default: Console.Printf("BSDONE"); done = true; break;
		}
	}
}
