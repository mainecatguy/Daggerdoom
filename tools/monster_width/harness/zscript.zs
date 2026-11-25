version "4.10"

// Monster width check (tools/monster_width/monster_width.py).
// 1. Spawns a few monsters with replacement (so DRLA's spawners pick their own monsters when DRLA is loaded), waits for
//    spawners to resolve, then prints every monster's class, default radius, live radius and movement width (MW lines).
//    The radius (the hitbox) must always stay stock; only the movement width narrows, and only on Daggerfall maps.
// 2. Hit tests against a stock DoomImp (radius 20): hitscans and an imp fireball passed beside it at chosen offsets.
//    Each must hit inside the stock edge and miss outside it, whatever the movement width is (MWHIT lines).
// Then MWDONE.
class DFHitShooter : Actor
{
	Default { Radius 1; Height 56; +NOBLOCKMAP +NOGRAVITY +NOINTERACTION }
	States { Spawn: TNT1 A -1; Stop; }
}

// An imp fireball that records the first thing it touched (PIT_CheckThing calls SpecialMissileHit on contact).
class DFHitBall : DoomImpBall
{
	override int SpecialMissileHit(Actor victim)
	{
		let h = DFMonsterWidthCheck(EventHandler.Find("DFMonsterWidthCheck"));	// the ball is gone soon after it explodes
		if (h && !h.touched) h.touched = victim;
		return -1;
	}
}

class DFMonsterWidthCheck : EventHandler
{
	Actor target;
	vector3 at;
	int hits, misses, wrong;
	DFHitBall ball;
	Actor touched;
	double ballOffset;

	void Report(String kind, double offset, bool hit, bool want)
	{
		if (hit == want) { if (hit) hits++; else misses++; } else wrong++;
		Console.Printf("MWHIT %s offset=%.1f radius=%.3f move=%.3f %s %s", kind, offset, target.radius, target.DD_MoveRadius(),
			hit ? "hit" : "miss", hit == want ? "ok" : "WRONG");
	}

	// A level shot along +x that passes the target's centre `offset` units to the side.
	bool Hitscan(double offset)
	{
		let s = Actor.Spawn("DFHitShooter", at + (-80, offset, 0), NO_REPLACE);
		FTranslatedLineTarget t;
		s.LineAttack(0, 160, 0, 0, 'Hitscan', "BulletPuff", LAF_NORANDOMPUFFZ, t);
		s.Destroy();
		return t.linetarget == target;
	}

	void Fire(double offset)
	{
		ballOffset = offset;
		touched = null;
		ball = DFHitBall(Actor.Spawn("DFHitBall", at + (-60, offset, 20), NO_REPLACE));
		ball.angle = 0;
		ball.Vel = (10, 0, 0);
	}

	override void WorldTick()
	{
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		if (level.maptime == 2)
		{
			static const Name kinds[] = { 'ZombieMan', 'ShotgunGuy', 'DoomImp', 'Demon', 'Cacodemon', 'HellKnight', 'Arachnotron', 'Cyberdemon' };
			for (int i = 0; i < kinds.Size(); i++)
			{
				// Far above the map's play space would fall back, so spawn at the player, non-solid until counted.
				let mo = Actor.Spawn(kinds[i], pmo.pos, ALLOW_REPLACE);
				if (mo) { mo.bSOLID = false; mo.Deactivate(null); }
			}
		}
		if (level.maptime == 20)
		{
			int narrow = 0, stock = 0, other = 0;
			Array<Actor> counted;
			let it = ThinkerIterator.Create("Actor");
			Actor mo;
			while (mo = Actor(it.Next()))
			{
				if (!mo.bIsMonster || mo.player) continue;
				counted.Push(mo);
				double d = mo.Default.radius, m = mo.DD_MoveRadius();
				String state = abs(mo.radius - d) >= 0.001 ? "other" : abs(m - d) < 0.001 ? "stock" : abs(m - d * 10.5 / 16) < 0.001 ? "narrow" : "other";
				if (state == "stock") stock++; else if (state == "narrow") narrow++; else other++;
				Console.Printf("MW %s default=%.3f radius=%.3f move=%.3f height=%.1f %s", mo.GetClassName(), d, mo.radius, m, mo.height, state);
			}
			Console.Printf("MWSUMMARY map=%s narrow=%d stock=%d other=%d", level.MapName, narrow, stock, other);
			// Clear the space for the hit tests: only the target may be hit.
			foreach (c : counted) { c.ClearCounters(); c.Destroy(); }
			pmo.bSHOOTABLE = false; pmo.bSOLID = false;
			at = pmo.pos;
			target = Actor.Spawn("DoomImp", at, NO_REPLACE);
			target.Deactivate(null);
			target.bNOGRAVITY = true;
			target.SetOrigin(at, false);
			// Hitscan: the imp is 20 wide for hits. 19 is outside its movement width on Daggerfall maps but inside its hitbox.
			Report("hitscan", 0, Hitscan(0), true);
			Report("hitscan", 19, Hitscan(19), true);
			Report("hitscan", -19, Hitscan(-19), true);
			Report("hitscan", 21, Hitscan(21), false);
			Report("hitscan", -21, Hitscan(-21), false);
			// Projectile: the fireball (radius 6) touches the imp when the offset is under 20 + 6.
			Fire(24);
		}
		if (level.maptime == 40)
		{
			Report("projectile", ballOffset, touched == target, true);
			if (ball) ball.Destroy();
			Fire(28);
		}
		if (level.maptime == 60)
		{
			Report("projectile", ballOffset, touched == target, false);
			if (ball) ball.Destroy();
			Console.Printf("MWHITSUMMARY hits=%d misses=%d wrong=%d", hits, misses, wrong);
			target.ClearCounters();
			target.Destroy();
			Console.Printf("MWDONE");
		}
	}
}
