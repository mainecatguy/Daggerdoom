#pragma once
// [Doomerfall] Monster movement width on generated Daggerfall maps (architecture.md, World Scale and Player Size).
// Monsters keep their stock radius, so everything that hits them (hitscan, projectiles, splash, melee, scripts) is
// unchanged. Only movement collision (walls, lines, other bodies, floor and ceiling finding) uses the narrower move
// radius. The Doomerfall mod decides the factor (DoomerfallBodies.MonsterScale); off Daggerfall maps, or without the
// mod, it is 1 and every function here returns exactly what stock code used.

#include "actor.h"

extern double DD_MonsterMoveScale;	// 10.5 / 16 on Daggerfall maps, otherwise 1

// Reads the factor for the level about to be set up. Called once per level load (also for saves).
void DD_BodiesLevelStart();

// The radius a body uses for movement collision.
inline double DD_MoveRadius(const AActor *a)
{
	return DD_MonsterMoveScale != 1. && (a->flags3 & MF3_ISMONSTER) && !a->player ? a->radius * DD_MonsterMoveScale : a->radius;
}

// Radius to pass to an iterator that takes an actor: -1 (the actor's own radius, as stock code passes) unless narrowed.
inline double DD_MoveCheckRadius(const AActor *a)
{
	double r = DD_MoveRadius(a);
	return r == a->radius ? -1 : r;
}

// How close two bodies may come when `mover` moves. A missile or a charging Lost Soul is an attack, so it touches
// the stock edge; a walking body uses both move radii.
inline double DD_BlockDist(const AActor *mover, const AActor *other)
{
	if (mover->flags & (MF_MISSILE | MF_SKULLFLY)) return mover->radius + other->radius;
	return DD_MoveRadius(mover) + DD_MoveRadius(other);
}
