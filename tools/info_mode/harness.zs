version "4.14"

// Info test. Outside a general store: Info on the building, then on a monster placed in view. Inside: Info on the
// nearest shown NPC, then on the nearest furniture container (Daggerfall's Info on a container is Grab, so it opens).
// Info on the store's door names it and enters, as Daggerfall's does. A screenshot follows each press.
class IMHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 20;
	int phase, timer, ticks, shotAt;
	Actor monster;
	bool done;

	void Finish(String why) { Console.Printf("IMDONE %s", why); done = true; }

	void Press(String what)
	{
		let p = players[0].mo;
		Console.Printf("IMPRESS %s at %.1f,%.1f angle %.1f pitch %.1f", what, p.pos.x, p.pos.y, p.angle, p.pitch);
		EventHandler.SendNetworkEvent("df_info");
		shotAt = ticks + 10;
	}

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
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
		ticks++;
		if (ticks == shotAt) { LevelLocals.MakeScreenShot(); Console.Printf("IMSHOT after %d tics", 10); }
		if (timer > LIMIT) { Console.Printf("IMFAIL timeout in phase %d", phase); Finish("failed"); return; }
		switch (phase)
		{
		case 0: // Outside, facing the store from a few steps away.
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; break; }
			p.SetOrigin((door.xy + normal * 160, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			p.pitch = 0;
			if (timer == 70) Press("building");
			if (timer == 105) { phase = 1; timer = 0; }
			break;
		case 1: // A monster between the player and the store.
			p.vel = (0, 0, 0);
			if (timer == 1)
			{
				monster = Actor.Spawn("ZombieMan", (door.xy + normal * 64, door.z), ALLOW_REPLACE);
				if (monster) { monster.bDORMANT = true; monster.angle = p.angle + 180; Console.Printf("IMMONSTER %s tag %s", monster.GetClassName(), monster.GetTag()); }
			}
			if (monster && timer < 30) Face(p, monster.pos + (0, 0, monster.height / 2));
			if (timer == 30) Press("monster");
			if (timer == 65)
			{
				if (monster) monster.Destroy();
				p.pitch = 0;
				p.SetOrigin((door.xy + normal * 48, door.z), false);
				p.angle = atan2(-normal.y, -normal.x);
			}
			if (timer == 75) Press("door"); // Info, not Use: Daggerfall's Info on a door enters.
			if (inside) { phase = 2; timer = 0; }
			break;
		case 2: // Inside: the nearest NPC Daggerfall lists as present.
			if (timer < 35 * 3) break;
			if (timer == 35 * 3)
			{
				Actor best = null;
				double range = 1e12;
				let it = ThinkerIterator.Create("DFNpc");
				Actor mo;
				while (mo = Actor(it.Next()))
				{
					if (mo.bInvisible) continue;
					double d = (mo.pos - p.pos).Length();
					if (d < range) { range = d; best = mo; }
				}
				if (!best) { Console.Printf("IMFAIL no NPC shown"); phase = 3; timer = 0; break; }
				int w, h;
				[w, h] = TexMan.GetSize(best.picnum);
				vector3 aim = best.pos + (0, 0, h * best.scale.y / 2);
				vector2 away = p.pos.xy - aim.xy;
				away = away.Length() > 1 ? away.Unit() : (1, 0);
				p.SetOrigin((aim.xy + away * 72, best.pos.z), false);
				p.vel = (0, 0, 0);
				Face(p, aim);
				Console.Printf("IMNPC %08x%08x at %.1f,%.1f,%.1f size %.1fx%.1f", best.args[1], best.args[0], aim.x, aim.y, aim.z, w * best.scale.x, h * best.scale.y);
			}
			p.vel = (0, 0, 0);
			if (timer == 35 * 4) Press("npc");
			if (timer == 35 * 5) { phase = 3; timer = 0; }
			break;
		case 3: // The nearest furniture container.
			if (timer == 1)
			{
				Actor best = null;
				double range = 1e12;
				let it = ThinkerIterator.Create("DoomerfallWorldContainer");
				Actor mo;
				while (mo = Actor(it.Next()))
				{
					double d = (mo.pos - p.pos).Length();
					if (d < range) { range = d; best = mo; }
				}
				let box = DoomerfallWorldContainer(best);
				if (!box) { Console.Printf("IMFAIL no container"); Finish("failed"); break; }
				vector3 aim = ((box.dfMinX + box.dfMaxX) / 2, (box.dfMinY + box.dfMaxY) / 2, (box.dfMinZ + box.dfMaxZ) / 2);
				vector2 away = p.pos.xy - aim.xy;
				away = away.Length() > 1 ? away.Unit() : (1, 0);
				p.SetOrigin((aim.xy + away * (40 + max(box.dfMaxX - box.dfMinX, box.dfMaxY - box.dfMinY) / 2), box.dfMinZ + 8), false);
				p.vel = (0, 0, 0);
				Face(p, aim);
				Console.Printf("IMBOX %s", box.dfId);
			}
			p.vel = (0, 0, 0);
			if (timer == 35) Press("container");
			if (timer == 35 * 4) Finish("route finished"); // Doom pauses while the window is open, so this counts after it closed.
			break;
		}
	}
}
