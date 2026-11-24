// [Doomerfall] Test only: runs the encounter planner and placer on the loaded map without Daggerfall, so a converted
// dungeon can be placed at any area level from the command line (tools/encounter_placer/placer_test.py):
//   uzdoom ... -ddenctest <areaLevel> [-ddenctestdungeon <index> <typeName>] +map MAP01
// 45 tics in (after DRLA's spawners have been claimed), it places the map's encounters with Privateer's Hold's facts (encounter card 4's paired run), checks
// them again a second later, and quits. p_tick.cpp calls DD_EncounterTestTick once per tic.

#include <cinttypes>
#include <cstdlib>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "c_dispatch.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "m_argv.h"
#include "p_local.h"
#include "printf.h"

void DD_MonstersTestEncounters(FLevelLocals *Level, const dfb_encounter_area &a, const char *location, const char *region, const char *type);

static int FindArg(const char *name)
{
	for (int i = 1; i < Args->NumArgs(); i++)
		if (!stricmp(Args->GetArg(i), name)) return i;
	return 0;
}

void DD_EncounterTestTick(FLevelLocals *Level)
{
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
		int monsters = 0, stuck = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (!mo->ddRecordId || mo->health <= 0) continue;
			monsters++;
			if (P_TestMobjLocation(mo)) continue;
			stuck++;
			AActor *by = mo->BlockingMobj;
			Printf("DDENCTEST stuck %016" PRIx64 " %s at %.1f,%.1f,%.1f floor %.1f ceiling %.1f radius %.0f height %.0f blocked by %s%s\n", mo->ddRecordId,
				mo->GetClass()->TypeName.GetChars(), mo->X(), mo->Y(), mo->Z(), mo->floorz, mo->ceilingz, mo->radius, mo->Height,
				by ? by->GetClass()->TypeName.GetChars() : (mo->BlockingLine ? "a line" : "floor or ceiling"), by && by->ddRecordId ? " (a mook)" : "");
		}
		Printf("DDENCTEST after 1 s: %d placed monsters, %d stuck\n", monsters, stuck);
		Printf("DDENCTEST done\n");
		state = 3;
		AddCommandString("quit");
	}
}
