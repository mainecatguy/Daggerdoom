version "4.14"

// NPC refusal test. Goes into the building whose door is DOORDATA, then presses Use (df_interact) on each NPC
// Daggerfall shows there, nearest first, from close by, in two rounds. Daggerfall's -dftalkrefuse test lowers the
// player's reputation after the first talk window, so later presses meet NPCs that refuse.
class NRHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 60; // per phase; the first entry may convert the interior
	const MAXNPCS = 4;
	const ROUNDS = 2;
	int phase, timer, pressed;
	Array<Actor> npcs;
	bool done;

	void Finish(String why) { Console.Printf("NRDONE %s", why); done = true; }

	static void StandBefore(PlayerPawn p, Actor npc, double distance)
	{
		int w, h;
		[w, h] = TexMan.GetSize(npc.picnum);
		vector3 aim = npc.pos + (0, 0, h * npc.scale.y / 2);
		vector2 away = p.pos.xy - aim.xy;
		away = away.Length() > 1 ? away.Unit() : (1, 0);
		p.SetOrigin((aim.xy + away * distance, npc.pos.z), false);
		p.vel = (0, 0, 0);
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
		Console.Printf("NRNPC %08x%08x from %.0f", npc.args[1], npc.args[0], distance);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (timer > LIMIT) { Console.Printf("NRFAIL timeout in phase %d", phase); Finish("failed"); return; }
		switch (phase)
		{
		case 0: // Outside: walk into the door.
			if (inside) { phase = 1; timer = 0; break; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			p.pitch = 0;
			if (timer == 35) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 1: // Inside: wait for Daggerfall's list of who is present, then collect the shown NPCs, nearest first.
			if (timer < 35 * 3) break;
			{
				let it = ThinkerIterator.Create("DFNpc");
				Actor mo;
				while (mo = Actor(it.Next()))
					if (!mo.bInvisible) npcs.Push(mo);
				for (int i = 1; i < npcs.Size(); i++)
					for (int j = i; j > 0 && (npcs[j].pos - p.pos).Length() < (npcs[j - 1].pos - p.pos).Length(); j--)
					{
						Actor t = npcs[j]; npcs[j] = npcs[j - 1]; npcs[j - 1] = t;
					}
				Console.Printf("NRLIST %d NPCs shown", npcs.Size());
				if (!npcs.Size()) { Console.Printf("NRFAIL no NPC shown"); Finish("failed"); break; }
				phase = 2; timer = 0;
			}
			break;
		case 2: // Use on each NPC from close by. Doom pauses while a Daggerfall window is open, so the timer waits it out.
			int count = min(npcs.Size(), MAXNPCS);
			if (timer == 1) StandBefore(p, npcs[pressed % count], 56);
			p.vel = (0, 0, 0);
			if (timer == 20) { Console.Printf("NRPRESS %d", pressed); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 70)
			{
				timer = 0;
				if (++pressed >= count * ROUNDS) Finish("route finished");
			}
			break;
		}
	}
}
