version "4.14"

// Quest NPC test. After a save inside a building loads, waits for the quest Persons Daggerfall places (DFNpc with
// args[2] 1, dd_npcs.cpp), reports each, stands before the first and presses Use (df_interact). Daggerfall's test
// (-dfquestnpctest) then hides that Person and restores it; each second this reports how many are shown.
class QNHarness : StaticEventHandler
{
	const LIMIT = 35 * 45;
	int phase, timer, total;
	Actor target;
	bool done;
	String last;

	void Finish(String why) { Console.Printf("QNDONE %s", why); done = true; }

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
	}

	// The shown quest Persons, and the shown layout NPCs, as one line.
	String Census(out Actor first)
	{
		first = null;
		int placed = 0, layout = 0;
		String rows = "";
		let it = ThinkerIterator.Create("DFNpc");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (mo.bInvisible) continue;
			if (mo.args[2] != 1) { layout++; continue; }
			placed++;
			if (!first) first = mo;
			int w, h;
			[w, h] = TexMan.GetSize(mo.picnum);
			rows = rows .. String.Format(" [%08x%08x at %.1f,%.1f,%.1f floor %.1f tex %s %dx%d scale %.3f,%.3f]", mo.args[1], mo.args[0], mo.pos.x, mo.pos.y, mo.pos.z,
				mo.floorz, TexMan.GetName(mo.picnum), w, h, mo.scale.x, mo.scale.y);
		}
		return String.Format("placed %d layout %d%s", placed, layout, rows);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		timer++;
		total++;
		if (total > LIMIT) { Console.Printf("QNFAIL timeout in phase %d", phase); Finish("failed"); return; }
		Actor first;
		String census = Census(first);
		if (census != last || timer % 35 == 0)
		{
			if (census != last) Console.Printf("QNSTATE t=%d %s", total, census);
			last = census;
		}
		switch (phase)
		{
		case 0: // Wait for Daggerfall's list to place someone.
			if (first) { target = first; phase = 1; timer = 0; }
			else if (timer > 35 * 20) { Console.Printf("QNFAIL no quest NPC placed"); Finish("failed"); }
			break;
		case 1: // Stand before it and press Use.
		{
			int w, h;
			[w, h] = TexMan.GetSize(target.picnum);
			vector3 aim = target.pos + (0, 0, h * target.scale.y / 2);
			if (timer == 1)
			{
				vector2 away = p.pos.xy - aim.xy;
				away = away.Length() > 1 ? away.Unit() : (1, 0);
				p.SetOrigin((aim.xy + away * 56, p.pos.z), false);
				Console.Printf("QNSTAND player at %.1f,%.1f,%.1f", p.pos.x, p.pos.y, p.pos.z);
			}
			p.vel = (0, 0, 0);
			Face(p, aim);
			if (timer == 20) { Console.Printf("QNPRESS"); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 40) { phase = 2; timer = 0; }
			break;
		}
		case 2: // Daggerfall's test closes the window, hides the Person, then restores it.
			if (timer > 35 * 20) Finish("route finished");
			break;
		}
	}
}
