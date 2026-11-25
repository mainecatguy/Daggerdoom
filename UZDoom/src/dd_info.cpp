// [Doomerfall] Doom's side of Daggerfall's Info interaction. The Info control names what the player looks at, and
// Daggerfall answers with the messages its own Info code showed, which Doom draws where Daggerfall's HUD draws them
// (zscript/Doomerfall.zs). As in Daggerfall, Info on anything else acts as Use, so Info on a building door names it and enters.
// Nothing here runs without a bridge session and a generated Daggerfall map.

#include <algorithm>
#include <cmath>
#include <cstring>
#include <string>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "actorinlines.h"
#include "d_player.h"
#include "events.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "p_linetracedata.h"
#include "p_local.h"
#include "p_spec.h"
#include "playsim/dd_treadmill.h"
#include "printf.h"
#include "sbar.h"
#include "texturemanager.h"
#include "v_font.h"

bool DD_ItemsInfoPress(player_t *player);
void DD_BridgeOpenTalk();
bool P_UseTraverse(AActor *usething, const DVector2 &start, const DVector2 &end, bool &foundline);

namespace
{
constexpr double InfoReach = 2304.0; // Daggerfall's 3072-unit activation ray at the 75% world scale.
constexpr double DoomPerDf = 0.75;
constexpr double AimSlack = 4.0;     // Billboards are thin, so the crosshair may pass a little beside one.

uint32_t nextRequest = 1, textRequest;
std::string pending;

bool IsNpc(const AActor *mo, bool &centered)
{
	static const FName town("DFNpc"), dungeon("DFDungeonNpc");
	const FName name = mo->GetClass()->TypeName;
	centered = name == dungeon;
	return (name == town || centered) && !(mo->renderflags & RF_INVISIBLE);
}

// A walking townsperson. Daggerfall's Info on one opens the talk window, which Doom does not route yet, so it only stops the ray.
bool IsTownsperson(const AActor *mo)
{
	static const FName walker("DFTownsperson");
	return mo->GetClass()->TypeName == walker && !(mo->renderflags & RF_INVISIBLE);
}

// Daggerfall's Info on doors, action doors, levers, ladders and shelves is the same as Grab. Doom's Use without its
// "oof", because Daggerfall's Info on a plain wall is silent.
void UseAsGrab(player_t *player)
{
	AActor *pmo = player->mo;
	const DVector2 start = pmo->GetPortalTransition(pmo->Height / 2).XY();
	const DVector2 end = start + pmo->Angles.Yaw.ToVector(pmo->FloatVar(NAME_UseRange));
	bool foundline = false;
	if (!P_UseTraverse(pmo, start, end, foundline))
	{
		sector_t *sec = pmo->Sector;
		if (sec->SecActTarget) sec->TriggerSectorActions(pmo, SECSPAC_Use | (foundline ? SECSPAC_UseWall : 0));
	}
	DDTreadmill_PressDoor();
}

// Daggerfall's HUD text (top, centered) or mid-screen text, for the Doomerfall mod to draw.
void Show(const std::string &text, bool mid)
{
	Printf(PRINT_LOG, "%s\n", text.c_str());
	FString name;
	name.Format("%s%s", mid ? "dfhud_mid:" : "dfhud_top:", text.c_str());
	staticEventManager.Console(-1, name, 0, 0, 0, false, true);
}

uint64_t NpcId(const AActor *mo) { return uint64_t(uint32_t(mo->args[1])) << 32 | uint32_t(mo->args[0]); }

// How far along the view ray it enters the actor's box, or a negative value on a miss. Doomerfall NPCs are billboards
// whose size is their picture's: a town NPC stands on its position, and a dungeon NPC is centered on it.
double RayHit(const DVector3 &eye, const DVector3 &dir, AActor *mo, bool npc, bool centered)
{
	double radius = mo->radius, bottom = mo->Z(), height = mo->Height;
	if (npc)
	{
		radius = 16;
		height = 56;
		if (mo->picnum.isValid())
			if (FGameTexture *tex = TexMan.GetGameTexture(mo->picnum))
			{
				radius = tex->GetDisplayWidth() * mo->Scale.X / 2;
				height = tex->GetDisplayHeight() * mo->Scale.Y;
			}
		if (centered) bottom -= height / 2;
	}
	radius += AimSlack;
	const double fx = eye.X - mo->X(), fy = eye.Y - mo->Y();
	const double a = dir.X * dir.X + dir.Y * dir.Y, b = 2 * (fx * dir.X + fy * dir.Y), c = fx * fx + fy * fy - radius * radius;
	double t0 = 0, t1 = InfoReach;
	if (a < 1e-9)
	{
		if (c > 0) return -1;
	}
	else
	{
		const double disc = b * b - 4 * a * c;
		if (disc < 0) return -1;
		const double root = sqrt(disc);
		t0 = std::max(0.0, (-b - root) / (2 * a));
		t1 = std::min(InfoReach, (-b + root) / (2 * a));
		if (t1 < t0) return -1;
	}
	// The part of the ray inside the circle must also pass between the box's bottom and top.
	const double z0 = eye.Z + dir.Z * t0, z1 = eye.Z + dir.Z * t1;
	if (std::max(z0, z1) < bottom || std::min(z0, z1) > bottom + height) return -1;
	if (z0 >= bottom && z0 <= bottom + height) return t0;
	return fabs(dir.Z) < 1e-9 ? -1 : ((dir.Z > 0 ? bottom : bottom + height) - eye.Z) / dir.Z;
}

void Send(dfb_session *session, uint16_t kind, const void *body, size_t size)
{
	dfb_event e{};
	e.kind = kind;
	e.tic = gametic;
	memcpy(e.payload, body, size);
	dfb_send(session, &e);
}

void SendRequest(dfb_session *session, uint32_t target, uint64_t id, double x, double z)
{
	dfb_info_request r{};
	r.request = nextRequest++;
	r.target = target;
	r.id = id;
	r.world_x = x;
	r.world_z = z;
	Send(session, DFB_KIND_INFO, &r, sizeof(r));
	textRequest = r.request;
	pending.clear();
}

// The NPC or living monster the view ray meets first, before a wall. wall and trace tell what the ray hit instead.
AActor *Pick(player_t *player, bool &bestNpc, double &bestDistance, bool &wall, FLineTraceData &trace)
{
	AActor *pmo = player->mo;
	const DAngle pitch = pmo->Angles.Pitch;
	const DVector3 dir(pitch.Cos() * pmo->Angles.Yaw.Cos(), pitch.Cos() * pmo->Angles.Yaw.Sin(), -pitch.Sin());
	const DVector3 eye(pmo->X(), pmo->Y(), player->viewz);
	wall = P_LineTrace(pmo, pmo->Angles.Yaw, InfoReach, pitch, TRF_THRUACTORS, player->viewz - pmo->Z(), 0, 0, &trace);

	AActor *best = nullptr;
	bestDistance = wall ? trace.Distance : InfoReach;
	bestNpc = false;
	TThinkerIterator<AActor> it(pmo->Level);
	while (AActor *mo = it.Next())
	{
		bool centered;
		const bool npc = IsNpc(mo, centered) || IsTownsperson(mo);
		if (!npc && (!(mo->flags3 & MF3_ISMONSTER) || mo->health <= 0 || mo == pmo)) continue;
		const double t = RayHit(eye, dir, mo, npc, centered);
		if (t >= 0 && t < bestDistance)
		{
			bestDistance = t;
			best = mo;
			bestNpc = npc;
		}
	}
	return best;
}

void Press(dfb_session *session, player_t *player)
{
	if (gamestate != GS_LEVEL || !player || !player->mo || player->health <= 0) return;
	double worldX, worldY, worldZ, yaw;
	const DDPlayerArea area = DDTreadmill_PlayerWorld(worldX, worldY, worldZ, yaw);
	if (area == DD_AREA_NONE) return; // Only a generated Daggerfall map has anything to describe.
	if (DD_ItemsInfoPress(player)) return;

	AActor *pmo = player->mo;
	bool bestNpc, wall;
	double bestDistance;
	FLineTraceData trace;
	AActor *best = Pick(player, bestNpc, bestDistance, wall, trace);
	if (best && IsTownsperson(best)) return;
	if (best && bestNpc)
	{
		SendRequest(session, DFB_INFO_NPC, NpcId(best), 0, 0);
		return;
	}
	if (best)
	{
		dfb_info_text name{};
		name.request = nextRequest;
		strncpy(name.text, best->GetTag(), sizeof(name.text) - 1);
		Send(session, DFB_KIND_INFO_NAME, &name, sizeof(name));
		SendRequest(session, DFB_INFO_MONSTER, 0, 0, 0);
		return;
	}
	// Outdoors, whatever the ray hit may be part of a building. Daggerfall decides from its footprints.
	if (wall && area == DD_AREA_EXTERIOR)
	{
		const DVector3 &hit = trace.HitLocation;
		SendRequest(session, DFB_INFO_BUILDING, 0, worldX + (hit.X - pmo->X()) / DoomPerDf, worldY + (hit.Y - pmo->Y()) / DoomPerDf);
	}
	// Daggerfall shows the building's name first, then a door enters it. Daggerfall reads the request before the door event.
	UseAsGrab(player);
}
}

// Use on an NPC: Daggerfall's Grab, or Steal while crouching, on the NPC the view ray meets first. Daggerfall checks
// the reach itself, so a far NPC gets its "too far away" message. True when the press went to an NPC, so a door
// behind it stays shut. Nothing happens without a bridge session on a generated Daggerfall map.
bool DD_InfoUseNpc(dfb_session *session, player_t *player, bool crouching)
{
	if (!session || gamestate != GS_LEVEL || !player || !player->mo || player->health <= 0) return false;
	double worldX, worldY, worldZ, yaw;
	if (DDTreadmill_PlayerWorld(worldX, worldY, worldZ, yaw) == DD_AREA_NONE) return false;
	bool npc, wall;
	double distance;
	FLineTraceData trace;
	AActor *best = Pick(player, npc, distance, wall, trace);
	if (!best || !npc) return false;
	dfb_npc_use use{};
	use.id = NpcId(best);
	use.request = nextRequest++;
	use.mode = crouching ? DFB_TAKE_STEAL : DFB_TAKE_GRAB;
	use.distance = distance / DoomPerDf;
	Send(session, DFB_KIND_NPC_USE, &use, sizeof(use));
	textRequest = use.request;
	pending.clear();
	return true;
}

// Use on a wall outdoors: Daggerfall's Info on the building it belongs to, which names the building and marks it on
// the town map. dd_treadmill calls this only for a press no door, item or NPC took, so doors work as before. Daggerfall
// decides from its footprints whether the wall is a building's.
void DD_InfoUseWall(dfb_session *session, player_t *player)
{
	if (!session || gamestate != GS_LEVEL || !player || !player->mo || player->health <= 0) return;
	double worldX, worldY, worldZ, yaw;
	if (DDTreadmill_PlayerWorld(worldX, worldY, worldZ, yaw) != DD_AREA_EXTERIOR) return;
	bool npc, wall;
	double distance;
	FLineTraceData trace;
	if (Pick(player, npc, distance, wall, trace) || !wall || trace.HitType != TRACE_HitWall) return;
	AActor *pmo = player->mo;
	const DVector3 &hit = trace.HitLocation;
	SendRequest(session, DFB_INFO_BUILDING, 0, worldX + (hit.X - pmo->X()) / DoomPerDf, worldY + (hit.Y - pmo->Y()) / DoomPerDf);
}

// True when the event belonged to Info or to Use on an NPC.
bool DD_InfoEvent(const dfb_event &e)
{
	if (e.kind == DFB_KIND_NPC_USE_RESULT)
	{
		dfb_npc_use_result r;
		memcpy(&r, e.payload, sizeof(r));
		if (r.status == DFB_NPC_USE_WINDOW && r.request == textRequest) DD_BridgeOpenTalk();
		return true;
	}
	if (e.kind != DFB_KIND_INFO_TEXT) return false;
	dfb_info_text t;
	memcpy(&t, e.payload, sizeof(t));
	if (t.request != textRequest) return true; // An answer to an older press.
	pending.append(t.text, strnlen(t.text, sizeof(t.text)));
	if (e.flags & DFB_INFO_MORE) return true;
	Show(pending, t.style == DFB_INFO_MID);
	pending.clear();
	return true;
}

// The Info control. True when the network event was Info's.
bool DD_InfoNetEvent(dfb_session *session, const char *name)
{
	if (strcmp(name, "df_info")) return false;
	if (session && consoleplayer >= 0) Press(session, &players[consoleplayer]);
	return true;
}
