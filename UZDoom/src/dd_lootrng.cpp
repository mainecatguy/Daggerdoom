// [Doomerfall] Fixed loot for Doom's own drops. Daggerfall's rule is that the same place gives the same loot to every
// character. Native Doom drops (DropItem lists, a mod's drop helpers, random spawners, death-state A_Jump rolls) draw
// from Doom's shared random streams, whose state depends on everything else that happened in the game.
//
// This gives each roll its own random state instead, seeded only from a fixed identity, without knowing any mod:
// - A monster with a Daggerfall id (ddRecordId) gets a loot state from that id when it starts dying. Its Die, its
//   death-state actions and anything they run draw from that state (DDLootScope sets DD_RngOverride, which every
//   gameplay FRandom stream honours; client-side cosmetic streams are untouched).
// - An actor spawned during such a roll that is not a monster, missile or player (a dropped item, a drop helper such
//   as DRLA's RL...Drop, a random spawner, gibs) gets its own state drawn from its parent's, so its later actions and
//   PostBeginPlay are fixed too. ddLootId keeps that first value, and names a dropped item that has no other id.
// - Encounter mooks, overworld seeds and map things on Daggerfall maps spawn under a state seeded from their id or
//   map spot, so a mod's random spawner standing in for them picks the same variant every game.
// - Live play: a living monster with a Daggerfall id ticks under its own state (ddAiRng), seeded from that id the first
//   time it ticks, and a missile or monster spawned while one runs gets a state drawn from it. So a Civil War plays out
//   the same way in every game until the player takes part, whenever and however the player arrives: no draw depends
//   on the player's own ticks or on anything else that happened in the game. The odds are untouched; only where the
//   numbers come from changes. The live state is dropped when the monster starts dying, so its loot never depends on
//   how it lived.
// - Summoned monsters drop nothing (owner rule, 2026-11-25). On a Daggerfall map in a bridge session, a monster that
//   dies without a Daggerfall id entered play some other way than Daggerfall's placements: a Pain Elemental's Lost Soul,
//   a DRLA summoner's minion, a boss cube's spawn, an A_SpawnItemEx or script spawn. One rule covers every route: it is
//   marked ddNoDrops, its death runs under a loot state as above, so everything spawned in its death and in the
//   actions of what that spawns (drop helpers, random spawners) carries the mark, and any loose item with the mark is
//   destroyed before its first PostBeginPlay (DD_LootVanish), so before anyone can see or touch it. Its corpse, gibs,
//   other effects and anything given into an inventory stay as they are.
// - Revived monsters drop nothing (owner rule, 2026-11-25). A monster whose seeded loot was rolled is marked ddDied; an
//   Arch-vile's Revive keeps its id and the mark, so its later deaths go the summoned way. The mark is saved, and the
//   treadmill keeps it for a parked monster (its row's death label, dd_treadmill.cpp). DRLA's "Reborn" forms are new
//   actors without an id, so they are summoned already.
// Living monsters never carry a loot state. A revived monster drops both states (AActor::Revive). Stock games never set
// ddRecordId and have no bridge session, so nothing here runs for them.
#include "dd_lootrng.h"
#include <unordered_map>
#include "actor.h"
#include "doomdata.h"
#include "g_levellocals.h"
#include "vm.h"
#include "playsim/dd_log.h"
#include "playsim/dd_treadmill.h"

bool DD_BridgeHasSession();

namespace
{
	// A floor item's id is shaped as dd_treadmill.cpp's session ids (tag 4 with bit 60), so the world table and the
	// location record treat it as a Doom drop, never as a monster, NPC or townsperson id (tags 5-7).
	constexpr uint64_t SESSION_ID = (1ull << 63) | (1ull << 60), ID_MASK = (1ull << 60) - 1, TAG_MASK = 7ull << 61;
	// A lasting floor item id also has bit 58, which the treadmill's own session ids (a counter, or bit 59 and a counter)
	// never have, so a gun's lasting id is told apart and kept through Daggerfall's location record (DD_LootGunKeepsId).
	constexpr uint64_t LASTING_MARK = 1ull << 58;
	// A session id (tag 4 with bit 60): Doom's own for this session. A living monster gets one only when the treadmill
	// parks and restores a monster that had no Daggerfall id. Not a tag test alone: monster, NPC and townsperson tags
	// (5-7) also have bit 63.
	bool IsSessionId(uint64_t id) { return (id & (TAG_MASK | (1ull << 60))) == SESSION_ID; }
	constexpr uint64_t SALT_DEATH = 0x6c6f6f7464656164ull, SALT_MAPTHING = 0x6c6f6f746d617074ull, SALT_LIVE = 0x6c6976657374617eull, SALT_FLOOR = 0x666c6f6f72676e75ull;

	uint64_t Mix(uint64_t h, uint64_t v)
	{
		h ^= v + 0x9E3779B97F4A7C15ull + (h << 6) + (h >> 2);
		h ^= h >> 30; h *= 0xBF58476D1CE4E5B9ull;
		h ^= h >> 27; h *= 0x94D049BB133111EBull;
		return h ^ (h >> 31);
	}

	uint64_t mapThingState;
	// Children so far, per owner and per (owner's loot id, class). Reset when an owner starts dying or is born, so a
	// reloaded game counts again from zero. Not saved: a corpse saved halfway through its death counts from zero after
	// the load, which can give two of its children the same seed (known gap, rare).
	std::unordered_map<AActor *, std::unordered_map<uint64_t, uint32_t>> spawnCounts;
}

AActor *DD_LootOwner, *DD_ActingActor;

DDLootScope::DDLootScope(AActor *mo) : DDLootScope(mo && mo->ddLootRng ? &mo->ddLootRng : nullptr, mo)
{
	prevActing = DD_ActingActor;
	DD_ActingActor = mo;
	acting = true;
}

uint64_t DD_LootSeedOf(uint64_t id, uint64_t salt)
{
	const uint64_t s = Mix(Mix(0x446f6f6d6572666cull, salt), id);
	return s ? s : 1;
}

void DD_LootDied(AActor *mo)
{
	const uint64_t live = mo->ddAiRng;
	mo->ddAiRng = 0;	// Dead: its corpse ticks as stock, and nothing it did alive reaches its loot.
	mo->ddNoDrops = 0;
	if (mo->player) return;
	const bool monster = (mo->flags3 & MF3_ISMONSTER) != 0, onDaggerfallMap = DD_BridgeHasSession() && DDTreadmill_OnDaggerfallMap();
	// Summoned: no Daggerfall id, or a session id (a summoned monster the treadmill parked and restored). Revived: its
	// seeded loot already dropped once (an Arch-vile's Revive keeps the id).
	const bool summoned = !mo->ddRecordId || (monster && IsSessionId(mo->ddRecordId)), revived = monster && mo->ddDied && onDaggerfallMap;
	if (summoned || revived)
	{
		// Drops nothing, only on Daggerfall maps. Its death needs a running state so that what it spawns inherits the
		// mark; a summoned monster from a placed one's live state reuses that state.
		if (!monster || !onDaggerfallMap) return;
		const uint64_t where = Mix(Mix(uint64_t(mo->Level->maptime), uint64_t(llround(mo->X()))), uint64_t(llround(mo->Y())));
		mo->ddNoDrops = 1;
		mo->ddLootRng = Mix(live ? live : where, SALT_DEATH) | 1;
		mo->ddLootId = 0;	// Not a Daggerfall seed: DD_LootSeed stays 0 for it.
		spawnCounts.erase(mo);
		DD_DebugPrintf("DDLOOT %s %s dies: no drops\n", revived ? "revived" : "summoned", mo->GetClass()->TypeName.GetChars());
		return;
	}
	if (monster) mo->ddDied = 1;
	mo->ddLootRng = mo->ddLootId = DD_LootSeedOf(mo->ddRecordId, SALT_DEATH);
	if (spawnCounts.size() > 100000) spawnCounts.clear();	// Only dead owners' finished counts are lost.
	spawnCounts.erase(mo);
}

void DD_LootInherit(AActor *mo)
{
	if (!DD_RngOverride || mo->player) return;
	if ((mo->flags3 & MF3_ISMONSTER) || (mo->flags & MF_MISSILE))
	{
		// A shot or a summoned monster: its own live state, one step of the running one.
		uint64_t &parent = *DD_RngOverride;
		parent = parent * 6364136223846793005ull + 0xda3e39cb94b95bdbull;
		const uint64_t s = Mix(parent, SALT_LIVE);
		mo->ddAiRng = s ? s : 1;
		return;
	}
	uint64_t s;
	if (DD_LootOwner && DD_LootOwner->ddLootId)
	{
		// The owner's id, the child's class and how many of that class it has spawned: not how many numbers the owner
		// drew first, which can depend on how it lived (a branch in its death states, a token it was given at spawn).
		uint64_t h = DD_LootOwner->ddLootId;
		for (const char *c = mo->GetClass()->TypeName.GetChars(); *c; c++) h = Mix(h, uint8_t(tolower(*c)));
		s = Mix(h, spawnCounts[DD_LootOwner][h]++);
	}
	else
	{
		uint64_t &parent = *DD_RngOverride;
		parent = parent * 6364136223846793005ull + 0xda3e39cb94b95bdbull;	// One step of the parent's stream (m_random.h).
		s = Mix(parent, 0x6b6964ull);
	}
	mo->ddLootRng = mo->ddLootId = s ? s : 1;
	mo->ddNoDrops = DD_LootOwner ? DD_LootOwner->ddNoDrops : 0;	// Made in a summoned monster's death, or by what that made.
	spawnCounts.erase(mo);
}

bool DD_LootVanish(AActor *mo)
{
	if (!mo->ddNoDrops || !mo->IsKindOf(NAME_Inventory) || mo->PointerVar<AActor>(NAME_Owner)) return false;
	DD_DebugPrintf("DDLOOT summoned drop removed %s\n", mo->GetClass()->TypeName.GetChars());
	mo->Destroy();
	return true;
}

uint64_t *DD_LootMapThingSeed(FLevelLocals *Level, FMapThing *mt, int index)
{
	if (!Level || !mt || !DD_BridgeHasSession()) return nullptr;
	uint64_t h = SALT_MAPTHING;
	for (const char *c = Level->MapName.GetChars(); *c; c++) h = Mix(h, uint8_t(tolower(*c)));
	h = Mix(Mix(h, uint64_t(index)), uint64_t(mt->EdNum));
	h = Mix(Mix(Mix(h, uint64_t(llround(mt->pos.X))), uint64_t(llround(mt->pos.Y))), uint64_t(llround(mt->pos.Z)));
	mapThingState = h ? h : 1;
	return &mapThingState;
}

DEFINE_ACTION_FUNCTION(AActor, DD_LootSeed)
{
	PARAM_SELF_PROLOGUE(AActor);
	ACTION_RETURN_INT(int(uint32_t(self->ddLootId ^ (self->ddLootId >> 32))));
}

uint64_t DD_LootItemId(AActor *item)
{
	if (!item) return 0;
	if (item->ddRecordId) return item->ddRecordId;
	return item->ddLootId ? SESSION_ID | LASTING_MARK | (item->ddLootId & (LASTING_MARK - 1)) : 0;
}

// Daggerfall's location record stores a loose Doom drop without its id, and a restored one gets a new session id, so a
// gun's lasting id would be lost on leaving and coming back, and with it the material Daggerfall rolls from it. A gun
// with a lasting id is recorded as a full fact with its id instead (not a session fact; dd_treadmill.cpp ToFact).
bool DD_LootGunKeepsId(uint64_t id, FName cls)
{
	return IsSessionId(id) && (id & LASTING_MARK) && DD_LootIsGunClass(cls);
}

// A gun restored from a session fact (a record written before guns kept their ids) gets a lasting id from where it
// lies, the same on every restore of that record; from then on the record keeps it as a full fact.
uint64_t DD_LootRestoredGunId(FName cls, double x, double y, double z)
{
	if (!DD_LootIsGunClass(cls)) return 0;
	uint64_t h = Mix(Mix(Mix(SALT_FLOOR ^ 0x7265, uint64_t(llround(x * 16))), uint64_t(llround(y * 16))), uint64_t(llround(z * 16)));
	for (const char *c = cls.GetChars(); *c; c++) h = Mix(h, uint8_t(tolower(*c)));
	return SESSION_ID | LASTING_MARK | (h & (LASTING_MARK - 1));
}

// A floor gun without a lasting id (a script or console spawn) gets one when Daggerfall first names it in the look label
// or takes it, so Daggerfall's material roll for it is fixed from then on: the same in the label and at the take, saved
// (ddlootid) and kept by the treadmill and the location record as a drop's id. Called only in bridge sessions.
bool DD_LootIsGunClass(FName cls)
{
	static const FName weapon("Weapon"), drlaPickup("RLBaseWeaponPickup");
	for (const PClass *c = PClass::FindActor(cls); c; c = c->ParentClass)
		if (c->TypeName == weapon || c->TypeName == drlaPickup) return true;
	return false;
}

uint64_t DD_LootFixItemId(AActor *item)
{
	if (!item) return 0;
	const uint64_t id = DD_LootItemId(item);
	// A gun holding one of the treadmill's counter ids (a game saved before guns kept lasting ids) gets a lasting one
	// too, or its next restore would give it another counter id and another material. A session id never needs a
	// tombstone, so the old id simply goes.
	if (id && IsSessionId(id) && !(id & LASTING_MARK) && item->ddRecordId == id && DD_LootIsGunClass(item->GetClass()->TypeName))
	{
		item->ddRecordId = 0;
		item->ddLootId = 0;
	}
	else if (id) return id;
	uint64_t h = Mix(SALT_FLOOR, uint64_t(item->Level->maptime));
	h = Mix(Mix(Mix(h, uint64_t(llround(item->X() * 16))), uint64_t(llround(item->Y() * 16))), uint64_t(llround(item->Z() * 16)));
	for (const char *c = item->GetClass()->TypeName.GetChars(); *c; c++) h = Mix(h, uint8_t(tolower(*c)));
	item->ddLootId = h ? h : 1;
	return DD_LootItemId(item);
}

uint64_t *DD_AiStateFor(DThinker *th)
{
	if (!DD_BridgeHasSession() || !th->IsKindOf(RUNTIME_CLASS(AActor))) return nullptr;
	AActor *mo = static_cast<AActor *>(th);
	if (mo->player) return nullptr;
	if (!mo->ddAiRng && mo->ddRecordId && (mo->flags3 & MF3_ISMONSTER) && mo->health > 0)
		mo->ddAiRng = DD_LootSeedOf(mo->ddRecordId, SALT_LIVE);
	return mo->ddAiRng ? &mo->ddAiRng : nullptr;
}
