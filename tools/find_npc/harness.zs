version "4.14"

// Find-NPC test (findnpc.py). Keeps the player safe, turns them slowly so the marker must follow the view, and on
// "netevent fn_go" (a key the driver presses) walks through the test door into the building (door row 0). Stages:
//   0  town; 1  walking in; 2  inside
class FNHarness : StaticEventHandler // Static: it must keep its stage across the trip indoors.
{
	static const double DOORDATA[] = { @DOOR@ };
	int stage, timer;
	bool ready;
	ui int menus, closedAt;
	ui bool wasOpen, sentGo, sentUse;
	bool useArmed;
	int useTimer;

	// Posted key presses reach Doom only while a menu captures input (in play it reads raw input), so the harness
	// opens the find menu the N key opens: twice outdoors, ten seconds after the last closed, then once indoors.
	override void UiTick()
	{
		bool open = Menu.GetCurrentMenu() != null;
		if (wasOpen && !open) closedAt = level.maptime;
		wasOpen = open;
		if (open || !playeringame[0]) return;
		// At the door (stage 1): menu 3 is typed into and closed with Esc, menu 4 sets a marker there, then the door is used.
		if (stage == 1 && menus == 4 && !sentUse && level.maptime - closedAt > 105) { sentUse = true; EventHandler.SendNetworkEvent("fn_use"); }
		bool due = stage == 0 ? level.maptime > 140 && level.maptime - closedAt > 350
			: stage == 1 ? timer > 70 && (menus == 2 || (menus == 3 && level.maptime - closedAt > 70))
			: stage == 2 && timer > 160 && menus == 4;
		if (!due) return;
		if (stage == 0 && menus == 2)
		{
			if (!sentGo && level.maptime - closedAt > 700) { sentGo = true; EventHandler.SendNetworkEvent("fn_go"); }
			return;
		}
		menus++;
		Console.Printf("FNMENU %d", menus);
		Menu.SetMenu("DoomerfallFindNpcMenu");
		wasOpen = true;
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "fn_go" && stage == 0) { stage = 1; timer = 0; Console.Printf("FNSTAGE 1 walking in"); }
		if (e.Name == "fn_use" && stage == 1) { useArmed = true; useTimer = 0; Console.Printf("FNSTAGE 1 using the door"); }
	}

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		timer++;
		bool inside = level.MapName.Left(3) ~== "DDS";
		if (level.maptime % 35 == 0) RemoveMonsters();
		switch (stage)
		{
		case 0:
			if (level.maptime == 70 && !inside) Console.Printf("FNSTAGE 0 outdoors in %s", level.MapName);
			if (level.maptime > 70) p.angle += 1.5;
			break;
		case 1:
			if (inside) { stage = 2; timer = 0; break; }
			{
				vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
				vector2 normal = (DOORDATA[3], DOORDATA[4]);
				p.SetOrigin((door.xy + normal * 48, door.z), false);
				p.vel = (0, 0, 0);
				p.angle = atan2(-normal.y, -normal.x);
				if (useArmed && (useTimer == 12 || useTimer % 140 == 139)) CVar.FindCVar("dd_tm_use").SetInt(1);
				if (useArmed) useTimer++;
			}
			break;
		case 2:
			if (timer == 140) Console.Printf("FNREADY indoors in %s", level.MapName);
			if (timer > 140) p.angle += 1.5;
			break;
		}
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
		{
			String cls = mo.GetClassName();
			if (mo.bISMONSTER && !mo.player && !(cls.Left(2) ~== "DF")) mo.Destroy(); // keep NPCs and townspeople
		}
	}
}
