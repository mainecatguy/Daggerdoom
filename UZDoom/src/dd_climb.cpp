// [Doomerfall] Engine half of climbing. The climb itself is ZScript (mods/doomerfall/src/zscript/DoomerfallClimb.zs).
// In:  Daggerfall's character sheet (DFB_SHEET_CLIMB_*), and the mod's "dfc_uses:<n>" network events.
// Out: "dfi_climb:<start>:<grasp>:<continue>:<regain>:<enhanced>" network events to the mod whenever those values change
//      ("dfi_climb:none" without a valid character), and DFB_KIND_CLIMB_USES events to Daggerfall.
// Nothing here runs without a bridge session, and the mod climbs only on a generated Daggerfall map.

#include <cstdlib>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "printf.h"
#include "zstring.h"

const int32_t *DD_BridgeSheet();

namespace
{
FString lastSent;
FString pending;
}

void DD_ClimbFrame(dfb_session *session)
{
	if (!session) return;
	const int32_t *sheet = DD_BridgeSheet();
	FString text = "dfi_climb:none";
	if (sheet)
	{
		const int32_t *c = sheet + DFB_SHEET_CLIMB_CHANCE;
		text.Format("dfi_climb:%d:%d:%d:%d:%d", c[DFB_CLIMB_START], c[DFB_CLIMB_GRASP], c[DFB_CLIMB_CONTINUE], c[DFB_CLIMB_REGAIN],
			sheet[DFB_SHEET_CLIMB_ENHANCED]);
	}
	if (text.Compare(lastSent) != 0)
	{
		lastSent = text;
		pending = text;
	}
	if (pending.IsEmpty() || gamestate != GS_LEVEL || !primaryLevel) return;
	if (primaryLevel->localEventManager->SendNetworkEvent(pending, 0, 0, 0, false))
	{
		Printf(PRINT_NONOTIFY, "[climb] sent %s\n", pending.GetChars());
		pending = "";
	}
}

// From DD_BridgeItemNetEvent. True for the climb mod's own events.
bool DD_ClimbNetEvent(dfb_session *session, const char *name)
{
	if (strncmp(name, "dfc_uses:", 9)) return false;
	const unsigned long uses = strtoul(name + 9, nullptr, 10);
	if (uses == 0 || uses > 1000) return true;
	dfb_event e{};
	e.kind = DFB_KIND_CLIMB_USES;
	e.tic = gametic;
	dfb_climb_uses body{};
	body.uses = uint32_t(uses);
	memcpy(e.payload, &body, sizeof(body));
	const int rc = dfb_send(session, &e);
	Printf(PRINT_NONOTIFY, "[climb] sent %lu Climbing uses (%d)\n", uses, rc);
	return true;
}
