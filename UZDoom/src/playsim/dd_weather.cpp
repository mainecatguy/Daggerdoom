// [Doomerfall] Daggerfall's sky, time-of-day light, weather and ambient sounds, drawn and played by Doom.
//
// Daggerfall owns time and weather. DoomerfallWorldLook.cs sends what its own sky, light and weather objects show,
// as the bridge text "sky <index> <frame> <stars> <night> <ambient> <weather> <loop> <sun> [<elevation> [<winter>]]", and every ambient one-shot
// Daggerfall's AmbientEffectsPlayer plays as "amb <clip>". Doom only renders them:
//   - Sky: the DFSKY texture is rewritten from SKYnn.DAT (frame, afternoon mirror) or NITEnnI0.IMG with stars, as
//     DaggerfallSky does. Read from the arena2 folder given by -ddarena2; nothing is written to disk.
//   - Light: in exteriors, Daggerfall's daylight: its exterior ambient (PlayerAmbientLight) plus its sun light
//     (SunlightManager) on an average surface, weighted by the sun's height (a low sun lights flat ground less). The town mesh takes it as is, Doom's sectors on a curve. Interiors take
//     Daggerfall's slight night tint. Dungeons are unchanged (Daggerfall has no time of day there).
//   - Fog: Daggerfall's exponential weather fog (WeatherManager), in sector fog and on the DFMesh layer.
//   - Rain and snow: particles around the player, outdoors only (PlayerWeather).
//   - Sounds: Daggerfall's clips from DAGGER.SND, loaded into Doom's sound system when first needed.
// Without Daggerfall nothing arrives and maps keep their own sky and light. The console command dd_sky feeds a line
// by hand for tests, for example: dd_sky "sky 18 31 0 0 214 0 0 106" (summer noon, clear).

#include <chrono>
#include <cstdio>
#include <cstring>
#include <vector>

#include "actor.h"
#include "bitmap.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_player.h"
#include "doomstat.h"
#include "filesystem.h"
#include "g_levellocals.h"
#include "m_argv.h"
#include "m_random.h"
#include "p_effect.h"
#include "s_doomsound.h"
#include "s_soundinternal.h"
#include "texturemanager.h"
#include "playsim/dd_log.h"
#include "playsim/dd_towncache.h"

std::pair<PalEntry, PalEntry> &R_GetSkyCapColor(FGameTexture *tex);	// hw_skydome.cpp
int DDTreadmill_Place();	// dd_treadmill.cpp: 0 none, 1 exterior, 2 building interior, 3 dungeon

CVAR(Bool, dd_weather, true, CVAR_ARCHIVE)			// Daggerfall's sky, daylight, weather and ambient sounds.
CVAR(Float, dd_sun_share, 0.5f, CVAR_ARCHIVE)		// How much of Daggerfall's sun light an average surface gets (mean facing).
CVAR(Int, dd_daylight_max, 192, CVAR_ARCHIVE)		// Exterior sector light at full daylight (the overworld's old fixed 192).
CVAR(Int, dd_daylight_min, 70, CVAR_ARCHIVE)		// Exterior sector light at no daylight. Fitted to Daggerfall: overworld night ground about 0.2 of noon.
CVAR(Int, dd_rain_drops, 24, CVAR_ARCHIVE)			// Rain particles spawned per tic.
CVAR(Int, dd_snow_flakes, 10, CVAR_ARCHIVE)		// Snow particles spawned per tic.
CVAR(Float, dd_ambient_volume, 1.f, CVAR_ARCHIVE)	// Volume of Daggerfall's weather and ambient sounds.

float dd_fog_unit = 1.f;	// hw_lighting.cpp: a sector fog density step; finer only while Daggerfall's fog is on this map

namespace
{
enum Weather { Sunny, Cloudy, Overcast, Fog, Rain, Thunder, Snow };	// Daggerfall's WeatherType
constexpr double DOOM_PER_METER = 100 * 0.75;		// Unity units are 100 Daggerfall units; Doom maps are at 0.75.
constexpr int LOOP_CHANNEL = 77;					// player channel for the rain and cricket loops
constexpr int SKY_W = 512, SKY_H = 220, NIGHT_H = 219;
constexpr int FOG_UNITS = 16;						// sector fog density steps per Doom fog density 1

struct World { int index = -1, frame = 0, stars = 0, night = 0, ambient = 0, weather = 0, loop = 0, sun = 0, elevation = 90, winter = -1; };	// winter: -1 when not sent	// elevation: sun height in degrees, 90 when not sent
World world;
bool haveWorld;
// Unity's fog as Daggerfall draws it now, from the bridge line "fog <on> <mode> <density> <start> <end> <r> <g> <b> <sky>".
struct FogLine { int on = 0, mode = 0; float density = 0, start = 0, end = 0; int r = 0, g = 0, b = 0, sky = 0; };
FogLine fogLine;
bool haveFog;
float FogDensity();
PalEntry FogTint();
FRandom pr_weather("DDWeather");

// A plain BGRA image texture whose pixels this file rewrites.
class DDImageTexture : public FTexture
{
public:
	std::vector<uint32_t> pixels;
	DDImageTexture(int w, int h) { SetSize(w, h); pixels.resize(size_t(w) * h); }
	FBitmap GetBgraBitmap(const PalEntry *, int *) override { return FBitmap((uint8_t *)pixels.data(), Width * 4, Width, Height); }
};

DDImageTexture *skyPixels;
FGameTexture *skyTexture;
int skyShown = -1;			// key of the sky image now in the texture
PalEntry fogColor;			// Daggerfall's fog colour: the sky's lower left pixel

FString Arena2File(const char *name)
{
	const char *dir = nullptr;
	for (int i = 1; i + 1 < Args->NumArgs(); i++)
		if (!stricmp(Args->GetArg(i), "-ddarena2")) dir = Args->GetArg(i + 1);
	return dir ? FStringf("%s/%s", dir, name) : FString();
}

bool ReadPart(const char *name, long offset, void *out, long size)
{
	FString path = Arena2File(name);
	FileSys::FileReader fr;
	if (path.IsEmpty() || !fr.OpenFile(path.GetChars())) return false;
	fr.Seek(offset, FileSys::FileReader::SeekSet);
	return fr.Read(out, size) == size;
}

uint32_t Bgra(const uint8_t *palette, int index)
{
	const uint8_t *c = palette + index * 3;
	return 0xff000000u | (c[0] << 16) | (c[1] << 8) | c[2];
}

// DaggerfallSky.LoadVanillaDaySky / LoadVanillaNightSky into a 1024 x 220 [east | west] image, as the converter's DFSKY.
bool BuildSky(std::vector<uint32_t> &out)
{
	uint8_t palette[768];
	std::vector<uint8_t> east(SKY_W * SKY_H), west(SKY_W * SKY_H);
	int height = SKY_H;
	if (world.stars)
	{
		static const int nightFor[] = { 3, 1, 2 };	// sky index 0-7, 8-15, 16-23; 0 otherwise
		const int nite = world.index >= 0 && world.index < 24 ? nightFor[world.index / 8] : 0;
		height = NIGHT_H;
		if (!ReadPart(FStringf("NITE%02dI0.IMG", nite).GetChars(), 0, east.data(), SKY_W * NIGHT_H) || !ReadPart("NIGHTSKY.COL", 8, palette, 768)) return false;
		static const uint8_t starColors[] = { 16, 32, 74, 105, 112, 120 };
		for (int i = 0; i < SKY_W * NIGHT_H; i++)
			if (east[i] > 16 && east[i] < 32 && pr_weather.RandomFloat() < 0.004) east[i] = starColors[pr_weather(6)];
		for (int y = 0; y < NIGHT_H; y++) east[y * SKY_W + SKY_W - 1] = east[y * SKY_W + SKY_W - 2];	// the seam
		west = east;
	}
	else
	{
		const bool afternoon = world.frame >= 32;
		const int frame = afternoon ? 63 - world.frame : std::max(world.frame, 0);
		const FString file = FStringf("SKY%02d.DAT", world.index);
		constexpr long images = 549120;
		if (!ReadPart(file.GetChars(), 776L * frame + 8, palette, 768)
			|| !ReadPart(file.GetChars(), images + long(SKY_W * SKY_H) * frame, east.data(), SKY_W * SKY_H)
			|| !ReadPart(file.GetChars(), images + long(SKY_W * SKY_H) * (32 + frame), west.data(), SKY_W * SKY_H)) return false;
		if (afternoon) std::swap(east, west);
	}
	out.resize(size_t(2 * SKY_W) * SKY_H);
	for (int y = 0; y < SKY_H; y++)
	{
		const int sy = std::min(y, height - 1);
		for (int x = 0; x < SKY_W; x++)
		{
			out[y * 2 * SKY_W + x] = Bgra(palette, east[sy * SKY_W + x]);
			out[y * 2 * SKY_W + SKY_W + x] = Bgra(palette, west[sy * SKY_W + x]);
		}
	}
	// DaggerfallSky's clear and fog colour is west[0] of a bottom-up Unity image: the west half's lower left pixel.
	fogColor = PalEntry(out[(height - 1) * 2 * SKY_W + SKY_W]);
	return true;
}

PalEntry Average(const uint32_t *p, int count)
{
	uint64_t r = 0, g = 0, b = 0;
	for (int i = 0; i < count; i++) { PalEntry c(p[i]); r += c.r; g += c.g; b += c.b; }
	return PalEntry(255, uint8_t(r / count), uint8_t(g / count), uint8_t(b / count));
}

void UpdateSky()
{
	// Heavy fog also fogs Daggerfall's sky (excludeSkybox off, 0.05/m): at sky distance that is the fog colour alone.
	const bool fogSky = haveFog && fogLine.on && fogLine.sky && FogDensity() > 0;
	const PalEntry fogSkyColor = fogSky ? FogTint() : PalEntry(0);
	const int key = fogSky ? -2 - int(fogSkyColor.d & 0xffffff) : world.stars ? 1000 + world.index : world.index * 64 + world.frame;
	FTextureID id = TexMan.CheckForTexture("DFSKY", ETextureType::Any);
	if (!id.isValid()) return;
	FGameTexture *current = TexMan.GetGameTexture(id);
	if (current == skyTexture && key == skyShown) return;
	const auto started = std::chrono::steady_clock::now();
	std::vector<uint32_t> image;
	skyShown = key;
	if (fogSky) image.assign(size_t(2 * SKY_W) * SKY_H, uint32_t(fogSkyColor.d) | 0xff000000u);
	else if (!BuildSky(image))
	{
		DD_DebugPrintf("DDWEATHER sky %d frame %d stars %d could not be read (is -ddarena2 set?)\n", world.index, world.frame, world.stars);
		return;
	}
	if (current != skyTexture)
	{
		// A map package may have brought its own DFSKY, so take that slot over once per texture.
		skyPixels = new DDImageTexture(2 * SKY_W, SKY_H);
		skyTexture = MakeGameTexture(skyPixels, "DFSKY", ETextureType::Wall);
		skyTexture->SetUpscaleFlag(false, true);
		TexMan.ReplaceTexture(id, skyTexture, false);
	}
	skyPixels->pixels = std::move(image);
	skyTexture->CleanHardwareData();
	auto &caps = R_GetSkyCapColor(skyTexture);
	caps.first = Average(skyPixels->pixels.data(), 2 * SKY_W * 30);
	caps.second = Average(skyPixels->pixels.data() + 2 * SKY_W * (SKY_H - 30), 2 * SKY_W * 30);
	const long long us = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - started).count();
	DD_DebugPrintf("DDWEATHER sky %d frame %d%s (%lld us)\n", world.index, world.frame, fogSky ? " fogged" : world.stars ? " night with stars" : "", us);
}

// Daggerfall's fog, as a Doom fog density (fog factor exp(-density * distance / 64000)).
float FogDensity()
{
	if (haveFog)
	{
		if (!fogLine.on) return 0;
		// Doom has only exponential fog. Unity's linear fog (clear weather, 0 to 2400 m) is matched at half its
		// range, where both are half fogged; exponential squared is taken as exponential.
		const float perMeter = fogLine.mode == 1 ? (fogLine.end > fogLine.start ? float(0.69314718 /((fogLine.end - fogLine.start) / 2)) : 0.f) : fogLine.density;
		return float(perMeter * 64000 / DOOM_PER_METER);
	}
	float perMeter = 0;
	switch (world.weather)
	{
	case Rain: case Thunder: perMeter = 0.003f; break;
	case Snow: perMeter = 0.005f; break;
	case Fog: perMeter = 0.05f; break;
	}
	return float(perMeter * 64000 / DOOM_PER_METER);
}

PalEntry FogTint()
{
	// Unity's own fog colour when Daggerfall sends it; black (interiors, dungeons) is sent as the darkest colour that
	// Doom still treats as coloured fog, since Doom's black "fog" is its light-level distance shading instead.
	if (haveFog) return fogLine.r | fogLine.g | fogLine.b ? PalEntry(fogLine.r, fogLine.g, fogLine.b) : PalEntry(1, 1, 1);
	// Older Daggerfall builds: SetSkyFogColor: grey for anything denser than rain fog, otherwise the sky's colour.
	return FogDensity() > 0.003f * 64000 / DOOM_PER_METER + 0.01f ? PalEntry(128, 128, 128) : PalEntry(fogColor.r, fogColor.g, fogColor.b);
}

// Unity lights in gamma space: a surface shows albedo x (ambient + sun x facing), full at 1. Facing is the share an
// average surface gets (dd_sun_share) times the sine of the sun's height, as on flat ground; fitted to Daggerfall's
// own camera (tools/daynight/brightness.py).
float Daylight()
{
	const float facing = float(std::max(sin(world.elevation * (M_PI / 180)), 0.0));
	return world.ambient / 255.f + *dd_sun_share * facing * world.sun / 100.f;
}

int place = -1;
int64_t applied = -1;	// a key of the light state the current map's sectors hold

void ApplyLight(FLevelLocals *Level)
{
	// The DFMesh layer takes Daggerfall's daylight as it is (DD_WeatherMeshLight). Doom's own sector lighting also
	// darkens with distance, so sectors map it onto min..max: fitted so the ground's average brightness follows
	// Daggerfall's own camera across the day (tools/daynight/brightness.py, work/notes/20261125-080437-daynight.md).
	const int light = clamp(int(*dd_daylight_min + (*dd_daylight_max - *dd_daylight_min) * std::min(Daylight(), 1.f) + 0.5f), 0, 255);
	const int ground = clamp(int(std::min(Daylight(), 1.f) * 255 + 0.5f), 0, 255);
	const float density = FogDensity();
	const PalEntry tint = density > 0 ? FogTint() : PalEntry(0);
	// Interiors and dungeons take fog only when Daggerfall sends its own (older builds sent weather alone).
	const bool fog = place == 1 || (haveFog && (place == 2 || place == 3));
	const int fogUnits = fog ? int(density * FOG_UNITS + 0.5f) : 0;
	const int64_t key = (int64_t(place == 1 ? ground : 0) << 40) ^ (int64_t((place == 1 ? light : place == 2 ? 1 + world.night : 0) << 20) ^ (fogUnits << 4) ^ int(tint.d) ^ place);
	if (key == applied) return;
	applied = key;
	if (fog)
	{
		// Sector fog densities are whole numbers and Daggerfall's clear fog is about 0.5, so this level's sectors
		// hold them in 1/FOG_UNITS steps (dd_fog_unit, read by hw_lighting.cpp).
		dd_fog_unit = 1.f / FOG_UNITS;
		for (auto &sec : Level->sectors)
		{
			sec.SetFade(tint);
			sec.SetFogDensity(fogUnits);
		}
	}
	if (place == 1)
	{
		for (auto &sec : Level->sectors) sec.SetLightLevel(light);
		DD_DebugPrintf("DDWEATHER exterior light %d ground %d (ambient %d, sun %d at %d deg), weather %d, fog %.2f colour %06x, %d sectors\n", light, ground, world.ambient, world.sun, world.elevation, world.weather, density, int(tint.d & 0xffffff), int(Level->sectors.Size()));
	}
	else if (place == 2)
	{
		// PlayerAmbientLight: interiors 0.18 grey by day, (0.20, 0.18, 0.20) at night.
		const PalEntry color = world.night ? PalEntry(255, 230, 255) : PalEntry(255, 255, 255);
		for (auto &sec : Level->sectors) sec.SetColor(color, 0);
		DD_DebugPrintf("DDWEATHER interior %s, fog %.2f colour %06x\n", world.night ? "night tint" : "day", fog ? density : 0.f, int(tint.d & 0xffffff));
	}
	else if (fog)
		DD_DebugPrintf("DDWEATHER dungeon fog %.2f colour %06x\n", density, int(tint.d & 0xffffff));
}

// Daggerfall's clips, from DAGGER.SND (a number-record BSA of 8-bit mono 11025 Hz sounds), wrapped as WAV lumps.
FSoundID ClipSound(int clip)
{
	static std::vector<FSoundID> ids;
	static std::vector<uint32_t> offsets, sizes;
	static bool read;
	if (!read)
	{
		read = true;
		FString path = Arena2File("DAGGER.SND");
		FileSys::FileReader fr;
		if (!path.IsEmpty() && fr.OpenFile(path.GetChars()))
		{
			int16_t count = 0;
			uint16_t type = 0;
			fr.Read(&count, 2);
			fr.Read(&type, 2);
			const long length = long(fr.GetLength());
			if (type == 0x0200 && count > 0)
			{
				std::vector<uint32_t> dir(size_t(count) * 2);
				fr.Seek(length - 8L * count, FileSys::FileReader::SeekSet);
				fr.Read(dir.data(), 8L * count);
				uint32_t at = 4;
				for (int i = 0; i < count; i++) { offsets.push_back(at); sizes.push_back(dir[i * 2 + 1]); at += dir[i * 2 + 1]; }
			}
		}
		ids.resize(offsets.size(), INVALID_SOUND);
		DD_DebugPrintf("DDWEATHER DAGGER.SND: %d clips\n", int(offsets.size()));
	}
	if (clip < 0 || size_t(clip) >= offsets.size() || sizes[clip] == 0) return INVALID_SOUND;
	if (ids[clip] != INVALID_SOUND) return ids[clip];
	const uint32_t size = sizes[clip];
	char *wav = new char[44 + size];	// kept: the lump reads from it
	const uint32_t header[11] = { 0x46464952, 36 + size, 0x45564157, 0x20746d66, 16, 0x00010001, 11025, 11025, 0x00080001, 0x61746164, size };
	memcpy(wav, header, 44);
	if (!ReadPart("DAGGER.SND", offsets[clip], wav + 44, size)) { delete[] wav; return INVALID_SOUND; }
	const FString name = FStringf("ddsnd%03d", clip);
	const int lump = fileSystem.AddFromBuffer(name.GetChars(), wav, 44 + size, -1, 0);
	ids[clip] = soundEngine->AddSoundLump(name.GetChars(), lump, 0);
	return ids[clip];
}

// AmbientEffectsPlayer's one-shots. Storm clips come from the horizon and others from somewhere near; Doom plays
// them around the player at the listener's volume, panned for the near ones.
void PlayOneShot(int clip)
{
	if (!*dd_weather || !primaryLevel || gamestate != GS_LEVEL) return;
	AActor *pmo = primaryLevel->Players[consoleplayer]->mo;
	const FSoundID id = ClipSound(clip);
	if (!pmo || id == INVALID_SOUND) return;
	if (clip >= 348 && clip <= 350) { S_Sound(CHAN_AUTO, 0, id, *dd_ambient_volume, ATTN_NONE); return; }
	const DAngle a = DAngle::fromDeg(pr_weather.RandomFloat() * 360);
	const DVector3 at = pmo->Pos() + DVector3(a.ToVector(160), 32);
	S_Sound(primaryLevel, at, CHAN_AUTO, 0, id, *dd_ambient_volume, ATTN_NORM);
}

void TickLoop(AActor *pmo)
{
	const int clip = *dd_weather && haveWorld ? world.loop : 0;
	static int playing;
	const FSoundID id = clip ? ClipSound(clip) : INVALID_SOUND;
	if (clip == playing && (!clip || S_IsActorPlayingSomething(pmo, LOOP_CHANNEL, id))) return;
	S_StopSound(pmo, LOOP_CHANNEL);
	playing = clip;
	if (id != INVALID_SOUND) S_Sound(pmo, LOOP_CHANNEL, CHANF_LOOP | CHANF_NOPAUSE, id, *dd_ambient_volume, ATTN_NONE);
}

FTextureID RainTexture()
{
	static FTextureID id;
	if (id.isValid()) return id;
	auto *pix = new DDImageTexture(16, 16);
	for (int y = 0; y < 16; y++) pix->pixels[y * 16 + 7] = pix->pixels[y * 16 + 8] = 0xffffffffu;	// a thin vertical streak
	auto *tex = MakeGameTexture(pix, "DDRAIN", ETextureType::Override);
	TexMan.AddGameTexture(tex);
	id = tex->GetID();
	return id;
}

// PlayerWeather's rain and snow particle systems, outdoors only.
void TickParticles(FLevelLocals *Level, AActor *pmo)
{
	const bool rain = world.weather == Rain || world.weather == Thunder, snow = world.weather == Snow;
	if (!rain && !snow) return;
	const int count = rain ? *dd_rain_drops : *dd_snow_flakes;
	const DVector3 lead = pmo->Pos() + pmo->Vel * 16;
	// Unlit like Unity's particles, at the brightness of Daggerfall's daylight, so they stay pale against the sky.
	const int v = clamp(int(Daylight() * 255), 40, 255);
	for (int i = 0; i < count; i++)
	{
		const double r = (rain ? 640 : 520) * sqrt(pr_weather.RandomFloat());
		const DAngle a = DAngle::fromDeg(pr_weather.RandomFloat() * 360);
		DVector3 pos = lead + DVector3(a.ToVector(r), 0);
		if (rain)
		{
			pos.Z = pmo->Z() + 200 + pr_weather.RandomFloat() * 360;
			P_SpawnParticle(Level, pos, DVector3(0, 0, -26), DVector3(0, 0, 0), PalEntry(v * 3 / 4, v * 25 / 32, v * 13 / 16), 0.45, 24, 40, 0, 0,
				SPF_FULLBRIGHT | SPF_NO_XY_BILLBOARD | SPF_NODYNAMICLIGHTING, RainTexture(), STYLE_Translucent);
		}
		else
		{
			pos.Z = pmo->Z() + pr_weather.RandomFloat() * 420;
			const DVector3 drift(pr_weather.RandomFloat() - 0.5, pr_weather.RandomFloat() - 0.5, -2.4);
			P_SpawnParticle(Level, pos, drift, DVector3(0, 0, 0), PalEntry(v, v, v), 0.9, 160, 8, 0, 0, SPF_FULLBRIGHT | SPF_NODYNAMICLIGHTING);
		}
	}
}
}

// Daggerfall's world look, from the bridge text or dd_sky. Returns false for any other text.
bool DD_WeatherText(const char *text)
{
	World w;
	int clip;
	if (sscanf(text, "amb %d", &clip) == 1) { PlayOneShot(clip); return true; }
	FogLine f;
	if (sscanf(text, "fog %d %d %f %f %f %d %d %d %d", &f.on, &f.mode, &f.density, &f.start, &f.end, &f.r, &f.g, &f.b, &f.sky) == 9)
	{
		if (!haveFog || f.on != fogLine.on || f.mode != fogLine.mode || f.density != fogLine.density || f.end != fogLine.end || f.sky != fogLine.sky)
			DD_DebugPrintf("DDWEATHER fog from Daggerfall: on %d mode %d density %g start %g end %g colour %d %d %d sky %d\n", f.on, f.mode, f.density, f.start, f.end, f.r, f.g, f.b, f.sky);
		fogLine = f;
		haveFog = true;
		return true;
	}
	if (sscanf(text, "sky %d %d %d %d %d %d %d %d %d %d", &w.index, &w.frame, &w.stars, &w.night, &w.ambient, &w.weather, &w.loop, &w.sun, &w.elevation, &w.winter) < 8) return false;
	if (w.winter >= 0) DDTownCache::SetWinter(w.winter != 0);
	if (!haveWorld || w.weather != world.weather || w.index != world.index || w.stars != world.stars)
		DD_DebugPrintf("DDWEATHER from Daggerfall: sky %d frame %d stars %d night %d ambient %d weather %d loop %d\n", w.index, w.frame, w.stars, w.night, w.ambient, w.weather, w.loop);
	world = w;
	haveWorld = true;
	return true;
}

// Brightness for the DFMesh layer outdoors: Daggerfall's daylight, full at 1 (hw_dfmesh.cpp).
bool DD_WeatherMeshLight(float &brightness)
{
	if (!*dd_weather || !haveWorld || place != 1) return false;
	brightness = std::min(Daylight(), 1.f);
	return true;
}

// Fog for the DFMesh layer, which draws outside Doom's sector lighting (hw_dfmesh.cpp).
bool DD_WeatherFog(PalEntry &color, float &density)
{
	if (!*dd_weather || !haveWorld || place < 1 || (place != 1 && !haveFog)) return false;
	density = FogDensity();
	color = FogTint();
	return density > 0;
}

void DD_WeatherTick(FLevelLocals *Level)
{
	static int lastTime;
	if (Level->maptime < lastTime || Level->maptime <= 1) applied = -1, dd_fog_unit = 1.f;	// a new map or a load: sectors are as the map made them
	lastTime = Level->maptime;
	AActor *pmo = Level->Players[consoleplayer]->mo;
	if (!pmo) return;
	place = DDTreadmill_Place();
	TickLoop(pmo);
	if (!*dd_weather || !haveWorld) return;
	if (place == 1) UpdateSky();
	ApplyLight(Level);
	if (place == 1) TickParticles(Level, pmo);
}

CCMD(dd_sky)
{
	if (argv.argc() < 2 || !DD_WeatherText(argv[1])) Printf("usage: dd_sky \"sky <index> <frame> <stars> <night> <ambient> <weather> <loop>\" or \"amb <clip>\"\n");
}
