version "4.14"

// Shop test. Goes into the building whose door is DOORDATA, presses Use (df_interact, Doom's Use without the door
// check) on each furniture container, nearest first (Daggerfall's test hook buys the cheapest item from the first shop shelf
// and closes anything else), then twice on the nearest NPC (the
// shopkeeper: the hook sells an item, then talks). Doom pauses while a window is open, so the timers wait it out.
class SMHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 25;
	const NPCPRESSES = 2;
	const MAXBOXES = 6;
	int phase, timer, presses, boxIndex;
	Actor npc;
	Array<Actor> boxes;
	bool done;

	void Finish(String why) { Console.Printf("NDDONE %s", why); done = true; }

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
	}

	static vector3 NpcAim(Actor npc)
	{
		int w, h;
		[w, h] = TexMan.GetSize(npc.picnum);
		return npc.pos + (0, 0, h * npc.scale.y / 2);
	}

	static vector3 BoxAim(DoomerfallWorldContainer box)
	{
		return ((box.dfMinX + box.dfMaxX) / 2, (box.dfMinY + box.dfMaxY) / 2, (box.dfMinZ + box.dfMaxZ) / 2);
	}

	Actor Nearest(PlayerPawn p, Name cls)
	{
		Actor best = null;
		let it = ThinkerIterator.Create(cls);
		Actor mo;
		while (mo = Actor(it.Next()))
			if (!mo.bInvisible && (!best || (mo.pos - p.pos).Length() < (best.pos - p.pos).Length())) best = mo;
		return best;
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
		case 1: // Inside: wait for Daggerfall's list of who is present, then pick the shopkeeper and a shelf.
			if (timer < 35 * 3) break;
			npc = Nearest(p, "DFNpc");
			{
				let it = ThinkerIterator.Create("DoomerfallWorldContainer");
				Actor mo;
				while (mo = Actor(it.Next())) boxes.Push(mo);
				for (int i = 1; i < boxes.Size(); i++)
					for (int j = i; j > 0 && (boxes[j].pos - p.pos).Length() < (boxes[j - 1].pos - p.pos).Length(); j--)
					{
						Actor t = boxes[j]; boxes[j] = boxes[j - 1]; boxes[j - 1] = t;
					}
			}
			Console.Printf("NDLIST npc %s, %d containers", npc ? "found" : "missing", boxes.Size());
			if (!npc || !boxes.Size()) { Console.Printf("NDFAIL no NPC or shelf shown"); Finish("failed"); break; }
			phase = 3; timer = 0;
			break;
		case 2: // Use on the shopkeeper from close by.
			if (timer == 1)
			{
				vector3 aim = NpcAim(npc);
				vector2 away = p.pos.xy - aim.xy;
				away = away.Length() > 1 ? away.Unit() : (1, 0);
				p.SetOrigin((aim.xy + away * 56, npc.pos.z), false);
				Face(p, aim);
			}
			p.vel = (0, 0, 0);
			if (timer == 20) { Console.Printf("NDPRESS npc %d", presses); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 70)
			{
				timer = 0;
				if (++presses >= NPCPRESSES) phase = 4;
			}
			break;
		case 3: // Use on the nearest shelf, standing off its box on the player's side.
			{
				let box = DoomerfallWorldContainer(boxes[boxIndex]);
				vector3 aim = BoxAim(box);
				if (timer == 1)
				{
					vector2 away = p.pos.xy - aim.xy;
					away = away.Length() > 1 ? away.Unit() : (1, 0);
					double reach = 40 + max(box.dfMaxX - box.dfMinX, box.dfMaxY - box.dfMinY) / 2;
					p.SetOrigin((aim.xy + away * reach, box.dfMinZ + 8), false);
				}
				p.vel = (0, 0, 0);
				if (timer <= 35) Face(p, aim);
				if (timer == 35) { Console.Printf("NDPRESS container %d", boxIndex); EventHandler.SendNetworkEvent("df_interact"); }
				if (timer == 35 * 3) { timer = 0; if (++boxIndex >= min(boxes.Size(), MAXBOXES)) phase = 2; }
			}
			break;
		case 4:
			Finish("route finished");
			break;
		}
	}
}
