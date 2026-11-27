version "4.14"

// Readable signs test (signs.py). Every press is Doom's own Use button through the QA channel (signs.py answers each
// SGUSE line), so it runs Doom's whole Use path. BOARD is one of the town's bulletin boards: x, y, bottom z, and the
// model's facing (either side may be the front, so both are tried). Route:
//   1. From 260 units away (Daggerfall's reach is 6.4 m, 192 Doom units), Use on the board from each side:
//      Daggerfall's "You are too far away." and no window.
//   2. From 40 units away, Use on the board from each side: Daggerfall's bulletin board box opens in Doom, and the
//      first one that opens ends the route (a menu takes the later presses).
class SGHarness : StaticEventHandler
{
	static const double BOARD[] = { @BOARD@ };
	static const double STANDS[] = { 260, -260, 40, -40 };
	const LIMIT = 35 * 60;

	int phase, timer, step;
	bool done, wantUse;
	double holdAngle;

	void Stand(PlayerPawn p, double away)
	{
		vector2 normal = (BOARD[3], BOARD[4]);
		p.SetOrigin(((BOARD[0], BOARD[1]) + normal * away, BOARD[2]), false);
		p.SetZ(p.floorz);
		p.vel = (0, 0, 0);
		p.angle = away > 0 ? atan2(-normal.y, -normal.x) : atan2(normal.y, normal.x);
		p.pitch = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (wantUse)
		{
			// Hold still until the press arrives. This tic's player think already ran it when BT_USE shows here.
			if (!(players[0].cmd.buttons & BT_USE)) { p.vel = (0, 0, 0); p.angle = holdAngle; p.pitch = 0; return; }
			wantUse = false;
			Console.Printf("SGUSED");
		}
		timer++;
		if (timer > LIMIT) { Console.Printf("SGDONE timeout in phase %d", phase); done = true; return; }
		if (phase == 0)
		{
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; return; }
			phase = 1; timer = 0;
			return;
		}
		if (step >= STANDS.Size()) { Console.Printf("SGDONE all presses"); done = true; return; }
		Stand(p, STANDS[step]);
		if (timer == 30)
		{
			wantUse = true;
			holdAngle = p.angle;
			Console.Printf("SGPRESS %d away %.0f at %.1f,%.1f angle %.1f", step, STANDS[step], p.pos.x, p.pos.y, p.angle);
			Console.Printf("SGUSE");
		}
		if (timer == 100) { step++; timer = 0; }
	}
}
