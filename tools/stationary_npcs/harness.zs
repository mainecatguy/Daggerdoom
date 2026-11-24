version "4.14"

// NPC test: report the town's NPCs, go through one door, wait for Daggerfall's list, and report who is shown.
class NPHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 30;
	int phase, timer;

	static void Rows(String tag)
	{
		int total = 0, visible = 0;
		for (int n = 0; n < 2; n++)
		{
			String name = n == 0 ? "DFNpc" : "DFDungeonNpc";
			class<Actor> cls = (class<Actor>)(name);
			if (!cls) continue;
			let it = ThinkerIterator.Create(cls);
			Actor mo;
			while (mo = Actor(it.Next()))
			{
				int w, h;
				[w, h] = TexMan.GetSize(mo.picnum);
				double center = name == "DFNpc" ? mo.pos.z + h * mo.scale.y / 2 : mo.pos.z;
				Console.Printf("NPROW %s %08x%08x %.2f %.2f %.2f %d %d %.3f %.3f", tag, mo.args[1], mo.args[0], mo.pos.x, mo.pos.y, center, mo.bInvisible ? 0 : 1, mo.bSolid || mo.bShootable ? 1 : 0, w * mo.scale.x, h * mo.scale.y);
				total++;
				if (!mo.bInvisible) visible++;
			}
		}
		Console.Printf("NPCOUNT %s total %d visible %d map %s", tag, total, visible, level.MapName);
	}

	override void WorldTick()
	{
		if (phase >= 3 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName ~== "MAP01" || level.MapName.Left(3) ~== "DDS";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (timer > LIMIT) { Console.Printf("NPDONE timeout phase %d", phase); phase = 3; return; }
		switch (phase)
		{
		case 0:
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 140) break;
			Rows("town");
			if (normal == (0, 0)) { Console.Printf("NPDONE ok"); phase = 3; break; }
			CVar.FindCVar("dd_tm_use").SetInt(1);
			phase = 1;
			timer = 0;
			break;
		case 1:
			if (!inside) break;
			phase = 2;
			timer = 0;
			break;
		case 2:
			if (timer < 175) break;
			Rows("inside");
			Console.Printf("NPDONE ok");
			phase = 3;
			break;
		}
	}
}
