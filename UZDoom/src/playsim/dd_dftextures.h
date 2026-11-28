// [Doomerfall] Daggerfall billboard images read at run time (dd_dftextures.cpp).
#pragma once

#include "texturemanager.h"
#include "vectors.h"

struct DDDfImage
{
	FTextureID tex;		// invalid when neither the game file nor a texture pack has the image
	DVector2 scale;		// actor Scale that gives the billboard Daggerfall's size in Doom units
};

// Frame `frame` of Daggerfall billboard archive:record. Read from TEXTURE.### in the -ddarena2 folder, or from a
// Daggerfall Unity texture pack's loose replacement (-ddtextures folder, named as Daggerfall Unity names it,
// "381_0-0.png"). A replacement keeps the original's size in the world, as in Daggerfall Unity. Nothing is written.
DDDfImage DD_DfBillboard(int archive, int record, int frame);

// Frames in archive:record, or 0 when the archive cannot be read.
int DD_DfFrames(int archive, int record);
