version "4.14"

// Building greeting test (building_greeting.py). Waits outdoors until Daggerfall is in play, then enters the test door
// with the dd_tm_use test hook and stands still inside. The script watches the logs and takes Doom's screenshots.
class BGHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 60;

	int phase, timer;
	bool done;

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS";
		timer++;
		if (timer > LIMIT) { Console.Printf("BGDONE timeout in phase %d", phase); done = true; return; }
		switch (phase)
		{
		case 0: // Outdoors in town, once Daggerfall is in play.
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			Console.Printf("BGNOTE outdoors (town %s)", level.MapName);
			phase = 1; timer = 0;
			break;
		case 1: // Stand at the door and press Use through the test hook until the space loads.
			if (inside) { Console.Printf("BGINSIDE %s", level.MapName); phase = 2; timer = 0; break; }
			{
				vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
				vector2 normal = (DOORDATA[3], DOORDATA[4]);
				p.SetOrigin((door.xy + normal * 48, door.z), false);
				p.vel = (0, 0, 0);
				p.angle = atan2(-normal.y, -normal.x);
				if (timer == 12 || timer % 140 == 139) CVar.FindCVar("dd_tm_use").SetInt(1);
			}
			break;
		case 2: // Inside: stand still while the script looks.
			if (timer >= 35 * 12) { Console.Printf("BGDONE inside"); done = true; }
			break;
		}
	}
}
