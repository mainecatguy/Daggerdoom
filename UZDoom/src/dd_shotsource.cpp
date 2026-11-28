// [Doomerfall] Exact spawn parents for the Doomerfall mod's shot tags (mods/doomerfall/src/zscript/DoomerfallShots.zs).
//
// When an actor is spawned, the actor responsible is the one whose state action, PostBeginPlay or death is running
// (DD_ActingActor, dd_lootrng.h), or else the actor whose Tick is running (a ZScript Tick override that spawns trails
// or fragments, or a missile exploding as it moves). The new actor records that parent's spawn serial in ddSpawnedBy.
// Serials are handed out lazily (to actors that spawn something, or that the mod asks about) from a counter that never
// repeats in a run.
// Neither field is saved: a game loaded from a save hands out new serials, and the mod only reads ddSpawnedBy in the
// tic an actor is spawned. Nothing is recorded outside bridge sessions, so stock Doom never touches these fields.

#include "actor.h"
#include "dd_lootrng.h"
#include "dd_shotsource.h"
#include "vm.h"

bool DD_BridgeHasSession();

DThinker *DD_TickingThinker;

namespace
{
	uint32_t nextSerial;

	uint32_t SerialOf(AActor *mo)
	{
		if (!mo->ddSerial)
		{
			if (++nextSerial == 0) nextSerial = 1;
			mo->ddSerial = nextSerial;
		}
		return mo->ddSerial;
	}
}

void DD_ShotSourceSpawned(AActor *mo)
{
	if (!DD_BridgeHasSession()) return;
	AActor *from = DD_ActingActor;
	if (!from && DD_TickingThinker && DD_TickingThinker->IsKindOf(RUNTIME_CLASS(AActor))) from = static_cast<AActor *>(DD_TickingThinker);
	if (from && from != mo && !(from->ObjectFlags & OF_EuthanizeMe)) mo->ddSpawnedBy = SerialOf(from);
}

// The serial of the actor that spawned this one, or 0 when unknown (spawned by the map, a script or the level).
DEFINE_ACTION_FUNCTION(AActor, DD_SpawnedBy)
{
	PARAM_SELF_PROLOGUE(AActor);
	ACTION_RETURN_INT(int(self->ddSpawnedBy));
}

// This actor's spawn serial, handed out now if it has none, so the mod can file a shot's tag under the serial its
// children will name (DD_SpawnedBy) before it spawns any of them.
DEFINE_ACTION_FUNCTION(AActor, DD_SpawnSerial)
{
	PARAM_SELF_PROLOGUE(AActor);
	ACTION_RETURN_INT(int(SerialOf(self)));
}
