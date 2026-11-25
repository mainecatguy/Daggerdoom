// [Doomerfall] Test only: runs the encounter planner and placer on the loaded map without Daggerfall, so a converted
// dungeon can be placed at any area level from the command line (tools/encounter_placer/placer_test.py):
//   uzdoom ... -ddenctest <areaLevel> [-ddenctestdungeon <index> <typeName>] +map MAP01
// 45 tics in (after DRLA's spawners have been claimed), it places the map's encounters with Privateer's Hold's facts (encounter card 4's paired run), checks
// them again a second later, and quits. p_tick.cpp calls DD_EncounterTestTick once per tic.
// Card 7: -ddenctestperf <tics> keeps running after the check: every placed monster is woken against the (god mode)
// player, and the playsim think time of each tic (the "think" stat) is logged as a summary before quitting.

#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <vector>
#include <cstdlib>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "c_dispatch.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "m_argv.h"
#include "p_local.h"
#include "p_checkposition.h"
#include "printf.h"
#include "stats.h"
#include "d_player.h"

void DD_MonstersTestEncounters(FLevelLocals *Level, const dfb_encounter_area &a, const char *location, const char *region, const char *type);

static int FindArg(const char *name)
{
	for (int i = 1; i < Args->NumArgs(); i++)
		if (!stricmp(Args->GetArg(i), name)) return i;
	return 0;
}

// Card 6 (tools/encounter_placer/civilwar_test.py): -ddtestsave <tic> <name> saves the game at that map time, and
// -ddtestquit <tic> quits at that map time (a loaded game keeps its map time, so both count from the map's start).
static void SaveQuitTick(FLevelLocals *Level)
{
	static int saveAt = -2, quitAt = -2;
	if (saveAt == -2)
	{
		const int s = FindArg("-ddtestsave"), q = FindArg("-ddtestquit");
		saveAt = s && s + 2 < Args->NumArgs() ? atoi(Args->GetArg(s + 1)) : -1;
		quitAt = q && q + 1 < Args->NumArgs() ? atoi(Args->GetArg(q + 1)) : -1;
	}
	if (saveAt >= 0 && Level->maptime == saveAt)
	{
		FString cmd;
		cmd.Format("save \"%s\"", Args->GetArg(FindArg("-ddtestsave") + 2));
		AddCommandString(cmd.GetChars());
		saveAt = -1;
	}
	if (quitAt >= 0 && Level->maptime >= quitAt) { quitAt = -1; AddCommandString("quit"); }
}

static int perfTics = 0, perfEnd = 0;
static bool perfStarted = false;
static std::chrono::steady_clock::time_point lastTic;
static std::vector<double> thinkMs, wallMs;

void DD_EncounterTestTick(FLevelLocals *Level)
{
	SaveQuitTick(Level);
	static int state = -1;
	if (state == -1)
	{
		const int at = FindArg("-ddenctest");
		state = at && at + 1 < Args->NumArgs() ? 0 : 3;
	}
	if (state >= 3) return;
	if (state == 0 && Level->maptime >= 45)
	{
		dfb_encounter_area a{};
		a.map_id = 187853213;
		a.dungeon_index = 1506;
		a.location_id = 50050;
		a.region_index = 17;
		a.world_x = 109.5f;
		a.world_y = 158.5f;
		a.dungeon_type = 2;
		a.area_level = atoi(Args->GetArg(FindArg("-ddenctest") + 1));
		FString type = "HumanStronghold";
		const int d = FindArg("-ddenctestdungeon");
		if (d && d + 2 < Args->NumArgs()) { a.dungeon_index = atoi(Args->GetArg(d + 1)); type = Args->GetArg(d + 2); }
		// Without a bridge the treadmill already put one stock leader (or a DRLA spawner's monster) on each marker; the test replaces them.
		int cleared = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (mo->ddRecordId || ((mo->flags3 & MF3_ISMONSTER) && !mo->player)) { mo->Destroy(); cleared++; }
		Printf("DDENCTEST level %d dungeonIndex %d type %s (cleared %d stock leaders)\n", a.area_level, a.dungeon_index, type.GetChars(), cleared);
		DD_MonstersTestEncounters(Level, a, "Privateer's Hold", "Daggerfall", type.GetChars());
		state = 1;
	}
	else if (state == 1 && Level->maptime >= 80)
	{
		int monsters = 0, stuck = 0, squeezed = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (!mo->ddRecordId || mo->health <= 0) continue;
			monsters++;
			if (P_TestMobjLocation(mo)) continue;
			// Squeezed in a gap: not stuck if a short step in some direction passes P_TryMove's rule (stock, or squeezing).
			bool free = false;
			for (int i = 0; i < 8 && !free; i++)
			{
				const DVector2 to = mo->Pos().XY() + DVector2(cos(i * M_PI / 4), sin(i * M_PI / 4)) * 4;
				FCheckPosition tm;
				free = P_CheckPosition(mo, to, tm);
				AActor *b = mo->BlockingMobj;
				if (!free && (!b || DD_IsDoorLeaf(b)) && DD_InGap(mo, to)) { DD_SqueezeActor = mo; free = P_CheckPosition(mo, to, tm); DD_SqueezeActor = nullptr; }
				free = free && tm.ceilingz - tm.floorz >= mo->Height && tm.floorz - mo->Z() <= mo->MaxStepHeight;
			}
			if (free) { squeezed++; continue; }
			stuck++;
			AActor *by = mo->BlockingMobj;
			Printf("DDENCTEST stuck %016" PRIx64 " %s at %.1f,%.1f,%.1f floor %.1f ceiling %.1f radius %.0f height %.0f blocked by %s%s\n", mo->ddRecordId,
				mo->GetClass()->TypeName.GetChars(), mo->X(), mo->Y(), mo->Z(), mo->floorz, mo->ceilingz, mo->radius, mo->Height,
				by ? by->GetClass()->TypeName.GetChars() : (mo->BlockingLine ? "a line" : "floor or ceiling"), by && by->ddRecordId ? " (a mook)" : "");
		}
		Printf("DDENCTEST after 1 s: %d placed monsters, %d stuck, %d overlapping but free to move\n", monsters, stuck, squeezed);
		const int perf = FindArg("-ddenctestperf");
		perfTics = perf && perf + 1 < Args->NumArgs() ? atoi(Args->GetArg(perf + 1)) : 0;
		if (perfTics > 0 && Level->PlayerInGame(consoleplayer) && Level->Players[consoleplayer]->mo)
		{
			player_t *pl = Level->Players[consoleplayer];
			pl->cheats |= CF_GODMODE;
			int woken = 0;
			auto wake = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = wake.Next())
				if (mo->ddRecordId && mo->health > 0 && mo->SeeState) { mo->target = pl->mo; mo->SetState(mo->SeeState); woken++; }
			Printf("DDENCTEST perf: woke %d monsters, measuring %d tics\n", woken, perfTics);
			perfEnd = Level->maptime + perfTics;
			state = 2;
			return;
		}
		Printf("DDENCTEST done\n");
		state = 3;
		AddCommandString("quit");
	}
	else if (state == 2)
	{
		// The think stat still holds the previous tic's playsim time (RunThinkers resets it when it starts).
		auto *stat = static_cast<FTextStat *>(FStat::FindStat("think"));
		double think = 0;
		int thinkers = 0;
		if (stat) sscanf(stat->GetStats().GetChars(), "Think time = %lf ms - %d", &think, &thinkers);
		const auto now = std::chrono::steady_clock::now();
		if (perfStarted) { thinkMs.push_back(think); wallMs.push_back(std::chrono::duration<double, std::milli>(now - lastTic).count()); }
		perfStarted = true;
		lastTic = now;
		if (Level->maptime < perfEnd) return;
		auto summary = [](std::vector<double> v, const char *what) {
			if (v.empty()) return;
			std::sort(v.begin(), v.end());
			double sum = 0;
			for (double x : v) sum += x;
			Printf("DDENCTEST perf %s ms: mean %.2f median %.2f p95 %.2f max %.2f over %d tics\n", what, sum / v.size(), v[v.size() / 2],
				v[std::min(v.size() - 1, v.size() * 95 / 100)], v.back(), int(v.size()));
		};
		summary(thinkMs, "think");
		summary(wallMs, "tic-to-tic (minimized window)");
		int alive = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next()) if (mo->ddRecordId && mo->health > 0) alive++;
		Printf("DDENCTEST perf: %d thinkers, %d placed monsters alive at the end\n", thinkers, alive);
		Printf("DDENCTEST done\n");
		state = 3;
		AddCommandString("quit");
	}
}
