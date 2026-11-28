#pragma once
// [Doomerfall] Which actor spawned which (dd_shotsource.cpp), so the Doomerfall mod can pass a gun's shot tag to exactly
// the things a shot spawns. Records nothing outside bridge sessions: stock Doom and standard WADs are unchanged.

class AActor;

// The actor whose state action, PostBeginPlay or death is running: what it spawns names it as the parent. Null inside
// damage processing and blood spawning (DDShotScope(nullptr)), so blood and things spawned on a hit (a damage
// handler's splash) are nobody's shots.
extern AActor *DD_ShotActing;
struct DDShotScope
{
	AActor *prev;
	explicit DDShotScope(AActor *mo) : prev(DD_ShotActing) { DD_ShotActing = mo; }
	~DDShotScope() { DD_ShotActing = prev; }
	DDShotScope(const DDShotScope &) = delete;
	DDShotScope &operator=(const DDShotScope &) = delete;
};

void DD_ShotSourceSpawned(AActor *mo);	// Just spawned: remember DD_ShotActing as its parent (ddSpawnedBy).
