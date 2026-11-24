version "4.14"

// Townspeople test: stand beside a tavern door, list the townspeople Doom shows twice (to see them move), then
// optionally kill the nearest one (test only: NPCs take no damage in game code yet) and autosave.
class TPHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 40;
	int phase, timer;
	double startX, startY, startAngle;

	static int Rows(String tag)
	{
		let it = ThinkerIterator.Create((class<Actor>)("DFTownsperson"));
		Actor mo;
		int count = 0;
		while (mo = Actor(it.Next()))
		{
			Console.Printf("TPROW %s %08x%08x %.1f %.1f %.1f %s", tag, mo.args[1], mo.args[0], mo.pos.x, mo.pos.y, mo.pos.z, TexMan.GetName(mo.picnum));
			count++;
		}
		Console.Printf("TPCOUNT %s %d map %s", tag, count, level.MapName);
		return count;
	}

	override void WorldTick()
	{
		if (phase >= 9 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		String mode = "@MODE@";
		bool inside = level.MapName ~== "MAP01" || level.MapName.Left(3) ~== "DDS";
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (timer > LIMIT) { Console.Printf("TPDONE timeout phase %d", phase); phase = 9; return; }
		switch (phase)
		{
		case 0:
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 64, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(normal.y, normal.x);
			if (timer < 420) break;
			Rows("first");
			phase = 1;
			timer = 0;
			break;
		case 1:
			if (timer < 105) break;
			Rows("later");
			if (mode.IndexOf("kill") < 0) { Console.Printf("TPDONE ok"); phase = 9; break; }
			Actor best;
			double range = 1000000000.0;
			let it = ThinkerIterator.Create((class<Actor>)("DFTownsperson"));
			Actor mo;
			while (mo = Actor(it.Next()))
				if (p.Distance2D(mo) < range) { range = p.Distance2D(mo); best = mo; }
			if (!best) { Console.Printf("TPDONE nobody to kill"); phase = 9; break; }
			Console.Printf("TPKILL %08x%08x at %.1f %.1f, %.0f away", best.args[1], best.args[0], best.pos.x, best.pos.y, range);
			best.Die(p, p);
			phase = 2;
			timer = 0;
			break;
		case 2:
			if (timer < 70) break;
			Rows("afterkill");
			if (mode.IndexOf("trip") >= 0) { phase = 4; timer = 0; break; }
			if (mode.IndexOf("leave") >= 0) { phase = 7; timer = 0; break; }
			if (mode.IndexOf("save") < 0) { Console.Printf("TPDONE ok"); phase = 9; break; }
			Console.Printf("TPSAVE");
			level.MakeAutoSave();
			phase = 3;
			timer = 0;
			break;
		case 3:
			if (timer < 210) break;
			Console.Printf("TPDONE ok");
			phase = 9;
			break;
		case 4:	// Leave the street: face the tavern door and press Use.
			if (inside) { Console.Printf("TPINSIDE map %s", level.MapName); phase = 5; timer = 0; break; }
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer == 8) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 5:	// Inside: stay a while, then turn round (the landing faces the door) and use it.
			if (timer == 2) { startX = p.pos.x; startY = p.pos.y; Console.Printf("TPARRIVE %.1f %.1f angle %.1f", p.pos.x, p.pos.y, p.angle); }
			if (timer == 2) startAngle = p.angle;
			// Try the exit facing the way the player landed, then turned round.
			if (timer == 140 || timer == 180)
			{
				p.vel = (0, 0, 0);
				p.SetOrigin((startX, startY, p.floorz), false);
				p.angle = startAngle + (timer == 180 ? 180 : 0);
				Console.Printf("TPEXIT try at %.1f %.1f angle %.1f", p.pos.x, p.pos.y, p.angle);
			}
			if (timer == 144 || timer == 184) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside && timer > 2) { Console.Printf("TPOUTSIDE map %s", level.MapName); phase = 6; timer = 0; }
			break;
		case 6:	// Back on the street: wait for Daggerfall's list, then report who is shown.
			if (timer < 280) break;
			Rows("return");
			Console.Printf("TPDONE ok");
			phase = 9;
			break;
		case 7:	// Leave town into the wilderness, as run_door.py does, and report who is shown there.
			if (timer == 1) { Console.Printf("TPLEAVE from %s", level.MapName); p.SetOrigin(p.pos + (30000, 0, 0), false); }
			if (timer < 280) break;
			Rows("away");
			Console.Printf("TPDONE ok");
			phase = 9;
			break;
		}
	}
}
