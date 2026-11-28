version "4.14"

// Running skill test (running.py), where the test town's map starts (outside the town walls). The runner holds Doom's own
// buttons through the QA console (+forward, +left, +speed) when this prints each RNPHASE line:
//   stand     nothing held
//   walk      +forward +left: walking in a circle (Always Run is off in the private config)
//   run       +speed added: running in a circle
//   runstand  -forward -left, +speed still held: the run key without moving
//   done      everything released
// Each phase ends with a summary: tics, distance moved, and tics with the run button and a movement key both held (the
// harness's own count of the input, to set the expected Running uses against).
class RNHarness : StaticEventHandler
{
	static const int LENGTHS[] = { 35 * 8, 35 * 8, 35 * 20, 35 * 8 };
	static const String NAMES[] = { "stand", "walk", "run", "runstand", "done" };
	const BT_RUN_BIT = 1 << 25;
	int phase, timer, wait, runInput;
	double moved;
	vector2 last;
	bool started, done;

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
			last = p.pos.xy;
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
		Console.Printf("RNPHASE %s at maptime %d", NAMES[phase], level.maptime);
		if (phase >= LENGTHS.Size()) done = true;
	}
}
