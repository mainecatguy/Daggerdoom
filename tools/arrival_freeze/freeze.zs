version "4.14"

// Test only (tools/arrival_freeze/run_freeze.py): enters Privateer's Hold by the town door, as tools/lockpick/paired
// does, then plays on inside for a few seconds and prints "AFDONE". The player stays a normal target, so the dungeon's
// monsters may act on it once play resumes. The freeze itself is checked by -dffreezetest in the bridge log.
// @DEMO@ = 1 (play.bat): only enters, then leaves the player in control.

class AFHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	bool DEMO, USE;
	int phase, timer, inside, firstTime, lastTime, gaps;
	override void OnRegister() { DEMO = @DEMO@; USE = @USE@; }

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		bool isInside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		timer++;
		if (isInside && !DEMO)
		{
			// Scripts must see every level.time value across the arrival (a handler is made anew for each map).
			// USE: on the new map's first tic (before the freeze) face back out of the entrance, as tools/lockpick's trip
			// does to leave, so the presses during the freeze are on the exit.
			if (inside == 0) { firstTime = level.time; if (USE) p.angle += 180; }
			else if (level.time != lastTime + 1) gaps++;
			lastTime = level.time;
			if (++inside == 35 * 6) Console.Printf("AFDONE health %d first_time %d time_gaps %d", p.health, firstTime, gaps);
			return;
		}
		if (phase == 0)
		{
			if (isInside) { phase = 1; return; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) return;
			vector3 tdoor = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
			vector2 normal = (DOORDATA[3], DOORDATA[4]);
			p.SetOrigin((tdoor.xy + normal * 48, tdoor.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) return;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			phase = 1;
			return;
		}
	}
}
