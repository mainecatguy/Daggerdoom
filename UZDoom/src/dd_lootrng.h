#pragma once
// [Doomerfall] Fixed loot for Doom's own drops (dd_lootrng.cpp). Inactive on every stock actor and outside bridge sessions.
#include <stdint.h>
#include "m_random.h"

class AActor;
class DThinker;
class FLevelLocals;
struct FMapThing;

// Draws every gameplay random number from one loot state while it lives. Null or zero state: no change.
extern AActor *DD_LootOwner;	// The actor whose loot state is running, or null for a raw state.
struct DDLootScope
{
	uint64_t *prev;
	AActor *prevOwner;
	bool active;
	explicit DDLootScope(uint64_t *state, AActor *owner = nullptr) : prev(DD_RngOverride), prevOwner(DD_LootOwner), active(state && *state)
	{
		if (active) { DD_RngOverride = state; DD_LootOwner = owner; }
	}
	explicit DDLootScope(AActor *mo);
	~DDLootScope() { if (active) { DD_RngOverride = prev; DD_LootOwner = prevOwner; } }
	DDLootScope(const DDLootScope &) = delete;
	DDLootScope &operator=(const DDLootScope &) = delete;
};

uint64_t DD_LootSeedOf(uint64_t id, uint64_t salt);	// A nonzero loot state from a fixed identity.
void DD_LootDied(AActor *mo);			// A monster with a Daggerfall id starts dying: seed its loot state from that id.
void DD_LootInherit(AActor *mo);		// Spawned during a loot roll: a drop, a drop helper or a spawner gets its own state.
uint64_t *DD_LootMapThingSeed(FLevelLocals *Level, FMapThing *mt, int index);	// Null outside bridge sessions.
uint64_t DD_LootItemId(AActor *item);	// The lasting id of a floor item, or 0 when it has none.
bool DD_LootVanish(AActor *mo);			// A loose item a dying summoned monster made: destroyed, true. Never true outside bridge sessions.
uint64_t *DD_AiStateFor(DThinker *th);	// The live random state a thinker ticks under, or null (always null outside bridge sessions).
