version "4.14"

// tools/rest_enemies: sets up each rest case in a paired run, then prints RENOW <label> and waits. The driver presses
// Doom's rest key, reads both logs, closes the window, and sends "netevent re_next" through -ddqa to go on.
// @MODE@ is "fresh" (town, tavern guards, save) or "load" (after -dfloadtest of that save).

class REHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 200;
	int phase, timer, waiting;
	bool next;
	Actor nearOne, farOne;

	static bool Inside() { return level.MapName.Left(3) ~== "DDS"; }

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "re_next") next = true;
	}

	void Now(String label)
	{
		Console.Printf("RENOW %s", label);
		waiting = phase;
		next = false;
	}

	void AtDoor(PlayerPawn p)
	{
		p.SetOrigin((DOORDATA[0] + DOORDATA[3] * 48, DOORDATA[1] + DOORDATA[4] * 48, DOORDATA[2]), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-DOORDATA[4], -DOORDATA[3]);
		p.pitch = 0;
	}

	// A ZombieMan at the given distance from the player, in the first direction where it fits. Null if none fits.
	Actor Place(PlayerPawn p, double dist, String tag)
	{
		for (int i = 0; i < 16; i++)
		{
			double a = p.angle + i * 22.5;
			vector3 at = (p.pos.xy + Actor.AngleToVector(a, dist), p.pos.z);
			let mo = Actor.Spawn("ZombieMan", at);
			if (!mo) continue;
			if (mo.TestMobjLocation())
			{
				mo.angle = a + 180;
				Console.Printf("REPLACE %s at %.1f %.1f, %.1f units from the player", tag, mo.pos.x, mo.pos.y, mo.Distance3D(p));
				return mo;
			}
			mo.Destroy();
		}
		Console.Printf("REPLACE %s found no spot", tag);
		return null;
	}

	static int KillGuards(PlayerPawn p)
	{
		int n = 0;
		for (int i = 1; i < MAXPLAYERS; i++)
			if (playeringame[i] && players[i].mo && players[i].mo.health > 0) { players[i].mo.DamageMobj(p, p, 1000000, 'None', DMG_FORCED); n++; }
		return n;
	}

	static Actor Guard()
	{
		for (int i = 1; i < MAXPLAYERS; i++)
			if (playeringame[i] && players[i].mo && players[i].mo.health > 0) return players[i].mo;
		return null;
	}

	override void WorldTick()
	{
		if (phase == 99 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		String mode = "@MODE@";
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		timer++;
		if (timer > LIMIT) { Console.Printf("REDONE timeout phase %d", phase); phase = 99; return; }
		if (waiting)
		{
			if (!next) return;
			waiting = 0;
			phase++;
			timer = 0;
			return;
		}
		switch (phase)
		{
		case 0:
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3 || timer < 420) break;
			phase = mode == "load" ? 20 : 1;
			timer = 0;
			break;
		case 1:	// Town: one monster within 12 m, one at about 20 m out of sight.
			nearOne = Place(p, 160, "near");
			farOne = Place(p, 600, "far");
			if (!nearOne) { Console.Printf("REDONE no spot for the near monster"); phase = 99; break; }
			Now("near");
			break;
		case 2:
			if (timer == 1) { nearOne.DamageMobj(p, p, 1000000, 'None', DMG_FORCED); Console.Printf("REKILL near, health %d, far alive %d", nearOne.health, farOne && farOne.health > 0); }
			if (timer < 70) break;
			Now("neardead");
			break;
		case 3:	// Into the tavern; Daggerfall's -dfguardtest sends guards three seconds after.
			if (Inside()) { Console.Printf("REINSIDE %s", level.MapName); phase = 4; timer = 0; break; }
			if (timer < 20) break;
			AtDoor(p);
			if (timer == 40) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (timer > 35 * 20) { Console.Printf("REDONE door did not open"); phase = 99; }
			break;
		case 4:
		{
			let g = Guard();
			if (!g) { if (timer > 35 * 40) { Console.Printf("REDONE no guard came"); phase = 99; } break; }
			if (timer < 35 * 3) break;
			Console.Printf("REGUARD player %d at %.1f %.1f, %.1f units from the player", g.PlayerNumber(), g.pos.x, g.pos.y, g.Distance3D(p));
			Now("guard");
			break;
		}
		case 5:
			if (timer == 1) Console.Printf("REKILL guards %d", KillGuards(p));
			if (timer < 70) break;
			if (Guard()) { KillGuards(p); if (timer < 35 * 10) break; }
			Now("guarddead");
			break;
		case 6:
			if (timer == 20) { Console.Printf("RESAVE"); level.MakeAutoSave(); }
			if (timer < 280) break;
			Console.Printf("REDONE ok");
			phase = 99;
			break;
		case 20:	// After the load, inside the tavern where the guards died.
			Console.Printf("RELOADED %s, guards alive %d", level.MapName, Guard() != null);
			Now("loaded");
			break;
		case 21:
			nearOne = Place(p, 120, "loadednear");
			if (!nearOne) { Console.Printf("REDONE no spot for the near monster"); phase = 99; break; }
			Now("loadednear");
			break;
		case 22:
			if (timer == 1) nearOne.DamageMobj(p, p, 1000000, 'None', DMG_FORCED);
			if (timer < 70) break;
			Now("loadeddead");
			break;
		case 23:
			Console.Printf("REDONE ok");
			phase = 99;
			break;
		}
	}
}
