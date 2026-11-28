// [Doomerfall] Running skill time. Daggerfall tallies Running uses while its player runs (PlayerEntity.FixedUpdate), but
// the hidden Daggerfall pawn never moves, so Doom reports the time the player spends running.
// Daggerfall's rule, mapped to Doom: the run key is held (Doom's BT_RUN: the Run key, inverted by Always Run, as
// Daggerfall's run key and its autorun toggle), and the player is moving (movement keys pressed and the body actually
// travelling, so running in place against a wall does not count). Riding is checked on the Daggerfall side.
// Out: DFB_KIND_RUN_TIME events carrying the running tics; Daggerfall turns them into uses (DoomerfallRunning.cs).
// Nothing here runs without a bridge session or off a generated Daggerfall map.

#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "d_event.h"
#include "d_player.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "printf.h"
#include "zstring.h"

void DD_BridgeLog(const char *text);

namespace
{
constexpr uint32_t SendEvery = TICRATE; // tics; a run longer than this goes out in pieces
constexpr double MinSpeed = 1.0;        // map units per tic; Doom walking is several times this
int lastTic = -1;
uint32_t pending;

bool Running()
{
	if (gamestate != GS_LEVEL || !playeringame[consoleplayer]) return false;
	const player_t &p = players[consoleplayer];
	if (!p.mo || p.playerstate != PST_LIVE || p.health <= 0) return false;
	const usercmd_t &cmd = p.cmd;
	if (!(cmd.buttons & BT_RUN) || (cmd.forwardmove == 0 && cmd.sidemove == 0)) return false;
	return p.mo->Vel.XY().Length() >= MinSpeed;
}

void Send(dfb_session *session)
{
	dfb_event e{};
	e.kind = DFB_KIND_RUN_TIME;
	e.tic = gametic;
	dfb_run_time body{};
	body.tics = pending;
	memcpy(e.payload, &body, sizeof(body));
	const int rc = dfb_send(session, &e);
	DD_BridgeLog(FStringf("running: sent %u running tics (%d)", pending, rc).GetChars());
	pending = 0;
}
}

// Once a frame from DD_BridgeFrame. worldContext is DFB_WORLD_NONE off a generated Daggerfall map.
void DD_RunningFrame(dfb_session *session, uint32_t worldContext)
{
	if (!session) return;
	const int now = gametic;
	const int elapsed = lastTic < 0 || now < lastTic ? 0 : now - lastTic;
	lastTic = now;
	const bool running = worldContext != DFB_WORLD_NONE && Running();
	if (running && elapsed > 0) pending += uint32_t(elapsed < TICRATE ? elapsed : TICRATE); // a long hitch is not running time
	if (pending >= SendEvery || (pending > 0 && !running)) Send(session);
}
