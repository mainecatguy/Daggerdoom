// [Doomerfall] Quest follower faces on Doom's HUD (card questfaces).
// In:  DFB_FACES_SLOT, which Daggerfall rewrites whenever the face list of its own HUD changes (DoomerfallFaces.cs).
// Out: a small row of the same portraits near the top left of the screen.
// Daggerfall owns the list, its saves, and its loads. Doom keeps no faces of its own: it shows exactly what the newest
// slot version holds, so a face Daggerfall drops (or a load does not have) disappears here too.

#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "am_map.h"
#include "bitmap.h"
#include "d_player.h"
#include "doomstat.h"
#include "gamestate.h"
#include "printf.h"
#include "texturemanager.h"
#include "textures.h"
#include "v_draw.h"
#include "v_video.h"

void DD_BridgeLog(const char *text);
bool DD_BridgeUiActive();
void DD_FaceTestFrame(dfb_session *session, int count, uint32_t version); // dd_facetest.cpp, test only

namespace
{
// Placement on Doom's screen, in Daggerfall's 320x200 HUD units scaled to the screen height. Daggerfall itself draws
// the faces at full size in a column at (8, 36); Doom shows them at FaceScale of that size in a row, below the lines
// of pickup and Daggerfall messages at the top left and away from the combat HUD at the bottom.
constexpr double FaceScale = 0.45;
constexpr double RowX = 4, RowY = 44, Gap = 3;

class DDFaceTexture : public FTexture
{
	TArray<uint8_t> image;

public:
	void SetPixels(const uint8_t *bgra, int width, int height)
	{
		FTexture::SetSize(width, height);
		image.Resize(width * height * 4);
		memcpy(image.Data(), bgra, image.Size());
	}

	FBitmap GetBgraBitmap(const PalEntry *, int *) override
	{
		return FBitmap(image.Data(), Width * 4, Width, Height);
	}
};

struct Face
{
	FGameTexture *texture;
	DDFaceTexture *pixels;
	int displayWidth, displayHeight;
};

Face faces[DFB_FACES_MAX];
int faceCount;
uint32_t slotVersion;
TArray<uint8_t> slot;

Face &EnsureTexture(int i)
{
	static const char *const names[DFB_FACES_MAX] = { "DoomerfallFace1", "DoomerfallFace2", "DoomerfallFace3" };
	Face &face = faces[i];
	FGameTexture *found = TexMan.FindGameTexture(names[i], ETextureType::Override);
	if (!found || found != face.texture)
	{
		face.pixels = new DDFaceTexture;
		face.texture = MakeGameTexture(face.pixels, names[i], ETextureType::Override);
		face.texture->SetUpscaleFlag(false, true);
		TexMan.AddGameTexture(face.texture);
	}
	return face;
}

// Takes the newest slot version. A version that does not parse clears the row, because Doom must never show a face
// Daggerfall no longer has.
void Refresh(dfb_session *session)
{
	if (dfb_bulk_version(session, DFB_FACES_SLOT) == slotVersion) return;
	slot.Resize(DFB_BULK_BYTES);
	uint32_t size = 0, version = 0;
	if (dfb_bulk_read(session, DFB_FACES_SLOT, slot.Data(), slot.Size(), &size, &version) != DFB_GOT) return; // Busy: next frame.
	slotVersion = version;
	faceCount = 0;
	dfb_faces head;
	if (size < sizeof(head)) return;
	memcpy(&head, slot.Data(), sizeof(head));
	if (head.format != DFB_FACES_FORMAT_VERSION || head.count > DFB_FACES_MAX) return;
	uint32_t at = sizeof(head);
	for (uint32_t i = 0; i < head.count; i++)
	{
		dfb_face face;
		if (size - at < sizeof(face)) break;
		memcpy(&face, slot.Data() + at, sizeof(face));
		at += sizeof(face);
		const uint32_t bytes = face.width * face.height * 4;
		if (!face.width || !face.height || face.width > DFB_FACE_MAX_SIDE || face.height > DFB_FACE_MAX_SIDE || size - at < bytes) break;
		Face &shown = EnsureTexture(faceCount);
		shown.pixels->SetPixels(slot.Data() + at, face.width, face.height);
		shown.texture->SetSize(face.width, face.height);
		shown.texture->CleanHardwareData();
		shown.displayWidth = face.display_width ? face.display_width : face.width;
		shown.displayHeight = face.display_height ? face.display_height : face.height;
		at += bytes;
		faceCount++;
	}
	char line[96];
	snprintf(line, sizeof(line), "faces: read v%u, %d face(s)", version, faceCount);
	DD_BridgeLog(line);
}
}

void DD_FacesFrame(dfb_session *session)
{
	if (!session) return;
	Refresh(session);
	DD_FaceTestFrame(session, faceCount, slotVersion);
}

// Drawn with the status bar, so it is hidden with the HUD, on the automap, and behind Daggerfall's menus.
void DD_FacesDraw()
{
	if (!faceCount || gamestate != GS_LEVEL || automapactive || DD_BridgeUiActive() || consoleplayer < 0) return;
	const player_t &player = players[consoleplayer];
	if (!player.mo || player.camera != player.mo) return;
	const double unit = twod->GetHeight() / 200.0;
	double x = RowX * unit;
	const double y = RowY * unit;
	for (int i = 0; i < faceCount; i++)
	{
		const Face &face = faces[i];
		const double w = face.displayWidth * unit * FaceScale, h = face.displayHeight * unit * FaceScale;
		DrawTexture(twod, face.texture, x, y, DTA_DestWidthF, w, DTA_DestHeightF, h, DTA_LeftOffset, 0, DTA_TopOffset, 0, TAG_DONE);
		x += w + Gap * unit * FaceScale;
	}
}
