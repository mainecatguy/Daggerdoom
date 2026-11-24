version "4.14"

// NPC kill test. Stands outside a building (or goes in), then tries to hurt each NPC kind with the real damage paths:
// a hit from nobody (as a stray monster shot would be), and a hitscan bullet fired by the player. Walking townspeople
// should refuse the first and die from the second; stationary NPCs (DFNpc, DFDungeonNpc) should take neither.
// Then it lists who is left, and optionally saves. With "load" it only lists who is there after the load.
class NKHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 60;
	int phase, timer;
	Array<String> killed;

	static String Id(Actor mo) { return String.Format("%08x%08x", mo.args[1], mo.args[0]); }
	static bool IsGuard(Actor mo) { return TexMan.GetName(mo.picnum).MakeLower().IndexOf("f399") >= 0; }

	static int Rows(String tag)
	{
		int count = 0;
		for (int n = 0; n < 3; n++)
		{
			String cls = n == 0 ? "DFTownsperson" : n == 1 ? "DFNpc" : "DFDungeonNpc";
			let it = ThinkerIterator.Create((class<Actor>)(cls));
			Actor mo;
			while (mo = Actor(it.Next()))
			{
				if (mo.bINVISIBLE) continue;
				Console.Printf("NKROW %s %s %s health %d shootable %d at %.1f %.1f %.1f r %.1f h %.1f %s", tag, cls, Id(mo), mo.health, mo.bSHOOTABLE, mo.pos.x, mo.pos.y, mo.pos.z, mo.radius, mo.height, TexMan.GetName(mo.picnum));
				count++;
			}
		}
		Console.Printf("NKCOUNT %s %d map %s", tag, count, level.MapName);
		return count;
	}

	// Stands the player 96 units from mo, facing its middle, and fires one 50-point hitscan bullet.
	static void Shoot(Actor p, Actor mo, String what)
	{
		// The first of eight spots around it that is free and can see it.
		vector2 away = (96, 0);
		for (int a = 0; a < 8; a++)
		{
			away = Actor.AngleToVector(a * 45, 96);
			p.SetOrigin((mo.pos.xy + away, mo.floorz), false);
			if (p.TestMobjLocation() && p.CheckSight(mo, SF_IGNOREVISIBILITY)) break;
		}
		p.vel = (0, 0, 0);
		double eye = p.pos.z + p.player.viewheight;
		double mid = mo.pos.z + max(mo.height, 16) / 2;
		p.angle = atan2(-away.y, -away.x);
		double pitch = atan2(eye - mid, 96);
		int health = mo.health;
		FTranslatedLineTarget t;
		Actor puff = p.LineAttack(p.angle, 512, pitch, 50, 'Hitscan', "BulletPuff", LAF_NORANDOMPUFFZ, t);
		if (puff) Console.Printf("NKPUFF at %.1f %.1f %.1f; shooter %.1f %.1f %.1f; target %.1f %.1f %.1f", puff.pos.x, puff.pos.y, puff.pos.z, p.pos.x, p.pos.y, p.pos.z, mo.pos.x, mo.pos.y, mo.pos.z);
		String hit = "nothing";
		if (t.linetarget == mo) hit = "it";
		else if (t.linetarget) hit = t.linetarget.GetClassName();
		Console.Printf("NKSHOOT %s %s %s hit %s health %d -> %d dead %d", what, mo.GetClassName(), Id(mo), hit, health, mo.health, mo.health <= 0);
	}

	static Actor Nearest(Actor p, String cls, int guard)
	{
		Actor best;
		double range = 1e9;
		let it = ThinkerIterator.Create((class<Actor>)(cls));
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (mo.bINVISIBLE || mo.health <= 0) continue;
			if (guard >= 0 && IsGuard(mo) != (guard == 1)) continue;
			if (p.Distance2D(mo) < range) { range = p.Distance2D(mo); best = mo; }
		}
		return best;
	}

	void Tests(Actor p)
	{
		// A stationary NPC: nobody's hit, then the player's bullet.
		for (int n = 0; n < 2; n++)
		{
			let npc = Nearest(p, n == 0 ? "DFNpc" : "DFDungeonNpc", -1);
			if (!npc) { Console.Printf("NKNPC none %s", n == 0 ? "DFNpc" : "DFDungeonNpc"); continue; }
			int before = npc.health;
			int got = npc.bSHOOTABLE ? npc.DamageMobj(null, null, 1000, 'None') : -1;
			Console.Printf("NKSTRAY %s %s damage %d health %d -> %d", npc.GetClassName(), Id(npc), got, before, npc.health);
			Shoot(p, npc, "npc");
		}
		// A commoner: nobody's hit first (refused), then the player's bullet (dies).
		let walker = Nearest(p, "DFTownsperson", 0);
		if (walker)
		{
			int before = walker.health;
			int got = walker.DamageMobj(null, null, 1000, 'None');
			Console.Printf("NKSTRAY townsperson %s damage %d health %d -> %d", Id(walker), got, before, walker.health);
			String id = Id(walker);
			Shoot(p, walker, "commoner");
			if (walker && walker.health <= 0) killed.Push(id);
		}
		else Console.Printf("NKNPC none commoner");
		let guard = Nearest(p, "DFTownsperson", 1);
		if (guard)
		{
			String id = Id(guard);
			Shoot(p, guard, "guard");
			if (guard && guard.health <= 0) killed.Push(id);
		}
		else Console.Printf("NKNPC none guard");
	}

	override void WorldTick()
	{
		if (phase >= 9 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		bool inside = level.MapName.Left(3) ~== "DDS";
		String mode = "@MODE@";
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (timer > LIMIT) { Console.Printf("NKDONE timeout phase %d", phase); phase = 9; return; }
		switch (phase)
		{
		case 0:	// Wait for Daggerfall and stand outside the door.
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (mode.IndexOf("load") >= 0)
			{
				if (timer < 420) break;
				Rows("loaded");
				Console.Printf("NKDONE ok");
				phase = 9;
				break;
			}
			p.SetOrigin((door.xy + normal * 64, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(normal.y, normal.x);
			if (timer < 420) break;
			timer = 0;
			phase = mode.IndexOf("inside") >= 0 ? 1 : 2;
			break;
		case 1:	// Face the door and press Use until inside.
			if (inside) { Console.Printf("NKINSIDE map %s", level.MapName); phase = 2; timer = 0; break; }
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer % 70 == 8) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 2:	// List, test, list again, and save.
			if (timer == 175) { Rows("before"); Tests(p); }
			if (timer == 280) Rows("after");
			if (timer == 300 && mode.IndexOf("save") >= 0) { Console.Printf("NKSAVE"); level.MakeAutoSave(); }
			if (timer == 420)
			{
				for (int i = 0; i < killed.Size(); i++) Console.Printf("NKKILLED %s", killed[i]);
				Console.Printf("NKDONE ok");
				phase = 9;
			}
			break;
		}
	}
}
