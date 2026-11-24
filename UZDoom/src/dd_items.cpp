// [Doomerfall] Doom's side of world items. Daggerfall lists the piles in the current space and performs
// each pickup. This file passes the list to ZScript and passes Interact back. Nothing here runs
// without a bridge session.

#include <cinttypes>
#include <cstdlib>
#include <cstring>
#include <deque>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "bitmap.h"
#include "r_state.h"
#include "s_sound.h"
#include "texturemanager.h"
#include "actorinlines.h"
#include "d_player.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "info.h"
#include "p_local.h"
#include "printf.h"

bool DD_BridgeHasSession();

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

// Doom items held by Daggerfall. A Use press asks Daggerfall, and the actor waits on the floor for the answer.
struct PendingTake
{
	uint32_t request;
	FName cls;
	DVector3 pos;
	int tic;
};
constexpr int PendingTics = 5 * TICRATE; // An unanswered request stops blocking presses after this.
std::deque<PendingTake> pendingTakes;
std::deque<FString> doomOutgoing; // Answers that must act inside the playsim, sent as network events.
uint32_t nextDoomRequest = 1;
TMap<FName, FTextureID> seenArt; // The sprite each class showed when the player took it.

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

// Guns stay usable in Doom when Daggerfall takes them, until the weapon hotkey task gives Doom only the active gun.
bool IsGun(const PClass *cls)
{
	static const FName weapon("Weapon"), drlaPickup("RLBaseWeaponPickup");
	for (; cls; cls = cls->ParentClass)
		if (cls->TypeName == weapon || cls->TypeName == drlaPickup) return true;
	return false;
}

void SendDoomItem(uint16_t kind, uint32_t request, uint32_t status, const char *cls)
{
	if (!itemSession) return;
	dfb_doom_item body{};
	body.request = request;
	body.status = status;
	strncpy(body.cls, cls, sizeof(body.cls) - 1);
	dfb_event e{};
	e.kind = kind;
	e.tic = gametic;
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(itemSession, &e);
}

FString ClassOf(const dfb_doom_item &d)
{
	char cls[sizeof(d.cls) + 1] = {};
	memcpy(cls, d.cls, sizeof(d.cls));
	return cls;
}

FTextureID FrameTexture(int sprite, int frame)
{
	if (sprite <= SPR_NOCHANGE || (unsigned)sprite >= sprites.Size()) return FNullTextureID();
	bool mirror;
	return sprites[sprite].GetSpriteFrame(frame, 0, nullAngle, &mirror);
}

// The floor sprite of a class: the one the player saw, else the first drawn frame of its spawn states, else its inventory icon.
FTextureID ArtFor(PClassActor *cls)
{
	if (FTextureID *seen = seenArt.CheckKey(cls->TypeName)) return *seen;
	FName labels[] = { NAME_Spawn, FName("SpawnFrame") };
	for (FName label : labels)
	{
		FState *st = cls->FindState(1, &label);
		for (int i = 0; st && i < 16; i++, st = st->GetNextState())
		{
			FTextureID tex = FrameTexture(st->sprite, st->GetFrame());
			if (tex.isValid()) return tex;
		}
	}
	AActor *def = GetDefaultByType(cls);
	return cls->IsDescendantOf(NAME_Inventory) ? def->TextureIDVar(FName("Icon")) : FNullTextureID();
}

// A display name without Doom's color codes or DRLA's "[Pickup]" suffix.
FString CleanTag(const char *tag)
{
	FString out;
	for (const char *c = tag; *c; c++)
	{
		if (*c == TEXTCOLOR_ESCAPE)
		{
			if (c[1] == '[') { while (c[1] && c[1] != ']') c++; }
			if (c[1]) c++;
			continue;
		}
		out += *c;
	}
	const char *suffix = " [Pickup]";
	const size_t n = strlen(suffix);
	if (out.Len() > n && !strcmp(out.GetChars() + out.Len() - n, suffix)) out.Truncate(out.Len() - n);
	return out;
}

// Writes the sprite and name of one class to the art slot. Larger sprites are shrunk to fit the slot.
void SendArt(uint32_t request, const FString &name)
{
	PClassActor *cls = PClass::FindActor(name.GetChars());
	FTextureID texid = cls ? ArtFor(cls) : FNullTextureID();
	FGameTexture *tex = texid.isValid() ? TexMan.GetGameTexture(texid) : nullptr;
	if (!tex)
	{
		SendDoomItem(DFB_KIND_DOOM_ITEM_ART, request, DFB_ITEM_GONE, name.GetChars());
		return;
	}
	FBitmap bmp = tex->GetTexture()->GetBgraBitmap(nullptr);
	const int srcW = bmp.GetWidth(), srcH = bmp.GetHeight();
	const int maxPixels = int(DFB_BULK_BYTES - DFB_ITEM_ART_HEADER) / 4;
	int w = srcW, h = srcH;
	while (w * h > maxPixels) { w = w * 3 / 4; h = h * 3 / 4; }
	if (w <= 0 || h <= 0)
	{
		SendDoomItem(DFB_KIND_DOOM_ITEM_ART, request, DFB_ITEM_GONE, name.GetChars());
		return;
	}
	static TArray<uint8_t> buffer;
	buffer.Resize(DFB_ITEM_ART_HEADER + w * h * 4);
	dfb_item_art header{};
	header.request = request;
	header.width = w;
	header.height = h;
	strncpy(header.cls, name.GetChars(), sizeof(header.cls) - 1);
	strncpy(header.tag, CleanTag(GetDefaultByType(cls)->GetTag()).GetChars(), sizeof(header.tag) - 1);
	memcpy(buffer.Data(), &header, sizeof(header));
	const uint8_t *src = bmp.GetPixels();
	uint8_t *dst = buffer.Data() + DFB_ITEM_ART_HEADER;
	for (int y = 0; y < h; y++)
		for (int x = 0; x < w; x++)
			memcpy(dst + (y * w + x) * 4, src + (y * srcH / h) * bmp.GetPitch() + (x * srcW / w) * 4, 4);
	uint32_t version;
	const bool ok = dfb_bulk_write(itemSession, DFB_ITEM_ART_SLOT, buffer.Data(), buffer.Size(), &version) == DFB_OK;
	SendDoomItem(DFB_KIND_DOOM_ITEM_ART, request, ok ? DFB_ITEM_TAKEN : DFB_ITEM_REFUSED, name.GetChars());
}

// Daggerfall answered a Use press. Runs inside the playsim.
void FinishTake(uint32_t request, uint32_t status)
{
	PendingTake take{};
	bool found = false;
	for (auto it = pendingTakes.begin(); it != pendingTakes.end(); ++it)
		if (it->request == request) { take = *it; pendingTakes.erase(it); found = true; break; }
	if (!found || consoleplayer < 0 || !players[consoleplayer].mo || !primaryLevel) return;
	AActor *pmo = players[consoleplayer].mo;
	if (status == DFB_ITEM_TOO_HEAVY) { Printf(PRINT_HIGH, "You cannot carry any more.\n"); return; }
	if (status != DFB_ITEM_TAKEN) { Printf(PRINT_HIGH, "You cannot take that now.\n"); return; }

	AActor *item = nullptr;
	double best = 64;
	TThinkerIterator<AActor> it(primaryLevel);
	while (AActor *mo = it.Next())
	{
		if (mo->GetClass()->TypeName != take.cls || !(mo->flags & MF_SPECIAL)) continue;
		const double d = (mo->Pos() - take.pos).Length();
		if (d < best) { best = d; item = mo; }
	}
	FString tag = CleanTag(item ? item->GetTag() : take.cls.GetChars());
	if (item && IsGun(item->GetClass()))
	{
		item->CallTouch(pmo); // Doom's normal pickup gives the gun, or only ammo when it is already held.
		if (!(item->ObjectFlags & OF_EuthanizeMe) && (item->flags & MF_SPECIAL)) item->Destroy();
	}
	else if (item)
	{
		S_Sound(pmo, CHAN_ITEM, 0, "misc/i_pkup", 1, ATTN_NORM);
		item->Destroy();
	}
	Printf(PRINT_HIGH, "You take %s.\n", tag.GetChars());
	Printf(PRINT_LOG, "doomitems: took %s (request %u) into Daggerfall's inventory%s\n", take.cls.GetChars(), request, item ? "" : ", actor already gone");
}

// The player used a Doom item in Daggerfall's inventory: Doom picks up a fresh copy at the player. Runs inside the playsim.
void UseFromDaggerfall(uint32_t request, const char *name)
{
	PClassActor *cls = PClass::FindActor(name);
	player_t *player = consoleplayer >= 0 ? &players[consoleplayer] : nullptr;
	bool used = false;
	if (cls && cls->IsDescendantOf(NAME_Inventory) && player && player->mo && player->health > 0 && primaryLevel && gamestate == GS_LEVEL)
	{
		AActor *mo = Spawn(primaryLevel, cls, player->mo->Pos(), NO_REPLACE);
		if (mo)
		{
			mo->ClearCounters();
			mo->flags |= MF_SPECIAL; // DRLA pickups turn this on only when they land.
			mo->CallTouch(player->mo);
			used = (mo->ObjectFlags & OF_EuthanizeMe) || !(mo->flags & MF_SPECIAL);
			if (!used) mo->Destroy();
		}
	}
	if (!used) Printf(PRINT_HIGH, "You cannot use that now.\n");
	Printf(PRINT_LOG, "doomitems: use %s from Daggerfall (request %u): %s\n", name, request, used ? "applied" : "refused");
	SendDoomItem(DFB_KIND_DOOM_ITEM_USED, request, used ? DFB_ITEM_TAKEN : DFB_ITEM_REFUSED, name);
}

// A Use press on a Doom item. Daggerfall decides, and the press is spent either way.
void AskDaggerfall(AActor *item)
{
	const FName cls = item->GetClass()->TypeName;
	for (auto it = pendingTakes.begin(); it != pendingTakes.end();)
	{
		if (gametic - it->tic > PendingTics) it = pendingTakes.erase(it);
		else if (it->cls == cls && (it->pos - item->Pos()).Length() < 1) return; // Already asked.
		else ++it;
	}
	FTextureID seen = FrameTexture(item->sprite, item->frame);
	if (seen.isValid()) seenArt[cls] = seen;
	const uint32_t request = nextDoomRequest++;
	pendingTakes.push_back({ request, cls, item->Pos(), gametic });
	SendDoomItem(DFB_KIND_DOOM_ITEM_TAKE, request, 0, cls.GetChars());
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
		ShowResult(r);
		return true;
	}
	case DFB_KIND_DOOM_ITEM_RESULT:
	case DFB_KIND_DOOM_ITEM_USE:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		if (e.kind == DFB_KIND_DOOM_ITEM_RESULT) doomOutgoing.push_back(FStringf("dfd_result:%u:%u", d.request, d.status));
		else doomOutgoing.push_back(FStringf("dfd_use:%u:%s", d.request, ClassOf(d).GetChars()));
		return true;
	}
	case DFB_KIND_DOOM_ITEM_ART_REQUEST:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		SendArt(d.request, ClassOf(d));
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
	for (int i = 0; i < MaxEventsPerFrame && !doomOutgoing.empty(); i++)
	{
		if (!primaryLevel->localEventManager->SendNetworkEvent(doomOutgoing.front(), 0, 0, 0, false)) break;
		doomOutgoing.pop_front();
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

	AActor *pmo = player->mo, *best = nullptr;
	double bestScore = -HUGE_VAL;
	TThinkerIterator<AActor> it(pmo->Level);
	while (AActor *mo = it.Next())
	{
		const bool pile = IsWorldPile(mo);
		if (!pile && (!(mo->flags & MF_SPECIAL) || !DD_PickupNeedsUse(mo))) continue;
		const double score = AimScore(pmo, player, mo);
		if (score > bestScore && P_CheckSight(pmo, mo, SF_IGNOREVISIBILITY))
		{
			bestScore = score;
			best = mo;
		}
	}
	if (!best) return false;

	if (IsWorldPile(best))
	{
		const uint64_t id = strtoull(best->StringVar(FName("dfId")).GetChars(), nullptr, 16);
		const bool crouching = (player->cmd.buttons & BT_CROUCH) || player->crouchfactor < 1;
		SendTake(id, crouching ? DFB_TAKE_STEAL : DFB_TAKE_GRAB);
		lastResult = id != refusedPile;
		return lastResult;
	}
	// Daggerfall holds every Doom item taken with Use. A class name too long for the bridge keeps Doom's own pickup.
	if (strlen(best->GetClass()->TypeName.GetChars()) < sizeof(dfb_doom_item::cls))
	{
		AskDaggerfall(best);
		lastResult = true;
		return true;
	}
	best->CallTouch(pmo);
	// A refused pickup, such as a weapon the player already holds, stays in the world and leaves the press for a door.
	lastResult = (best->ObjectFlags & OF_EuthanizeMe) || !(best->flags & MF_SPECIAL);
	return lastResult;
}

// The Interact control is the same action as Use, without Doom's door use.
bool DD_ItemsNetEvent(dfb_session *session, const char *name)
{
	const bool result = !strncmp(name, "dfd_result:", 11);
	if (result || !strncmp(name, "dfd_use:", 8))
	{
		char *end;
		const uint32_t request = uint32_t(strtoul(name + (result ? 11 : 8), &end, 10));
		if (*end == ':')
		{
			if (result) FinishTake(request, uint32_t(strtoul(end + 1, nullptr, 10)));
			else UseFromDaggerfall(request, end + 1);
		}
		return true;
	}
	if (strcmp(name, "df_interact")) return false;
	if (session && consoleplayer >= 0) DD_UsePress(&players[consoleplayer]);
	return true;
}
