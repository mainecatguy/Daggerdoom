// [Doomerfall] Distant terrain view for Daggerfall exteriors. See hw_ddhorizon.cpp.
#pragma once

struct HWDrawInfo;
class FRenderState;

void DDHorizon_Draw(HWDrawInfo *di, FRenderState &state);	// does nothing off Daggerfall exteriors

#include <vector>
// The ring's near nature flats in map coordinates (tile corner, ground height minus sink) and texture index. Returns
// false until the ring's flats are fully built for the current view. Read by hw_ddhorizon_test.cpp.
struct DDHorizonPlacedFlat { double x, y, z; int texture; };
bool DDHorizon_NearFlats(std::vector<DDHorizonPlacedFlat> &out);
