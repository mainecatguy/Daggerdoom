// [Doomerfall] Monster movement width on Daggerfall maps. See dd_bodies.h.

#include "dd_bodies.h"
#include "c_cvars.h"
#include "vm.h"

double DD_MonsterMoveScale = 1.;

// Read-only report of the factor on the current map, for test tools that cannot depend on the Doomerfall mod.
CVAR(Float, dd_monstermovescale, 1.f, CVAR_NOSET | CVAR_NOSAVE)

void DD_BodiesLevelStart()
{
	VMFunction *scale = nullptr;	// looked up each level: cheap, and survives a restart that recompiles scripts
	PClass::FindFunction(&scale, "DoomerfallBodies", "MonsterScale");
	double s = 1.;
	if (scale)
	{
		VMReturn ret(&s);
		VMCall(scale, nullptr, 0, &ret, 1);
	}
	DD_MonsterMoveScale = s > 0 && s < 1 ? s : 1.;
	dd_monstermovescale = (float)DD_MonsterMoveScale;
}
