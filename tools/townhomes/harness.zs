version "4.14"

// Townspeople at home test: stand outside a lived-in house and list the townspeople Doom shows, go in and list who is
// at home, leave, come back in, and list again (the same people should stand on the same spots).
class THHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 50;
	int phase, timer, visits;
	double startX, startY, startAngle;

	static int Rows(String tag)
	{
		let it = ThinkerIterator.Create((class<Actor>)("DFTownsperson"));
		Actor mo;
		int count = 0;
		while (mo = Actor(it.Next()))
		{
			Console.Printf("THROW %s %08x%08x %.1f %.1f %.1f %s", tag, mo.args[1], mo.args[0], mo.pos.x, mo.pos.y, mo.pos.z, TexMan.GetName(mo.picnum));
			count++;
		}
		Console.Printf("THCOUNT %s %d map %s", tag, count, level.MapName);
		return count;
	}

	// Test only: townspeople take no damage in game code yet.
	static void Kill(Actor p)
	{
		Actor best;
		double range = 1000000000.0;
		let it = ThinkerIterator.Create((class<Actor>)("DFTownsperson"));
		Actor mo;
		while (mo = Actor(it.Next()))
			if (p.Distance2D(mo) < range) { range = p.Distance2D(mo); best = mo; }
		if (!best) { Console.Printf("THKILL nobody"); return; }
		Console.Printf("THKILL %08x%08x at %.1f %.1f", best.args[1], best.args[0], best.pos.x, best.pos.y);
		best.Die(p, p);
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
		if (timer > LIMIT) { Console.Printf("THDONE timeout phase %d", phase); phase = 9; return; }
		switch (phase)
		{
		case 0:	// Wait for Daggerfall, stand outside the door, and list the street.
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (mode.IndexOf("load") >= 0)	// A save made at home: stay where it puts us and list who is there.
			{
				if (timer < 420) break;
				Rows("loaded");
				Console.Printf("THDONE ok");
				phase = 9;
				break;
			}
			p.SetOrigin((door.xy + normal * 64, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(normal.y, normal.x);
			if (timer < 420) break;
			Rows("street");
			phase = 1;
			timer = 0;
			break;
		case 1:	// Face the door and press Use.
			if (inside) { visits++; Console.Printf("THINSIDE %d map %s", visits, level.MapName); phase = 2; timer = 0; break; }
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer % 70 == 8) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 2:	// Inside: wait for Daggerfall's list, report, then leave by the door the player came in.
			if (timer == 2) { startX = p.pos.x; startY = p.pos.y; startAngle = p.angle; Console.Printf("THARRIVE %.1f %.1f %.1f", p.pos.x, p.pos.y, p.pos.z); }
			if (timer == 175) Rows(visits == 1 ? "home" : "again");
			if (timer == 176 && visits == 1 && mode.IndexOf("kill") >= 0) Kill(p);
			if (timer < 175) break;
			if (timer == 250 && mode.IndexOf("save") >= 0) { Console.Printf("THSAVE"); level.MakeAutoSave(); }
			if (timer < 460 && mode.IndexOf("save") >= 0) break;
			if (timer == 460 && mode.IndexOf("save") >= 0) { Console.Printf("THDONE ok"); phase = 9; break; }
			if (visits >= 2) { Console.Printf("THDONE ok"); phase = 9; break; }
			if (timer == 180 || timer == 220)
			{
				p.vel = (0, 0, 0);
				p.SetOrigin((startX, startY, p.floorz), false);
				p.angle = startAngle + (timer == 220 ? 180 : 0);
			}
			if (timer == 184 || timer == 224) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { Console.Printf("THOUTSIDE map %s", level.MapName); phase = 3; timer = 0; }
			break;
		case 3:	// Back on the street: list again, then go back in.
			if (timer < 140) break;
			Rows("out");
			phase = 1;
			timer = 0;
			break;
		}
	}
}
