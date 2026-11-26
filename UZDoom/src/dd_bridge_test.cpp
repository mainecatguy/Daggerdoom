// [Doomerfall] Test only: bridge test drivers, each behind its own command-line flag. They drive the real menu, save,
// load, death, and HP paths of dd_bridge.cpp and log what happened; the tools under tools/ and bridge/test read the log.
//   -dfbridgetestpause ext|game|menu   bridge/test/real_games_test.py
//   -dfhptest basic|monsters           tools/hp_sync
//   -dfsavetest file|autoN             tools/synchronized_save, bridge/test (the fault injection -dfsavetestfail stays in dd_bridge.cpp)
//   -dfloadtest mode:file              tools/synchronized_load and many paired tests ("resume" loads a save, then the route continues)
//   -dfnewgametest once|twice|escape          tools/new_game, tools/demo_combined/walk.py, tools/reported_location
//   -dfplainloadtest once              tools/plain_load

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

#include "../../bridge/doomerfall_bridge.h"
#include "dd_bridge_test.h"
#include "actor.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_net.h"
#include "d_player.h"
#include "d_protocol.h"
#include "doomstat.h"
#include "g_game.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "i_interface.h"
#include "m_argv.h"
#include "menu.h"
#include "p_local.h"
#include "playsim/dd_treadmill.h"
#include "printf.h"
#include "zstring.h"

FARG_ADVANCED(dfnewgametest, "Doomerfall", "once|twice|escape", "Bridge test only: chooses New Game and a difficulty through the real menu path (escape: New Game at every return to the title, no difficulty).");
FARG_ADVANCED(dfnewgameskill, "Doomerfall", "index", "Bridge test only: the difficulty -dfnewgametest chooses in the skill menu (default 2).");
FARG_ADVANCED(dfplainloadtest, "Doomerfall", "once", "Bridge test only: runs dd_load_daggerfall at the title and chooses a difficulty.");
FARG_ADVANCED(dfbridgetestpause, "Doomerfall", "ext|game|menu", "Bridge test only: enters a pause state for six seconds.");
FARG_ADVANCED(dfsavetest, "Doomerfall", "file|autoN", "Save test only: makes one synchronized save to this file, or N real autosaves, then quits.");
FARG_ADVANCED(dfloadtest, "Doomerfall", "mode:file", "Load test only: cycle, death, menu, bad, newgame, again, restart, or resume, using this save file.");
FARG_ADVANCED(dfhptest, "Doomerfall", "basic|monsters", "HP sync test only: scripts hits, heals, and a lethal hit.");

EXTERN_CVAR(Int, dd_ui_test_hold)
void DD_BridgeLog(const char *text);
void G_SaveGame(const char *filename, const char *description, bool quick);
void P_UnPredictClient();

namespace
{
bool parsed;
DDBridgeTestView v;

void Log(const char *format, ...)
{
	char line[512];
	va_list args;
	va_start(args, format);
	vsnprintf(line, sizeof(line), format, args);
	va_end(args);
	DD_BridgeLog(line);
}

//==========================================================================
// -dfbridgetestpause: enters a real pause state, holds it, and leaves it.
//==========================================================================

const char *testPause;
int testPhase;
int64_t testAtNs;

void SetTestPause(bool on)
{
	if (!strcmp(testPause, "ext")) pauseext = on;
	else if (!strcmp(testPause, "game")) C_DoCommand("pause");
	else if (!strcmp(testPause, "menu")) C_DoCommand(on ? "menu_main" : "closemenu");
}

void RunTestPause(int64_t now)
{
	if (!testPause || testPhase == 2 || !v.peerSeen || gamestate != GS_LEVEL) return;
	if (!testAtNs) testAtNs = now + 5000000000LL;
	if (now < testAtNs) return;
	const bool begin = testPhase == 0;
	Log("test pause %s: %s", testPause, begin ? "begin" : "end");
	SetTestPause(begin);
	testPhase++;
	testAtNs = now + 6000000000LL;
	DD_BridgeTestForceLog();
}

//==========================================================================
// -dfhptest basic|monsters: drives hits, heals, rapid hits, Daggerfall-side damage, a direct health assignment,
// and a lethal hit through Doom's real code, logging what the player shows at each step.
//==========================================================================

const char *hpTestMode;
int hpTestStep;
int hpTestPending; // A step that must run inside a tic. Outside a tic the player is a prediction copy.
int64_t hpTestNextNs;

void HpTestLog(const char *what)
{
	DD_BridgeTestView(v);
	const player_t &p = players[consoleplayer];
	Log("hp test: %s | shown=%d confirmed=%d/%d state=%d sent=%u applied=%u", what, p.health, v.hpCurrent, v.hpMax, int(p.playerstate),
		v.hpSent, v.hpApplied);
}

void RunHpTest(int64_t now)
{
	if (!hpTestMode || hpTestStep < 0 || gamestate != GS_LEVEL || !v.hpValid || !players[consoleplayer].mo) return;
	if (hpTestPending) return;
	if (!hpTestNextNs) hpTestNextNs = now + 2000000000LL;
	if (now < hpTestNextNs) return;
	const bool settled = v.hpApplied >= v.hpSent;
	if (!settled && now < hpTestNextNs + 3000000000LL) return; // Wait for Daggerfall to confirm the last step.
	if (!strcmp(hpTestMode, "monsters"))
	{
		if (hpTestStep == 0)
		{
			C_DoCommand("summon DoomImp");
			C_DoCommand("summon DoomImp");
			C_DoCommand("summon DoomImp");
			HpTestLog("summoned three imps");
		}
		else if (hpTestStep % 4 == 0) HpTestLog("monsters");
		hpTestStep++;
		hpTestNextNs = now + 500000000LL;
		return;
	}

	if (hpTestStep >= 1 && hpTestStep <= 7)
	{
		hpTestPending = hpTestStep; // Done at the next player tic by DD_BridgeTestTic.
		return;
	}
	switch (hpTestStep)
	{
	case 0: HpTestLog("start"); break;
	case 8: HpTestLog("after Daggerfall reported death"); break;
	case 9: HpTestLog("finished"); hpTestStep = -1; C_DoCommand("quit"); return;
	}
	hpTestStep++;
	hpTestNextNs = now + (hpTestStep == 8 ? 1500000000LL : 600000000LL);
}

//==========================================================================
// -dfsavetest file|autoN: one synchronized save with HP events in flight, or N autosaves through the real net command.
//==========================================================================

const char *saveTestFile;
bool saveTestStarted;
int64_t saveTestAtNs;
int saveTestAutos; // Autosaves still to trigger in an autoN test.

void RunSaveTest(int64_t now)
{
	if (!saveTestFile) return;
	if (!strncmp(saveTestFile, "auto", 4))
	{
		if (!saveTestStarted && gamestate == GS_LEVEL && v.saveReady)
		{
			saveTestStarted = true;
			saveTestAutos = std::max(atoi(saveTestFile + 4), 1);
			saveTestAtNs = now + 2000000000LL;
		}
		if (saveTestAutos > 0 && v.saveIdle && now >= saveTestAtNs && gamestate == GS_LEVEL && v.saveReady)
		{
			saveTestAutos--;
			saveTestAtNs = now + 1500000000LL;
			for (int i = 0; i < 5; i++) DD_BridgeTestHit(1, "autosave test");
			Net_WriteInt8(DEM_CHECKAUTOSAVE);
		}
	}
	else if (!saveTestStarted && v.peerSeen && gamestate == GS_LEVEL && v.dfPhase == DFB_DF_PHASE_PLAY)
	{
		if (!saveTestAtNs) saveTestAtNs = now + 2000000000LL;
		if (now >= saveTestAtNs)
		{
			saveTestStarted = true;
			for (int i = 0; i < 20; i++) DD_BridgeTestHit(1, "save test"); // In flight when the request is sent.
			G_SaveGame(saveTestFile, "Doomerfall save test", false);
		}
	}
}

//==========================================================================
// -dfnewgametest and -dfplainloadtest: go through the real New Game menu entry, or dd_load_daggerfall, once
// Daggerfall is ready at the title, then choose difficulty 2 in the real skill menu.
//==========================================================================

const char *ngTest, *plainTest;
bool difficultyTest;
int64_t ngTestAt, difficultyAt;

void RunNewGameTest(int64_t now)
{
	if (!v.flowMode) return;
	if (v.ngDifficulty)
	{
		if (!difficultyTest || !menuactive) return;
		if (!difficultyAt) difficultyAt = now + 1000000000LL;
		if (now < difficultyAt) return;
		difficultyAt = now + 5000000000LL;
		const char *skill = Args->CheckValue(FArg_dfnewgameskill);
		const int index = skill ? atoi(skill) : 2;
		Log("new game test: choosing difficulty %d", index);
		M_SetMenu(FName("Startgame"), index);
		return;
	}
	difficultyAt = 0;
	const bool ready = v.ngIdle && v.atTitle && gamestate != GS_STARTUP && v.peerSeen && v.dfPhase != DFB_DF_PHASE_BOOT &&
		v.dfPhase != DFB_DF_PHASE_LOADING;
	if (!ready || (!plainTest && !ngTest)) return;
	if (!ngTestAt) ngTestAt = now + 1000000000LL;
	if (now < ngTestAt) return;
	ngTestAt = 0;
	if (plainTest)
	{
		plainTest = nullptr;
		Log("plain load test: running dd_load_daggerfall");
		C_DoCommand("dd_load_daggerfall");
		return;
	}
	const char *mode = ngTest;
	ngTest = !strcmp(mode, "escape") ? mode : strcmp(mode, "twice") ? nullptr : "once"; // escape: every time, and the driver picks the difficulty
	Log("new game test: choosing New Game");
	M_StartControlPanel(false);
	M_SetMenu(FName("PlayerclassMenu"), -1);
}

//==========================================================================
// -dfloadtest mode:file: drives the same save, load, and death entry points the menus use.
//==========================================================================

const char *loadTestMode;
FString loadTestFile;
int loadTestStep, loadTestSavedHp;
double loadTestPos[3];
int64_t loadTestAtNs;

void LoadTestLog(const char *what)
{
	DD_BridgeTestView(v);
	const player_t &p = players[consoleplayer];
	double x = 0, y = 0, z = 0, yaw = 0;
	const bool world = gamestate == GS_LEVEL && DDTreadmill_PlayerWorld(x, y, z, yaw) != DD_AREA_NONE;
	Log("load test: %s | doom hp %d, Daggerfall hp %d dead %d, world %d at %.1f,%.1f, gamestate %d, death %d, hold %d, menu %d", what, p.health,
		v.hpCurrent, int(v.hpDead), int(world), x, y, int(gamestate), v.death, int(v.flowHold), int(menuactive));
}

// restart mode: changes the saved game, so the new one can be told apart from it.
void RestartPlay()
{
	DD_BridgeTestHit(17, "load test change");
	P_UnPredictClient();
	if (AActor *mo = players[consoleplayer].mo) mo->SetOrigin(mo->Pos() + DVector3(96, 0, 0), false);
}

// restart mode: what the new character holds in Doom, for the driver to compare with a first New Game.
void RestartLogFresh()
{
	DD_BridgeTestView(v);
	const player_t &p = players[consoleplayer];
	FString inv;
	int count = 0;
	if (p.mo) for (AActor *item = p.mo->Inventory; item; item = item->Inventory, count++) inv.AppendFormat(" %s", item->GetClass()->TypeName.GetChars());
	LoadTestLog("second character arrived");
	Log("load test: fresh doom hp %d, Daggerfall hp %d/%d, map %s, %d inventory items:%s", p.health, v.hpCurrent, v.hpMax, primaryLevel->MapName.GetChars(), count, inv.GetChars());
}

void RunLoadTest(int64_t now)
{
	if (!loadTestMode || loadTestStep < 0 || now < loadTestAtNs) return;
	if (!strcmp(loadTestMode, "resume")) // Loads once both games are playing, then lets the map's own test continue.
	{
		if (gamestate != GS_LEVEL || !v.saveReady) return;
		if (!loadTestAtNs) { loadTestAtNs = now + 3000000000LL; return; } // Lets the first terrain streaming finish.
		G_LoadGame(loadTestFile.GetChars());
		dd_ui_test_hold = 0;
		loadTestStep = -1;
		return;
	}
	if (!v.uiClosed)
	{
		// A New Game's quests open Daggerfall windows by themselves. The test answers them as a player would.
		if (v.daggerfallUiOpen) DD_BridgeTestCloseUi();
		loadTestAtNs = now + 500000000LL;
		return;
	}
	const bool newgame = !strcmp(loadTestMode, "newgame");
	const bool restart = !strcmp(loadTestMode, "restart");
	const bool bad = !strcmp(loadTestMode, "bad"), death = !strcmp(loadTestMode, "death"), menu = !strcmp(loadTestMode, "menu") || !strcmp(loadTestMode, "again");
	const player_t &player = players[consoleplayer];
	double x = 0, y = 0, z = 0, yaw = 0;
	const auto finish = [&]()
	{
		const bool world = gamestate == GS_LEVEL && DDTreadmill_PlayerWorld(x, y, z, yaw) != DD_AREA_NONE;
		int space;
		if (newgame && world && DDTreadmill_PlayerSpace(x, y, z, yaw, space)) // As the new game save measured it.
			Log("load test: dungeon position %.1f,%.1f, saved at %.1f,%.1f", x, y, loadTestPos[0], loadTestPos[1]);
		const double moved = std::hypot(x - loadTestPos[0], y - loadTestPos[1]);
		const bool rightFile = !newgame || v.loadedNewGameSave;
		if (newgame) Log("load test: loaded %s, the new game save %s", v.loadFile, rightFile ? "yes" : "NO");
		const bool pass = rightFile && world && !v.flowHold && v.death == 0 && player.playerstate == PST_LIVE &&
			player.health == loadTestSavedHp && v.hpCurrent == loadTestSavedHp && !v.hpDead && moved < 2.0;
		LoadTestLog(pass ? "PASS" : "FAIL");
		Log("load test: moved %.2f from the saved position", moved);
		loadTestStep = -1;
		C_DoCommand("quit");
	};
	switch (loadTestStep)
	{
	case 0:
		if (gamestate != GS_LEVEL || !v.saveReady || !v.hpValid) return;
		if (newgame) // No save of its own: dies and loads the new game's start save.
		{
			if (!v.ngSaveDone || !v.settled) return;
			loadTestSavedHp = v.ngSaveHp;
			memcpy(loadTestPos, v.ngSavePos, sizeof(loadTestPos));
			LoadTestLog("new game save written");
			P_UnPredictClient();
			if (AActor *mo = players[consoleplayer].mo) mo->SetOrigin(mo->Pos() + DVector3(48, 0, 0), false); // The load must undo this.
			DD_BridgeTestHit(100000, "load test lethal");
			loadTestStep = 4;
			loadTestAtNs = now + 1500000000LL;
			return;
		}
		if (v.ngSaveBusy || !v.settled) return; // After a New Game, its start save goes first.
		if (!loadTestAtNs) { loadTestAtNs = now + 2000000000LL; return; }
		LoadTestLog("start");
		if (bad)
		{
			loadTestSavedHp = player.health;
			DDTreadmill_PlayerWorld(loadTestPos[0], loadTestPos[1], loadTestPos[2], yaw);
			G_LoadGame(loadTestFile.GetChars());
			loadTestStep = 10;
			loadTestAtNs = now + 3000000000LL;
			return;
		}
		DD_BridgeTestHit(13, "load test setup");
		loadTestStep = 1;
		loadTestAtNs = now + 700000000LL;
		return;
	case 1:
		if (v.hpApplied != v.hpSent) return;
		loadTestSavedHp = v.hpCurrent;
		G_SaveGame(loadTestFile.GetChars(), "Doomerfall load test", false);
		loadTestStep = 2;
		loadTestAtNs = now + 1000000000LL;
		return;
	case 2:
		if (!v.settled || !v.saveReady) return;
		DDTreadmill_PlayerWorld(loadTestPos[0], loadTestPos[1], loadTestPos[2], yaw);
		LoadTestLog("saved");
		if (restart) { RestartPlay(); loadTestStep = 20; loadTestAtNs = now + 1500000000LL; return; }
		if (death || menu) DD_BridgeTestHit(100000, "load test lethal");
		else
		{
			DD_BridgeTestHit(17, "load test change");
			P_UnPredictClient();
			if (AActor *mo = players[consoleplayer].mo) mo->SetOrigin(mo->Pos() + DVector3(96, 0, 0), false);
		}
		loadTestStep = death || menu ? 4 : 3;
		loadTestAtNs = now + 1500000000LL;
		return;
	case 3:
		LoadTestLog("changed");
		G_LoadGame(loadTestFile.GetChars());
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	case 4:
		if (v.death != 2 || !menuactive) return;
		LoadTestLog("death menu open");
		loadTestStep = 11;
		loadTestAtNs = now + 4000000000LL;
		return;
	case 11:
		C_DoCommand("screenshot"); // Some frames after opening, so the picture shows the drawn menu.
		loadTestStep = 5;
		loadTestAtNs = now + 1000000000LL; // With the wait above, longer than Daggerfall's own restart timer.
		return;
	case 5:
		LoadTestLog("still dead after Daggerfall's restart time");
		if (menu)
		{
			C_DoCommand("dd_death_mainmenu");
			loadTestStep = 6;
			loadTestAtNs = now + 2000000000LL;
			return;
		}
		C_DoCommand("dd_death_loadlast");
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	case 6:
		LoadTestLog("at the title");
		if (!strcmp(loadTestMode, "again")) // A second character in the same session, after the first one died.
		{
			ngTest = "once";
			loadTestStep = -1;
			return;
		}
		C_DoCommand("map DDT09183"); // Must be refused while no game is loaded.
		loadTestStep = 7;
		loadTestAtNs = now + 1500000000LL;
		return;
	case 7:
		LoadTestLog("after trying a new game from the title");
		G_LoadGame(loadTestFile.GetChars());
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	case 8:
		if (!v.settled || v.flowHold) return;
		loadTestStep = 9;
		loadTestAtNs = now + 2000000000LL; // Both games run together for a moment before the check.
		return;
	case 9:
		finish();
		return;
	case 10:
		if (!v.settled) return;
		finish();
		return;
	case 20: // restart: New Game in the running game, through the real menu entry. The driver answers Yes.
		if (gamestate != GS_LEVEL || !v.settled) return;
		LoadTestLog("played on, choosing New Game in the running game");
		M_StartControlPanel(false);
		M_SetMenu(FName("PlayerclassMenu"), -1);
		Log("load test: asking to confirm New Game, menu %d", int(menuactive));
		loadTestStep = 21;
		return;
	case 21:
		if (!v.atTitle) return;
		LoadTestLog("old game dropped, at the title");
		loadTestStep = 22;
		return;
	case 22: // The second character has arrived and its start save is written; then the earlier save must still load.
		if (v.atTitle || !v.ngIdle || gamestate != GS_LEVEL || !v.hpValid || !v.ngSaveDone || !v.settled) return;
		RestartLogFresh();
		G_LoadGame(loadTestFile.GetChars());
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	}
}

void Parse()
{
	parsed = true;
	testPause = Args->CheckValue(FArg_dfbridgetestpause);
	hpTestMode = Args->CheckValue(FArg_dfhptest);
	saveTestFile = Args->CheckValue(FArg_dfsavetest);
	ngTest = Args->CheckValue(FArg_dfnewgametest);
	plainTest = Args->CheckValue(FArg_dfplainloadtest);
	difficultyTest = (ngTest && strcmp(ngTest, "escape")) || plainTest;
	if (const char *test = Args->CheckValue(FArg_dfloadtest))
	{
		static std::string mode(test);
		const size_t colon = mode.find(':');
		if (colon != std::string::npos)
		{
			loadTestFile = mode.substr(colon + 1).c_str();
			mode.resize(colon);
			loadTestMode = mode.c_str();
		}
	}
}
}

void DD_BridgeTestFrame(int64_t now)
{
	if (!parsed) Parse();
	DD_ArrivalTestFrame(now); // -dfsetuptest, -dffreezetest (dd_arrival_test.cpp)
	if (!testPause && !hpTestMode && !saveTestFile && !difficultyTest && !loadTestMode) return;
	DD_BridgeTestView(v);
	RunSaveTest(now);
	RunLoadTest(now);
	RunNewGameTest(now);
	RunHpTest(now);
	RunTestPause(now);
}

void DD_BridgeTestSaveDone()
{
	if (!parsed) Parse();
	if (saveTestFile && saveTestAutos <= 0) C_DoCommand("quit"); // An autoN test continues after a failure, to prove play resumes.
}

bool DD_BridgeTestSaveAnyMap()
{
	if (!parsed) Parse();
	return saveTestFile != nullptr;
}

void DD_BridgeTestTic()
{
	if (!hpTestPending) return;
	player_t &p = players[consoleplayer];
	AActor *mo = p.mo;
	char note[96];
	switch (hpTestPending)
	{
	case 1: P_DamageMobj(mo, nullptr, nullptr, 40, NAME_None); HpTestLog("after one hit of 40 (same tic)"); break;
	case 2: P_GiveBody(mo, 25, 100); HpTestLog("after a heal of 25 (same tic)"); break;
	case 3:
		for (int i = 0; i < 20; i++) P_DamageMobj(mo, nullptr, nullptr, 1 + i % 3, NAME_None);
		HpTestLog("after 20 rapid hits in one tic");
		break;
	case 4: DD_BridgeTestSendText("hptest damage 15"); HpTestLog("asked Daggerfall for 15 damage"); break;
	case 5: p.health -= 6; HpTestLog("after a direct health assignment of -6"); break;
	case 6: C_DoCommand("give medikit"); HpTestLog("queued give medikit"); break;
	case 7:
		P_DamageMobj(mo, nullptr, nullptr, 500, NAME_None);
		snprintf(note, sizeof(note), "after a lethal hit of 500 (same tic), player alive=%d", p.playerstate == PST_LIVE);
		HpTestLog(note);
		break;
	}
	hpTestStep = hpTestPending + 1;
	hpTestPending = 0;
	hpTestNextNs = dfb_now_ns() + (hpTestStep == 8 ? 1500000000LL : 600000000LL);
}
