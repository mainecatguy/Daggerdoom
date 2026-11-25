version "4.14"

// Look-label test (tools/look_label/look_label.py). Puts the player in front of each kind of target, holds still, and
// marks the end of each case with LLEND; the engine logs the label as `look: "<text>"` whenever it changes, so the
// runner reads the label in force at each LLEND. DOORDATA is a general store's door: x, y, z, normal x, normal y.
class LLHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const HOLD = 30;
	static const int ORDER[] = { 0, 3, 4, 5, 6, 1, 2 }; // outdoors first, then into the store for the pile and the NPC
	const LIMIT = 35 * 40;

	int phase, timer;
	bool done, holding;
	String holdMap;
	vector3 at;
	double holdAngle, holdPitch;
	Actor target, npc;

	void Finish(String why) { Console.Printf("LLDONE %s", why); done = true; }
	void Next() { phase++; timer = 0; }

	vector2 Normal() { return (DOORDATA[3], DOORDATA[4]); }
	vector3 Street(double away) { return (DOORDATA[0] + DOORDATA[3] * away, DOORDATA[1] + DOORDATA[4] * away, DOORDATA[2]); }

	// Stand at `from` facing the point `to`.
	void Face(PlayerPawn p, vector3 from, vector3 to)
	{
		at = from;
		holding = true;
		holdMap = level.MapName;
		p.SetOrigin(from, false);
		vector3 d = to - (from.x, from.y, from.z + p.player.viewheight);
		holdAngle = atan2(d.y, d.x);
		holdPitch = -atan2(d.z, d.xy.Length());
	}

	// Stand `dist` from the actor's middle, on the first of 8 sides where the player fits and sees it.
	bool FaceActor(PlayerPawn p, Actor mo, double dist, double midZ, bool sight = true)
	{
		for (int i = 0; i < 8; i++)
		{
			double a = mo.angle + i * 45;
			vector3 from = (mo.pos.x + cos(a) * dist, mo.pos.y + sin(a) * dist, mo.pos.z);
			from.z = mo.GetZAt(from.x, from.y, 0, GZF_ABSOLUTEPOS);
			p.SetOrigin(from, false);
			if (!p.CheckPosition(from.xy) || (sight && !p.CheckSight(mo, SF_IGNOREVISIBILITY))) continue;
			Face(p, from, (mo.pos.x, mo.pos.y, mo.pos.z + midZ));
			return true;
		}
		return false;
	}

	void End(String name, String expect) { Console.Printf("LLEND %s | %s", name, expect); }

	Actor Nearest(PlayerPawn p, Name cls)
	{
		Actor best;
		double bestDist = 1e9;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
			if (mo.GetClassName() == cls && p.Distance2D(mo) < bestDist) { best = mo; bestDist = p.Distance2D(mo); }
		return best;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (holding && level.MapName == holdMap) { p.SetOrigin(at, false); p.vel = (0, 0, 0); p.angle = holdAngle; p.pitch = holdPitch; }
		timer++;
		if (timer > LIMIT) { Console.Printf("LLFAIL timeout in phase %d", phase); Finish("failed"); return; }
		switch (ORDER[phase])
		{
		case 0: // Wait for Daggerfall.
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			Console.Printf("LLREADY");
			Next();
			break;
		case 1: // The pile Daggerfall drops in the store (-dflooktest): 48 units away, then out of reach.
			if (!target)
			{
				target = Nearest(p, 'DoomerfallWorldItem');
				if (!target && timer > 35 * 20) { Console.Printf("LLFAIL no pile"); Finish("failed"); }
				timer = target ? 0 : timer;
				break;
			}
			if (timer == 1) FaceActor(p, target, 48, 0);
			if (timer == HOLD) { End("pile", "Iron Longsword"); Console.Printf("LLSHOT pile"); }
			if (timer == HOLD + 110 && !FaceActor(p, target, 130, 0)) Console.Printf("LLNOTE no clear side for the far pile");
			if (timer == 2 * HOLD + 110) { End("pile-far", ""); Next(); }
			break;
		case 6: // Use on the store's door enters it (Doom's real Use button, through the QA channel).
			if (timer == 1) Face(p, Street(48), Street(0) + (0, 0, 40));
			if (timer == 10) Console.Printf("LLUSE");
			if (level.MapName.Left(3) ~== "DDS") { if (holding && level.MapName == holdMap) { holding = false; timer = 0; } else if (timer == 35) Next(); }
			break;
		case 2: // A standing Daggerfall NPC, inside talk reach, then outside it.
			if (timer == 1)
			{
				npc = Nearest(p, 'DFNpc');
				if (!npc) npc = Nearest(p, 'DFDungeonNpc');
				if (!npc) { Console.Printf("LLFAIL no NPC in the store"); Finish("failed"); return; }
				if (!FaceActor(p, npc, 72, 28)) Console.Printf("LLNOTE no clear side for the NPC");
				Console.Printf("LLNPC %.0f,%.0f ids %d %d", npc.pos.x, npc.pos.y, npc.args[0], npc.args[1]);
			}
			if (timer == HOLD) { End("npc", "*"); Console.Printf("LLSHOT npc"); }
			if (timer == HOLD + 110 && !FaceActor(p, npc, 210, 28) && FaceActor(p, npc, 210, 28, false)) Console.Printf("LLNOTE the room is too small to see the NPC from 210 units; standing 210 away without sight");
			if (timer == 2 * HOLD + 110) { End("npc-far", ""); Finish("route finished"); }
			break;
		case 3: // A monster, frozen, 64 units away, then 160.
			if (timer == 1)
			{
				target = Actor.Spawn("Zombieman", Street(130), NO_REPLACE);
				target.bDORMANT = true;
				target.bNOTARGET = true;
				Face(p, Street(194), Street(130) + (0, 0, 28));
			}
			if (target) { target.SetOrigin(Street(130), false); target.vel = (0, 0, 0); } // Keep it where the case expects it.
			if (timer == HOLD) { End("monster", target.GetTag("Monster")); Console.Printf("LLSHOT monster"); }
			if (timer == HOLD + 110) Face(p, Street(290), Street(130) + (0, 0, 28));
			if (timer == 2 * HOLD + 110) { End("monster-far", ""); target.Destroy(); Next(); }
			break;
		case 4: // A Doom gun on the floor (DRLA's own when DRLA is loaded), 48 units away, then 200.
			if (timer == 1) Actor.Spawn("Shotgun", Street(130));
			if (timer == 6)
			{
				let it = ThinkerIterator.Create("Weapon");
				Inventory mo;
				while (mo = Inventory(it.Next())) if (mo.bSPECIAL && mo.Distance2D(p) < 400 && !mo.owner) target = mo;
				if (!target) { Console.Printf("LLFAIL no gun spawned"); Finish("failed"); return; }
				Face(p, Street(178), (target.pos.x, target.pos.y, target.pos.z));
				Console.Printf("LLGUN %s", target.GetClassName());
			}
			if (timer == HOLD) { End("gun", target.GetTag("")); Console.Printf("LLSHOT gun"); }
			if (timer == HOLD + 110) Face(p, Street(330), (target.pos.x, target.pos.y, target.pos.z));
			if (timer == 2 * HOLD + 110) { End("gun-far", ""); target.Destroy(); Next(); }
			break;
		case 5: // The store's door, then the same door from outside Use reach, then a bare stretch of the store's wall.
			if (timer == 1) Face(p, Street(48), Street(0) + (0, 0, 40));
			if (timer == HOLD) { End("door", "*"); Console.Printf("LLSHOT door"); }
			if (timer == HOLD + 110) Face(p, Street(150), Street(0) + (0, 0, 40));
			if (timer == 2 * HOLD + 110) End("door-far", "");
			if (timer == 2 * HOLD + 120)
			{
				vector2 along = (-DOORDATA[4], DOORDATA[3]);
				vector3 wall = Street(0) + (along.x * 160, along.y * 160, 40);
				Face(p, wall + (DOORDATA[3] * 40, DOORDATA[4] * 40, -40), wall);
			}
			if (timer == 3 * HOLD + 120) { End("wall", ""); Next(); }
			break;
		}
	}
}
