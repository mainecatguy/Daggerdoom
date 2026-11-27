// [Doomerfall] Test only, active with -ddnaturetest: dd_nature_dump <mapPixelX> <mapPixelY> <file> writes a map pixel's
// nature layout (Daggerfall Unity's map pixel numbering), which tools/nature compares with Daggerfall Unity's own.
// Needs a running overworld.

#include <cstdio>
#include <cstdlib>

#include "c_dispatch.h"
#include "m_argv.h"
#include "dd_nature.h"

const std::vector<DDNatureFlat> *DDTreadmill_NatureOf(int px, int north);	// dd_treadmill.cpp

CCMD(dd_nature_dump)
{
	bool enabled = false;
	for (int i = 1; i < Args->NumArgs(); i++) enabled |= !stricmp(Args->GetArg(i), "-ddnaturetest");
	if (!enabled || argv.argc() < 4) return;
	constexpr int WORLD_H = 500;
	const int px = atoi(argv[1]), north = WORLD_H - 1 - atoi(argv[2]);
	const std::vector<DDNatureFlat> *flats = DDTreadmill_NatureOf(px, north);
	FILE *f = fopen(argv[3], "w");
	if (!f) return;
	fprintf(f, "pixel %d %d archive %d flats %d\n", px, atoi(argv[2]), DDNature_Archive(px, north, false), flats ? int(flats->size()) : -1);
	if (flats) for (const DDNatureFlat &n : *flats) fprintf(f, "%d %d %d\n", n.x, n.y, n.record);
	fclose(f);
}
