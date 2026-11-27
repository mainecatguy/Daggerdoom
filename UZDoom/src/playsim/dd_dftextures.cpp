// [Doomerfall] Daggerfall billboard images (people, corpses, blood, creatures), read at run time.
//
// Daggerfall Unity reads TEXTURE.### from the game's ARENA2 folder (TextureFile.cs) and lets a texture pack replace
// any image with a loose PNG in StreamingAssets/Textures (TextureReplacement.cs, named "archive_record-frame.png").
// This does the same: nothing is extracted or written to disk, so a texture pack that changes an image in Daggerfall
// Unity changes it in Doom too. The folders come from -ddarena2 and -ddtextures (the launcher adds -ddtextures).
// Daggerfall Unity mods packed as .dfmod are Unity asset bundles, which Doom cannot read.
// Nothing here runs until a Daggerfall billboard is asked for.

#include <cstring>
#include <map>
#include <memory>
#include <vector>

#include "bitmap.h"
#include "cmdlib.h"
#include "files.h"
#include "m_argv.h"
#include "printf.h"
#include "stb_image.h"
#include "texturemanager.h"
#include "textures.h"
#include "playsim/dd_dftextures.h"
#include "playsim/dd_log.h"

namespace
{
constexpr double DoomPerDf = 0.75;	// PlayerScale.DoomUnitsPerDaggerfallUnit
constexpr int ScaleDivisor = 256;	// BlocksFile.ScaleDivisor

// A BGRA image held in memory.
class DDBillboardTexture : public FTexture
{
public:
	std::vector<uint32_t> pixels;
	DDBillboardTexture(int w, int h, std::vector<uint32_t> &&p) : pixels(std::move(p)) { SetSize(w, h); }
	FBitmap GetBgraBitmap(const PalEntry *, int *) override { return FBitmap((uint8_t *)pixels.data(), Width * 4, Width, Height); }
};

struct Record { int width = 0, height = 0, compression = 0, frames = 0, scaleX = 0, scaleY = 0; long position = 0, dataOffset = 0; };
struct Archive { bool ok = false; std::vector<uint8_t> bytes; std::vector<Record> records; };

std::map<int, Archive> archives;
std::map<int64_t, DDDfImage> images;
uint8_t palette[768];
bool paletteRead, paletteOk;

const char *ArgFolder(const char *name)
{
	for (int i = 1; i + 1 < Args->NumArgs(); i++)
		if (!stricmp(Args->GetArg(i), name)) return Args->GetArg(i + 1);
	return nullptr;
}

bool ReadWhole(const FString &path, std::vector<uint8_t> &out)
{
	FileSys::FileReader fr;
	if (path.IsEmpty() || !fr.OpenFile(path.GetChars())) return false;
	out.resize(fr.GetLength());
	return fr.Read(out.data(), (long)out.size()) == (long)out.size();
}

int I16(const std::vector<uint8_t> &b, size_t at) { return at + 2 <= b.size() ? int16_t(b[at] | b[at + 1] << 8) : 0; }
int U16(const std::vector<uint8_t> &b, size_t at) { return at + 2 <= b.size() ? int(b[at] | b[at + 1] << 8) : 0; }
long I32(const std::vector<uint8_t> &b, size_t at) { return at + 4 <= b.size() ? long(int32_t(b[at] | b[at + 1] << 8 | b[at + 2] << 16 | uint32_t(b[at + 3]) << 24)) : 0; }

// TextureFile.ReadHeader, ReadRecordHeaders and ReadRecords.
const Archive &ArchiveFor(int archive)
{
	auto found = archives.find(archive);
	if (found != archives.end()) return found->second;
	Archive &a = archives[archive];
	const char *dir = ArgFolder("-ddarena2");
	if (!dir || !ReadWhole(FStringf("%s/TEXTURE.%03d", dir, archive), a.bytes) || a.bytes.size() < 26)
	{
		DD_DebugPrintf("DDDFTEX TEXTURE.%03d could not be read (is -ddarena2 set?)\n", archive);
		return a;
	}
	const int count = I16(a.bytes, 0);
	for (int r = 0; r < count; r++)
	{
		Record rec;
		rec.position = I32(a.bytes, 26 + r * 20 + 2);
		const size_t p = rec.position;
		rec.width = I16(a.bytes, p + 4);
		rec.height = I16(a.bytes, p + 6);
		rec.compression = U16(a.bytes, p + 8);
		rec.dataOffset = I32(a.bytes, p + 14);
		rec.frames = U16(a.bytes, p + 20);
		rec.scaleX = I16(a.bytes, p + 24);
		rec.scaleY = I16(a.bytes, p + 26);
		a.records.push_back(rec);
	}
	a.ok = true;
	return a;
}

bool ReadPalette()
{
	if (paletteRead) return paletteOk;
	paletteRead = true;
	std::vector<uint8_t> col;
	const char *dir = ArgFolder("-ddarena2");
	paletteOk = dir && ReadWhole(FStringf("%s/ART_PAL.COL", dir), col) && col.size() >= 8 + 768;	// a .COL file has an 8 byte header
	if (paletteOk) memcpy(palette, col.data() + 8, 768);
	return paletteOk;
}

// TextureFile.ReadImage and ReadRle: palette indices, 0 transparent.
bool Decode(const Archive &a, const Record &rec, int frame, std::vector<uint8_t> &out)
{
	const std::vector<uint8_t> &b = a.bytes;
	const int w = rec.width, h = rec.height;
	if (w <= 0 || h <= 0 || frame < 0 || frame >= std::max(rec.frames, 1)) return false;
	out.assign(size_t(w) * h, 0);
	size_t pos = rec.position + rec.dataOffset;
	auto byteAt = [&](size_t at) -> uint8_t { return at < b.size() ? b[at] : 0; };
	if (rec.compression == 0x0108 || rec.compression == 0x1108)
	{
		size_t headers = pos + size_t(h) * frame * 4;
		size_t dst = 0;
		for (int y = 0; y < h; y++)
		{
			size_t row = rec.position + I16(b, headers + y * 4);	// signed, as TextureFile reads it
			const bool rle = U16(b, headers + y * 4 + 2) == 0x8000;
			if (!rle)
			{
				for (int x = 0; x < w && dst < out.size(); x++) out[dst++] = byteAt(row + x);
				continue;
			}
			const int rowWidth = U16(b, row);
			row += 2;
			int done = 0;
			while (done < rowWidth && row < b.size())
			{
				int probe = I16(b, row);
				row += 2;
				if (probe < 0)
				{
					const uint8_t pixel = byteAt(row++);
					for (int i = 0; i < -probe && dst < out.size(); i++, done++) out[dst++] = pixel;
				}
				else if (probe > 0)
				{
					for (int i = 0; i < probe && dst < out.size(); i++, done++) out[dst++] = byteAt(row++);
				}
				else break;
			}
		}
		return true;
	}
	if (rec.frames <= 1)
	{
		for (int y = 0; y < h; y++)
			for (int x = 0; x < w; x++) out[size_t(y) * w + x] = byteAt(pos + size_t(y) * 256 + x);
		return true;
	}
	// Several uncompressed frames: an offset list, then each frame's rows as (transparent run, pixel run) pairs.
	size_t at = pos + I32(b, pos + frame * 4);
	const int cx = I16(b, at), cy = I16(b, at + 2);
	at += 4;
	for (int y = 0; y < cy && y < h; y++)
	{
		int x = 0;
		while (x < cx && at < b.size())
		{
			int run = byteAt(at++);
			for (int i = 0; i < run && x < cx; i++, x++) if (x < w) out[size_t(y) * w + x] = 0;
			run = byteAt(at++);
			for (int i = 0; i < run && x < cx; i++, x++) { const uint8_t p = byteAt(at++); if (x < w) out[size_t(y) * w + x] = p; }
		}
	}
	return true;
}

// A texture pack's loose replacement, as BGRA. False when there is none.
bool ReadReplacement(int archive, int record, int frame, int &w, int &h, std::vector<uint32_t> &out, FString &path)
{
	const char *dir = ArgFolder("-ddtextures");
	if (!dir) return false;
	path = FStringf("%s/%03d_%d-%d.png", dir, archive, record, frame);
	std::vector<uint8_t> file;
	if (!ReadWhole(path, file)) return false;
	int channels = 0;
	uint8_t *rgba = stbi_load_from_memory(file.data(), (int)file.size(), &w, &h, &channels, 4);
	if (!rgba) return false;
	out.resize(size_t(w) * h);
	for (size_t i = 0; i < out.size(); i++)
	{
		const uint8_t *c = rgba + i * 4;
		out[i] = uint32_t(c[3]) << 24 | c[0] << 16 | c[1] << 8 | c[2];
	}
	stbi_image_free(rgba);
	return true;
}
}

int DD_DfFrames(int archive, int record)
{
	const Archive &a = ArchiveFor(archive);
	if (!a.ok || record < 0 || record >= (int)a.records.size()) return 0;
	return std::max(a.records[record].frames, 1);
}

DDDfImage DD_DfBillboard(int archive, int record, int frame)
{
	const int64_t key = int64_t(archive) << 32 | int64_t(record) << 16 | frame;
	auto found = images.find(key);
	if (found != images.end()) return found->second;
	DDDfImage &image = images[key];
	const Archive &a = ArchiveFor(archive);
	if (!a.ok || record < 0 || record >= (int)a.records.size()) return image;
	const Record &rec = a.records[record];
	std::vector<uint8_t> indices;
	if (!ReadPalette() || !Decode(a, rec, frame, indices)) return image;
	const int w = rec.width, h = rec.height;
	int tw = w, th = h;
	std::vector<uint32_t> pixels;
	FString path;
	const bool replaced = ReadReplacement(archive, record, frame, tw, th, pixels, path);
	if (!replaced)
	{
		pixels.resize(indices.size());
		for (size_t i = 0; i < indices.size(); i++)
		{
			const uint8_t *c = palette + indices[i] * 3;
			pixels[i] = indices[i] ? 0xff000000u | c[0] << 16 | c[1] << 8 | c[2] : 0;
		}
	}
	auto *tex = MakeGameTexture(new DDBillboardTexture(tw, th, std::move(pixels)), FStringf("DFBB%03d_%d_%d", archive, record, frame).GetChars(), ETextureType::Special);
	tex->SetDisplaySize(float(w), float(h));		// a replacement keeps the original's size
	tex->SetOffsets(tw / 2, th);					// billboards stand on their base
	image.tex = TexMan.AddGameTexture(tex);
	// MeshReader.GetBillboardMesh: each axis grows by a truncated fraction of its pixel size.
	const int xChange = int(w * (rec.scaleX / double(ScaleDivisor))), yChange = int(h * (rec.scaleY / double(ScaleDivisor)));
	image.scale = DVector2(DoomPerDf * (w + xChange) / w, DoomPerDf * (h + yChange) / h);
	if (replaced) DD_DebugPrintf("DDDFTEX %d_%d-%d from the texture pack: %s (%dx%d shown at %dx%d)\n", archive, record, frame, path.GetChars(), tw, th, w, h);
	return image;
}
