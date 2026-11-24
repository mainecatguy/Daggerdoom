// [Doomerfall] Doom's side of world items. Daggerfall lists the piles and furniture containers in the current
// space and opens its own window for each one. This file passes the list to ZScript and passes Use back.
// Nothing here runs without a bridge session.

#include <algorithm>
#include <cinttypes>
#include <cstdlib>
#include <cstring>
#include <deque>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "actorinlines.h"
#include "d_player.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "info.h"
#include "p_linetracedata.h"
#include "p_local.h"
#include "printf.h"

bool DD_BridgeHasSession();
void DD_BridgeOpenLoot();
bool DD_InfoUseNpc(dfb_session *session, player_t *player, bool crouching);
bool DD_PickupNeedsUse(AActor *special);

namespace
{
constexpr int MaxEventsPerFrame = 16; // Keeps a long list from overflowing one tic's network buffer.
constexpr double UseReach = 96.0;     // Daggerfall's 128-unit treasure reach at the 75% world scale.
constexpr double MinAim = 0.90;       // About 25 degrees around the crosshair.
constexpr double FloorDrop = 64.0;    // How far below the eye an item in front of the player still counts.

std::deque<FString> outgoing;
uint32_t acceptedGeneration, nextRequest = 1, currentContext;
int32_t currentTarget = -1;
bool spaceValid, wantList, useRules;
dfb_session *itemSession;
uint64_t refusedPile; // A pile Daggerfall just refused must not keep a door behind it from opening.

// Only health and ammo pick up by touch. DRLA's versions are CustomInventory, and DRLA also uses Ammo
// classes as hidden tokens, so its pickups are named here. Each name covers its subclasses.
bool PicksUpByTouch(const PClass *cls)
{
	static const FName names[] = {
		"Health", "HealthPickup", "Ammo", "Megasphere",
		"RLHealthBonus", "RLStimpack", "RLMedikit", "RLAaaghSphere", "RLMarathonStimpack", "RLMarathonMedikit", "RLDuke2AtomicHealth",
		"RLClip", "RLClipBox", "RLShell", "RLShellBox", "RLRocketAmmo", "RLRocketBox", "RLCell", "RLCellPack",
	};
	for (; cls; cls = cls->ParentClass)
		for (const FName &name : names)
			if (cls->TypeName == name) return true;
	return false;
}

bool IsWorldPile(AActor *mo)
{
	static const FName pile("DoomerfallWorldItem");
	return mo->GetClass()->TypeName == pile;
}

bool IsWorldContainer(AActor *mo)
{
	static const FName container("DoomerfallWorldContainer");
	return mo->GetClass()->TypeName == container;
}

// How far the view ray travels before entering a container's box, or a negative value when it misses within reach.
double BoxHit(const DVector3 &from, const DVector3 &dir, AActor *box)
{
	static const FName names[6] = { "dfMinX", "dfMinY", "dfMinZ", "dfMaxX", "dfMaxY", "dfMaxZ" };
	const double origin[3] = { from.X, from.Y, from.Z }, step[3] = { dir.X, dir.Y, dir.Z };
	double enter = 0, leave = UseReach;
	for (int a = 0; a < 3; a++)
	{
		const double lo = box->FloatVar(names[a]), hi = box->FloatVar(names[a + 3]);
		if (fabs(step[a]) < 1e-9)
		{
			if (origin[a] < lo || origin[a] > hi) return -1;
			continue;
		}
		double t1 = (lo - origin[a]) / step[a], t2 = (hi - origin[a]) / step[a];
		if (t1 > t2) std::swap(t1, t2);
		enter = std::max(enter, t1);
		leave = std::min(leave, t2);
		if (enter > leave) return -1;
	}
	return enter;
}

// The nearest furniture container on the view ray pitched down by `lower`, and its distance. A wall in front of it hides it.
AActor *ContainerOnRay(AActor *pmo, player_t *player, DAngle lower, double &distance)
{
	const DAngle pitch = std::min(pmo->Angles.Pitch + lower, DAngle::fromDeg(89.));
	const DVector3 dir(pitch.Cos() * pmo->Angles.Yaw.Cos(), pitch.Cos() * pmo->Angles.Yaw.Sin(), -pitch.Sin());
	const DVector3 eye(pmo->X(), pmo->Y(), player->viewz);
	AActor *best = nullptr;
	distance = HUGE_VAL;
	TThinkerIterator<AActor> it(pmo->Level);
	while (AActor *mo = it.Next())
	{
		if (!IsWorldContainer(mo)) continue;
		const double t = BoxHit(eye, dir, mo);
		if (t >= 0 && t < distance)
		{
			distance = t;
			best = mo;
		}
	}
	if (!best) return nullptr;
	// The converted furniture is often solid itself, so the trace may stop at the box's own face.
	FLineTraceData trace;
	if (P_LineTrace(pmo, pmo->Angles.Yaw, distance, pitch, TRF_THRUACTORS, player->viewz - pmo->Z(), 0, 0, &trace) && trace.Distance < distance - 8) return nullptr;
	return best;
}

// How well the player is aiming at an item, or a negative infinity when it is out of reach.
double AimScore(AActor *pmo, player_t *player, AActor *item)
{
	const double targetZ = IsWorldPile(item) ? 0 : item->Height / 2;
	DVector3 to = pmo->Vec3To(item);
	to.Z += targetZ - player->viewheight;
	const double distance = to.Length();
	if (distance > UseReach) return -HUGE_VAL;
	const double pitchCos = pmo->Angles.Pitch.Cos(), yawCos = pmo->Angles.Yaw.Cos(), yawSin = pmo->Angles.Yaw.Sin();
	const DVector3 aim(pitchCos * yawCos, pitchCos * yawSin, -pmo->Angles.Pitch.Sin());
	const double facing = distance > 1 ? (to | aim) / distance : 1;
	if (facing > MinAim) return facing;
	// Doom players rarely look down, so an item on the floor ahead counts, at a lower priority than one under the crosshair.
	const double flat = to.XY().Length();
	if (flat <= pmo->radius + item->radius && fabs(to.Z) <= player->viewheight + item->Height) return -1;
	const double flatFacing = flat > 1 ? (to.X * yawCos + to.Y * yawSin) / flat : 1;
	return to.Z < 0 && -to.Z <= FloorDrop && flatFacing > MinAim ? flatFacing - 1 : -HUGE_VAL;
}

// The pile, container, or (with `doomItems`) Doom pickup that Use would take, or null.
AActor *ItemInView(player_t *player, bool doomItems)
{
	AActor *pmo = player->mo, *best = nullptr;
	double bestScore = -HUGE_VAL;
	TThinkerIterator<AActor> it(pmo->Level);
	while (AActor *mo = it.Next())
	{
		const bool pile = IsWorldPile(mo);
		if (!pile && (!doomItems || !(mo->flags & MF_SPECIAL) || !DD_PickupNeedsUse(mo))) continue;
		const double score = AimScore(pmo, player, mo);
		if (score > bestScore && P_CheckSight(pmo, mo, SF_IGNOREVISIBILITY))
		{
			bestScore = score;
			best = mo;
		}
	}
	// Furniture under the crosshair wins over an item that only counts because it lies on the floor ahead. Doom players
	// rarely look down, so a low chest also counts a little below the crosshair when nothing else is there.
	double boxDistance;
	if (bestScore <= 0)
		if (AActor *box = ContainerOnRay(pmo, player, nullAngle, boxDistance)) best = box;
	if (!best)
		best = ContainerOnRay(pmo, player, DAngle::fromDeg(20.), boxDistance);
	return best;
}

void SendTake(uint64_t id, uint32_t mode)
{
	dfb_item_take take{};
	take.id = id;
	take.request = nextRequest++;
	take.mode = mode;
	dfb_event e{};
	e.kind = DFB_KIND_ITEM_TAKE;
	e.tic = gametic;
	memcpy(e.payload, &take, sizeof(take));
	dfb_send(itemSession, &e);
}

void SendRequest(dfb_session *session)
{
	dfb_event e{};
	e.kind = DFB_KIND_ITEMS_REQUEST;
	e.tic = gametic;
	const dfb_world_items body{ 0, currentContext, currentTarget, 0 };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

void ShowResult(const dfb_item_result &r)
{
	char name[sizeof(r.name) + 1] = {};
	memcpy(name, r.name, sizeof(r.name));
	switch (r.status)
	{
	case DFB_ITEM_TAKEN:
		if (r.taken > 1) Printf(PRINT_HIGH, "You take %s and more (%d).\n", name, r.taken);
		else Printf(PRINT_HIGH, "You take %s.\n", name);
		break;
	case DFB_ITEM_PARTIAL:
		Printf(PRINT_HIGH, "You take what you can carry (%d). %d left.\n", r.taken, r.remaining);
		break;
	case DFB_ITEM_TOO_HEAVY:
		Printf(PRINT_HIGH, "You cannot carry any more.\n");
		break;
	case DFB_ITEM_GONE:
		Printf(PRINT_HIGH, "There is nothing there.\n");
		break;
	default:
		Printf(PRINT_HIGH, "You cannot take that now.\n");
		break;
	}
}
}

// True when the event belonged to world items.
bool DD_ItemsEvent(const dfb_event &e)
{
	switch (e.kind)
	{
	case DFB_KIND_ITEMS_BEGIN:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		// A list for a place Doom has already left is stale.
		acceptedGeneration = spaceValid && b.context == currentContext && b.target == currentTarget ? b.generation : 0;
		return true;
	}
	case DFB_KIND_ITEM:
	{
		dfb_world_item i;
		memcpy(&i, e.payload, sizeof(i));
		if (acceptedGeneration && i.generation == acceptedGeneration)
			outgoing.push_back(FStringf("dfi_item:%u:%016" PRIx64 ":%d:%d:%d:%.3f:%.3f:%.3f:%.3f:%.3f", i.generation, i.id, i.archive, i.record, i.item_count, i.x, i.y, i.z, i.width, i.height));
		return true;
	}
	case DFB_KIND_CONTAINER:
	{
		dfb_world_container c;
		memcpy(&c, e.payload, sizeof(c));
		if (acceptedGeneration && c.generation == acceptedGeneration)
			outgoing.push_back(FStringf("dfi_box:%u:%016" PRIx64 ":%.3f:%.3f:%.3f:%.3f:%.3f:%.3f", c.generation, c.id, c.min_x, c.min_y, c.min_z, c.max_x, c.max_y, c.max_z));
		return true;
	}
	case DFB_KIND_ITEMS_END:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		if (acceptedGeneration && b.generation == acceptedGeneration)
			outgoing.push_back(FStringf("dfi_end:%u:%u", b.generation, b.count));
		return true;
	}
	case DFB_KIND_ITEM_RESULT:
	{
		dfb_item_result r;
		memcpy(&r, e.payload, sizeof(r));
		refusedPile = r.status == DFB_ITEM_TOO_HEAVY || r.status == DFB_ITEM_REFUSED ? r.id : 0;
		if (r.status == DFB_ITEM_WINDOW) DD_BridgeOpenLoot();
		else ShowResult(r);
		return true;
	}
	default:
		return false;
	}
}

// Runs each frame, after Doom has published where the player is.
void DD_ItemsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target)
{
	itemSession = session;
	useRules = context != DFB_WORLD_NONE; // Only a generated Daggerfall map changes how pickups work.
	if (context != currentContext || inSpace != spaceValid || (inSpace && target != currentTarget))
	{
		currentContext = context;
		spaceValid = inSpace;
		currentTarget = inSpace ? target : -1;
		acceptedGeneration = 0;
		outgoing.clear();
		outgoing.push_back("dfi_clear");
		// Tells the Doomerfall mod whether Daggerfall's rules apply here, so it shows Sneaking only on a Daggerfall map.
		outgoing.push_back(useRules ? "dfi_rules:1" : "dfi_rules:0");
		wantList = inSpace;
	}
	if (wantList && gamestate == GS_LEVEL)
	{
		wantList = false;
		SendRequest(session);
	}
	if (gamestate != GS_LEVEL || !primaryLevel) return;
	for (int i = 0; i < MaxEventsPerFrame && !outgoing.empty(); i++)
	{
		if (!primaryLevel->localEventManager->SendNetworkEvent(outgoing.front(), 0, 0, 0, false)) break;
		outgoing.pop_front();
	}
}

// After a load, Doom's restored actors may not match Daggerfall until a fresh list arrives.
void DD_ItemsResync()
{
	wantList = spaceValid;
}

// True when this item must wait for the Use button. False for everything outside a generated map.
bool DD_PickupNeedsUse(AActor *special)
{
	if (!useRules || !DD_BridgeHasSession() || !special->IsKindOf(NAME_Inventory)) return false;
	// An invisible helper cannot be aimed at, so it keeps working by touch.
	static const int noSprite = GetSpriteIndex("TNT1");
	if (special->sprite == noSprite || (special->renderflags & RF_INVISIBLE)) return false;
	return !PicksUpByTouch(special->GetClass());
}

// One press of Use. Takes the item in view and returns true when that press is spent, so a door behind it stays shut.
// The town door check and Doom's own use check both ask during one tic, and only the first acts.
bool DD_UsePress(player_t *player)
{
	static int lastTic = -1;
	static bool lastResult;
	if (!useRules || !DD_BridgeHasSession() || !player || !player->mo || player->health <= 0) return false;
	if (lastTic == gametic) return lastResult;
	lastTic = gametic;
	lastResult = false;

	AActor *pmo = player->mo, *best = ItemInView(player, true);
	const bool crouching = (player->cmd.buttons & BT_CROUCH) || player->crouchfactor < 1;
	if (!best) return lastResult = DD_InfoUseNpc(itemSession, player, crouching);

	if (IsWorldPile(best) || IsWorldContainer(best))
	{
		const uint64_t id = strtoull(best->StringVar(FName("dfId")).GetChars(), nullptr, 16);
		SendTake(id, crouching ? DFB_TAKE_STEAL : DFB_TAKE_GRAB);
		lastResult = id != refusedPile;
		return lastResult;
	}
	best->CallTouch(pmo);
	// A refused pickup, such as a weapon the player already holds, stays in the world and leaves the press for a door.
	lastResult = (best->ObjectFlags & OF_EuthanizeMe) || !(best->flags & MF_SPECIAL);
	return lastResult;
}

// Daggerfall's Info on a pile or container is the same as Grab (PlayerActivate.ActivateLootContainer), so the Info
// control opens the same window as Use. True when a pile or container was in view.
bool DD_ItemsInfoPress(player_t *player)
{
	if (!useRules || !DD_BridgeHasSession() || !player || !player->mo || player->health <= 0) return false;
	AActor *best = ItemInView(player, false);
	if (!best) return false;
	SendTake(strtoull(best->StringVar(FName("dfId")).GetChars(), nullptr, 16), DFB_TAKE_GRAB);
	return true;
}

// The Interact control is the same action as Use, without Doom's door use.
bool DD_ItemsNetEvent(dfb_session *session, const char *name)
{
	if (strcmp(name, "df_interact")) return false;
	if (session && consoleplayer >= 0) DD_UsePress(&players[consoleplayer]);
	return true;
}
