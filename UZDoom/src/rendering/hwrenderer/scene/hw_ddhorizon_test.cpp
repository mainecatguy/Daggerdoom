// [Doomerfall] Test only, active with -ddhorizontest: set dd_horizon_dump to "<x> <y> <radius> <file>" (map units) to
// write the distant view's near nature flats within radius of x,y, one per line: dx dy z texture-name. The first line
// says whether the ring's flats were fully built. tools/nature/town_lookback.py sets it from its ZScript harness.

#include <cmath>
#include <cstdio>
#include <vector>

#include "c_cvars.h"
#include "m_argv.h"
#include "filesystem.h"
#include "texturemanager.h"
#include "hw_ddhorizon.h"

CUSTOM_CVAR(String, dd_horizon_dump, "", CVAR_NOSAVE | CVAR_MOD)
{
	double x, y, radius;
	char file[512];
	bool enabled = false;
	for (int i = 1; i < Args->NumArgs(); i++) enabled |= !stricmp(Args->GetArg(i), "-ddhorizontest");
	if (!enabled || sscanf(*self, "%lf %lf %lf %511s", &x, &y, &radius, file) != 4) return;
	std::vector<DDHorizonPlacedFlat> flats;
	const bool complete = DDHorizon_NearFlats(flats);
	FILE *f = fopen(file, "w");
	if (!f) return;
	fprintf(f, "complete %d\n", complete ? 1 : 0);
	for (const DDHorizonPlacedFlat &fl : flats)
		if (std::hypot(fl.x - x, fl.y - y) <= radius)
		{
			FGameTexture *tex = TexMan.GameByIndex(fl.texture);
			// Named as ZScript's TexMan.GetName names it: a full path texture by its source lump.
			const FString name = !tex ? FString("-") : tex->GetName().IsNotEmpty() ? tex->GetName() : FString(fileSystem.GetFileFullName(tex->GetSourceLump()));
			fprintf(f, "%.2f %.2f %.2f %s\n", fl.x - x, fl.y - y, fl.z, name.GetChars());
		}
	fclose(f);
}
