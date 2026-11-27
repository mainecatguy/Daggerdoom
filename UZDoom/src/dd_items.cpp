// [Doomerfall] Doom's side of world items. Daggerfall lists the piles and furniture containers in the current
// space and opens its own window for each one. This file passes the list to ZScript and passes Use back.
// Nothing here runs without a bridge session.

#include <algorithm>
#include "dd_lootrng.h"
#include <cinttypes>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <map>

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
#include "gstrings.h"
#include "gamestate.h"
#include "info.h"
#include "p_3dfloors.h"
#include "p_linetracedata.h"
#include "p_local.h"
#include "printf.h"
#include "c_dispatch.h"
#include "vm.h"

#ifdef _WIN32
extern "C" __declspec(dllimport) short __stdcall GetKeyState(int key); // Avoids windows.h in this file.
#endif

bool DD_BridgeHasSession();
void DD_BridgeOpenLoot();
bool DD_InfoUseNpc(dfb_session *session, player_t *player, bool crouching);
void DD_InfoUseWall(dfb_session *session, player_t *player);
bool DD_PickupNeedsUse(AActor *special);
bool DD_PickupVisible(AActor *special);
bool DD_BridgeMapPixel(int &x, int &y);

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
// The token a gun dropped from Daggerfall's inventory carries (DoomerfallGuns.zs): its Daggerfall material plus 1.
constexpr const char *GunMaterialClass = "DoomerfallGunMaterial";

// Only health and ammo pick up by touch. DRLA's versions are CustomInventory, and DRLA also uses Ammo
// classes as hidden tokens, so its pickups are named here. Each name covers its subclasses.
bool PicksUpByTouch(const PClass *cls)
{
	static const FName names[] = {
		"Health", "HealthPickup", "Ammo", "Megasphere",
		"RLHealthBonus", "RLStimpack", "RLMedikit", "RLAaaghSphere", "RLMarathonStimpack", "RLMarathonMedikit", "RLDuke2AtomicHealth",
		"RLClip", "RLClipBox", "RLShell", "RLShellBox", "RLRocketAmmo", "RLRocketBox", "RLCell", "RLCellPack",
		"DoomerfallAmmoPickup",
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

// True when a solid 3D floor lies between the player's eye and the item: it is on another storey of a converted
// dungeon. Doom's sight check lets this through for an item lying on the 3D floor's top within the player's own sector,
// and the floor-ahead rule in AimScore ignores where the player faces, so a clip on the storey above showed a label.
// The slab must lie between the two heights both where the item is and where the player stands, so an item on a
// ledge or platform seen from an open room still counts.
bool SlabBetween(sector_t *sector, const DVector2 &at, double eye, AActor *item)
{
	for (F3DFloor *rover : sector->e->XFloor.ffloors)
	{
		if (!(rover->flags & FF_EXISTS) || !(rover->flags & FF_SOLID)) continue;
		const double top = rover->top.plane->ZatPoint(at), bottom = rover->bottom.plane->ZatPoint(at);
		if (eye <= bottom && item->Z() >= top - 1) return true;
		if (eye >= top && item->Top() <= bottom + 1) return true;
	}
	return false;
}

bool OtherStorey(player_t *player, AActor *item)
{
	return SlabBetween(item->Sector, item->Pos().XY(), player->viewz, item) && SlabBetween(player->mo->Sector, player->mo->Pos().XY(), player->viewz, item);
}

// The pile, container, or (with `doomItems`) Doom pickup that Use would take, or null. With `look` (the label only),
// items on another storey are left out; Use and Info still choose as before.
AActor *ItemInView(player_t *player, bool doomItems, bool touchToo = false, bool look = false)
{
	AActor *pmo = player->mo, *best = nullptr;
	double bestScore = -HUGE_VAL;
	TThinkerIterator<AActor> it(pmo->Level);
	while (AActor *mo = it.Next())
	{
		const bool pile = IsWorldPile(mo);
		if (!pile && (!doomItems || !(mo->flags & MF_SPECIAL) || !(touchToo ? DD_PickupVisible(mo) : DD_PickupNeedsUse(mo)))) continue;
		const double score = AimScore(pmo, player, mo);
		if (score > bestScore && P_CheckSight(pmo, mo, SF_IGNOREVISIBILITY) && !(look && OtherStorey(player, mo)))
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

// Guns stay usable in Doom when Daggerfall takes them, until the weapon hotkey task gives Doom only the active gun.
bool IsGun(const PClass *cls)
{
	static const FName weapon("Weapon"), drlaPickup("RLBaseWeaponPickup");
	for (; cls; cls = cls->ParentClass)
		if (cls->TypeName == weapon || cls->TypeName == drlaPickup) return true;
	return false;
}

bool DescendsFrom(const PClass *cls, const FName &name)
{
	for (; cls; cls = cls->ParentClass)
		if (cls->TypeName == name) return true;
	return false;
}

// The weapon a gun pickup gives: the pickup itself (stock Doom), or DRLA's RL<Weapon>Pickup[Modded]. Same rule as DoomerfallGuns.zs.
PClassActor *WeaponOf(const PClass *pickup)
{
	if (pickup->IsDescendantOf(NAME_Weapon)) return (PClassActor *)pickup;
	FString name = pickup->TypeName.GetChars();
	for (const char *suffix : { "PickupModded", "Pickup" })
	{
		const size_t n = strlen(suffix);
		if (name.Len() > n && !strcmp(name.GetChars() + name.Len() - n, suffix))
		{
			name.Truncate(name.Len() - n);
			PClassActor *w = PClass::FindActor(name.GetChars());
			return w && w->IsDescendantOf(NAME_Weapon) ? w : nullptr;
		}
	}
	return nullptr;
}

// What Daggerfall needs to know about a Doom item taken with Use (DFB_DOOM_ITEM_*).
uint32_t TakeFlags(player_t *player, const PClass *cls)
{
	if (IsGun(cls))
	{
		uint32_t flags = DFB_DOOM_ITEM_GUN;
		int slot, index;
		if (PClassActor *w = WeaponOf(cls))
			if (player && player->weapons.LocateWeapon(w, &slot, &index) && slot >= 0 && slot <= 9)
				flags |= uint32_t(slot + 1) << DFB_DOOM_ITEM_SLOT_SHIFT;
		return flags;
	}
	static const FName armor("Armor"), drlaBonus("RLArmorBonusPickup"), drlaArmor("RLGenericArmorPickup"), drlaBoots("RLGenericBootsPickup");
	if (DescendsFrom(cls, drlaArmor) || DescendsFrom(cls, drlaBoots)) return DFB_DOOM_ITEM_ARMOR | DFB_DOOM_ITEM_WEARABLE;
	if (DescendsFrom(cls, armor) || DescendsFrom(cls, drlaBonus)) return DFB_DOOM_ITEM_ARMOR;
	return 0;
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
// DRLA's own SpawnFrame label comes first. Its pickups inherit Spawn from RLBaseWeaponPickup, whose static
// "Goto SpawnFrame" lands on the base class's pistol frame (PISG X); only the runtime A_Jump reaches the gun's own frame.
FTextureID ArtFor(PClassActor *cls)
{
	if (FTextureID *seen = seenArt.CheckKey(cls->TypeName)) return *seen;
	FName labels[] = { FName("SpawnFrame"), NAME_Spawn };
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

// The item's name: the Doomerfall mod's rule (zscript/DoomerfallLook.zs DoomerfallItemName.Of: its tag, the tag of the
// stock item it replaces, its pickup message cut to the noun, its class name). Without the mod, its tag or pickup message.
FString ItemName(AActor *mo)
{
	static VMFunction *rule = nullptr;
	static bool looked = false;
	if (!looked)
	{
		PClass::FindFunction(&rule, "DoomerfallItemName", "Of");
		looked = true;
	}
	if (rule)
	{
		FString answer;
		VMValue params[] = { mo };
		VMReturn ret(&answer);
		VMCall(rule, params, 1, &ret, 1);
		if (answer.IsNotEmpty()) return CleanTag(answer.GetChars());
	}
	const char *tag = mo->GetTag("");
	if (!tag[0] && mo->IsKindOf(NAME_Inventory))
	{
		const FString &msg = mo->StringVar(NAME_PickupMsg);
		tag = msg.GetChars();
		if (tag[0] == '$') tag = GStrings.GetString(tag + 1);
	}
	return CleanTag(tag[0] ? tag : mo->GetClass()->TypeName.GetChars());
}

// A gun's types or brief description for Daggerfall's item description (zscript/DoomerfallWeaponTypes.zs), or "" for
// an item that is not a gun or when the Doomerfall mod is not loaded. Daggerfall holds DRLA guns by their pickup class.
FString WeaponText(const char *what, PClassActor *cls)
{
	FString answer;
	VMFunction *f = nullptr;
	PClass::FindFunction(&f, "DoomerfallWeaponTypes", what);
	PClassActor *weapon = IsGun(cls) ? WeaponOf(cls) : nullptr;
	if (!f || !weapon) return answer;
	VMValue params[] = { (void *)weapon };
	VMReturn ret(&answer);
	VMCall(f, params, 1, &ret, 1);
	return answer;
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
	strncpy(header.tag, ItemName(GetDefaultByType(cls)).GetChars(), sizeof(header.tag) - 1);
	strncpy(header.types, WeaponText("Types", cls).GetChars(), sizeof(header.types) - 1);
	strncpy(header.brief, WeaponText("Brief", cls).GetChars(), sizeof(header.brief) - 1);
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
	FString tag = item ? ItemName(item) : CleanTag(take.cls.GetChars());
	if (item && IsGun(item->GetClass()))
	{
		// Daggerfall holds the gun and a hotkey draws it. Guns never give ammo (owner, 2026-11-24, gamedesign.md).
		S_Sound(pmo, CHAN_ITEM, 0, "misc/w_pkup", 1, ATTN_NORM);
		item->Destroy();
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
void AskDaggerfall(player_t *player, AActor *item)
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
	const uint32_t flags = TakeFlags(player, item->GetClass());
	// A DRLA modded pickup carries its gun's mods as its own inventory (<Weapon>PowerMod, <Weapon>ModLimit, ...), which
	// DRLA would transfer on touch. They go to Daggerfall as the gun's state, the same lines a hotkey swap stores.
	if (flags & DFB_DOOM_ITEM_GUN)
		if (PClassActor *w = WeaponOf(item->GetClass()))
		{
			const FString prefix = w->TypeName.GetChars();
			for (AActor *inv = item->Inventory; inv; inv = inv->Inventory)
			{
				const FString name = inv->GetClass()->TypeName.GetChars();
				const int amount = inv->IntVar(NAME_Amount);
				if (amount <= 0 || name.Len() <= prefix.Len() || strncmp(name.GetChars(), prefix.GetChars(), prefix.Len())) continue;
				if (name.IndexOf("TypeWeapon") >= 0 || name.IndexOf("Selected") >= 0 || name.Len() >= sizeof(dfb_doom_item::cls)) continue;
				SendDoomItem(DFB_KIND_DOOM_ITEM_GUN_STATE, request, uint32_t(amount), name.GetChars());
				Printf(PRINT_LOG, "doomitems: %s carries %s %d\n", cls.GetChars(), name.GetChars(), amount);
			}
		}
	// A gun dropped from Daggerfall's inventory carries the material Daggerfall gave it (DoomerfallGunMaterial, amount
	// material + 1), so Daggerfall gives it back unchanged.
	if (flags & DFB_DOOM_ITEM_GUN)
		if (AActor *m = item->FindInventory(FName(GunMaterialClass)); m && m->IntVar(NAME_Amount) > 0)
			SendDoomItem(DFB_KIND_DOOM_ITEM_GUN_STATE, request, uint32_t(m->IntVar(NAME_Amount)), GunMaterialClass);
	if (const uint64_t id = (flags & DFB_DOOM_ITEM_GUN) ? DD_LootFixItemId(item) : DD_LootItemId(item); id && itemSession)	// Daggerfall seeds the item's rolls with it.
	{
		const dfb_item_take body{ id, request, 0 };
		dfb_event e{};
		e.kind = DFB_KIND_DOOM_ITEM_ID;
		e.tic = gametic;
		memcpy(e.payload, &body, sizeof(body));
		dfb_send(itemSession, &e);
	}
	SendDoomItem(DFB_KIND_DOOM_ITEM_TAKE, request, flags, cls.GetChars());
}

// Reserve ammo held by Daggerfall (DFB_KIND_AMMO). Doom's counts are the live ones that guns spend. Subclasses such as
// DRLA's pickups add to these parent classes, and each DRLA gun's loaded magazine is gun state, not reserve ammo.
const char *const AmmoClasses[] = { "Clip", "Shell", "RocketAmmo", "Cell" };
constexpr int AmmoKinds = 4;
int sentAmmo[AmmoKinds] = { -1, -1, -1, -1 };
uint32_t ammoAddApplied, sentAmmoAck;
int sentReadyAmmo = -2; // AmmoClasses index the ready weapon uses, -1 for none, -2 before any report.

// Area levels Daggerfall answered, by map pixel (y * 1000 + x, plus one million inside a dungeon). The Doomerfall mod
// rolls ammo drop tiers with the level of the player's pixel (DoomerfallAmmo.zs), sent as dfa_level:<level or -1>.
std::map<uint32_t, int> areaLevels;
uint32_t askedLevelKey = ~0u;
int askedLevelTic, sentLevel = -2;

void PublishAreaLevel()
{
	int level = -1, x, y;
	if (useRules)
	{
		// After a load straight into a space Doom has not seen the outdoor pixel yet, so it asks for "where Daggerfall's
		// player is" (key 2000000), which DD_ItemsFrame forgets on every change of place.
		const uint32_t key = !DD_BridgeMapPixel(x, y) ? 2000000u
			: uint32_t(y * 1000 + x) + (currentContext == DFB_WORLD_DUNGEON ? 1000000u : 0u);
		auto known = areaLevels.find(key);
		if (known != areaLevels.end()) level = known->second;
		else if (key != askedLevelKey || gametic < askedLevelTic || gametic - askedLevelTic > 2 * TICRATE)
		{
			SendDoomItem(DFB_KIND_AREA_LEVEL_REQUEST, key, 0, "");
			askedLevelKey = key;
			askedLevelTic = gametic;
		}
	}
	if (level == sentLevel) return;
	outgoing.push_back(FStringf("dfa_level:%d", level));
	sentLevel = level;
	Printf(PRINT_LOG, "doomitems: area level for ammo drops %d\n", level);
}

// The reserve ammo the ready weapon uses: the first of its ammo types (DRLA's magazine is AmmoType1, so its reserve
// is AmmoType2) that is or derives from one of AmmoClasses. -1 for none, such as fists.
int ReadyAmmo(player_t *player)
{
	AActor *w = player->ReadyWeapon;
	if (!w) return -1;
	for (FName field : { NAME_AmmoType1, NAME_AmmoType2 })
	{
		PClassActor *type = w->PointerVar<PClassActor>(field);
		if (!type) continue;
		for (int i = 0; i < AmmoKinds; i++)
			if (type->IsDescendantOf(FName(AmmoClasses[i]))) return i;
	}
	return -1;
}

// Sends every count that changed since the last report, and all of them after an AMMO_ADD so its answer carries the ack.
// Also tells Daggerfall when the ready weapon's reserve ammo changes, so it can load that ammo and its damage bonus.
void ReportAmmo()
{
	if (!itemSession || gamestate != GS_LEVEL || consoleplayer < 0) return;
	player_t *player = &players[consoleplayer];
	if (!player->mo || player->playerstate != PST_LIVE || player->health <= 0) return;
	const int ready = ReadyAmmo(player);
	// Also on any new ready weapon, so Daggerfall knows when a gun it handed over is up (each gun remembers its own
	// loaded tier). The pointer is only compared. Status 1 means the ready weapon is a melee weapon (fists) or none,
	// which gets no weapon material bonus in Daggerfall; 0 is a gun, with or without reserve ammo (DRLA's Blaster).
	static const void *sentReadyWeapon;
	if (ready != sentReadyAmmo || player->ReadyWeapon != sentReadyWeapon)
	{
		sentReadyWeapon = player->ReadyWeapon;
		const bool melee = !player->ReadyWeapon || (player->ReadyWeapon->IntVar(NAME_WeaponFlags) & WIF_MELEEWEAPON);
		SendDoomItem(DFB_KIND_AMMO_READY, 0, melee ? 1 : 0, ready >= 0 ? AmmoClasses[ready] : "");
		Printf(PRINT_LOG, "doomitems: ready weapon %s uses %s\n", player->ReadyWeapon ? player->ReadyWeapon->GetClass()->TypeName.GetChars() : "none",
			ready >= 0 ? AmmoClasses[ready] : "no reserve ammo");
		sentReadyAmmo = ready;
	}
	const bool ackChanged = sentAmmoAck != ammoAddApplied;
	for (int i = 0; i < AmmoKinds; i++)
	{
		AActor *inv = player->mo->FindInventory(FName(AmmoClasses[i]));
		const int count = inv ? std::max(0, inv->IntVar(NAME_Amount)) : 0;
		if (count == sentAmmo[i] && !ackChanged) continue;
		SendDoomItem(DFB_KIND_AMMO, ammoAddApplied, uint32_t(count), AmmoClasses[i]);
		sentAmmo[i] = count;
	}
	sentAmmoAck = ammoAddApplied;
}

// Daggerfall's inventory gained or lost reserve ammo. Doom accepts more than its own maximum. Runs inside the playsim.
void AddAmmo(uint32_t request, int delta, const char *name)
{
	player_t *player = consoleplayer >= 0 ? &players[consoleplayer] : nullptr;
	PClassActor *cls = PClass::FindActor(name);
	int before = -1, after = -1;
	if (cls && cls->IsDescendantOf(NAME_Ammo) && player && player->mo && player->health > 0)
	{
		AActor *inv = player->mo->FindInventory(cls);
		if (!inv && delta > 0 && (inv = player->mo->GiveInventoryType(cls))) inv->IntVar(NAME_Amount) = 0;
		if (inv)
		{
			int &amount = inv->IntVar(NAME_Amount);
			before = amount;
			amount = int(std::max<int64_t>(0, int64_t(amount) + delta));
			after = amount;
		}
	}
	// Acknowledged either way, so Daggerfall takes the next report as the truth.
	ammoAddApplied = std::max(ammoAddApplied, request);
	Printf(PRINT_LOG, "doomitems: ammo add %u %s %+d: %d -> %d\n", request, name, delta, before, after);
}

// The reserve ammo index (AmmoClasses) a weapon uses, and its magazine: the other ammo type, when that is not reserve
// ammo (DRLA guns load AmmoType1 from AmmoType2). Stock guns have no magazine.
int WeaponAmmo(AActor *w, PClassActor **magazine)
{
	*magazine = nullptr;
	int reserve = -1;
	PClassActor *other = nullptr;
	for (FName field : { NAME_AmmoType1, NAME_AmmoType2 })
	{
		PClassActor *type = w->PointerVar<PClassActor>(field);
		if (!type) continue;
		int kind = -1;
		for (int i = 0; i < AmmoKinds; i++)
			if (type->IsDescendantOf(FName(AmmoClasses[i]))) kind = i;
		if (kind >= 0 && reserve < 0) reserve = kind;
		else if (kind < 0 && !other) other = type;
	}
	if (reserve >= 0) *magazine = other;
	return reserve;
}

// DFB_KIND_AMMO_UNLOAD: Daggerfall changes the tier a gun loads. The gun (the ready weapon, else the first held gun that
// uses this reserve ammo) gives up its magazine, and Daggerfall puts those rounds back as the old tier. An automatic
// change (the reserve ran out) is refused while the magazine still holds rounds. Runs inside the playsim.
void UnloadMagazine(uint32_t request, bool automatic, const char *name)
{
	player_t *player = consoleplayer >= 0 ? &players[consoleplayer] : nullptr;
	uint32_t rounds = 0;
	const char *gun = "none", *mag = "none";
	if (player && player->mo && player->health > 0)
	{
		AActor *found = nullptr;
		PClassActor *magazine = nullptr;
		auto matches = [&](AActor *w) { return w && w->IsKindOf(NAME_Weapon) && WeaponAmmo(w, &magazine) >= 0 && !strcmp(AmmoClasses[WeaponAmmo(w, &magazine)], name); };
		if (matches(player->ReadyWeapon)) found = player->ReadyWeapon;
		for (AActor *inv = player->mo->Inventory; inv && !found; inv = inv->Inventory)
			if (matches(inv)) found = inv;
		if (found)
		{
			gun = found->GetClass()->TypeName.GetChars();
			WeaponAmmo(found, &magazine);
			AActor *held = magazine ? player->mo->FindInventory(magazine) : nullptr;
			if (held)
			{
				mag = magazine->TypeName.GetChars();
				int &amount = held->IntVar(NAME_Amount);
				if (automatic && amount > 0) rounds = 0xFFFFFFFFu;
				else
				{
					rounds = uint32_t(std::max(0, amount));
					amount = 0;
				}
			}
		}
	}
	SendDoomItem(DFB_KIND_AMMO_UNLOADED, request, rounds, name);
	// A change by the key is a reload (owner, 2026-11-24). Daggerfall swapped the reserve to the new tier just before.
	// A ready gun starts now, in this tic, so no round fires first: its Reload state fills the magazine from the
	// reserve, and a gun with no magazine is lowered and raised. DoomerfallAmmo.zs waits for a busy gun to be ready.
	AActor *ready = player ? player->ReadyWeapon : nullptr;
	if (!automatic && ready && !strcmp(gun, ready->GetClass()->TypeName.GetChars()))
	{
		PClassActor *magazine = nullptr;
		WeaponAmmo(ready, &magazine);
		FState *reload = magazine ? ready->FindState(NAME_Reload) : nullptr;
		const bool busy = !(player->WeaponState & WF_WEAPONREADY); // Setting a state clears the flag.
		if (busy) doomOutgoing.push_back(FStringf("dfa_reload:%s", gun));
		else if (reload) P_SetPsprite(player, PSP_WEAPON, reload);
		else if (FState *down = ready->FindState(NAME_Deselect))
		{
			player->PendingWeapon = ready;
			P_SetPsprite(player, PSP_WEAPON, down);
		}
		Printf(PRINT_LOG, "doomitems: change ammo reload of %s: %s\n", gun, busy ? "the gun is busy, waiting" : reload ? "reload" : "lowered and raised");
	}
	Printf(PRINT_LOG, "doomitems: ammo unload %u%s %s: gun %s magazine %s, %s\n", request, automatic ? " (automatic)" : "", name, gun, mag,
		rounds == 0xFFFFFFFFu ? "refused, the magazine still holds rounds" : FStringf("%u rounds back to Daggerfall", rounds).GetChars());
}

void SendHotkey(int slot, uint32_t mod)
{
	SendDoomItem(DFB_KIND_HOTKEY, uint32_t(slot), mod, "");
	Printf(PRINT_LOG, "doomitems: hotkey %d modifier %u\n", slot, mod);
}
}

// A weapon slot key on a generated map is a Daggerfall hotkey. Ctrl and Alt pick the square, however they are bound.
bool DD_HotkeySlot(int slot)
{
	if (!useRules || !itemSession || !DD_BridgeHasSession() || slot < 0 || slot > 9) return false;
	uint32_t mod = DFB_HOTKEY_PLAIN;
#ifdef _WIN32
	if (GetKeyState(0x11 /* VK_CONTROL */) & 0x8000) mod = DFB_HOTKEY_CTRL;
	else if (GetKeyState(0x12 /* VK_MENU */) & 0x8000) mod = DFB_HOTKEY_ALT;
#endif
	SendHotkey(slot, mod);
	return true;
}

// Test and console form: dd_hotkey <key 0-9> [0 plain, 1 Ctrl, 2 Alt].
CCMD(dd_hotkey)
{
	if (argv.argc() < 2 || !itemSession || !DD_BridgeHasSession()) return;
	SendHotkey(atoi(argv[1]) % 10, argv.argc() > 2 ? uint32_t(atoi(argv[2])) : DFB_HOTKEY_PLAIN);
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
	case DFB_KIND_DOOM_ITEM_RESULT:
	case DFB_KIND_DOOM_ITEM_USE:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		if (e.kind == DFB_KIND_DOOM_ITEM_RESULT) doomOutgoing.push_back(FStringf("dfd_result:%u:%u", d.request, d.status));
		// [Doomerfall] Daggerfall's inventory window dropped this Doom item: status bit 0x100 (plus 0x200 when it is
		// the gun Doom holds). DoomerfallGuns.zs spawns its pickup, carrying the gun's GUN_STATE lines sent just before, and
		// answers with DOOM_ITEM_USED, so Daggerfall lets go of the item only once the pickup exists.
		else if (d.status & 0x100) doomOutgoing.push_back(FStringf("dfg_drop:%u:%u:%s", d.request, d.status, ClassOf(d).GetChars()));
		else doomOutgoing.push_back(FStringf("dfd_use:%u:%s", d.request, ClassOf(d).GetChars()));
		return true;
	}
	case DFB_KIND_GUN_STATE:
	case DFB_KIND_GUN_EQUIP:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		doomOutgoing.push_back(FStringf("%s:%u:%u:%s", e.kind == DFB_KIND_GUN_STATE ? "dfg_state" : "dfg_equip", d.request, d.status, ClassOf(d).GetChars()));
		return true;
	}
	case DFB_KIND_AMMO_ADD:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		doomOutgoing.push_back(FStringf("dfa_add:%u:%d:%s", d.request, int32_t(d.status), ClassOf(d).GetChars()));
		return true;
	}
	case DFB_KIND_AMMO_UNLOAD:
	case DFB_KIND_AMMO_LOADED:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		// The loaded ammo goes to DoomerfallAmmo.zs for the HUD: dfa_loaded:<tier or -1>:<type>:<tags>.
		if (e.kind == DFB_KIND_AMMO_LOADED) doomOutgoing.push_back(FStringf("dfa_loaded:%d:%u:%s", int32_t(d.request), d.status, ClassOf(d).GetChars()));
		else doomOutgoing.push_back(FStringf("dfa_unload:%u:%u:%s", d.request, d.status, ClassOf(d).GetChars()));
		return true;
	}
	case DFB_KIND_AREA_LEVEL:
	{
		dfb_doom_item d;
		memcpy(&d, e.payload, sizeof(d));
		areaLevels[d.request] = int(d.status);
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
		// Tells the Doomerfall mod whether Daggerfall's rules apply here, so it shows Sneaking only on a Daggerfall map.
		outgoing.push_back(useRules ? "dfi_rules:1" : "dfi_rules:0");
		wantList = inSpace;
		sentLevel = -2;
		areaLevels.erase(2000000u);
	}
	PublishAreaLevel();
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
	ReportAmmo();
}

// After a load, Doom's restored actors may not match Daggerfall until a fresh list arrives.
void DD_ItemsResync()
{
	// The snapshot's markers carry the saving session's list numbers, which can equal a new list's after a load in a
	// new launch, so a pile Daggerfall no longer has could survive as a ghost. Remove them all until the list arrives.
	acceptedGeneration = 0;
	outgoing.clear();
	outgoing.push_back("dfi_clear");
	outgoing.push_back(useRules ? "dfi_rules:1" : "dfi_rules:0");
	wantList = spaceValid;
	for (int &count : sentAmmo) count = -1; // Daggerfall forgot its reports when it loaded.
	sentReadyAmmo = -2;
	sentLevel = -2;
}

// New Game and plain Daggerfall load arrivals (NgSendArrived): tells Daggerfall the starter gun, the loaded mods' pistol (DRLA's RLPistol, else
// stock Pistol) by its world pickup class, its weapon slot, and the player class's start amount of its reserve ammo.
void DD_ItemsSendStarter()
{
	PClassActor *weapon = PClass::FindActor("RLPistol");
	if (!weapon || !weapon->IsDescendantOf(NAME_Weapon)) weapon = PClass::FindActor("Pistol");
	player_t *player = consoleplayer >= 0 ? &players[consoleplayer] : nullptr;
	if (!weapon || !weapon->IsDescendantOf(NAME_Weapon) || !player || !player->mo)
	{
		SendDoomItem(DFB_KIND_STARTER, 0, 0, "");
		Printf(PRINT_LOG, "doomitems: starter: no pistol class is loaded\n");
		return;
	}
	FString pickup = FStringf("%sPickup", weapon->TypeName.GetChars());	// As DoomerfallGuns.zs PickupFor names a held gun.
	if (!PClass::FindActor(pickup.GetChars())) pickup = weapon->TypeName.GetChars();
	int slot = -1, index = -1;
	if (!player->weapons.LocateWeapon(weapon, &slot, &index)) slot = -1;
	PClassActor *magazine;
	const int kind = WeaponAmmo(GetDefaultByType(weapon), &magazine);
	int amount = 0;
	bool listed = false;
	if (kind >= 0)
		for (FDropItem *di = player->mo->GetClass()->ActorInfo()->DropItems; di; di = di->Next)
		{
			PClassActor *item = PClass::FindActor(di->Name);
			if (item && item->IsDescendantOf(FName(AmmoClasses[kind]))) { amount += di->Amount; listed = true; }
		}
	// Some classes (DRLA X) give their start ammo by script, not Player.StartItem. Doom has been frozen since its new game
	// started, so what the player holds now is still the class's start amount.
	if (kind >= 0 && !listed)
		if (AActor *inv = player->mo->FindInventory(FName(AmmoClasses[kind]))) amount = std::max(0, inv->IntVar(NAME_Amount));
	Printf(PRINT_LOG, "doomitems: starter %s (slot %d), class %s starts with %d %s%s\n", pickup.GetChars(), slot,
		player->mo->GetClass()->TypeName.GetChars(), amount, kind >= 0 ? AmmoClasses[kind] : "no reserve ammo", listed ? "" : " (none listed)");
	SendDoomItem(DFB_KIND_STARTER, uint32_t(slot & 0xff) | uint32_t(kind + 1) << 8, uint32_t(amount), pickup.GetChars());
}

// A pickup the player can see, which touch would take. Invisible helpers are left out.
bool DD_PickupVisible(AActor *special)
{
	static const int noSprite = GetSpriteIndex("TNT1");
	return special->IsKindOf(NAME_Inventory) && special->sprite != noSprite && !(special->renderflags & RF_INVISIBLE);
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

// The label under the crosshair (dd_look.cpp): what Use would take, or a visible pickup taken by touch, by Use's own aim
// and reach. world is true for a Daggerfall pile or container, whose id is then set; otherwise name is Daggerfall's
// inventory name for a Doom item (DoomerfallDoomItems.NameFor gets the same ItemName through the art slot).
AActor *DD_LookItem(player_t *player, bool &world, uint64_t &id, FString &name)
{
	if (!useRules || !DD_BridgeHasSession() || !player || !player->mo) return nullptr;
	AActor *best = ItemInView(player, true, true, true);
	if (!best) return nullptr;
	world = IsWorldPile(best) || IsWorldContainer(best);
	if (world) id = strtoull(best->StringVar(FName("dfId")).GetChars(), nullptr, 16);
	else name = ItemName(best);
	return best;
}

// A Doom gun in view, with what fixes its Daggerfall material: its lasting floor id (Daggerfall's seeded roll; a gun
// without one gets one now) and the material it carries (a gun dropped from the inventory, 0 when none). dd_look.cpp asks
// Daggerfall for its name.
bool DD_LookGun(AActor *item, uint64_t &id, int &carried)
{
	if (!item || !IsGun(item->GetClass()) || strlen(item->GetClass()->TypeName.GetChars()) >= sizeof(dfb_doom_item::cls)) return false;
	AActor *m = item->FindInventory(FName(GunMaterialClass));
	carried = m ? std::max(0, m->IntVar(NAME_Amount)) : 0;
	id = DD_LootFixItemId(item);
	return true;
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
	// Daggerfall holds every Doom item taken with Use. A class name too long for the bridge keeps Doom's own pickup.
	if (strlen(best->GetClass()->TypeName.GetChars()) < sizeof(dfb_doom_item::cls))
	{
		AskDaggerfall(player, best);
		lastResult = true;
		return true;
	}
	// Guns never give ammo, and Doom's own pickup of a gun would (DRLA's Pickup states, a Weapon's AmmoGive).
	if (IsGun(best->GetClass()))
	{
		Printf(PRINT_HIGH, "You cannot take that.\n");
		return lastResult = true;
	}
	best->CallTouch(pmo);
	// A refused pickup, such as a weapon the player already holds, stays in the world and leaves the press for a door.
	lastResult = (best->ObjectFlags & OF_EuthanizeMe) || !(best->flags & MF_SPECIAL);
	return lastResult;
}

// A press of Use outdoors that no door, item or NPC took: Daggerfall's Info on the building wall in view, if any.
void DD_UseWall(player_t *player)
{
	if (useRules && itemSession) DD_InfoUseWall(itemSession, player);
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

// Doomerfall's own events. df_interact is Use's interaction without the door use; players interact with Doom's Use
// (P_CheckUse), and only test harnesses still send it.
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
	if (!strncmp(name, "dfa_add:", 8))
	{
		char *end;
		const uint32_t request = uint32_t(strtoul(name + 8, &end, 10));
		if (*end == ':')
		{
			const int delta = int(strtol(end + 1, &end, 10));
			if (*end == ':') AddAmmo(request, delta, end + 1);
		}
		return true;
	}
	if (!strncmp(name, "dfa_unload:", 11))
	{
		char *end;
		const uint32_t request = uint32_t(strtoul(name + 11, &end, 10));
		if (*end == ':')
		{
			const uint32_t flags = uint32_t(strtoul(end + 1, &end, 10));
			if (*end == ':') UnloadMagazine(request, flags & 1, end + 1);
		}
		return true;
	}
	// The change ammo key (Doomerfall Controls). Daggerfall decides what changes. Harnesses send the same event.
	if (!strcmp(name, "df_change_ammo"))
	{
		if (useRules && session)
		{
			SendDoomItem(DFB_KIND_AMMO_CHANGE, 0, 0, "");
			Printf(PRINT_LOG, "doomitems: change ammo key\n");
		}
		return true;
	}
	// DoomerfallAmmo.zs: the player touched a tiered pickup, dfa_take:<tier>:<rounds>:<reserve class>.
	if (!strncmp(name, "dfa_take:", 9))
	{
		char *end;
		const uint32_t tier = uint32_t(strtoul(name + 9, &end, 10));
		if (*end == ':')
		{
			const uint32_t rounds = uint32_t(strtoul(end + 1, &end, 10));
			if (*end == ':')
			{
				SendDoomItem(DFB_KIND_AMMO_TAKE, tier, rounds, end + 1);
				Printf(PRINT_LOG, "doomitems: ammo take tier %u x%u %s\n", tier, rounds, end + 1);
			}
		}
		return true;
	}
	// Test harnesses press a hotkey as dd_hotkey:<key>:<modifier>, since ZScript cannot run the console command.
	if (!strncmp(name, "dd_hotkey:", 10))
	{
		char *end;
		const int key = int(strtol(name + 10, &end, 10));
		if (useRules && key >= 0 && key <= 9) SendHotkey(key, *end == ':' ? uint32_t(strtoul(end + 1, nullptr, 10)) : DFB_HOTKEY_PLAIN);
		return true;
	}
	// DoomerfallGuns.zs reports a gun swap: dfg_out:<state|stashed|kept|done>:<request>:<status>:<class>.
	if (!strncmp(name, "dfg_out:", 8))
	{
		static const struct { const char *word; uint16_t kind; } kinds[] = {
			{ "state:", DFB_KIND_GUN_STATE }, { "stashed:", DFB_KIND_GUN_STASHED }, { "kept:", DFB_KIND_GUN_KEPT }, { "done:", DFB_KIND_GUN_EQUIPPED },
			{ "dropped:", DFB_KIND_DOOM_ITEM_USED } };	// [Doomerfall] a dropped Doom item's pickup was spawned, or not
		for (auto &k : kinds)
		{
			const size_t n = strlen(k.word);
			if (strncmp(name + 8, k.word, n)) continue;
			char *end;
			const uint32_t request = uint32_t(strtoul(name + 8 + n, &end, 10));
			if (*end != ':') break;
			const uint32_t status = uint32_t(strtoul(end + 1, &end, 10));
			if (*end != ':') break;
			SendDoomItem(k.kind, request, status, end + 1);
			if (k.kind != DFB_KIND_GUN_STATE) Printf(PRINT_LOG, "doomitems: gun %s%u status %u %s\n", k.word, request, status, end + 1);
			break;
		}
		return true;
	}
	if (strcmp(name, "df_interact")) return false;
	if (session && consoleplayer >= 0) DD_UsePress(&players[consoleplayer]);
	return true;
}
