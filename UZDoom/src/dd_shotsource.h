#pragma once
// [Doomerfall] Which actor spawned which (dd_shotsource.cpp), so the Doomerfall mod can pass a gun's shot tag to exactly
// the things a shot spawns. Records nothing outside bridge sessions: stock Doom and standard WADs are unchanged.

class AActor;
class DThinker;

extern DThinker *DD_TickingThinker;	// The thinker whose Tick is running (scoped by DDTickScope).
struct DDTickScope
{
	DThinker *prev;
	explicit DDTickScope(DThinker *th) : prev(DD_TickingThinker) { DD_TickingThinker = th; }
	~DDTickScope() { DD_TickingThinker = prev; }
	DDTickScope(const DDTickScope &) = delete;
	DDTickScope &operator=(const DDTickScope &) = delete;
};

void DD_ShotSourceSpawned(AActor *mo);	// Just spawned: remember the actor whose action or tick made it (ddSpawnedBy).
