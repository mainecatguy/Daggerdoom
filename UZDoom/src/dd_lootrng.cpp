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
// Living monsters, players and missiles never carry a loot state, so combat and AI randomness stay as they were. A
// revived monster drops its state (AActor::Revive). Stock games never set ddRecordId and have no bridge session, so
// nothing here runs for them.
#include "dd_lootrng.h"
#include <unordered_map>
#include "actor.h"
#include "doomdata.h"
#include "g_levellocals.h"
#include "vm.h"

bool DD_BridgeHasSession();

namespace
{
	constexpr uint64_t DYNAMIC_BIT = 1ull << 63, ID_MASK = (1ull << 61) - 1;	// As dd_treadmill.cpp's session ids.
	constexpr uint64_t SALT_DEATH = 0x6c6f6f7464656164ull, SALT_MAPTHING = 0x6c6f6f746d617074ull;

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

AActor *DD_LootOwner;

DDLootScope::DDLootScope(AActor *mo) : DDLootScope(mo && mo->ddLootRng ? &mo->ddLootRng : nullptr, mo) {}

uint64_t DD_LootSeedOf(uint64_t id, uint64_t salt)
{
	const uint64_t s = Mix(Mix(0x446f6f6d6572666cull, salt), id);
	return s ? s : 1;
}

void DD_LootDied(AActor *mo)
{
	if (!mo->ddRecordId || mo->player) return;
	mo->ddLootRng = mo->ddLootId = DD_LootSeedOf(mo->ddRecordId, SALT_DEATH);
	if (spawnCounts.size() > 100000) spawnCounts.clear();	// Only dead owners' finished counts are lost.
	spawnCounts.erase(mo);
}

void DD_LootInherit(AActor *mo)
{
	if (!DD_RngOverride || mo->player || (mo->flags3 & MF3_ISMONSTER) || (mo->flags & MF_MISSILE)) return;
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
	spawnCounts.erase(mo);
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
	return item->ddLootId ? DYNAMIC_BIT | (item->ddLootId & ID_MASK) : 0;
}
