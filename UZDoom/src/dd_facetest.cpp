// [Doomerfall] Test only (-dffacetest <folder>, with Daggerfall's -dffacetest hook, DoomerfallFaceTest.cs).
// Daggerfall adds face A once in game, adds face B after its half of a save, and drops A three seconds after a load.
// This side waits for each state of the slot, takes a screenshot of it into <folder>, saves after A, loads after B,
// and quits. Each step logs "DDFACES <step> faces=<n>" to the console; the last line is "DDFACES PASS" or "DDFACES FAIL".

#include "../../bridge/doomerfall_bridge.h"
#include "c_dispatch.h"
#include "doomstat.h"
#include "gamestate.h"
#include "g_game.h"
#include "m_argv.h"
#include "printf.h"
#include "zstring.h"

FARG_ADVANCED(dffacetest, "Doomerfall", "folder", "Face test only: saves, loads, and screenshots quest follower faces into this folder.");

void DD_BridgeLog(const char *text);
bool DD_BridgeSaveIdle();
void G_SaveGame(const char *filename, const char *description, bool quick);

namespace
{
constexpr int64_t SettleNs = 1500000000LL, LimitNs = 90000000000LL;
int step = -1; // -1 not started, 99 finished
FString folder;
int64_t startNs, stepNs;
uint32_t loadVersion;

void Note(const char *what, int count)
{
	FString line;
	line.Format("DDFACES %s faces=%d", what, count);
	Printf("%s\n", line.GetChars());
	DD_BridgeLog(line.GetChars());
}

void Shot(const char *name)
{
	FString path;
	path.Format("%s/%s.png", folder.GetChars(), name);
	G_ScreenShot(path.GetChars());
}

void Finish(bool pass, int count)
{
	Note(pass ? "PASS" : "FAIL", count);
	step = 99;
	C_DoCommand("wait 35; quit");
}
}

void DD_FaceTestFrame(dfb_session *session, int count, uint32_t version)
{
	if (step == 99) return;
	const int64_t now = dfb_now_ns();
	if (step < 0)
	{
		const char *arg = Args->CheckValue(FArg_dffacetest);
		if (!arg) { step = 99; return; }
		folder = arg;
		step = 0;
		startNs = now;
	}
	if (now - startNs > LimitNs) { Finish(false, count); return; }
	if (!DD_BridgeSaveIdle() || gamestate != GS_LEVEL) { stepNs = 0; return; }
	// Each state must hold for SettleNs with both games idle before its screenshot.
	const auto settled = [&](bool want) { if (!want) { stepNs = 0; return false; } if (!stepNs) stepNs = now; return now - stepNs >= SettleNs; };
	FString save;
	save.Format("%s/facetest.zds", folder.GetChars());
	switch (step)
	{
	case 0: // Daggerfall added face A.
		if (!settled(count == 1)) return;
		Note("added", count);
		Shot("faces-1-added");
		G_SaveGame(save.GetChars(), "Doomerfall face test", false);
		step = 1; stepNs = 0;
		return;
	case 1: // After its half of the save, Daggerfall added face B, which the save does not have.
		if (!settled(count == 2)) return;
		Note("unsaved second face", count);
		Shot("faces-2-unsaved");
		loadVersion = version;
		G_LoadGame(save.GetChars());
		step = 2; stepNs = 0;
		return;
	case 2: // The load restored Daggerfall's list: A only.
		if (!settled(version != loadVersion && count == 1)) return;
		Note("loaded", count);
		Shot("faces-3-loaded");
		step = 3; stepNs = 0;
		return;
	case 3: // Daggerfall dropped A.
		if (!settled(count == 0)) return;
		Note("dropped", count);
		Shot("faces-4-dropped");
		Finish(true, count);
		return;
	}
}
