// [Doomerfall] The label under the crosshair: a short name for what the player looks at, shown only for things close
// enough to interact with (owner, 2026-11-24). The target is chosen by Use's own rules (dd_items.cpp ItemInView,
// dd_info.cpp Pick, dd_treadmill.cpp TickTownDoors, Doom's use trace for converted action doors). Doom names monsters
// and Doom items itself; Daggerfall names NPCs, townspeople, piles and building doors through DFB_KIND_LOOK, once per
// target, and the answer is kept until the map changes. Daggerfall also names a Doom gun on the floor, by the same rule
// as its take (its lasting floor id, or the material it carries), so the label shows the material it will have once taken. The Doomerfall mod draws the label (zscript/DoomerfallLook.zs).
// Nothing here runs without a bridge session and a generated Daggerfall map.

#include <cstring>
#include <map>
#include <string>
#include <tuple>
#include <utility>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "actorinlines.h"
#include "d_player.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "p_linetracedata.h"
#include "p_local.h"
#include "playsim/dd_treadmill.h"
#include "printf.h"

AActor *DD_LookItem(player_t *player, bool &world, uint64_t &id, FString &name);
AActor *DD_InfoLookPick(player_t *player, double &distance, int &kind, uint64_t &id);
bool DD_LookGun(AActor *item, uint64_t &id, int &carried);

namespace
{
constexpr double NpcReach = 192.0;     // Daggerfall's 256-unit static and mobile NPC activation distance at the 75% world scale.
constexpr double MonsterReach = 96.0;  // Daggerfall's default 128-unit activation distance, as for items and doors.
constexpr int PileRefreshTics = 35;    // A pile's contents change when the player takes from it, so its label is asked again.
constexpr int UnknownGunTics = 4;      // A gun Daggerfall could not name yet (its art was on the way) is asked again soon.

using Key = std::pair<uint32_t, uint64_t>;
struct Entry { std::string text; bool known = false; int askedTic = -1000000; };

std::map<Key, Entry> labels;
std::map<uint32_t, Key> asked;          // request number -> target
using GunKey = std::tuple<FName, uint64_t, int>;	// pickup class, floor id, carried material
std::map<GunKey, Entry> guns;
std::map<uint32_t, GunKey> askedGuns;
std::string partial;
uint32_t nextRequest = 1;
FString labelMap;
std::string shown;

// Daggerfall's label for this target, or nothing while the answer is on its way.
std::string Ask(dfb_session *session, uint32_t target, uint64_t id, double worldX = 0, double worldZ = 0)
{
	Entry &entry = labels[Key(target, id)];
	if ((!entry.known || target == DFB_INFO_PILE) && gametic - entry.askedTic >= PileRefreshTics)
	{
		dfb_info_request r{};
		r.request = nextRequest++;
		r.target = target;
		r.id = id;
		r.world_x = worldX;
		r.world_z = worldZ;
		dfb_event e{};
		e.kind = DFB_KIND_LOOK;
		e.tic = gametic;
		memcpy(e.payload, &r, sizeof(r));
		dfb_send(session, &e);
		asked[r.request] = Key(target, id);
		entry.askedTic = gametic;
	}
	return entry.text;
}

// Daggerfall's inventory name for a Doom gun on the floor, or Doom's own name until it answers. Asked again while in
// view, like a pile: the roll uses the area level, and Daggerfall knows the name only once it has the class's art.
std::string AskGun(dfb_session *session, AActor *item, uint64_t id, int carried, const FString &doomName)
{
	const FName cls = item->GetClass()->TypeName;
	Entry &entry = guns[GunKey(cls, id, carried)];
	if (gametic - entry.askedTic >= (entry.known ? PileRefreshTics : UnknownGunTics))
	{
		dfb_info_text name{};
		name.request = nextRequest;
		strncpy(name.text, cls.GetChars(), sizeof(name.text) - 1);
		dfb_event e{};
		e.kind = DFB_KIND_INFO_NAME;
		e.tic = gametic;
		memcpy(e.payload, &name, sizeof(name));
		dfb_send(session, &e);
		dfb_info_request r{};
		r.request = nextRequest++;
		r.target = DFB_INFO_DOOM_GUN;
		r.id = id;
		r.world_x = carried;
		e = dfb_event{};
		e.kind = DFB_KIND_LOOK;
		e.tic = gametic;
		memcpy(e.payload, &r, sizeof(r));
		dfb_send(session, &e);
		askedGuns[r.request] = GunKey(cls, id, carried);
		entry.askedTic = gametic;
	}
	return entry.known ? entry.text : std::string(doomName.GetChars());
}

// A converted Daggerfall action door (door_objects.zs DFDoorBlocker) on Doom's use line, within the player's Use range.
// lockValue is its door's live lock value (door_objects.zs DFDoor.lockValue): 0 when not locked.
bool ActionDoorInReach(player_t *player, int &lockValue)
{
	static const FName blocker("DFDoorBlocker");
	AActor *pmo = player->mo;
	FLineTraceData trace;
	lockValue = 0;
	if (!P_LineTrace(pmo, pmo->Angles.Yaw, pmo->FloatVar(NAME_UseRange), pmo->Angles.Pitch, 0, player->viewz - pmo->Z(), 0, 0, &trace)) return false;
	if (trace.HitType != TRACE_HitActor || !trace.HitActor || trace.HitActor->GetClass()->TypeName != blocker) return false;
	if (AActor *door = trace.HitActor->PointerVar<AActor>("door")) lockValue = door->IntVar("lockValue");
	return true;
}

std::string Label(dfb_session *session)
{
	if (gamestate != GS_LEVEL || consoleplayer < 0 || !primaryLevel) return "";
	player_t *player = &players[consoleplayer];
	if (!player->mo || player->health <= 0 || player->camera != player->mo) return "";
	double x, y, z, yaw;
	if (DDTreadmill_PlayerWorld(x, y, z, yaw) == DD_AREA_NONE) return "";
	if (labelMap.CompareNoCase(primaryLevel->MapName) != 0)
	{
		labelMap = primaryLevel->MapName;
		labels.clear(); // Door indexes are per map; everything else is cheap to ask again.
		guns.clear();
	}

	bool world = false;
	uint64_t id = 0;
	FString name;
	if (AActor *item = DD_LookItem(player, world, id, name))
	{
		if (world) return Ask(session, DFB_INFO_PILE, id);
		int carried;
		return DD_LookGun(item, id, carried) ? AskGun(session, item, id, carried, name) : std::string(name.GetChars());
	}

	double distance;
	int kind;
	if (AActor *mo = DD_InfoLookPick(player, distance, kind, id))
	{
		if (kind == 3 && distance <= MonsterReach)
		{
			const char *tag = mo->GetTag(nullptr);
			return tag && *tag ? tag : "Monster";
		}
		if (kind != 3 && distance <= NpcReach) return Ask(session, kind == 1 ? DFB_INFO_NPC : DFB_INFO_TOWNSPERSON, id);
	}

	int doorKind, index;
	double doorX, doorY;
	if (DDTreadmill_DoorInReach(player->mo, doorKind, index, doorX, doorY))
		return doorKind == 0 ? Ask(session, DFB_INFO_BUILDING, uint64_t(index), doorX, doorY) : "Door";
	int lockValue;
	if (!ActionDoorInReach(player, lockValue)) return "";
	if (lockValue <= 0) return "Door";
	const std::string text = Ask(session, DFB_INFO_DOOR, uint64_t(lockValue)); // Daggerfall names the lock ("Locked.")
	return text.empty() ? "Door" : text;
}
}

// Once per tic from the bridge frame. The mod hears the label only when it changes.
void DD_LookFrame(dfb_session *session)
{
	static int lastTic = -1;
	if (!session || gametic == lastTic) return;
	lastTic = gametic;
	const std::string label = Label(session);
	if (label == shown) return;
	shown = label;
	Printf(PRINT_LOG, "look: \"%s\"\n", label.c_str());
	FString text;
	text.Format("dflook:%s", label.c_str());
	staticEventManager.Console(-1, text, 0, 0, 0, false, true);
}

// Daggerfall's answers to DFB_KIND_LOOK. True when the event was one.
bool DD_LookEvent(const dfb_event &e)
{
	if (e.kind != DFB_KIND_LOOK_TEXT) return false;
	dfb_info_text t;
	memcpy(&t, e.payload, sizeof(t));
	partial.append(t.text, strnlen(t.text, sizeof(t.text)));
	if (e.flags & DFB_INFO_MORE) return true;
	if (auto gun = askedGuns.find(t.request); gun != askedGuns.end())
	{
		// Empty while Daggerfall cannot name it yet: Doom's own name stays until the next answer.
		Entry &entry = guns[gun->second];
		entry.text = partial;
		entry.known = !partial.empty();
		askedGuns.erase(gun);
	}
	auto it = asked.find(t.request);
	if (it != asked.end())
	{
		Entry &entry = labels[it->second];
		entry.text = partial;
		entry.known = true;
		asked.erase(it);
	}
	partial.clear();
	return true;
}
