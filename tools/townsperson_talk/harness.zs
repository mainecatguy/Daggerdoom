version "4.14"

// Townsperson talk test (townsperson_talk.py). In town, presses Use (df_interact) on the nearest shown townspeople
// from close by, then once on one from beyond Daggerfall's reach, then goes into the general store whose door is
// DOORDATA and presses Use on the nearest NPC there, to show merchants still work.
class TTHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 30;
	const PEOPLE = 3;
	int phase, timer, talked;
	Array<Actor> folk;
	Actor npc;
	bool done;

	void Finish(String why) { Console.Printf("TTDONE %s", why); done = true; }

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
	}

	// Stands the player this far from the actor's middle, on the side the player is already on, facing it.
	static void StandBefore(PlayerPawn p, Actor mo, double distance, bool say)
	{
		int w, h;
		[w, h] = TexMan.GetSize(mo.picnum);
		vector3 aim = mo.pos + (0, 0, h * mo.scale.y / 2);
		vector2 away = p.pos.xy - aim.xy;
		away = away.Length() > 1 ? away.Unit() : (1, 0);
		p.SetOrigin((aim.xy + away * distance, mo.pos.z), false);
		p.vel = (0, 0, 0);
		Face(p, aim);
		if (say) Console.Printf("TTAT %s %08x%08x at %.1f,%.1f from %.0f", mo.GetClassName(), mo.args[1], mo.args[0], aim.x, aim.y, distance);
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
		if (timer > LIMIT) { Console.Printf("TTFAIL timeout in phase %d", phase); Finish("failed"); return; }
		switch (phase)
		{
		case 0: // Town: wait for the sync, stand by the store door, and collect the shown townspeople, nearest first.
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			if (timer == 1) { p.SetOrigin((door.xy + normal * 200, door.z), false); p.vel = (0, 0, 0); }
			if (timer < 35 * 4) break;
			{
				let it = ThinkerIterator.Create("DFTownsperson");
				Actor mo;
				while (mo = Actor(it.Next()))
					if (!mo.bInvisible && mo.health > 0) folk.Push(mo);
				for (int i = 1; i < folk.Size(); i++)
					for (int j = i; j > 0 && (folk[j].pos - p.pos).Length() < (folk[j - 1].pos - p.pos).Length(); j--)
					{
						Actor t = folk[j]; folk[j] = folk[j - 1]; folk[j - 1] = t;
					}
				Console.Printf("TTLIST %d townspeople shown", folk.Size());
				if (!folk.Size()) { Console.Printf("TTFAIL no townsperson shown"); Finish("failed"); break; }
				phase = 1; timer = 0;
			}
			break;
		case 1: // Use on each townsperson from close by. They walk, so the player keeps stepping up to them until the press.
			if (!folk[talked]) { timer = 70; }
			else if (timer <= 20) StandBefore(p, folk[talked], 48, timer == 1);
			if (timer == 20) { Console.Printf("TTPRESS townsperson %d", talked); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer >= 70)
			{
				timer = 0;
				if (++talked >= min(folk.Size(), PEOPLE)) phase = 2;
			}
			break;
		case 2: // Use on the nearest townsperson from beyond Daggerfall's reach (256 classic units, 192 Doom units).
			if (timer <= 20 && folk[0]) StandBefore(p, folk[0], 260, timer == 1);
			if (timer == 20) { Console.Printf("TTPRESS far townsperson 0"); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 70) { phase = 3; timer = 0; }
			break;
		case 3: // Into the store.
			if (inside) { phase = 4; timer = 0; break; }
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			p.pitch = 0;
			if (timer == 35) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 4: // Inside: wait for Daggerfall's list of who is present, then Use on the nearest shown NPC.
			if (timer == 35 * 3)
			{
				let it = ThinkerIterator.Create("DFNpc");
				Actor mo;
				double best = 1e9;
				while (mo = Actor(it.Next()))
					if (!mo.bInvisible && (mo.pos - p.pos).Length() < best) { best = (mo.pos - p.pos).Length(); npc = mo; }
				if (!npc) { Console.Printf("TTFAIL no NPC shown in the store"); Finish("failed"); break; }
				StandBefore(p, npc, 56, true);
			}
			if (npc) p.vel = (0, 0, 0);
			if (timer == 35 * 3 + 20) { Console.Printf("TTPRESS merchant"); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 35 * 3 + 90) Finish("route finished");
			break;
		}
	}
}
