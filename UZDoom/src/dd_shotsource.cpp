// [Doomerfall] Exact spawn parents for the Doomerfall mod's shot tags (mods/doomerfall/src/zscript/DoomerfallShots.zs).
//
// When an actor is spawned, its parent is the actor whose state action, PostBeginPlay or death is running
// (DD_ShotActing, set by DDShotScope beside the fixed-loot scopes in FState::CallAction, CallPostBeginPlay and Die).
// Nothing else counts: not the actor whose Tick is running (blood a missile sheds as it moves is not its shot), and
// nobody inside damage processing or blood spawning (P_DamageMobj, DoDamageMobj, P_SpawnBlood, P_BloodSplatter*,
// P_RipperBlood, P_TraceBleed set it to null), so things spawned on a hit, such as a damage handler's splash, are
// nobody's shots; a victim's death inside the damage sets it again to the victim. A missile that explodes is in its
// death state's actions, so what it spawns there names it. The new actor records the parent's spawn serial in
// ddSpawnedBy. Serials are handed out lazily (to actors that spawn something, or when the mod asks) from a counter that
// never repeats in a run. Neither field is saved: a game loaded from a save hands out new serials, and the mod only
// reads ddSpawnedBy in the tic an actor is spawned. Nothing is recorded outside bridge sessions.

#include "actor.h"
#include "dd_shotsource.h"
#include "vm.h"

bool DD_BridgeHasSession();

AActor *DD_ShotActing;

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
	AActor *from = DD_ShotActing;
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
