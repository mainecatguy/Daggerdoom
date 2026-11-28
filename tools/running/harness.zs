version "4.14"

// Running skill test (running.py), where the test town's map starts (outside the town walls). The runner holds Doom's own
// buttons through the QA console (+forward, +left, +speed, pause) when this prints each RNPHASE line:
//   stand     nothing held
//   walk      +forward +left: walking in a circle (Always Run is off in the private config)
//   run       +speed added: running in a circle
//   runstand  -forward -left, +speed still held: the run key without moving
//   wall      the harness puts the player against the nearest tall wall, facing straight into it; +forward (run held)
//   slide     the same spot, turned 45 degrees along the wall; +forward still held, so the player slides along it
//   pause     back at the start, +forward +left (running a circle); the runner presses Pause for a while (WorldTick and
//             this phase's clock stop meanwhile), then unpauses
//   done      everything released
// Each phase ends with a summary: tics, distance moved, and tics with the run button and a movement key both held (the
// harness's own count of the input, to set the expected Running uses against).
class RNHarness : StaticEventHandler
{
	static const int LENGTHS[] = { 35 * 8, 35 * 8, 35 * 20, 35 * 8, 35 * 8, 35 * 8, 35 * 6 };
	static const String NAMES[] = { "stand", "walk", "run", "runstand", "wall", "slide", "pause", "done" };
	const BT_RUN_BIT = 1 << 25;
	int phase, timer, wait, runInput;
	double moved, wallAngle;
	vector2 last, startPos;
	vector3 wallSpot;
	bool started, done, haveWall;

	// The nearest wall at least 40 units tall (a trace at 40 units up hits it), from the start point.
	void FindWall(PlayerPawn p)
	{
		double best = 1e9;
		for (int i = 0; i < 64; i++)
		{
			double a = i * 360. / 64;
			FLineTraceData t;
			if (!p.LineTrace(a, 2048, 0, TRF_THRUACTORS, 40, data: t) || t.HitType != TRACE_HitWall) continue;
			if (t.Distance >= best || !t.HitLine) continue;
			best = t.Distance;
			wallSpot = t.HitLocation;
			// Face square into the wall: the line's normal, turned to point away from the player.
			vector2 n = (t.HitLine.delta.y, -t.HitLine.delta.x).Unit();
			if (n dot (p.pos.xy - wallSpot.xy) < 0) n = -n;
			wallAngle = atan2(-n.y, -n.x);
		}
		haveWall = best < 1e9;
		if (haveWall) Console.Printf("RNWALL at %.0f,%.0f angle %.1f distance %.0f", wallSpot.x, wallSpot.y, wallAngle, best);
		else Console.Printf("RNWALL none found");
	}

	void PlaceAtWall(PlayerPawn p, double turn)
	{
		if (!haveWall) return;
		vector2 dir = (cos(wallAngle), sin(wallAngle));
		p.SetOrigin((wallSpot.xy - dir * (p.radius * 1.45 + 2), p.pos.z), false); // clear of the square box's corners
		p.SetZ(p.floorz);
		p.vel = (0, 0, 0);
		p.angle = wallAngle + turn;
		p.pitch = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (!started)
		{
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { wait = 0; return; }
			if (++wait < 35 * 4) return;
			started = true;
			startPos = last = p.pos.xy;
			FindWall(p);
			Console.Printf("RNPHASE %s at maptime %d", NAMES[0], level.maptime);
			return;
		}
		moved += (p.pos.xy - last).Length();
		last = p.pos.xy;
		let cmd = players[0].cmd;
		if ((cmd.buttons & BT_RUN_BIT) && (cmd.forwardmove != 0 || cmd.sidemove != 0)) runInput++;
		if (++timer < LENGTHS[phase]) return;
		Console.Printf("RNSUM %s tics %d moved %.0f runinput %d speed %.1f", NAMES[phase], timer, moved, runInput, p.vel.xy.Length());
		phase++;
		timer = 0; moved = 0; runInput = 0;
		if (NAMES[phase] == "wall") PlaceAtWall(p, 0);
		else if (NAMES[phase] == "slide") PlaceAtWall(p, 45);
		else if (NAMES[phase] == "pause")
		{
			p.SetOrigin((startPos, p.pos.z), false);
			p.SetZ(p.floorz);
			p.vel = (0, 0, 0);
		}
		last = p.pos.xy;
		Console.Printf("RNPHASE %s at maptime %d", NAMES[phase], level.maptime);
		if (phase >= LENGTHS.Size()) done = true;
	}
}
