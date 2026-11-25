// [Doomerfall] What the bridge test drivers (dd_bridge_test.cpp) may read and do. Test only; game code never calls these.
#pragma once

#include <cstdint>

struct DDBridgeTestView
{
	bool peerSeen;
	uint32_t dfPhase;
	bool hpValid, hpDead;
	int hpCurrent, hpMax;
	uint32_t hpApplied, hpSent;	// Last HP event Daggerfall applied, and the last one Doom sent.
	bool flowMode, atTitle, ngIdle, ngDifficulty, ngPlain, flowHold;
	bool settled;	// No load, save, or queued save.
	bool saveIdle, saveReady;
	bool uiClosed, daggerfallUiOpen;
	int death;	// 0 none, 1 Doom's death view, 2 the death menu.
	bool ngSaveDone, ngSaveBusy;	// The new character's first save: written, or still waiting or writing.
	int ngSaveHp;
	double ngSavePos[3];
	const char *loadFile;	// The save the last load used.
	bool loadedNewGameSave;	// That file is the new character's first save.
};

// dd_bridge.cpp
void DD_BridgeTestView(DDBridgeTestView &view);
void DD_BridgeTestHit(int amount, const char *source);	// A hit reported to Daggerfall, as from P_DamageMobj.
void DD_BridgeTestSendText(const char *text);
void DD_BridgeTestCloseUi();	// Closes the open Daggerfall window, as a player would.
void DD_BridgeTestForceLog();	// The status line is written at the next frame.

// dd_bridge_test.cpp: each does nothing without its test's command-line flag.
void DD_BridgeTestFrame(int64_t now);	// Once per bridge frame, between tics.
void DD_BridgeTestTic();	// Inside the bridged player's tic, from DD_BridgeHpThink.
void DD_BridgeTestSaveDone();	// A bridged save finished: -dfsavetest quits unless autosaves remain.
bool DD_BridgeTestSaveAnyMap();	// -dfsavetest also saves through the bridge on a regular map.
