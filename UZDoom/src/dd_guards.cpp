// [Doomerfall] Doom's side of city guards. Daggerfall spawns its guards as usual, keeps them inert, and sends
// DFB_KIND_GUARD_SPAWN for each. This puts a hostile UZDoom bot in a free player slot for each one: Doomguy's pawn
// with one random vanilla weapon (never the BFG), drawn with the Daggerfall guard's sprite (archive 399). The guard id
// lives in the pawn's ddRecordId, so dd_guards.h can tell guard bots apart; the bot code hunts players with them.
// A guard bot never respawns: its slot is freed and its body stays. All guard bots leave at a level change.
// Nothing here runs until Daggerfall sends a guard.

#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "b_bot.h"
#include "d_netinf.h"
#include "d_player.h"
#include "dd_guards.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "m_random.h"
#include "p_local.h"
#include "p_maputl.h"
#include "printf.h"
#include "r_data/r_translate.h"
#include "texturemanager.h"

bool DD_MobileSprite(AActor *mo, int archive, int base, double facing, AActor *camera);
void P_UnPredictClient();

static FRandom pr_ddguard("DDGuard");

namespace
{
constexpr int GuardArchive = 399;	// Knight_CityWatch's texture
constexpr int MoveRecords = 0, AttackRecords = 5, HurtRecords = 10, IdleRecord = 15;
constexpr double Spread = 40;

struct Pending { uint64_t id; uint32_t context; int32_t target; DVector2 pos; int index; };
struct Arm { const char *weapon, *ammo; int amount; };

// Vanilla Doom's weapons except the BFG and the fist, with enough ammo to keep firing.
const Arm Arms[] = {
	{ "Pistol", "Clip", 200 }, { "Shotgun", "Shell", 50 }, { "SuperShotgun", "Shell", 50 }, { "Chaingun", "Clip", 300 },
	{ "RocketLauncher", "RocketAmmo", 40 }, { "PlasmaRifle", "Cell", 300 }, { "Chainsaw", nullptr, 0 },
};

std::vector<Pending> pending;
uint32_t currentContext;
int32_t currentTarget = -1;
bool spaceValid;

void Arm(AActor *mo, const struct Arm &arm)
{
	player_t *p = mo->player;
	std::vector<AActor *> drop;
	for (AActor *item = mo->Inventory; item; item = item->Inventory)
		if (item->IsKindOf(NAME_Weapon)) drop.push_back(item);
	p->ReadyWeapon = nullptr;
	p->PendingWeapon = (AActor *)WP_NOCHANGE;
	for (AActor *item : drop) item->Destroy();
	PClassActor *weaponClass = PClass::FindActor(arm.weapon);
	AActor *weapon = weaponClass ? mo->GiveInventoryType(weaponClass) : nullptr;
	if (arm.ammo)
		if (PClassActor *ammoClass = PClass::FindActor(arm.ammo))
		{
			AActor *ammo = mo->FindInventory(ammoClass);
			if (!ammo) ammo = mo->GiveInventoryType(ammoClass);
			if (ammo) ammo->IntVar(NAME_Amount) = arm.amount;
		}
	if (weapon) p->PendingWeapon = weapon;
}

// Whether a pawn could walk straight from `from` to `to`: no one-sided or blocking line, and every opening on the way
// tall enough and within a step. Without this a spot past the door line (a closed door or the void) can pass.
bool Reachable(FLevelLocals *Level, AActor *mo, const DVector2 &from, const DVector2 &to)
{
	sector_t *start = Level->PointInSector(from);
	const double floor = start->floorplane.ZatPoint(from);
	FPathTraverse it(Level, from.X, from.Y, to.X, to.Y, PT_ADDLINES);
	while (intercept_t *in = it.Next())
	{
		const line_t *ld = in->d.line;
		if (!ld->backsector || (ld->flags & (ML_BLOCKING | ML_BLOCK_PLAYERS | ML_BLOCKEVERYTHING))) return false;
		FLineOpening open;
		P_LineOpening(open, mo, ld, it.InterceptPoint(in));
		if (open.range < mo->Height || open.bottom - floor > mo->MaxStepHeight || open.top - floor < mo->Height) return false;
	}
	return true;
}

// A free spot near the requested one that does not overlap a wall, a guard, or the player, and that a guard could
// walk to from the requested one.
void Settle(AActor *mo, const DVector2 &at, int index)
{
	static const DVector2 rings[] = { {0, 0}, {1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {-1, -1}, {1, -1}, {-1, 1}, {2, 0}, {-2, 0}, {0, 2}, {0, -2} };
	const int n = int(sizeof(rings) / sizeof(rings[0]));
	auto place = [mo](const DVector2 &to) {
		mo->SetOrigin(DVector3(to, mo->Z()), false);
		P_FindFloorCeiling(mo, FFCF_ONLYSPAWNPOS);
		mo->SetZ(mo->floorz);
	};
	bool placed = false;
	for (int i = 0; i < n && !placed; i++)
	{
		const DVector2 to = at + rings[(i + index) % n] * Spread;
		place(to);
		bool crowded = false;
		for (int k = 0; k < MAXPLAYERS && !crowded; k++)
			if (playeringame[k] && players[k].mo && players[k].mo != mo && (players[k].mo->Pos().XY() - to).Length() < mo->radius * 2) crowded = true;
		placed = !crowded && P_TestMobjLocation(mo) && Reachable(mo->Level, mo, at, to);
	}
	if (!placed) place(at);	// Overlapping inside the room beats standing outside it.
	mo->ClearInterpolation();
}

void Spawn(FLevelLocals *Level, const Pending &g)
{
	int slot = -1;
	for (int i = 0; i < MAXPLAYERS; i++)
		if (!playeringame[i]) { slot = i; break; }
	if (slot < 0) { Printf("DDGUARD no free player slot for %016" PRIx64 "\n", g.id); return; }

	static const char info[] = "\\name\\Guard\\autoaim\\0\\skin\\base";
	TArrayView<uint8_t> stream((uint8_t *)info, uint32_t(sizeof(info)));
	D_ReadUserInfoStrings(slot, stream, false);
	player_t &p = players[slot];
	// Like FCajunMaster::DoAddBot, except that it leaves multiplayer off and spawns here instead of at a start.
	p.Bot = Level->CreateThinker<DBot>();
	p.Bot->player = &p;
	p.Bot->skill = { 85, 70, 85, 60 };	// aiming, perfection, reaction, self-preservation, out of 100
	playeringame[slot] = true;
	p.mo = nullptr;
	p.playerstate = PST_ENTER;
	// A plain Doom pawn, not the human's class: a DRLA class pawn aims and holds fire with a vanilla weapon but never
	// shoots. SpawnPlayer keeps a class that is already set.
	if (PClassActor *doomPlayer = PClass::FindActor("DoomPlayer"); doomPlayer && doomPlayer->IsDescendantOf(NAME_PlayerPawn))
		p.cls = doomPlayer;
	FPlayerStart start;
	start.pos = DVector3(g.pos, 0);
	start.angle = 0;
	start.type = int16_t(slot + 1);
	AActor *mo = Level->SpawnPlayer(&start, slot);
	if (!mo) { Level->BotInfo.ClearPlayer(slot, false); Printf("DDGUARD could not spawn %016" PRIx64 "\n", g.id); return; }
	mo->ddRecordId = g.id;
	mo->flags &= ~MF_FRIENDLY;	// Players are teammates only while both are friendly, so the player can hurt guards and they the player.
	mo->Translation = NO_TRANSLATION;
	Settle(mo, g.pos, g.index);
	if (AActor *pmo = Level->Players[consoleplayer]->mo) mo->Angles.Yaw = mo->AngleTo(pmo);
	Level->localEventManager->PlayerEntered(slot, false);
	const struct Arm &arm = Arms[pr_ddguard() % (sizeof(Arms) / sizeof(Arms[0]))];
	Arm(mo, arm);
	DD_MobileSprite(mo, GuardArchive, MoveRecords, mo->Angles.Yaw.Degrees(), Level->Players[consoleplayer]->camera);
	Printf("DDGUARD spawned %016" PRIx64 " in slot %d with %s at %.1f,%.1f\n", g.id, slot, arm.weapon, mo->X(), mo->Y());
}

int RecordsFor(AActor *mo)
{
	// The player pawn's attack states are one state each, and its pain is two.
	FState *s = mo->state, *pain = mo->FindState(NAME_Pain);
	if (s && (s == mo->FindState(NAME_Missile) || s == mo->FindState(NAME_Melee))) return AttackRecords;
	if (s && pain && (s == pain || s == pain->NextState)) return HurtRecords;
	return mo->Vel.XY().LengthSquared() > 0.25 ? MoveRecords : IdleRecord;
}

// A dead guard keeps its body, drawn with Daggerfall's guard corpse, and gives its slot back.
void Bury(FLevelLocals *Level, int slot)
{
	AActor *body = players[slot].mo;
	FTextureID corpse = TexMan.CheckForTexture("dfmesh/a380r01.png", ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup);
	if (corpse.isValid()) { body->picnum = corpse; body->renderflags &= ~RF_XFLIP; }
	// Nothing may keep pointing at the slot once it is reset, or its next think reads a player with no pawn.
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
		if (mo->player == &players[slot]) mo->player = nullptr;
	players[slot].mo = nullptr;
	players[slot].camera = nullptr;
	Printf("DDGUARD buried slot %d\n", slot);
	Level->BotInfo.ClearPlayer(slot, false);
}
}

bool DD_GuardsEvent(const dfb_event &e)
{
	if (e.kind != DFB_KIND_GUARD_SPAWN) return false;
	dfb_guard_spawn g;
	memcpy(&g, e.payload, sizeof(g));
	pending.push_back({ g.id, g.context, g.target, DVector2(g.x, g.y), g.index });
	return true;
}

void DD_GuardsFrame(dfb_session *, uint32_t context, bool inSpace, int32_t target)
{
	currentContext = context;
	spaceValid = inSpace;
	currentTarget = inSpace ? target : -1;
	if (gamestate != GS_LEVEL || !primaryLevel) return;
	FLevelLocals *Level = primaryLevel;
	// This runs between tics, while UZDoom's client prediction is active: anything spawned now would be destroyed when
	// the prediction rolls back, and the rollback restores the player from its snapshot. End the prediction first, as
	// the save code does. The next tic predicts again.
	bool dead = false;
	for (int i = 0; i < MAXPLAYERS && !dead; i++)
		dead = playeringame[i] && players[i].Bot && DD_IsGuardBot(players[i].mo) && players[i].mo->health <= 0;
	if (!pending.empty() || dead) P_UnPredictClient();
	for (const Pending &g : pending)
	{
		if (g.context != DFB_WORLD_INTERIOR || !spaceValid || g.context != currentContext || g.target != currentTarget)
		{
			Printf("DDGUARD dropped %016" PRIx64 ": it is for context %u target %d, Doom is in %u target %d\n", g.id, g.context, g.target, currentContext, currentTarget);
			continue;
		}
		Spawn(Level, g);
	}
	pending.clear();

	AActor *camera = Level->Players[consoleplayer]->camera;
	for (int i = 0; i < MAXPLAYERS; i++)
	{
		if (!playeringame[i] || !players[i].Bot || !DD_IsGuardBot(players[i].mo)) continue;
		AActor *mo = players[i].mo;
		if (mo->health <= 0) { Bury(Level, i); continue; }
		if (!DD_MobileSprite(mo, GuardArchive, RecordsFor(mo), mo->Angles.Yaw.Degrees(), camera))
			DD_MobileSprite(mo, GuardArchive, MoveRecords, mo->Angles.Yaw.Degrees(), camera);
	}
}

void DD_GuardDied(dfb_session *session, AActor *mo)
{
	if ((mo->ddRecordId >> 61) != DFB_GUARD_TAG) return;
	const dfb_guard_death death{ mo->ddRecordId };
	dfb_event e{};
	e.kind = DFB_KIND_GUARD_DEATH;
	e.tic = gametic;
	memcpy(e.payload, &death, sizeof(death));
	dfb_send(session, &e);
	Printf("DDGUARD died %016" PRIx64 "\n", death.id);
}

// FCajunMaster::End, before a level change: guard bots belong to the place they were spawned in.
void DD_GuardsLeaveLevel(FCajunMaster &bots)
{
	pending.clear();
	for (int i = 0; i < MAXPLAYERS; i++)
		if (playeringame[i] && players[i].Bot && DD_IsGuardBot(players[i].mo))
		{
			Printf("DDGUARD removed slot %d at a level change\n", i);
			bots.ClearPlayer(i, false);
		}
}
