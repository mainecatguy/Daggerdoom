version "4.14"

// Interaction skills test (skillbasics.py), in the test town.
// town: Use on the nearest townsperson standing (talk: Daggerfall's -dfskillbasicstest asks a polite and a blunt question),
//       then crouching Use on the next two (Daggerfall's Steal: pickpocket), then into the general store whose door is
//       DOORDATA and Use on the nearest NPC (the merchant menu; -dfshoptest sells one item).
// rest: presses the rest control where the map starts (outside the town walls), as tools/rest does; -dfskillbasicstest
//       presses Rest Until Healed.
class SBHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 60;
	const PEOPLE = 3;
	const REST = @REST@;
	int phase, timer, talked;
	Array<Actor> folk;
	Actor npc;
	bool done;

	void Finish(String why) { Console.Printf("SBDONE %s", why); done = true; }

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
	}

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
		if (say) Console.Printf("SBAT %s %08x%08x at %.1f,%.1f from %.0f", mo.GetClassName(), mo.args[1], mo.args[0], aim.x, aim.y, distance);
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
		if (timer > LIMIT) { Console.Printf("SBFAIL timeout in phase %d", phase); Finish("failed"); return; }
		if (phase == 0 && (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3)) { timer = 0; return; }
		if (REST != 0)
		{
			if (timer == 35 * 4) Console.Printf("SBPRESS rest"); // the runner types "netevent df_rest" (the rest key's command)
			if (timer == 35 * 40) Finish("rest route finished");
			return;
		}
		switch (phase)
		{
		case 0: // Town: stand by the store door, and collect the shown townspeople, nearest first.
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
				Console.Printf("SBLIST %d townspeople shown", folk.Size());
				if (!folk.Size()) { Console.Printf("SBFAIL no townsperson shown"); Finish("failed"); break; }
				phase = 1; timer = 0;
			}
			break;
		case 1: // The first townsperson standing (talk), the next ones crouching (Steal: pickpocket).
			if (!folk[talked]) { timer = 105; }
			else if (timer <= 20) StandBefore(p, folk[talked], 48, timer == 1);
			if (talked > 0 && timer <= 25) players[0].crouchfactor = 0.5;
			if (timer == 20)
			{
				Console.Printf("SBPRESS townsperson %d%s", talked, talked > 0 ? " crouching" : "");
				EventHandler.SendNetworkEvent("df_interact");
			}
			if (timer >= 105)
			{
				timer = 0;
				if (++talked >= min(folk.Size(), PEOPLE)) phase = 3;
			}
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
				if (!npc) { Console.Printf("SBFAIL no NPC shown in the store"); Finish("failed"); break; }
				StandBefore(p, npc, 56, true);
			}
			if (npc) p.vel = (0, 0, 0);
			if (timer == 35 * 3 + 20) { Console.Printf("SBPRESS merchant"); EventHandler.SendNetworkEvent("df_interact"); }
			if (timer == 35 * 3 + 35 * 14) Finish("town route finished");
			break;
		}
	}
}
