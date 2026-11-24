version "4.14"

// Talk test. Goes into the building whose door is DOORDATA, then presses Use (the df_interact control, which is
// Doom's Use without the door check) on each NPC Daggerfall lists as present, nearest first, from close by. Last, it
// presses Use on the first NPC from far away, where Daggerfall answers "too far away" and opens nothing.
class NDHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 25;
	const MAXNPCS = 4;
	int phase, timer, talked;
	Array<Actor> npcs;
	bool done;

	void Finish(String why) { Console.Printf("NDDONE %s", why); done = true; }

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
	}

	// Stands the player this far from the NPC's middle, on the side the player is already on, facing it.
	static void StandBefore(PlayerPawn p, Actor npc, double distance)
	{
		int w, h;
		[w, h] = TexMan.GetSize(npc.picnum);
		vector3 aim = npc.pos + (0, 0, h * npc.scale.y / 2);
		vector2 away = p.pos.xy - aim.xy;
		away = away.Length() > 1 ? away.Unit() : (1, 0);
		p.SetOrigin((aim.xy + away * distance, npc.pos.z), false);
		p.vel = (0, 0, 0);
		Face(p, aim);
		Console.Printf("NDNPC %08x%08x at %.1f,%.1f,%.1f from %.0f, player at %.1f,%.1f", npc.args[1], npc.args[0], aim.x, aim.y, aim.z, distance, p.pos.x, p.pos.y);
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
		if (timer > LIMIT) { Console.Printf("NDFAIL timeout in phase %d", phase); Finish("failed"); return; }
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
				Console.Printf("NDLIST %d NPCs shown", npcs.Size());
				if (!npcs.Size()) { Console.Printf("NDFAIL no NPC shown"); Finish("failed"); break; }
				phase = 2; timer = 0;
			}
			break;
		case 2: // Use on each NPC from close by. Doom pauses while the window is open, so the timer waits it out.
			if (timer == 1) StandBefore(p, npcs[talked], 56);
			p.vel = (0, 0, 0);
			if (timer == 20) { Console.Printf("NDPRESS near %d", talked); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 70)
			{
				timer = 0;
				if (++talked >= min(npcs.Size(), MAXNPCS)) phase = 3;
			}
			break;
		case 3: // Use on the first NPC from far away: Daggerfall's "too far away", and no window.
			if (timer == 1)
			{
				// Beyond Daggerfall's reach (256 classic units, 192 Doom units), somewhere the player fits and sees the NPC.
				bool clear = false;
				for (double d = 300; d >= 210 && !clear; d -= 30)
					for (double a = 0; a < 360 && !clear; a += 15)
					{
						p.SetOrigin(npcs[0].pos + (cos(a), sin(a), 0) * (d + 1), false);
						StandBefore(p, npcs[0], d);
						clear = level.IsPointInLevel(p.pos) && p.CheckSight(npcs[0], SF_IGNOREVISIBILITY);
						for (int i = 1; clear && i < npcs.Size(); i++)
							if ((npcs[i].pos.xy - p.pos.xy).Length() < 48) clear = false; // Not inside another NPC's billboard.
					}
				Console.Printf("NDFAR %s", clear ? "spot found" : "no clear spot");
			}
			p.vel = (0, 0, 0);
			if (timer == 20) { Console.Printf("NDPRESS far 0"); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 70) Finish("route finished");
			break;
		}
	}
}
