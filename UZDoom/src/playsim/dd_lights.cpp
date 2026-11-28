// [Doomerfall] Daggerfall's light sprites (texture archive 210) give light, as in Daggerfall Unity.
// Interior lamps: DaggerfallInterior.AddLight (position and per-record range, intensity, and color), always on.
// Town lamps: RMBLayout.AddLight and the City light prefab, on only while Daggerfall's clock says city lights are on
// (DaggerfallLight, WorldTime.Now.IsCityLightsOn). Daggerfall sends that as the bridge text "citylights 0" or "1".
// Dungeon lights come from the dungeon's RDB light records and are spawned by the converter's action_objects.zs.
//
// A light is a user light attached to the billboard actor, so it goes away with the billboard and is saved with it.
// Daggerfall Unity's ranges are Unity point light ranges, whose falloff is much steeper than Doom's linear one.
// dd_light_range scales them to a Doom radius (see the task notes for the comparison).

#include <cstdio>
#include <cstring>
#include <unordered_map>

#include "actor.h"
#include "a_dynlight.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "printf.h"
#include "texturemanager.h"
#include "playsim/dd_log.h" // [Doomerfall]

int AttachLightDirect(AActor *self, int _lightid, int type, int color, int radius1, int radius2, int flags, double ofs_x, double ofs_y, double ofs_z, double param, double spoti, double spoto, double spotp, double intensity);
int RemoveLight(AActor *self, int _lightid);
int DDTreadmill_Place();	// dd_treadmill.cpp: 0 none, 1 exterior, 2 interior, 3 dungeon

CVAR(Bool, dd_lights, true, CVAR_ARCHIVE)				// Daggerfall's lights in generated places.
CVAR(Float, dd_light_range, 0.4f, CVAR_ARCHIVE)			// Doom light reach per Daggerfall Unity light range.
// Sector light in dungeons that have light records (176 before lights, then 112 as dd_dungeon_light, which old
// configs still hold and the dungeon script still reads). Daggerfall Unity's dungeon ambient is 0.12 of full, and the
// DFMesh layer shows sector light / 176, so 0.12 would be 21; 32 fits Daggerfall Unity's camera best with the torch on
// (tools/lightparity, work/notes/20261128-021156.md).
CVAR(Int, dd_dungeon_ambient, 32, CVAR_ARCHIVE)
CVAR(Bool, dd_torch, true, CVAR_ARCHIVE)				// Daggerfall Unity's player torch in dungeons.
CVAR(Float, dd_torch_range, 1.f, CVAR_ARCHIVE)			// Torch reach per Daggerfall Unity's (scaled like dd_light_range).
CVAR(Int, dd_interior_light, 48, CVAR_ARCHIVE)			// Sector light in building interiors (was 176).
CVAR(Int, dd_citylights, -1, CVAR_NOSAVE)				// -1 follows Daggerfall's clock, 0 forces town lamps off, 1 on.

namespace
{
constexpr double DOOM_PER_METER = 100 * 0.75;	// Unity units are 100 Daggerfall units; Doom maps are at 0.75.
constexpr int LAMP_MARK = 0x4c414d50;			// special1 of a town lamp billboard, so the night switch can find it.
constexpr int RANDOM_FLICKER = 3;				// ELightType RandomFlickerLight
constexpr int FLICKER_TICS = 3;					// DaggerfallLight steps its range about 14 times a second.

struct LampKind { float range, intensity, r, g, b, offset, heightFraction; };

// DaggerfallInterior.AddLight, by texture record: range in meters, intensity, color, then the shift of the light
// from the billboard's center, in meters plus a fraction of the billboard's height. Unlisted records use the prefab.
const LampKind InteriorDefault = { 15, 1, 1, 1, 1, 0, 0 };
LampKind InteriorLamp(int record)
{
	switch (record)
	{
	case 0: return { 20, 1.1f, 0.95f, 0.91f, 0.63f, -0.1f, 0 };		// Bowl with fire
	case 2: return { 5, 0.6f, 1.0f, 0.99f, 0.82f, 0.1f, 0 };		// Skull candle
	case 3: return { 5, 1, 1, 1, 1, 0.1f, 0 };						// Candle
	case 4: return { 5, 1, 1, 1, 1, 0, 0 };							// Candle with base
	case 5: return { 7.5f, 0.33f, 1.0f, 0.89f, 0.61f, 0.15f, 0 };	// Candleholder with 3 candles
	case 6: return { 15, 0.75f, 1.0f, 0.93f, 0.62f, 0.6f, 0 };		// Skull torch
	case 8: return { 15, 1, 0.68f, 1.0f, 0.94f, 0, 0 };				// Turkis lamp
	case 9: return { 15, 0.65f, 1.0f, 0.92f, 0.6f, 0.4f, 0 };		// Metallic chandelier with burning candles
	case 11: return { 5, 0.5f, 1, 1, 1, -0.4f, 0 };					// Candle in lamp
	case 13: return { 18, 1.1f, 0.93f, 0.84f, 0.49f, -0.35f, 0 };	// Round lamp
	case 14: case 15: return { 15, 1, 1, 1, 1, 0, 0.5f };			// Standing lanterns
	case 17: return { 15, 0.8f, 1.0f, 0.97f, 0.87f, 0.2f, 0 };		// Mounted torch 1
	case 20: return { 12, 0.75f, 1.0f, 0.92f, 0.72f, 0.6f, 0 };		// Brazier torch
	case 21: return { 5, 0.5f, 1.0f, 0.95f, 0.67f, 0, 1 / 2.4f };	// Standing candle
	case 22: return { 15, 1.5f, 1.0f, 0.95f, 0.78f, -0.5f, 0 };		// Round lantern with medium chain
	case 24: return { 15, 1.4f, 1.0f, 0.98f, 0.64f, -1.85f, 0 };	// Lantern with long chain
	case 25: return { 15, 1.4f, 1.0f, 0.98f, 0.64f, -1.0f, 0 };		// Lantern with medium chain
	case 26: return { 15, 1.4f, 1.0f, 0.98f, 0.64f, 0, 0 };			// Lantern with short chain
	case 27: return { 15, 1.4f, 1.0f, 0.98f, 0.64f, -0.02f, 0 };	// Lantern with no chain
	default: return InteriorDefault;
	}
}

std::unordered_map<int, int> lampRecords;	// texture id to archive 210 record, or -1
bool cityLightsFromDaggerfall = false;
int appliedCity = -1;						// what town lamps were last switched to
int interiorLamps = 0;						// lamps lit since the last interior entry, for the log

// The archive 210 record a billboard texture shows, or -1. DD_LightsTextureName registers names as they resolve.
int LampRecord(FTextureID tex)
{
	auto found = lampRecords.find(tex.GetIndex());
	return found != lampRecords.end() ? found->second : -1;
}

double Height(AActor *mo)
{
	auto *t = TexMan.GetGameTexture(mo->picnum);
	return t ? t->GetDisplayHeight() * mo->Scale.Y : 0;
}

int Color(float r, float g, float b)
{
	auto c = [](float v) { return v <= 0 ? 0 : v >= 1 ? 255 : int(v * 255 + 0.5f); };
	return int(0xff000000u | (c(r) << 16) | (c(g) << 8) | c(b));
}

bool CityLightsOn()
{
	return *dd_citylights >= 0 ? *dd_citylights != 0 : cityLightsFromDaggerfall;
}

void AttachTownLamp(AActor *mo)
{
	// The City light prefab: white, intensity 1, range 18, animated, at the top of the billboard.
	const double size = 18 * DOOM_PER_METER * dd_light_range / 2;	// a Doom light reaches twice its size
	AttachLightDirect(mo, FName("ddlamp").GetIndex(), RANDOM_FLICKER, Color(1, 1, 1), int((size - DOOM_PER_METER * dd_light_range / 2) + 0.5), int(size + 0.5),
		LF_ATTENUATE, 0, 0, Height(mo), FLICKER_TICS / 360.0, 10, 25, 1000, 1.0);
}
}

// The treadmill resolved a DFFLATS texture name (dfflat/F210R05.png in the cache, F210R05 in a city package).
void DD_LightsTextureName(const char *name, FTextureID tex)
{
	if (!tex.isValid()) return;
	const char *at = strstr(name, "F210R");
	if (at && (at == name || at[-1] == '/')) lampRecords[tex.GetIndex()] = atoi(at + 5);
}

// A billboard was just spawned in a generated town or interior. Lamps get their light.
void DD_LightsFlat(AActor *mo, bool interior)
{
	if (!mo || !*dd_lights) return;
	const int record = LampRecord(mo->picnum);
	if (record < 0) return;
	if (!interior)
	{
		mo->special1 = LAMP_MARK;
		if (CityLightsOn()) AttachTownLamp(mo);
		return;
	}
	// Interior billboards stand on their base, so the center is half their height up.
	interiorLamps++;
	const LampKind k = InteriorLamp(record);
	const double h = Height(mo), z = h / 2 + k.offset * DOOM_PER_METER + k.heightFraction * h;
	AttachLightDirect(mo, FName("ddlamp").GetIndex(), 0, Color(k.r, k.g, k.b), int(k.range * DOOM_PER_METER * dd_light_range / 2 + 0.5), 0,
		LF_ATTENUATE, 0, 0, z, 0, 10, 25, 1000, k.intensity);
}

// A fresh entry to a building interior: darker sector light, so the lamps show, as Daggerfall Unity's interior ambient does.
void DD_LightsInterior(FLevelLocals *Level)
{
	if (!*dd_lights) return;
	for (auto &sec : Level->sectors) sec.SetLightLevel(*dd_interior_light);
	DD_DebugPrintf("DDLIGHTS interior lamps %d, sector light %d\n", interiorLamps, *dd_interior_light);
	interiorLamps = 0;
}

CCMD(dd_lights_status)
{
	int n = 0, active = 0;
	for (FDynamicLight *l = primaryLevel->lights; l; l = l->next) { n++; if (l->IsActive()) active++; }
	DD_DebugPrintf("DDLIGHTS status lights=%d active=%d\n", n, active);
}

// From the bridge: Daggerfall's WorldTime.Now.IsCityLightsOn.
void DD_LightsSetCity(bool on)
{
	cityLightsFromDaggerfall = on;
}

// A save was loaded: its lamps are in whatever state they were saved in.
namespace
{
int appliedDungeon = -1;	// the dungeon ambient and torch state last applied, or -1 after a new map or a load
}

void DD_LightsReset()
{
	appliedCity = -1;
	appliedDungeon = -1;	// sectors and the torch come back as saved; TickDungeon applies the current settings again
}

namespace
{

// Daggerfall Unity lights its dungeons with a dark ambient (PlayerAmbientLight.DungeonAmbientLight, 0.12) and the
// player's torch (EnablePlayerTorch: on in every dungeon unless the torch comes from items, which is off by default;
// PlayerAdvanced prefab: white point light, intensity 1, range 6 m, 0.6 m above the body's center). The dungeon script
// set its own sector light when it spawned the lights (action_objects.zs SpawnLights); this replaces it.
void TickDungeon(FLevelLocals *Level, int place)
{
	AActor *pmo = Level->Players[consoleplayer]->mo;
	if (!pmo) return;
	static bool lit;
	if (appliedDungeon == -1)	// once per map or load (and each tic of a dungeon's first second while it has no lights yet)
	{
		lit = false;
		static PClass *lightClass = PClass::FindClass("DFDungeonLight");
		if (place == 3 && *dd_lights && lightClass)
		{
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next()) if (mo->IsKindOf(lightClass)) { lit = true; break; }
		}
		if (!lit && place == 3 && Level->maptime < TICRATE) return;	// the dungeon script may not have spawned them yet
	}
	const int want = lit && *dd_lights ? 1 + (*dd_torch ? 1 : 0) : 0;
	if (want == appliedDungeon) return;
	appliedDungeon = want;
	if (lit)
	{
		const int ambient = clamp(*dd_dungeon_ambient, 0, 255);
		for (auto &sec : Level->sectors) sec.SetLightLevel(ambient);
	}
	if (want == 2)
	{
		const double meter = DOOM_PER_METER * dd_light_range;	// Doom units per Daggerfall Unity meter (30 by default)
		AttachLightDirect(pmo, FName("ddtorch").GetIndex(), 0, Color(1, 1, 1), int(6 * meter * dd_torch_range / 2 + 0.5), 0,
			LF_ATTENUATE, 0, 0, (0.9 + 0.6) * 30, 0, 10, 25, 1000, 1.0);
	}
	else RemoveLight(pmo, FName("ddtorch").GetIndex());
	if (lit) DD_DebugPrintf("DDLIGHTS dungeon ambient %d, torch %s\n", clamp(*dd_dungeon_ambient, 0, 255), want == 2 ? "on" : "off");
}
}

// Switches town lamps when Daggerfall's clock or dd_citylights changes, or after a load.
void DD_LightsTick(FLevelLocals *Level)
{
	static int lastTime = 0;
	if (Level->maptime < lastTime || Level->maptime <= 1) appliedCity = -1;	// a new map or a load: lamps may be in any state
	// A new map or a load (also DD_LightsReset). Not every tic while the arrival freeze holds the map at maptime 1.
	if (Level->maptime < lastTime || (Level->maptime <= 1 && lastTime > 1)) appliedDungeon = -1;
	lastTime = Level->maptime;
	TickDungeon(Level, DDTreadmill_Place());
	const int want = *dd_lights && CityLightsOn() ? 1 : 0;
	if (want == appliedCity) return;
	appliedCity = want;
	int count = 0;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (mo->special1 != LAMP_MARK) continue;
		if (want) AttachTownLamp(mo);
		else RemoveLight(mo, FName("ddlamp").GetIndex());
		count++;
	}
	if (count) DD_DebugPrintf("DDLIGHTS town lamps %s: %d\n", want ? "on" : "off", count);
}
