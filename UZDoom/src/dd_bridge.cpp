// Doomerfall: UZDoom's side of the bridge. Does nothing unless started with -dfbridge <session>.
//
// The pump runs once per D_DoomLoop iteration rather than from G_Ticker, because TryRunTics
// returns before G_Ticker and P_RunClientSideLogic while pauseext is set.

#include <algorithm>
#include <chrono>
#include <cstdarg>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <memory>
#include <fstream>
#include <string>
#include <thread>
#include <vector>
#include <miniz.h>

#include "../../bridge/doomerfall_bridge.h"
#include "dd_bridge_test.h"
#include "am_map.h"
#include "bitmap.h"
#include "c_bind.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_event.h"
#include "d_net.h"
#include "d_protocol.h"
#include "doomstat.h"
#include "engineerrors.h"
#include "fs_decompress.h"
#include "g_game.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "i_interface.h"
#include "m_argv.h"
#include "menu.h"
#include "d_player.h"
#include "gamedata/g_mapinfo.h"
#include "p_local.h"
#include "playsim/dd_treadmill.h"
#include "printf.h"
#include "resourcefile.h"
#include "savegamemanager.h"
#include "texturemanager.h"
#include "textures.h"
#include "v_draw.h"
#include "v_font.h"
#include "v_video.h"
#include "playsim/dd_log.h" // [Doomerfall]

void G_SaveGame(const char *filename, const char *description, bool quick);
void G_DoAutoSave();
extern FString savename;

// World items: see dd_items.cpp.
bool DD_ItemsEvent(const dfb_event &e);
void DD_ItemsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target);
void DD_ItemsResync();
void DD_ItemsSendStarter();
bool DD_ItemsNetEvent(dfb_session *session, const char *name);
bool DD_MonstersEvent(const dfb_event &e);
void DD_MonstersFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target);
void DD_MonstersResync();
#include "dd_locations.h"
void DD_MonsterDied(dfb_session *session, AActor *mo);
bool DD_NpcsEvent(const dfb_event &e);
void DD_NpcsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target);
void DD_NpcsResync();
bool DD_InfoEvent(const dfb_event &e);
void DD_InfoUiClosed();
bool DD_InfoNetEvent(dfb_session *session, const char *name);
bool DD_LookEvent(const dfb_event &e);
void DD_LookFrame(dfb_session *session);
bool DD_TownsfolkEvent(const dfb_event &e);
void DD_TownsfolkFrame(dfb_session *session, uint32_t context);
void DD_TownsfolkResync();
void DD_TownsfolkDied(dfb_session *session, AActor *mo);
void DD_ClimbFrame(dfb_session *session);
void DD_FacesFrame(dfb_session *session);
bool DD_ClimbNetEvent(dfb_session *session, const char *name);
bool DD_GuardsEvent(const dfb_event &e);
bool DD_DoorsEvent(const dfb_event &e);
bool DD_DoorsNetEvent(dfb_session *session, const char *name);
void DD_DoorsFrame(uint32_t context, bool inSpace, int32_t target);
void DD_SetupLevelLoaded(bool fromSave);
bool DD_SetupNetEvent(const char *name);
bool DD_SetupReady(int64_t now);
double DD_SetupAgeMs(int64_t now);
double DD_SetupReadyMs();
void DD_LightsSetCity(bool on);	// playsim/dd_lights.cpp
bool DD_WeatherText(const char *text);	// playsim/dd_weather.cpp
bool DFMesh_WindowText(const char *text);	// rendering/hwrenderer/scene/hw_dfmesh.cpp
void DD_GuardsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target);
void DD_GuardDied(dfb_session *session, AActor *mo);

FARG_ADVANCED(dfbridge, "Doomerfall", "session", "Attaches to the Doomerfall bridge session created by the launcher.");
FARG_ADVANCED(dfbridgelog, "Doomerfall", "file", "Appends Doomerfall bridge traffic and latency to a log file.");
FARG_ADVANCED(dfuitest, "Doomerfall", "count", "Bridge test only: opens the fast travel menu this many times.");
FARG(dfflow, "Doomerfall", "Starts at Doom's title with New Game and Load Game driving both games.", "", "");
FARG_ADVANCED(dfsavetestfail, "Doomerfall", "uz_zip|uz_commit|uz_crash", "Save test only: fails the save at this step.");
// The other bridge test flags and their drivers are in dd_bridge_test.cpp.

CVAR(Bool, dd_bridge_session, false, CVAR_NOSAVE) // Read by scripts: Daggerfall is attached (door locks hold). Set on attach; tests may set it.
CVAR(Int, dd_sync_df_phase, 0, CVAR_NOSAVE) // Read by the position sync test route.
CVAR(Int, dd_ui_test_hold, 0, CVAR_NOSAVE | CVAR_MOD) // Test only: a route holds -dfuitest until it reaches the place to open the menu.
CVAR(Int, dd_ui_test_menu, 1, CVAR_NOSAVE | CVAR_MOD) // Test only: the menu -dfuitest opens. 1 is the travel map, 2 the inventory, 3 the map command, 9 the journal.
CVAR(Bool, dd_ui_test_doommap, false, CVAR_NOSAVE) // Test only: opens Doom's own map just before -dfuitest opens its menu.
EXTERN_CVAR(Bool, dfmesh_view)
static bool UiCanOpen();

namespace
{
constexpr int64_t PingIntervalNs = 50000000;
constexpr int64_t LogIntervalNs = 2000000000;
constexpr int64_t StaleNs = 1000000000;
constexpr int SampleCount = 1024;

struct Samples
{
	int64_t values[SampleCount];
	int count = 0, next = 0;

	void Add(int64_t v)
	{
		values[next] = v;
		next = (next + 1) % SampleCount;
		count = std::min(count + 1, SampleCount);
	}

	void Format(char *out, size_t cap) const
	{
		if (!count) { snprintf(out, cap, "n=0"); return; }
		int64_t sorted[SampleCount];
		std::copy(values, values + count, sorted);
		std::sort(sorted, sorted + count);
		snprintf(out, cap, "n=%d p50=%.2fms p99=%.2fms max=%.2fms", count, sorted[count / 2] / 1e6,
			sorted[count * 99 / 100] / 1e6, sorted[count - 1] / 1e6);
	}
};

dfb_session *session;
FILE *logFile;
dfb_uz_state ownState;
dfb_df_state peerState;
int32_t sheet[DFB_SHEET_INTS]; // Doom's read-only copy of Daggerfall's character sheet.
uint32_t sheetVersion;
Samples rtt, oneWayOut, oneWayIn, stateAge;
uint32_t nextPing = 1;
uint64_t pingsAnswered, pongsReceived, unknownKinds;
int64_t nextPingNs, nextLogNs;
bool peerSeen, peerStale;
int64_t peerStaleAt;

void Log(const char *format, ...)
{
	char line[512];
	va_list args;
	va_start(args, format);
	vsnprintf(line, sizeof(line), format, args);
	va_end(args);
	Printf(DD_DebugLevel(), "[bridge] %s\n", line);
	if (logFile)
	{
		fprintf(logFile, "%.3f %s\n", dfb_now_ns() / 1e9, line);
		fflush(logFile);
	}
}

void SendText(const char *text)
{
	dfb_event e{};
	e.tic = gametic;
	e.kind = DFB_KIND_TEXT;
	strncpy(reinterpret_cast<char *>(e.payload), text, sizeof(e.payload));
	dfb_send(session, &e);
}

// Publishes the player's Daggerfall world position. An area change also goes out as an event, so
// Daggerfall can act on it at once instead of waiting for its next position update.
void PublishPosition()
{
	constexpr int WorldUnitsPerPixel = 32768, MaxPixelX = 999, MaxPixelY = 499;
	double x = 0, y = 0, z = 0, yaw = 0;
	const DDPlayerArea area = gamestate == GS_LEVEL ? DDTreadmill_PlayerWorld(x, y, z, yaw) : DD_AREA_NONE;
	const uint32_t context = area == DD_AREA_EXTERIOR ? DFB_WORLD_EXTERIOR : area == DD_AREA_INTERIOR ? DFB_WORLD_INTERIOR
		: area == DD_AREA_DUNGEON ? DFB_WORLD_DUNGEON : DFB_WORLD_NONE;
	int pixelX = -1, pixelY = -1;
	if (area == DD_AREA_INTERIOR || area == DD_AREA_DUNGEON)
	{
		// Indoors the published position stays at the last outdoor place, which is the door the player used.
		pixelX = ownState.map_pixel_x;
		pixelY = ownState.map_pixel_y;
	}
	else if (area == DD_AREA_EXTERIOR)
	{
		pixelX = std::clamp(int(floor(x / WorldUnitsPerPixel)), 0, MaxPixelX);
		pixelY = MaxPixelY - std::clamp(int(floor(y / WorldUnitsPerPixel)), 0, MaxPixelY);
		ownState.world_x = x;
		ownState.world_z = y;
		ownState.world_height = z;
		ownState.yaw_degrees = float(yaw);
	}
	double spaceYaw = 0;
	int spaceTarget = 0;
	const bool inSpace = (area == DD_AREA_INTERIOR || area == DD_AREA_DUNGEON) &&
		DDTreadmill_PlayerSpace(ownState.space_x, ownState.space_y, ownState.space_z, spaceYaw, spaceTarget);
	ownState.space_yaw = float(spaceYaw);
	ownState.space_target = spaceTarget;
	ownState.space_valid = inSpace ? 1 : 0;
	if (context != ownState.world_context || pixelX != ownState.map_pixel_x || pixelY != ownState.map_pixel_y)
	{
		ownState.world_context = context;
		ownState.map_pixel_x = pixelX;
		ownState.map_pixel_y = pixelY;
		ownState.area_seq++;

		dfb_event e{};
		e.kind = DFB_KIND_AREA;
		e.tic = gametic;
		const dfb_area body{ context, pixelX, pixelY, ownState.area_seq, dfb_now_ns() };
		memcpy(e.payload, &body, sizeof(body));
		dfb_send(session, &e);
	}
}

void HandleUiState(const dfb_event &e);
void HandleUiResult(const dfb_event &e);
void HandleUiAsk();
void HandleTravel(const dfb_event &e);
void HandleSaveReply(const dfb_event &e);
void HandleLoadReady(const dfb_event &e);
void HandleLoadResume(const dfb_event &e);
bool flowHold; // A load is running, or a failed load or the title left no game both halves agree on.

// New Game (-dfflow). Doom's menu opens Daggerfall's character creation, asks for a difficulty, walks into
// the start location, and only then lets Daggerfall start its clock and quests.
enum NewGameState { NgIdle, NgWaitDf, NgCreating, NgDifficulty, NgLoading, NgTravel, NgDoor, NgWaitGo };
bool flowMode, ngHaveWorld, ngResult;
bool ngAskedAbandon; // Escape closed the difficulty prompt, and the question about dropping the character is open.
int64_t ngPromptAt; // When the difficulty prompt first opened.
constexpr int64_t NgEscapeGraceNs = 1000000000LL;
NewGameState ngState = NgIdle;
dfb_new_game ngWorld;
// A plain Daggerfall save (no Doom half) runs the same chain from Daggerfall's Load window (DFB_KIND_PLAIN_LOAD).
bool ngPlain;
dfb_plain_load plainWorld;
int64_t ngDeadline, ngTravelAt;
constexpr int64_t NgStallNs = 30000000000LL; // Daggerfall stalls for seconds while it builds a new character's world.
FString campaignId, loadCampaign; // Keeps each character's auto and quick slots apart.
void HandleNewGameGo();
}
FString DD_BridgeSlotName(const char *slot);
namespace
{
// The new character's first save: one normal bundled save at the start point (PumpNewGameSave).
enum NewGameSaveState { NgsNone, NgsWaiting, NgsWriting, NgsDone };
NewGameSaveState ngSave = NgsNone;
int ngSaveAttempts, ngSaveHp;
int64_t ngSaveQuietSince, ngSaveGoNs;
double ngSavePos[3];
FString ngSaveFile;

void HandleEvent(const dfb_event &e, int64_t now)
{
	switch (e.kind)
	{
	case DFB_KIND_UI_STATE:
		HandleUiState(e);
		break;
	case DFB_KIND_UI_RESULT:
		HandleUiResult(e);
		break;
	case DFB_KIND_UI_ASK:
		HandleUiAsk();
		break;
	case DFB_KIND_TRAVEL:
		HandleTravel(e);
		break;
	case DFB_KIND_SAVE_PREPARED:
		HandleSaveReply(e);
		break;
	case DFB_KIND_LOAD_READY:
		HandleLoadReady(e);
		break;
	case DFB_KIND_LOAD_RESUME:
		HandleLoadResume(e);
		break;
	case DFB_KIND_NEWGAME:
		memcpy(&ngWorld, e.payload, sizeof(ngWorld));
		ngHaveWorld = ngState == NgCreating;
		Log("new game: Daggerfall holds a character at pixel %d,%d, dungeon %d", ngWorld.map_pixel_x, ngWorld.map_pixel_y, ngWorld.dungeon_map_id);
		break;
	case DFB_KIND_NEWGAME_GO:
		HandleNewGameGo();
		break;
	case DFB_KIND_PLAIN_LOAD:
		memcpy(&plainWorld, e.payload, sizeof(plainWorld));
		ngHaveWorld = ngPlain && ngState == NgCreating;
		Log("plain load: Daggerfall holds a loaded save, area %u at %.1f,%.1f yaw %.1f, dungeon %d, space start %.1f,%.1f,%.1f yaw %.1f%s",
			plainWorld.context, plainWorld.world_x, plainWorld.world_z, plainWorld.yaw_degrees, plainWorld.dungeon_map_id,
			plainWorld.start_x, plainWorld.start_y, plainWorld.start_z, plainWorld.start_yaw, ngHaveWorld ? "" : " (not expected, ignored)");
		break;
	case DFB_KIND_PING:
	{
		dfb_event reply = e;
		dfb_ping ping;
		memcpy(&ping, e.payload, sizeof(ping));
		ping.replier_ns = now;
		memcpy(reply.payload, &ping, sizeof(ping));
		reply.kind = DFB_KIND_PONG;
		reply.tic = gametic;
		dfb_send(session, &reply);
		pingsAnswered++;
		break;
	}
	case DFB_KIND_PONG:
	{
		dfb_ping ping;
		memcpy(&ping, e.payload, sizeof(ping));
		rtt.Add(now - ping.sent_ns);
		oneWayOut.Add(ping.replier_ns - ping.sent_ns);
		oneWayIn.Add(now - ping.replier_ns);
		pongsReceived++;
		break;
	}
	case DFB_KIND_TEXT:
	{
		char text[sizeof(e.payload) + 1] = {};
		memcpy(text, e.payload, sizeof(e.payload));
		int lampsOn;
		if (sscanf(text, "citylights %d", &lampsOn) == 1) { DD_LightsSetCity(lampsOn != 0); break; }	// Daggerfall's clock, for town lamps
		if (DD_WeatherText(text)) break;	// Daggerfall's sky, light, weather and ambient sounds (dd_weather.cpp)
		if (DFMesh_WindowText(text)) break;	// Daggerfall's window glow colour (hw_dfmesh.cpp)
		Log("message from Daggerfall: \"%s\" (seq %u)", text, e.seq);
		break;
	}
	case DFB_KIND_HELLO:
		Log("hello from Daggerfall (seq %u)", e.seq);
		break;
	default:
		if (!DD_ItemsEvent(e) && !DD_MonstersEvent(e) && !DD_LocationsEvent(e) && !DD_NpcsEvent(e) && !DD_InfoEvent(e) && !DD_LookEvent(e) && !DD_TownsfolkEvent(e) && !DD_GuardsEvent(e) && !DD_DoorsEvent(e)) unknownKinds++; // contract rule 7: skip, never fatal
		break;
	}
}

//==========================================================================
// Daggerfall menus shown inside Doom. Daggerfall draws the real window into the shared surface.
// While one is open Doom is paused, draws the newest frame, and forwards all input.
//==========================================================================

class DDUiTexture : public FTexture
{
	TArray<uint8_t> image;

public:
	void SetFrame(const void *bgra, int width, int height)
	{
		if (width != Width || height != Height)
		{
			FTexture::SetSize(width, height);
			image.Resize(width * height * 4);
		}
		memcpy(image.Data(), bgra, image.Size());
	}

	FBitmap GetBgraBitmap(const PalEntry *, int *) override
	{
		return FBitmap(image.Data(), Width * 4, Width, Height);
	}
};

enum UiState { UiClosed, UiOpening, UiOpen };
constexpr int64_t UiOpenTimeoutNs = 5000000000LL;
constexpr int64_t UiMinFrameNs = 8000000; // Paused Doom has no tic wait, so keep it near 120 Hz.

UiState uiState = UiClosed;
uint32_t uiId;
bool uiSavedPause, uiHasFrame;
int64_t uiOpenedNs, uiLastInputSeen, uiLastFrameNs;
FGameTexture *uiTextures[2];
DDUiTexture *uiPixels[2];
int uiActiveTexture;
dfb_surface_frame uiFrame;
int uiMapTimeAtOpen;
uint32_t uiFrames;
Samples uiInputLatency, uiFrameAge, uiUpload;

// Test only (-dfuitest <count>): opens the menu through the real command, count times.
int uiTestRemaining;
int64_t uiTestAtNs, uiTestShotNs;

void EnsureUiTextures()
{
	static const char *const names[2] = { "DoomerfallUiFrame1", "DoomerfallUiFrame2" };
	for (int i = 0; i < 2; i++)
	{
		FGameTexture *found = TexMan.FindGameTexture(names[i], ETextureType::Override);
		if (found && found == uiTextures[i]) continue;
		uiPixels[i] = new DDUiTexture;
		uiTextures[i] = MakeGameTexture(uiPixels[i], names[i], ETextureType::Override);
		uiTextures[i]->SetUpscaleFlag(false, true);
		TexMan.AddGameTexture(uiTextures[i]);
	}
}

void SendUiCommand(uint16_t kind, uint32_t id, uint32_t context = 0)
{
	dfb_event e{};
	e.kind = kind;
	e.tic = gametic;
	const dfb_ui_command body{ id, context, dfb_now_ns() };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

void SendUiInput(uint32_t type, int a = 0, int b = 0)
{
	dfb_event e{};
	e.kind = DFB_KIND_UI_INPUT;
	e.tic = gametic;
	const dfb_ui_input body{ type, a, b, 0, dfb_now_ns() };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

void OpenUi(uint32_t id, uint32_t context = 0)
{
	EnsureUiTextures();
	uiId = id;
	uiState = UiOpening;
	uiHasFrame = false;
	uiOpenedNs = dfb_now_ns();
	uiLastInputSeen = 0;
	uiFrames = 0;
	uiSavedPause = pauseext;
	pauseext = true;
	uiMapTimeAtOpen = primaryLevel ? primaryLevel->maptime : -1;
	SendUiCommand(DFB_KIND_UI_OPEN, id, context);
	Log("ui: asked Daggerfall to open menu %u, maptime %d", id, uiMapTimeAtOpen);
}

void FinishUi(const char *why)
{
	if (uiState == UiClosed) return;
	uiState = UiClosed;
	uiHasFrame = false;
	pauseext = uiSavedPause;
	char input[96], age[96], upload[96];
	uiInputLatency.Format(input, sizeof(input));
	uiFrameAge.Format(age, sizeof(age));
	uiUpload.Format(upload, sizeof(upload));
	Log("ui: closed (%s), %u frames shown, maptime %d then %d", why, uiFrames, uiMapTimeAtOpen,
		primaryLevel ? primaryLevel->maptime : -1);
	Log("ui latency: input to shown %s | capture to shown %s | texture copy %s", input, age, upload);
	uiInputLatency.count = uiInputLatency.next = uiFrameAge.count = uiFrameAge.next = uiUpload.count = uiUpload.next = 0;
	uiTestShotNs = 0;
	uiTestAtNs = dfb_now_ns() + 2000000000LL;
	DD_InfoUiClosed();
}

void HandleUiState(const dfb_event &e)
{
	dfb_ui_state body;
	memcpy(&body, e.payload, sizeof(body));
	if (uiState == UiClosed || body.ui_id != uiId) return;
	if (body.state == DFB_UI_OPENED)
	{
		uiState = UiOpen;
		Log("ui: Daggerfall opened menu %u at %ux%u, %.1f ms after the request", body.ui_id, body.surface_width,
			body.surface_height, (dfb_now_ns() - uiOpenedNs) / 1e6);
		return;
	}
	static const char *const reasons[] = { "none", "player closed it", "Daggerfall refused", "choice made", "Doom asked" };
	if (body.reason == DFB_UI_REASON_REFUSED) Printf("Daggerfall cannot open that menu here.\n");
	if ((body.ui_id == DFB_UI_NEW_GAME || body.ui_id == DFB_UI_LOAD_GAME) && body.reason == DFB_UI_REASON_RESULT)
	{
		ngResult = true;
		ngDeadline = dfb_now_ns() + 20000000000LL;
	}
	FinishUi(body.reason < 5 ? reasons[body.reason] : "unknown");
}

void HandleUiResult(const dfb_event &e)
{
	dfb_ui_result body;
	memcpy(&body, e.payload, sizeof(body));
	body.name[sizeof(body.name) - 1] = 0;
	Log("ui: fast travel to %s at map pixel %d,%d", body.name, body.map_pixel_x, body.map_pixel_y);
}

// Daggerfall opened a window by itself, such as a quest message, and is paused behind it. It asks again until shown.
void HandleUiAsk()
{
	if (uiState != UiClosed || !UiCanOpen()) return;
	Log("ui: Daggerfall asked to show a window it opened by itself");
	OpenUi(DFB_UI_DAGGERFALL);
}

void HandleTravel(const dfb_event &e)
{
	dfb_travel body;
	memcpy(&body, e.payload, sizeof(body));
	// The player arrives looking at the world, not at Doom's map or the debug collider view.
	const bool hadMap = automapactive, hadColliders = !dfmesh_view;
	if (hadMap) AM_Stop();
	if (hadColliders) dfmesh_view = true;
	const bool accepted = DDTreadmill_RequestTravel(body.world_x, body.world_z, body.yaw_degrees);
	Log("travel: Daggerfall placed the player at world %.1f,%.1f yaw %.1f pixel %d,%d, %s", body.world_x, body.world_z,
		body.yaw_degrees, body.map_pixel_x, body.map_pixel_y, accepted ? "loading" : "refused");
	if (hadMap || hadColliders) Log("travel: closed Doom's map %d, left collider view %d", hadMap, hadColliders);
}

void PumpUi(int64_t now)
{
	if (uiState == UiClosed) return;
	pauseext = true; // A focus change can clear it while the menu is open.

	if (uiState == UiOpening && now - uiOpenedNs > UiOpenTimeoutNs)
	{
		SendUiCommand(DFB_KIND_UI_CLOSE, uiId);
		Printf("Daggerfall did not open the menu.\n");
		FinishUi("no answer from Daggerfall");
		return;
	}
	if (peerStale && (ngState != NgCreating || now - peerStaleAt > NgStallNs))
	{
		Printf("Daggerfall stopped responding, closing its menu.\n");
		FinishUi("Daggerfall heartbeat stale");
		return;
	}

	dfb_surface_frame frame;
	const void *pixels = nullptr;
	if (uiState == UiOpen && dfb_surface_acquire(session, &frame, &pixels) == DFB_GOT && pixels && frame.captured_ns >= uiOpenedNs)
	{
		const int64_t copyStart = dfb_now_ns();
		const int next = uiActiveTexture ^ 1;
		uiPixels[next]->SetFrame(pixels, frame.width, frame.height);
		uiTextures[next]->SetSize(frame.width, frame.height);
		uiTextures[next]->CleanHardwareData();
		uiActiveTexture = next;
		uiFrame = frame;
		uiHasFrame = true;
		uiFrames++;
		const int64_t shown = dfb_now_ns();
		uiUpload.Add(shown - copyStart);
		uiFrameAge.Add(shown - frame.captured_ns);
		if (frame.input_ns > uiLastInputSeen)
		{
			uiLastInputSeen = frame.input_ns;
			uiInputLatency.Add(shown - frame.input_ns);
		}
	}

	if (uiTestRemaining >= 0 && uiHasFrame && !uiTestShotNs)
		uiTestShotNs = now + 1500000000LL;
	if (uiTestShotNs > 0 && now >= uiTestShotNs)
	{
		uiTestShotNs = now + 1000000000LL;
		C_DoCommand("screenshot");
		Log("ui test: screenshot of the open menu");
	}

	// Paused Doom skips its tic wait so the cursor stays responsive. This keeps it from spinning.
	while (dfb_now_ns() - uiLastFrameNs < UiMinFrameNs) std::this_thread::sleep_for(std::chrono::microseconds(500));
	uiLastFrameNs = dfb_now_ns();
}

const char *UiCommandName(uint32_t id)
{
	if (id == DFB_UI_TALK) return "+use";
	if (id == DFB_UI_JOURNAL) return "netevent df_journal";
	if (id == DFB_UI_REST) return "netevent df_rest";
	return id == DFB_UI_INVENTORY || id == DFB_UI_LOOT ? "netevent df_inventory" : id == DFB_UI_MAP ? "togglemap" : "netevent df_fast_travel";
}

void RunUiTest(int64_t now)
{
	if (uiTestRemaining <= 0 || dd_ui_test_hold || uiState != UiClosed || gamestate != GS_LEVEL || peerState.df_phase != DFB_DF_PHASE_PLAY) return;
	if (!uiTestAtNs) uiTestAtNs = now + 3000000000LL;
	if (now < uiTestAtNs) return;
	uiTestRemaining--;
	uiTestAtNs = 0;
	if (dd_ui_test_doommap && !automapactive) // The map command can no longer open Doom's map here, so the fast travel test does.
	{
		AM_ToggleMap();
		Log("ui test: Doom's map is %s", automapactive ? "open" : "closed");
	}
	C_DoCommand(UiCommandName(dd_ui_test_menu));
}

void UiRect(int &x, int &y, int &w, int &h)
{
	const int screenW = twod->GetWidth(), screenH = twod->GetHeight();
	const int frameW = uiHasFrame ? uiFrame.width : 16, frameH = uiHasFrame ? uiFrame.height : 10;
	w = screenW;
	h = int(int64_t(screenW) * frameH / frameW);
	if (h > screenH)
	{
		h = screenH;
		w = int(int64_t(screenH) * frameW / frameH);
	}
	x = (screenW - w) / 2;
	y = (screenH - h) / 2;
}

void SendUiMouse(long long lParam)
{
	if (!uiHasFrame || !screen) return;
	int16_t mx = int16_t(lParam & 0xFFFF), my = int16_t((lParam >> 16) & 0xFFFF);
	if (uiTestRemaining >= 0)
	{
		// Test only: a minimized window has no usable client area, so the driver sends surface pixels.
		SendUiInput(DFB_UI_INPUT_MOVE, std::clamp<int>(mx, 0, uiFrame.width - 1), std::clamp<int>(my, 0, uiFrame.height - 1));
		return;
	}
	screen->ScaleCoordsFromWindow(mx, my);
	int x, y, w, h;
	UiRect(x, y, w, h);
	const int px = std::clamp(int(int64_t(mx - x) * uiFrame.width / std::max(w, 1)), 0, int(uiFrame.width) - 1);
	const int py = std::clamp(int(int64_t(my - y) * uiFrame.height / std::max(h, 1)), 0, int(uiFrame.height) - 1);
	SendUiInput(DFB_UI_INPUT_MOVE, px, py);
}

// Windows reports one code for both Shift keys, Ctrl keys, and Alt keys.
int SidedVirtualKey(uint64_t vk, long long lParam)
{
	const int scan = int((lParam >> 16) & 0xFF);
	const bool extended = (lParam >> 24) & 1;
	switch (vk)
	{
	case 0x10: return scan == 0x36 ? 0xA1 : 0xA0;
	case 0x11: return extended ? 0xA3 : 0xA2;
	case 0x12: return extended ? 0xA5 : 0xA4;
	default: return int(vk);
	}
}

// The control that opened the open menu also closes it, on whatever key the player bound.
bool IsOpenMenuKey(long long lParam)
{
	int key = int((lParam >> 16) & 0xFF);
	if ((lParam >> 24) & 1) key |= 0x80;
	const FString &bound = Bindings.GetBinding(key);
	if (uiId == DFB_UI_DAGGERFALL) return false; // No Doom control opened it. The player answers it in Daggerfall.
	return bound.CompareNoCase(UiCommandName(uiId)) == 0;
}

// In Daggerfall's map screens, the keys the player bound to Doom's movement pan the view. Daggerfall's maps pan
// with the arrow keys, so those keys are sent as arrows. Every other key, and every other menu, is sent unchanged.
int MapPanKey(int vk, long long lParam)
{
	if (uiId != DFB_UI_MAP && uiId != DFB_UI_TRAVEL_MAP) return vk;
	int key = int((lParam >> 16) & 0xFF);
	if ((lParam >> 24) & 1) key |= 0x80;
	const FString &bound = Bindings.GetBinding(key);
	if (bound.CompareNoCase("+forward") == 0) return 0x26;
	if (bound.CompareNoCase("+back") == 0) return 0x28;
	if (bound.CompareNoCase("+moveleft") == 0) return 0x25;
	if (bound.CompareNoCase("+moveright") == 0) return 0x27;
	return vk;
}
}

void DD_BridgeTransition(int action, double x, double y, int target)
{
	if (!session) return;
	static uint32_t transitionSeq;
	dfb_event e{};
	e.kind = DFB_KIND_TRANSITION;
	e.tic = gametic;
	const dfb_transition body{ uint32_t(action), ++transitionSeq, x, y, target, 0 };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
	Log("transition %u: action %d, door %.1f,%.1f, target %d", body.seq, action, x, y, target);
}

bool DD_BridgeUiActive() { return uiState != UiClosed; }
bool DD_BridgeSaveActive();

static bool UiCanOpen()
{
	if (gamestate != GS_LEVEL || flowHold || players[consoleplayer].health <= 0 || DDTreadmill_HandoffPending() || DD_BridgeSaveActive()) return false; // Not while going through a door or map seam, or saving.
	if (!peerSeen || peerStale || peerState.df_phase != DFB_DF_PHASE_PLAY)
	{
		Printf("Daggerfall is not ready to show that menu.\n");
		Log("ui: open refused, Daggerfall phase %u", peerState.df_phase);
		return false;
	}
	return true;
}

// The togglemap command. True means Daggerfall handled it. Regular Doom maps and non-bridge launches return false.
bool DD_BridgeToggleMap()
{
	if (!session) return false;
	if (uiState != UiClosed)
	{
		SendUiCommand(DFB_KIND_UI_CLOSE, uiId);
		return true;
	}
	if (gamestate != GS_LEVEL || automapactive) return false; // An already open Doom map can always be closed.
	double x, y, z, yaw;
	const DDPlayerArea area = DDTreadmill_PlayerWorld(x, y, z, yaw);
	if (area == DD_AREA_NONE) return false;
	if (UiCanOpen()) OpenUi(DFB_UI_MAP, uint32_t(area));
	return true;
}

bool DD_BridgeHasSession() { return session != nullptr; }

// The map pixel Doom last published (indoors, the door's pixel), or false before one is known.
bool DD_BridgeMapPixel(int &x, int &y)
{
	x = ownState.map_pixel_x;
	y = ownState.map_pixel_y;
	return session != nullptr && x >= 0 && y >= 0;
}

// Daggerfall answered Use on a container with its own window. Doom shows it like any other Daggerfall menu.
void DD_BridgeOpenLoot()
{
	if (session && uiState == UiClosed && UiCanOpen()) OpenUi(DFB_UI_LOOT);
}

// Daggerfall answered Use on an NPC with its own activation, which shows the talk window or whatever it opens.
void DD_BridgeOpenTalk()
{
	if (session && uiState == UiClosed && UiCanOpen()) OpenUi(DFB_UI_TALK);
}

static void RefreshSheet()
{
	if (!session || dfb_bulk_version(session, DFB_SHEET_SLOT) == sheetVersion) return;
	int32_t incoming[DFB_SHEET_INTS];
	uint32_t size = 0, version = 0;
	if (dfb_bulk_read(session, DFB_SHEET_SLOT, incoming, sizeof(incoming), &size, &version) != DFB_GOT || size != sizeof(incoming)) return;
	bool logIt = sheetVersion == 0;
	for (int i = 0; i < DFB_SHEET_INTS && !logIt; i++) // Fatigue and magicka change constantly.
		logIt = incoming[i] != sheet[i] && (i < DFB_SHEET_FATIGUE_CURRENT || i > DFB_SHEET_MAGICKA_MAX);
	memcpy(sheet, incoming, sizeof(sheet));
	sheetVersion = version;
	if (!logIt) return;
	uint32_t sum = 2166136261u;
	for (int value : sheet) sum = (sum ^ uint32_t(value)) * 16777619u;
	Log("sheet: read v%u epoch %d valid %d level %d str %d/%d archery %d/%d armor0 %d/%d fire %d/%d sum %08x"
		" shotguns %d/%d automatics %d/%d explosives %d/%d pistols %d/%d rifles %d/%d energy %d/%d melee %d/%d", version, sheet[DFB_SHEET_EPOCH],
		sheet[DFB_SHEET_VALID], sheet[DFB_SHEET_LEVEL], sheet[DFB_SHEET_STATS_BASE], sheet[DFB_SHEET_STATS_LIVE],
		sheet[DFB_SHEET_SKILLS_BASE + 33], sheet[DFB_SHEET_SKILLS_LIVE + 33], sheet[DFB_SHEET_ARMOR_BASE], sheet[DFB_SHEET_ARMOR_LIVE], // 33 is Archery
		sheet[DFB_SHEET_RESIST_ACTIVE], sheet[DFB_SHEET_RESIST_CHANCE], (unsigned)sum,
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_SHOTGUNS], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_SHOTGUNS],
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_AUTOMATICS], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_AUTOMATICS],
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_EXPLOSIVES], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_EXPLOSIVES],
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_PISTOLS], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_PISTOLS],
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_RIFLES], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_RIFLES],
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_ENERGY], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_ENERGY],
		sheet[DFB_SHEET_SKILLS_BASE + DFB_SKILL_MELEE], sheet[DFB_SHEET_SKILLS_LIVE + DFB_SKILL_MELEE]);
}

// Daggerfall's current character sheet, indexed by DFB_SHEET_*, or null when there is no valid character.
// Doom only reads it. Anything derived from it must be dropped when DFB_SHEET_EPOCH changes.
const int32_t *DD_BridgeSheet()
{
	RefreshSheet();
	return sheetVersion && sheet[DFB_SHEET_VALID] == 1 && sheet[DFB_SHEET_FORMAT] == DFB_SHEET_FORMAT_VERSION ? sheet : nullptr;
}

// Daggerfall's live value of one skill (DFCareer.Skills slot) for ZScript (Actor.DD_SheetSkill), or -1 without a
// valid character, so a Doom-only game reads -1.
int DD_BridgeSkillLive(int slot)
{
	const int32_t *s = DD_BridgeSheet();
	return s && slot >= 0 && slot < DFB_SHEET_SKILLS_LIVE - DFB_SHEET_SKILLS_BASE ? s[DFB_SHEET_SKILLS_LIVE + slot] : -1;
}

// One value of the character sheet (DFB_SHEET_* index) for ZScript (Actor.DD_SheetValue), such as the perk rules
// Daggerfall sends (DFB_SHEET_AUTO_*). -1 without a valid character or for an index out of range.
int DD_BridgeSheetValue(int index)
{
	const int32_t *s = DD_BridgeSheet();
	return s && index >= 0 && index < DFB_SHEET_INTS ? s[index] : -1;
}

// One line in the bridge log (-dfbridgelog) and the console, for the other dd_*.cpp files.
void DD_BridgeLog(const char *text) { Log("%s", text); }

// From AActor::Die, for actors with a Doomerfall record id only.
void DD_BridgeMonsterDied(AActor *mo)
{
	if (session) DD_MonsterDied(session, mo);
	if (session) DD_TownsfolkDied(session, mo);
	if (session) DD_GuardDied(session, mo);
}

// A ZScript pickup request, seen as its network event runs. False for every other event and outside a session.
bool DD_BridgeItemNetEvent(const char *name)
{
	return session && (DD_ItemsNetEvent(session, name) || DD_InfoNetEvent(session, name) || DD_ClimbNetEvent(session, name) || DD_DoorsNetEvent(session, name) || DD_SetupNetEvent(name));
}

bool DD_IsDrlaSpawner(AActor *mo);

// What Daggerfall's rest checks would see if its world were the one shown (DaggerfallUI's rest message,
// GameManager.AreEnemiesNearby while resting): a live hostile monster that targets the player and sees them, or
// any within Daggerfall's 12 m resting distance; and whether the player stands on the ground, out of deep water.
static uint32_t RestState()
{
	constexpr double RestingDistance = 12 * 75.0; // Daggerfall's metres, at the Doom maps' 75 units per metre
	AActor *pmo = players[consoleplayer].mo;
	if (!pmo) return DFB_REST_NOT_GROUNDED;
	uint32_t state = 0;
	const bool standing = pmo->Z() <= pmo->floorz + 1 || (pmo->flags2 & MF2_ONMOBJ); // on the floor, or on top of a solid actor
	if (!standing || pmo->waterlevel >= 2) state |= DFB_REST_NOT_GROUNDED;
	int near = 0, seeing = 0;
	AActor *first = nullptr;
	auto it = primaryLevel->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (!(mo->flags3 & MF3_ISMONSTER) || mo->health <= 0 || (mo->flags & (MF_FRIENDLY | MF_CORPSE)) || DD_IsDrlaSpawner(mo)) continue;
		const bool sees = mo->target == pmo && P_CheckSight(mo, pmo, SF_IGNOREVISIBILITY);
		if (!sees && (mo->Pos() - pmo->Pos()).Length() > RestingDistance) continue;
		near++;
		seeing += sees;
		if (!first) first = mo;
	}
	if (near) state |= DFB_REST_MONSTERS_NEAR;
	Log("rest: %d hostile monsters near (%d see the player)%s%s, on the ground %d", near, seeing, first ? ", first " : "",
		first ? first->GetClass()->TypeName.GetChars() : "", !(state & DFB_REST_NOT_GROUNDED));
	return state;
}

bool DD_BridgeNetEvent(const char *name)
{
	if (session && !strcmp(name, "df_hp_damage")) // Demo only: stands in for a Daggerfall-side attacker
	{
		SendText("hptest damage 15");
		return true;
	}
	if (!session) return false;
	const bool inventory = !strcmp(name, "df_inventory"), journal = !strcmp(name, "df_journal"), rest = !strcmp(name, "df_rest");
	if (!inventory && !journal && !rest && strcmp(name, "df_fast_travel")) return false;
	if (uiState != UiClosed)
	{
		SendUiCommand(DFB_KIND_UI_CLOSE, uiId);
		return true;
	}
	if (!UiCanOpen()) return true;
	if (inventory)
	{
		OpenUi(DFB_UI_INVENTORY);
		return true;
	}
	if (journal) // Daggerfall refuses travel from the journal's map unless Doom is outdoors, as below.
	{
		OpenUi(DFB_UI_JOURNAL, ownState.world_context);
		return true;
	}
	if (rest) // Daggerfall decides, with its own messages, from what Doom sees around the player.
	{
		OpenUi(DFB_UI_REST, RestState());
		return true;
	}
	// Daggerfall's own indoor check cannot see this: its hidden player waits outside the door Doom used.
	if (ownState.world_context != DFB_WORLD_EXTERIOR)
	{
		Printf(PRINT_HIGH, "You cannot travel from indoors.\n");
		Log("ui: open refused, indoors");
		return true;
	}
	OpenUi(DFB_UI_TRAVEL_MAP);
	return true;
}

void DD_BridgeDrawUi()
{
	if (ngState >= NgLoading) // The trip to the start location happens behind this.
	{
		Dim(twod, 0, 1.f, 0, 0, twod->GetWidth(), twod->GetHeight());
		const char *text = "Entering Daggerfall...";
		DrawText(twod, NewSmallFont, CR_GOLD, (twod->GetWidth() - NewSmallFont->StringWidth(text) * CleanXfac) / 2, twod->GetHeight() / 2, text, DTA_CleanNoMove, true, TAG_DONE);
		return;
	}
	if (uiState == UiClosed) return;
	Dim(twod, 0, 1.f, 0, 0, twod->GetWidth(), twod->GetHeight());
	if (!uiHasFrame) return;
	int x, y, w, h;
	UiRect(x, y, w, h);
	DrawTexture(twod, uiTextures[uiActiveTexture], x, y, DTA_DestWidth, w, DTA_DestHeight, h, DTA_LeftOffset, 0, DTA_TopOffset, 0, TAG_DONE);
}

// Runs on Doom's window thread while the GUI has the input. True means the message was consumed.
bool DD_BridgeUiWndProc(unsigned int message, unsigned long long wParam, long long lParam)
{
	if (uiState == UiClosed) return false;
	constexpr unsigned WmKillFocus = 0x0008, WmKeyDown = 0x0100, WmKeyUp = 0x0101, WmChar = 0x0102, WmSysKeyDown = 0x0104,
		WmSysKeyUp = 0x0105, WmSysChar = 0x0106, WmMouseMove = 0x0200, WmLDown = 0x0201, WmLUp = 0x0202, WmRDown = 0x0204,
		WmRUp = 0x0205, WmMDown = 0x0207, WmMUp = 0x0208, WmWheel = 0x020A;
	constexpr unsigned long long VkReturn = 0x0D, VkF4 = 0x73;
	// Test only: the scripted driver marks its mouse messages, because Windows also reports the real cursor.
	if (uiTestRemaining >= 0 && message >= WmMouseMove && message <= WmMUp && !(wParam & 0x8000)) return true;
	switch (message)
	{
	case WmKillFocus:
		SendUiInput(DFB_UI_INPUT_RELEASE_ALL);
		return false;
	case WmSysKeyDown:
		if (wParam == VkF4 || wParam == VkReturn) return false; // Keep Alt+F4 and Alt+Enter working.
		[[fallthrough]];
	case WmKeyDown:
		if (lParam & 0x40000000) return true; // Auto-repeat. Daggerfall tracks held keys itself.
		if (IsOpenMenuKey(lParam))
		{
			SendUiCommand(DFB_KIND_UI_CLOSE, uiId);
			return true;
		}
		SendUiInput(DFB_UI_INPUT_KEY_DOWN, MapPanKey(SidedVirtualKey(wParam, lParam), lParam));
		return true;
	case WmSysKeyUp:
	case WmKeyUp:
		SendUiInput(DFB_UI_INPUT_KEY_UP, MapPanKey(SidedVirtualKey(wParam, lParam), lParam));
		return true;
	case WmChar:
		if (wParam >= 32) SendUiInput(DFB_UI_INPUT_CHAR, int(wParam));
		return true;
	case WmSysChar:
		return false;
	case WmMouseMove:
		SendUiMouse(lParam);
		return true;
	case WmLDown: case WmRDown: case WmMDown:
		SendUiMouse(lParam);
		SendUiInput(DFB_UI_INPUT_BUTTON_DOWN, message == WmLDown ? 0 : message == WmRDown ? 1 : 2);
		return true;
	case WmLUp: case WmRUp: case WmMUp:
		SendUiMouse(lParam);
		SendUiInput(DFB_UI_INPUT_BUTTON_UP, message == WmLUp ? 0 : message == WmRUp ? 1 : 2);
		return true;
	case WmWheel:
		SendUiInput(DFB_UI_INPUT_WHEEL, int(int16_t((wParam >> 16) & 0xFFFF)) / 120);
		return true;
	}
	return false;
}

//==========================================================================
// Player HP. Daggerfall owns the value. Doom reports each hit or heal as a numbered event, shows
// Daggerfall's confirmed HP on the pawn, and only dies when Daggerfall reports death.
// Every function here does nothing outside a bridge session, or while Daggerfall has no live player.
//==========================================================================

namespace
{
constexpr int HpPendingRing = 4096;
constexpr int HpLogLimit = 600; // Per-event log lines; the summary line is not limited.

uint32_t hpNextEvent = 1;
uint32_t hpSeenApplied;
uint64_t hpHits, hpHeals, hpDirect, hpSendFailed, hpKills, hpLogged;
int64_t hpSentNs[HpPendingRing];
int hpSentDelta[HpPendingRing]; // Signed: + heal, - hit. For HpExpected.
Samples hpConfirm;
AActor *hpMaxPawn; // The pawn whose MaxHealth follows Daggerfall's max HP, and its own value to restore.
int hpMaxSaved;
constexpr int StockFullHealth = 100; // What mods write for "full health" (DRLA: A_JumpIfHealthLower(100) on medkits).
AActor *hpMirroredPawn;
int hpMirrored;
bool hpAllowKill;

bool HpActive()
{
	return session && !flowHold && peerSeen && (peerState.hp_flags & DFB_HPF_VALID) && !hpAllowKill;
}

bool HpIsBridgedPlayer(player_t *player)
{
	return player && player == &players[consoleplayer] && !(player->cheats & CF_PREDICTING);
}

void HpSend(uint32_t type, int amount, const char *source)
{
	dfb_event e{};
	e.kind = DFB_KIND_HP;
	e.tic = gametic;
	dfb_hp_event body{};
	body.event_no = hpNextEvent;
	body.type = type;
	body.amount = amount;
	body.sent_ns = dfb_now_ns();
	memcpy(e.payload, &body, sizeof(body));
	if (dfb_send(session, &e) != DFB_OK)
	{
		hpSendFailed++;
		Log("hp: event %u (%s %d) was refused by the bridge", hpNextEvent, type == DFB_HP_HIT ? "hit" : "heal", amount);
		return;
	}
	hpSentNs[hpNextEvent % HpPendingRing] = body.sent_ns;
	hpSentDelta[hpNextEvent % HpPendingRing] = type == DFB_HP_HIT ? -amount : amount;
	(type == DFB_HP_HIT ? hpHits : hpHeals)++;
	if (hpLogged++ < HpLogLimit)
		Log("hp: sent event %u: %s %d (%s), shown hp %d, confirmed hp %d, applied through %u", hpNextEvent,
			type == DFB_HP_HIT ? "hit" : "heal", amount, source, players[consoleplayer].health, peerState.hp_current,
			peerState.hp_applied_event);
	hpNextEvent++;
}

void HpTrackConfirmations()
{
	const uint32_t applied = peerState.hp_applied_event;
	const int64_t now = dfb_now_ns();
	for (; hpSeenApplied < applied && hpSeenApplied + 1 < hpNextEvent; hpSeenApplied++)
		hpConfirm.Add(now - hpSentNs[(hpSeenApplied + 1) % HpPendingRing]);
}

// Daggerfall's HP once it has applied every event Doom sent that it has not confirmed yet (it clamps each to
// 0..max). The shown health is only the confirmed value, so two pickups in one tic would otherwise both look
// useful.
int HpExpected()
{
	int hp = peerState.hp_current;
	const uint32_t applied = peerState.hp_applied_event;
	if (applied + 1 >= hpNextEvent || hpNextEvent - applied > 256) return hp; // Nothing pending, or not a sane gap
	for (uint32_t e = applied + 1; e < hpNextEvent; e++)
		hp = std::clamp(hp + hpSentDelta[e % HpPendingRing], 0, std::max(0, peerState.hp_max));
	return hp;
}

// Doom's own max health on the pawn (Player.MaxHealth, ACS APROP_SpawnHealth, P_GetRealMaxHealth) follows
// Daggerfall's max HP while Daggerfall owns HP, and goes back to the pawn's own value when it stops.
void HpFollowMax(player_t *player)
{
	AActor *pawn = player ? player->mo : nullptr;
	if (hpMaxPawn && hpMaxPawn != pawn) hpMaxPawn = nullptr; // A new pawn (map change, load): the old one is gone
	if (!pawn || peerState.hp_max <= 0) return;
	int &maxHealth = pawn->IntVar(NAME_MaxHealth);
	if (!hpMaxPawn)
	{
		hpMaxPawn = pawn;
		hpMaxSaved = maxHealth;
		Log("hp: Doom max health now follows Daggerfall's %d (pawn had %d)", peerState.hp_max, maxHealth);
	}
	else if (maxHealth != peerState.hp_max && hpLogged++ < HpLogLimit)
		Log("hp: Doom max health %d -> %d from Daggerfall", maxHealth, peerState.hp_max);
	maxHealth = peerState.hp_max;
}

void HpReleaseMax()
{
	if (!hpMaxPawn) return;
	if (players[consoleplayer].mo == hpMaxPawn) hpMaxPawn->IntVar(NAME_MaxHealth) = hpMaxSaved;
	hpMaxPawn = nullptr;
}
}

// True while Daggerfall owns this player's HP (Doom's heals are only requests).
bool DD_BridgeHpOwns(player_t *player)
{
	return HpActive() && HpIsBridgedPlayer(player);
}

// A_JumpIfHealthLower. Mods compare against Doom's stock full health (DRLA's stimpack and medikit fail unless
// health < 100); on the bridged player that number means Daggerfall's max HP, net of heals and hits in flight.
int DD_BridgeHpCheckLimit(AActor *actor, int health)
{
	if (health != StockFullHealth || !actor || !DD_BridgeHpOwns(actor->player) || actor->player->mo != actor) return health;
	return peerState.hp_max - HpExpected() + actor->health;
}

// P_DamageMobj, where the player's health would drop. True means the hit was reported and Doom must not
// change the player's health or run its own death.
bool DD_BridgeHpHit(player_t *player, int damage)
{
	if (!HpActive() || !HpIsBridgedPlayer(player) || damage <= 0) return false;
	HpSend(DFB_HP_HIT, damage, "damage");
	return true;
}

// P_DamageMobj, next to the source's DamageMultiply: the damage the bridged player deals to anything but itself,
// times Daggerfall's damage bonus (dfb_df_state.damage_bonus_bp). Unchanged with no session or a bonus of 0.
int DD_BridgeDamageBonus(AActor *source, AActor *target, int damage)
{
	const int32_t bp = peerState.damage_bonus_bp;
	if (!session || bp == 0 || damage <= 0 || !source || source == target || !HpIsBridgedPlayer(source->player) ||
		source->player->mo != source)
		return damage;
	const int scaled = std::max(1, int(damage * (1.0 + std::max(bp, -10000) / 10000.0)));
	static int logged;
	if (logged < 200)
	{
		logged++;
		Log("damage bonus: %s hit by the player, %d -> %d (%d bp)", target ? target->GetClass()->TypeName.GetChars() : "?",
			damage, scaled, bp);
	}
	return scaled;
}

// P_GiveBody. True means the heal was reported instead of applied; *accepted is what P_GiveBody returns.
bool DD_BridgeHpHeal(player_t *player, int num, int max, bool *accepted)
{
	if (!HpActive() || !HpIsBridgedPlayer(player)) return false;
	max = std::min(max, peerState.hp_max); // Do not consume a pickup Daggerfall could not use.
	const int health = HpExpected(); // Not the shown health: earlier heals may still be on their way.
	int amount = 0;
	if (num < 0)
	{
		const int target = max * -num / 100; // Strife style: raise to a percentage of full health
		if (health < target) amount = target - health;
	}
	else if (num > 0 && health < max)
	{
		num = std::max(1, int(num * G_SkillProperty(SKILLP_HealthFactor)));
		amount = std::min(num, max - health);
	}
	*accepted = amount > 0;
	if (amount > 0) HpSend(DFB_HP_HEAL, amount, "heal");
	return true;
}

// Start of P_PlayerThink: report health changes made by paths with no hook of their own (a script that
// assigns health, for example), then show Daggerfall's confirmed HP. Kills the pawn once Daggerfall says dead.
void DD_BridgeHpThink(player_t *player)
{
	if (!HpActive()) { hpMirroredPawn = nullptr; HpReleaseMax(); return; } // Re-adopt Daggerfall's value if it comes back
	if (!HpIsBridgedPlayer(player) || !player->mo || player->playerstate != PST_LIVE) return;
	HpFollowMax(player);
	DD_BridgeTestTic(); // Test only (-dfhptest steps that must run inside a tic), dd_bridge_test.cpp.
	if (peerState.hp_flags & DFB_HPF_DEAD)
	{
		hpKills++;
		Log("hp: Daggerfall reports death, killing the player (shown hp %d, applied through event %u)", player->health,
			peerState.hp_applied_event);
		hpAllowKill = true;
		P_DamageMobj(player->mo, nullptr, nullptr, 1000000, NAME_None, DMG_FORCED);
		hpAllowKill = false;
		return;
	}
	if (hpMirroredPawn == player->mo && player->health != hpMirrored)
	{
		const int delta = player->health - hpMirrored;
		hpDirect++;
		HpSend(delta < 0 ? DFB_HP_HIT : DFB_HP_HEAL, std::abs(delta), "direct assignment");
	}
	const int confirmed = std::max(1, peerState.hp_current); // 0 without the dead flag cannot be shown as alive
	player->health = player->mo->health = confirmed;
	hpMirrored = confirmed;
	hpMirroredPawn = player->mo;
}

//==========================================================================
// Synchronized save. Doom freezes and sends a request, which the ordered ring places after all its
// earlier events. Daggerfall applies those, writes a real save to a staging folder, and answers.
// Doom writes one .zds holding both games to a temp file, verifies it, and atomically replaces the
// old save. Any failure before that replace leaves the old save untouched.
//==========================================================================

void G_DoSaveGame(bool okForQuicksave, bool forceQuicksave, FString filename, const char *description);

namespace
{
namespace fs = std::filesystem;
constexpr int64_t SaveTimeoutNs = 10000000000LL;
constexpr int SaveFormat = 1;

enum SaveState { SaveIdle, SaveWaiting, SaveWriting };
SaveState saveState = SaveIdle;
uint32_t saveTxn;
bool saveSavedPause, saveCommitted, saveHaveReply;
int64_t saveStartNs;
FString saveFile, saveDescription, saveStage;
dfb_save_reply saveReply;
std::vector<std::vector<uint8_t>> saveBuffers;
const char *saveTestFail;
bool saveIsAuto, autosaveHeld, saveStartPending, savePendingAuto;
FString savePendingFile, savePendingDescription;
int64_t autosaveHeldUntil, saveReplyNs;
constexpr int64_t AutosaveHoldNs = 60000000000LL;
// A stitched map change autosaves before its first frame is shown, so the save adds to the load's hitch
// instead of making a second one in play. The screen keeps the last frame from before the change until it ends.
bool arrivalPending, arrivalQueued, saveIsArrival, arrivalSave;
int64_t arrivalAtNs;
constexpr int64_t ArrivalWaitNs = 2000000000LL, ArrivalHoldNs = 12000000000LL;
// While the change waits for its setup the playsim is frozen (DD_BridgeArrivalFreeze); a long hold says "Loading".
int arrivalFrozenTics;
int64_t arrivalFrozenNs;
constexpr int64_t LoadingAfterNs = 1000000000LL; // a normal arrival with its autosave ends in about 0.5 s: no flash

void ArrivalFreezeEnd(const char *why)
{
	if (arrivalFrozenTics) Log("arrival: playsim frozen %d tics, %.1f ms, until %s", arrivalFrozenTics, (dfb_now_ns() - arrivalFrozenNs) / 1e6, why);
	arrivalFrozenTics = 0;
}

bool SaveOnDaggerfallMap()
{
	double x, y, z, yaw;
	return gamestate == GS_LEVEL && DDTreadmill_PlayerWorld(x, y, z, yaw) != DD_AREA_NONE;
}

// For the save and load logs: where Doom's player is, in Daggerfall units.
FString WhereForLog()
{
	double x = 0, y = 0, z = 0, yaw = 0;
	int target = 0;
	FString where;
	where.Format("map %s", gamestate == GS_LEVEL ? primaryLevel->MapName.GetChars() : "-");
	if (gamestate != GS_LEVEL) return where;
	if (DDTreadmill_PlayerSpace(x, y, z, yaw, target)) where.AppendFormat(", space %d at %.1f,%.1f,%.1f", target, x, y, z);
	else if (DDTreadmill_PlayerWorld(x, y, z, yaw) == DD_AREA_EXTERIOR) where.AppendFormat(", world %.1f,%.1f", x, y);
	return where;
}

bool SaveReady()
{
	return uiState == UiClosed && !flowHold && !DDTreadmill_HandoffPending() && peerSeen && !peerStale && peerState.df_phase == DFB_DF_PHASE_PLAY;
}

fs::path SavePath(const char *utf8) { return fs::path(std::u8string(reinterpret_cast<const char8_t *>(utf8))); }

void SaveRemoveStage()
{
	if (saveStage.IsEmpty()) return;
	std::error_code ignored;
	fs::remove_all(SavePath(saveStage.GetChars()), ignored);
}

void SaveFinish(bool committed, const char *why)
{
	dfb_event e{};
	e.kind = DFB_KIND_SAVE_DONE;
	e.tic = gametic;
	const dfb_save_done body{ saveTxn, committed ? 1u : 0u };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
	dfb_flush(session);

	SaveRemoveStage();
	std::error_code ignored;
	fs::remove(SavePath((saveFile + ".tmp").GetChars()), ignored);
	saveBuffers.clear();
	saveState = SaveIdle;
	pauseext = saveSavedPause;
	const int64_t endNs = dfb_now_ns();
	Log("save %u: %s%s (%s), %.1f ms frozen, Daggerfall %.1f ms, Doom %.1f ms", saveTxn, saveIsArrival ? "map change autosave " : saveIsAuto ? "autosave " : "",
		committed ? "committed" : "FAILED, previous save untouched", why, (endNs - saveStartNs) / 1e6,
		saveReplyNs ? (saveReplyNs - saveStartNs) / 1e6 : 0.0, saveReplyNs ? (endNs - saveReplyNs) / 1e6 : 0.0);
	if (!committed) Printf(PRINT_HIGH, "Save failed: %s. Your previous save is unchanged.\n", why);
	DD_BridgeTestSaveDone(); // Test only: -dfsavetest quits here (dd_bridge_test.cpp).
}

bool SaveAddEntry(TArray<FCompressedBuffer> &content, TArray<FString> &names, const FString &name, const uint8_t *data, size_t size)
{
	std::vector<uint8_t> packed(compressBound(uLong(size)) + 64);
	z_stream stream{};
	if (deflateInit2(&stream, Z_DEFAULT_COMPRESSION, Z_DEFLATED, -MAX_WBITS, 8, Z_DEFAULT_STRATEGY) != Z_OK) return false;
	stream.next_in = const_cast<Bytef *>(data);
	stream.avail_in = uInt(size);
	stream.next_out = packed.data();
	stream.avail_out = uInt(packed.size());
	const int rc = deflate(&stream, Z_FINISH);
	const size_t packedSize = stream.total_out;
	deflateEnd(&stream);
	if (rc != Z_STREAM_END) return false;
	packed.resize(packedSize);
	saveBuffers.push_back(std::move(packed));
	FCompressedBuffer entry{};
	entry.mSize = size;
	entry.mCompressedSize = packedSize;
	entry.mMethod = FileSys::METHOD_DEFLATE;
	entry.mCRC32 = crc32(0, data, uInt(size));
	entry.mBuffer = reinterpret_cast<char *>(saveBuffers.back().data());
	content.Push(entry);
	names.Push(name);
	return true;
}

void SaveRun()
{
	saveState = SaveWriting;
	saveCommitted = false;
	player_t &player = players[consoleplayer];
	P_UnPredictClient(); // The save must hold the real player, not the prediction drawn between tics.
	if (saveReply.hp_applied != hpNextEvent - 1)
	{
		SaveFinish(false, "Daggerfall had not applied every HP event");
		return;
	}
	if ((peerState.hp_flags & DFB_HPF_VALID) && player.mo && saveReply.hp_current > 0)
	{
		player.health = player.mo->health = saveReply.hp_current; // Both halves hold Daggerfall's value.
		hpMirrored = saveReply.hp_current;
		hpMirroredPawn = player.mo;
	}
	try
	{
		G_DoSaveGame(!saveIsAuto, false, saveFile, saveDescription.GetChars());
	}
	catch (const CRecoverableError &error)
	{
		Printf(PRINT_HIGH, "%s\n", error.GetMessage());
		saveCommitted = false;
	}
	SaveFinish(saveCommitted, saveCommitted ? "both games saved" : "could not write the bundle");
}

void HandleSaveReply(const dfb_event &e)
{
	dfb_save_reply body;
	memcpy(&body, e.payload, sizeof(body));
	if (saveState != SaveWaiting || body.txn != saveTxn)
	{
		Log("save: ignored a late answer for transaction %u", body.txn);
		return;
	}
	if (body.status != DFB_SAVE_OK)
	{
		SaveFinish(false, body.status == DFB_SAVE_REFUSED ? "Daggerfall cannot save right now" : "Daggerfall could not write its save");
		return;
	}
	saveReply = body;
	saveHaveReply = true;
	saveReplyNs = dfb_now_ns();
	Log("save %u: Daggerfall prepared %u files, %llu bytes, hp %d/%d, position %d,%d", body.txn, body.file_count,
		(unsigned long long)body.total_bytes, body.hp_current, body.hp_max, body.world_x, body.world_z);
}

bool SaveStart(const char *filename, const char *description, bool isAuto);

// The autosave of a stitched map change, once the change's first tic has run and the map's setup is done (dd_setup.cpp:
// Daggerfall's door facts arm the locks). If either game cannot save then (a window open, a New Game still arriving),
// it is dropped rather than made later in play.
void PumpArrival(int64_t now)
{
	if (!arrivalPending || saveState != SaveIdle || saveStartPending) return;
	const bool handoff = DDTreadmill_HandoffPending();
	if (handoff && now - arrivalAtNs <= ArrivalWaitNs) return; // The new map's first tic finishes the change.
	if (!handoff && !DD_SetupReady(now)) return; // Bounded by the gate's own timeout.
	arrivalPending = false;
	ArrivalFreezeEnd(handoff ? "the handoff wait ran out" : "setup was done or timed out");
	if (!arrivalSave) return; // Autosaves are off: the wait only kept the map still until its setup was done.
	const bool alive = gamestate == GS_LEVEL && players[consoleplayer].playerstate == PST_LIVE && players[consoleplayer].health > 0;
	if (!handoff && alive && SaveOnDaggerfallMap() && SaveReady() && gameaction == ga_nothing && !paused)
	{
		arrivalQueued = true;
		Log("save: autosave for a map change, %.1f ms after the new map loaded (setup done at %.1f ms)", DD_SetupAgeMs(now), DD_SetupReadyMs());
		G_DoAutoSave(); // Queues it on the bridge; it starts below in this same frame.
		if (!saveStartPending) arrivalQueued = false;
		return;
	}
	Log("save: dropped the autosave for a map change, handoff %d, alive %d, ui %d, flow %d, Daggerfall phase %u, stale %d, paused %d",
		int(handoff), int(alive), int(uiState), int(flowHold), peerState.df_phase, int(peerStale), int(paused));
}

void PumpSave(int64_t now)
{
	PumpArrival(now);
	// Here no game tic is running, so nothing can happen in Doom between its final state and the request.
	if (saveStartPending && saveState == SaveIdle)
	{
		saveStartPending = false;
		SaveStart(savePendingFile.GetChars(), savePendingDescription.GetChars(), savePendingAuto);
	}
	// An autosave that came while Daggerfall was busy runs as soon as it is ready.
	if (autosaveHeld && saveState == SaveIdle)
	{
		if (now > autosaveHeldUntil || !SaveOnDaggerfallMap())
		{
			autosaveHeld = false;
			Log("save: dropped a held autosave");
		}
		else if (SaveReady() && DD_SetupReady(now) && gameaction == ga_nothing && !paused && !pauseext && players[consoleplayer].playerstate == PST_LIVE)
		{
			autosaveHeld = false;
			gameaction = ga_autosave;
		}
	}
	if (saveState != SaveWaiting) return;
	pauseext = true; // A focus change can clear it during the save.
	if (saveHaveReply)
	{
		saveHaveReply = false;
		SaveRun();
	}
	else if (peerStale) SaveFinish(false, "Daggerfall stopped responding");
	else if (now - saveStartNs > SaveTimeoutNs) SaveFinish(false, "Daggerfall did not answer in time");
}
}

bool DD_BridgeSaveActive() { return saveState != SaveIdle; }

// G_DoAutoSave: true while Daggerfall cannot save yet on a Daggerfall map. The autosave then runs when it can,
// so a Daggerfall map never gets a Doom-only autosave.
bool DD_BridgeAutosaveHold()
{
	if (!session || !SaveOnDaggerfallMap()) return false;
	if (saveState == SaveIdle && !saveStartPending && SaveReady() && DD_SetupReady(dfb_now_ns())) return false;
	if (!autosaveHeld) Log("save: holding an autosave until Daggerfall is ready and the map's setup is done");
	autosaveHeld = true;
	autosaveHeldUntil = dfb_now_ns() + AutosaveHoldNs;
	return true;
}

// Saves are asked for during a tic or menu event and start at the next frame.
static bool SaveQueue(const char *filename, const char *description, bool isAuto)
{
	if (saveState != SaveIdle || saveStartPending) { Printf("A save is already in progress.\n"); return true; }
	savePendingFile = filename;
	savePendingDescription = description;
	savePendingAuto = isAuto;
	saveStartPending = true;
	return true;
}

// G_DoAutoSave: true means the bridge took this autosave.
bool DD_BridgeAutosaveBegin(const char *filename, const char *description)
{
	if (!session || !SaveOnDaggerfallMap()) return false;
	return SaveQueue(filename, description, true);
}

// G_DoLoadLevel: a stitched map change has loaded. It waits for its setup (frozen), then autosaves if save is set
// (autosaves on), at the next frame once the setup is done (PumpArrival).
void DD_BridgeArrivalAutosave(bool save)
{
	if (!session || netgame) return;
	ArrivalFreezeEnd("another map change");
	arrivalSave = save;
	arrivalPending = true;
	arrivalQueued = false;
	arrivalAtNs = dfb_now_ns();
}

// P_Ticker, after DDTreadmill_Tick: true while a stitched map change waits for its setup (PumpArrival). The screen holds
// the old frame then, so nothing in the map may act unseen: no actor, player, weapon or sector special runs. The setup
// itself goes on: Daggerfall's answers arrive as network events (G_Ticker) and records (DDTreadmill_Tick, before this).
// Level time stands still, so scripts see every tic value after the wait. The first tic of the new map runs (it
// finishes the handoff).
bool DD_BridgeArrivalFrozen()
{
	return session && arrivalPending && primaryLevel && primaryLevel->maptime >= 1 && !DDTreadmill_HandoffPending()
		&& dfb_now_ns() - arrivalAtNs <= ArrivalHoldNs;
}

bool DD_BridgeArrivalFreeze(FLevelLocals *Level)
{
	if (Level != primaryLevel) return false;
	if (!DD_BridgeArrivalFrozen())
	{
		if (arrivalPending && dfb_now_ns() - arrivalAtNs > ArrivalHoldNs) ArrivalFreezeEnd("the hold limit");
		return false;
	}
	const int64_t now = dfb_now_ns();
	if (!arrivalFrozenTics++)
	{
		arrivalFrozenNs = now;
		Log("arrival: playsim frozen at maptime %d, %.1f ms after the map loaded, until its setup is done", Level->maptime, (now - arrivalAtNs) / 1e6);
	}
	return true;
}

int DD_BridgeArrivalFrozenTics() { return arrivalFrozenTics; }

// G_DoLoadLevel, after the map's WorldLoaded handlers: autosaves wait for this map's setup (dd_setup.cpp).
void DD_BridgeLevelLoaded(bool fromSave)
{
	if (session && !netgame) DD_SetupLevelLoaded(fromSave);
}

// D_DoomLoop: true while a map change's autosave runs, so the screen keeps showing the frame from before the change.
bool DD_BridgeHoldFrame()
{
	if (!session || dfb_now_ns() - arrivalAtNs > ArrivalHoldNs) return false;
	return arrivalPending || (saveStartPending && arrivalQueued) || (saveState != SaveIdle && saveIsArrival);
}

// D_DoomLoop, in place of D_Display while DD_BridgeHoldFrame: a short hold keeps the old frame; a long one (a slow setup
// or the arrival autosave) shows a loading message, drawn each frame so the window stays live.
void DD_BridgeDrawLoading()
{
	if (dfb_now_ns() - arrivalAtNs < LoadingAfterNs) return;
	static int64_t shownFor = 0;
	if (shownFor != arrivalAtNs) Log("arrival: showing the loading message, %.1f ms after the map loaded", (dfb_now_ns() - arrivalAtNs) / 1e6);
	shownFor = arrivalAtNs;
	static const char text[] = "Loading...";
	screen->BeginFrame();
	twod->ClearClipRect();
	twod->Begin(screen->GetWidth(), screen->GetHeight());
	ClearRect(twod, 0, 0, twod->GetWidth(), twod->GetHeight(), -1, 0); // opaque black
	DrawText(twod, BigFont, CR_UNTRANSLATED, (twod->GetWidth() - BigFont->StringWidth(text) * CleanXfac) / 2,
		(twod->GetHeight() - BigFont->GetHeight() * CleanYfac) / 2, text, DTA_CleanNoMove, true, TAG_DONE);
	twod->End();
	screen->Update();
	twod->OnFrameDone();
}

// G_SaveGame, for a save from the menu or console. True means the bridge took it, or refused it with a message.
bool DD_BridgeSaveBegin(const char *filename, const char *description)
{
	if (!session || (!SaveOnDaggerfallMap() && !DD_BridgeTestSaveAnyMap())) return false; // A regular WAD saves normally.
	return SaveQueue(filename, description, false);
}

namespace
{
bool SaveStart(const char *filename, const char *description, bool isAuto)
{
	const bool arrival = arrivalQueued;
	arrivalQueued = false;
	if (saveState != SaveIdle) { Printf("A save is already in progress.\n"); return true; }
	if (gamestate != GS_LEVEL || players[consoleplayer].health <= 0 || !SaveReady())
	{
		Printf(PRINT_HIGH, "Cannot save right now. Daggerfall is not ready.\n");
		Log("save: refused before starting, Daggerfall phase %u, stale %d", peerState.df_phase, int(peerStale));
		return true;
	}
	saveIsAuto = isAuto;
	saveIsArrival = arrival;
	saveReplyNs = 0;
	saveFile = filename;
	saveDescription = description;
	saveTxn++;
	saveStage.Format("%s.dfstage", filename);
	SaveRemoveStage();
	std::error_code error;
	fs::create_directories(SavePath(saveStage.GetChars()), error);
	uint32_t version;
	if (error || dfb_bulk_write(session, DFB_SAVE_PATH_SLOT, saveStage.GetChars(), uint32_t(saveStage.Len() + 1), &version) != DFB_OK)
	{
		SaveRemoveStage();
		Printf(PRINT_HIGH, "Save failed: could not prepare the staging folder. Your previous save is unchanged.\n");
		return true;
	}
	saveSavedPause = pauseext;
	pauseext = true;
	saveHaveReply = false;
	saveState = SaveWaiting;
	saveStartNs = dfb_now_ns();
	PublishPosition();
	dfb_publish_state(session, &ownState, sizeof(ownState)); // Daggerfall reads the frozen position after the request.
	dfb_event e{};
	e.kind = DFB_KIND_SAVE_REQUEST;
	e.tic = gametic;
	const dfb_save_request body{ saveTxn, hpNextEvent - 1, saveStartNs };
	memcpy(e.payload, &body, sizeof(body));
	DD_LocationsSave(session, e); // Behind the dungeon's record (dd_locations.cpp), paced so a big record cannot overflow.
	Log("save %u: Doom frozen at tic %d, %s, file %s, requested Daggerfall's save", saveTxn, gametic, WhereForLog().GetChars(), ExtractFileBase(filename, true).GetChars());
	return true;
}
}

FString DD_BridgeSaveWritePath(const FString &filename)
{
	return saveState == SaveWriting ? filename + ".tmp" : filename;
}

// Adds Daggerfall's staged files and the manifest to the zip.
bool DD_BridgeSaveAddFiles(TArray<FCompressedBuffer> &content, TArray<FString> &names)
{
	if (saveState != SaveWriting) return true;
	saveBuffers.clear();
	saveBuffers.reserve(256); // Entries point into these buffers, so they must not move.
	std::error_code error;
	const fs::path root = SavePath(saveStage.GetChars());
	uint32_t files = 0;
	uint64_t bytes = 0;
	FString list;
	for (fs::recursive_directory_iterator it(root, error), end; !error && it != end; it.increment(error))
	{
		if (!it->is_regular_file()) continue;
		if (saveBuffers.size() >= 250) return false;
		const std::u8string relative = fs::relative(it->path(), root, error).generic_u8string();
		if (error) return false;
		const std::string name(reinterpret_cast<const char *>(relative.data()), relative.size());
		std::ifstream in(it->path(), std::ios::binary);
		if (!in) return false;
		std::vector<uint8_t> data(size_t(it->file_size()));
		if (!data.empty()) in.read(reinterpret_cast<char *>(data.data()), std::streamsize(data.size()));
		if (!in || !SaveAddEntry(content, names, FStringf("doomerfall/daggerfall/%s", name.c_str()), data.data(), data.size())) return false;
		list.AppendFormat("%s\"%s\"", files ? "," : "", name.c_str());
		files++;
		bytes += data.size();
	}
	if (error || files != saveReply.file_count || bytes != saveReply.total_bytes)
	{
		Log("save %u: staged files do not match Daggerfall's report (%u files, %llu bytes)", saveTxn, files, (unsigned long long)bytes);
		return false;
	}
	FString manifest;
	manifest.Format("{\"format\":%d,\"txn\":%u,\"hp\":%d,\"hp_max\":%d,\"hp_applied\":%u,\"doom_hp\":%d,"
		"\"df_world\":[%d,%d],\"doom_world\":[%.3f,%.3f,%.3f],\"yaw\":%.3f,\"context\":%u,\"map_pixel\":[%d,%d],\"map\":\"%s\",\"campaign\":\"%s\",\"files\":[%s]}\n",
		SaveFormat, saveTxn, saveReply.hp_current, saveReply.hp_max, saveReply.hp_applied, players[consoleplayer].health,
		saveReply.world_x, saveReply.world_z, ownState.world_x, ownState.world_z, ownState.world_height, ownState.yaw_degrees,
		ownState.world_context, ownState.map_pixel_x, ownState.map_pixel_y, primaryLevel->MapName.GetChars(), campaignId.GetChars(), list.GetChars());
	if (!SaveAddEntry(content, names, "doomerfall/manifest.json", reinterpret_cast<const uint8_t *>(manifest.GetChars()), manifest.Len())) return false;
	return !(saveTestFail && !strcmp(saveTestFail, "uz_zip"));
}

// The commit point. True means the file named filename is now the new save.
bool DD_BridgeSaveCommit(const FString &written, const FString &filename)
{
	if (saveState != SaveWriting) return true;
	if (saveTestFail && !strcmp(saveTestFail, "uz_crash"))
	{
		Log("save %u: test crash after writing the temp file", saveTxn);
		std::_Exit(3);
	}
	if (saveTestFail && !strcmp(saveTestFail, "uz_commit")) return false;
	saveCommitted = dfb_atomic_replace(written.GetChars(), filename.GetChars()) == DFB_OK;
	return saveCommitted;
}

//==========================================================================
// Synchronized load and the death screen. Doom freezes, proves the whole bundle is intact, and stages
// Daggerfall's files. Daggerfall checks its half and restores first, then Doom restores, and play resumes
// only when both have confirmed. Nothing is touched until both halves pass their checks.
//==========================================================================

bool G_DDCheckSave(FResourceFile *resfile, FString &map);
bool G_DDLoadNow(const char *file);
void D_StartTitle();

namespace
{
constexpr int64_t LoadTimeoutNs = 30000000000LL, LoadPeerWaitNs = 15000000000LL, DeathViewNs = 2500000000LL, LoadStallNs = 10000000000LL;
enum LoadState { LoadIdle, LoadPending, LoadWaitDf, LoadWaitResume };
enum DeathState { DeathNone, DeathView, DeathMenu };
LoadState loadState = LoadIdle;
DeathState deathState = DeathNone;
bool loadBroken; // Daggerfall or Doom lost its game in a failed load, so only another load can continue.
bool atTitle;
uint32_t loadTxn;
int64_t loadStartNs, deathAtNs;
FString loadFile, loadStage;
dfb_save_reply loadReply;

struct BundleInfo
{
	int hp = 0, hpMax = 0, x = 0, z = 0;
	uint32_t files = 0;
	FString map, campaign;
};

bool ManifestInt(const std::string &text, const char *key, int &out)
{
	const std::string needle = std::string("\"") + key + "\":";
	const size_t at = text.find(needle);
	return at != std::string::npos && sscanf(text.c_str() + at + needle.size(), "%d", &out) == 1;
}

bool ManifestPair(const std::string &text, const char *key, int &a, int &b)
{
	const std::string needle = std::string("\"") + key + "\":[";
	const size_t at = text.find(needle);
	return at != std::string::npos && sscanf(text.c_str() + at + needle.size(), "%d,%d", &a, &b) == 2;
}

std::string LowerName(std::string name)
{
	std::transform(name.begin(), name.end(), name.begin(), [](unsigned char c) { return char(tolower(c)); });
	return name;
}

// Proves every entry's checksum and that the manifest, Doom's half, and the Daggerfall files agree.
// With extract set, also writes the Daggerfall files to the stage. Never changes the save.
bool BundleCheck(const char *file, BundleInfo &info, FString &why, const fs::path *extract)
{
	try
	{
		std::unique_ptr<FResourceFile> res(FResourceFile::OpenResourceFile(file, true));
		if (!res) { why = "the file cannot be read"; return false; }
		const int manifestEntry = res->FindEntry("doomerfall/manifest.json");
		if (manifestEntry < 0) { why = "it is not a Doomerfall save"; return false; }
		std::vector<std::string> names;
		for (uint32_t i = 0; i < res->EntryCountU(); i++)
		{
			FCompressedBuffer raw = res->GetRawData(i);
			const uint32_t expected = raw.mCRC32;
			raw.Clean();
			auto data = res->Read(i);
			if (crc32(0, reinterpret_cast<const Bytef *>(data.data()), uInt(data.size())) != expected)
			{
				why.Format("damaged entry %s", res->getName(i));
				return false;
			}
			const std::string name = res->getName(i);
			static const std::string prefix = "doomerfall/daggerfall/";
			if (LowerName(name).compare(0, prefix.size(), prefix)) continue;
			const std::string relative = name.substr(prefix.size());
			if (relative.empty() || relative.find("..") != std::string::npos || relative[0] == '/' || relative.find(':') != std::string::npos)
			{
				why = "unsafe file name in the bundle";
				return false;
			}
			names.push_back(LowerName(relative));
			if (extract)
			{
				const fs::path target = *extract / SavePath(relative.c_str());
				std::error_code error;
				fs::create_directories(target.parent_path(), error);
				std::ofstream out(target, std::ios::binary);
				if (error || !out.write(reinterpret_cast<const char *>(data.data()), std::streamsize(data.size())))
				{
					why = "could not stage the Daggerfall files";
					return false;
				}
			}
		}
		auto manifestData = res->Read(manifestEntry);
		const std::string manifest(reinterpret_cast<const char *>(manifestData.data()), manifestData.size());
		int format = 0;
		if (!ManifestInt(manifest, "format", format) || format != SaveFormat) { why = "unsupported bundle format"; return false; }
		if (!ManifestInt(manifest, "hp", info.hp) || !ManifestInt(manifest, "hp_max", info.hpMax) ||
			!ManifestPair(manifest, "df_world", info.x, info.z)) { why = "the manifest is incomplete"; return false; }
		const size_t mapAt = manifest.find("\"map\":\""), listAt = manifest.find("\"files\":[");
		if (mapAt == std::string::npos || listAt == std::string::npos) { why = "the manifest is incomplete"; return false; }
		const size_t mapEnd = manifest.find('"', mapAt + 7);
		const std::string manifestMap = manifest.substr(mapAt + 7, mapEnd - mapAt - 7);
		const size_t campaignAt = manifest.find("\"campaign\":\""); // Absent in saves made before New Game existed.
		if (campaignAt != std::string::npos)
		{
			const size_t campaignEnd = manifest.find('"', campaignAt + 12);
			if (campaignEnd != std::string::npos) info.campaign = manifest.substr(campaignAt + 12, campaignEnd - campaignAt - 12).c_str();
		}
		std::vector<std::string> listed;
		const size_t listEnd = manifest.find(']', listAt);
		for (size_t at = manifest.find('"', listAt + 9); at != std::string::npos && at < listEnd;)
		{
			const size_t end = manifest.find('"', at + 1);
			if (end == std::string::npos) break;
			listed.push_back(LowerName(manifest.substr(at + 1, end - at - 1)));
			at = manifest.find('"', end + 1);
		}
		std::sort(names.begin(), names.end());
		std::sort(listed.begin(), listed.end());
		if (names.empty() || names != listed) { why = "the Daggerfall files do not match the manifest"; return false; }
		info.files = uint32_t(names.size());
		if (!G_DDCheckSave(res.get(), info.map)) { why = "Doom's half does not fit this game or its mods"; return false; }
		if (info.map.CompareNoCase(manifestMap.c_str())) { why = "Doom's half and the manifest name different maps"; return false; }
		return true;
	}
	catch (const std::exception &error)
	{
		why.Format("the file is damaged (%s)", error.what());
		return false;
	}
}

void LoadRemoveStage()
{
	if (loadStage.IsEmpty()) return;
	std::error_code ignored;
	fs::remove_all(SavePath(loadStage.GetChars()), ignored);
	loadStage = "";
}

// Refused before anything changed: the running game simply continues.
void LoadRefuse(const char *why)
{
	LoadRemoveStage();
	const bool wasFrozen = loadState == LoadWaitDf;
	loadState = LoadIdle;
	if (wasFrozen && !loadBroken) pauseext = false;
	if (!loadBroken && !atTitle) flowHold = false;
	Log("load: refused, %s", why);
	Printf(PRINT_HIGH, "Cannot load that save: %s.\n", why);
	if (gamestate == GS_STARTUP) D_StartTitle();
}

// A half was lost. Neither game may run until a save loads, so the death screen stays up.
void LoadBreak(const char *why)
{
	LoadRemoveStage();
	loadState = LoadIdle;
	loadBroken = true;
	flowHold = true;
	Log("load: FAILED after restore began, %s", why);
	Printf(PRINT_HIGH, "Load failed: %s. Choose another save.\n", why);
	if (gamestate != GS_LEVEL)
	{
		atTitle = true;
		D_StartTitle();
	}
	deathState = DeathMenu;
}

void LoadStart()
{
	BundleInfo info;
	FString why;
	loadTxn = ++saveTxn;
	loadStage.Format("%s.load.dfstage", loadFile.GetChars());
	std::error_code error;
	const fs::path stage = SavePath(loadStage.GetChars());
	fs::remove_all(stage, error);
	fs::create_directories(stage, error);
	if (error) { LoadRefuse("could not prepare the staging folder"); return; }
	if (!BundleCheck(loadFile.GetChars(), info, why, &stage)) { LoadRefuse(why.GetChars()); return; }
	loadCampaign = info.campaign;
	uint32_t version;
	if (dfb_bulk_write(session, DFB_SAVE_PATH_SLOT, loadStage.GetChars(), uint32_t(loadStage.Len() + 1), &version) != DFB_OK)
	{
		LoadRefuse("could not reach Daggerfall");
		return;
	}
	pauseext = true;
	flowHold = true;
	loadState = LoadWaitDf;
	loadStartNs = dfb_now_ns();
	dfb_event e{};
	e.kind = DFB_KIND_LOAD_REQUEST;
	e.tic = gametic;
	const dfb_load_request body{ loadTxn, info.hp, info.hpMax, info.x, info.z, info.files, loadStartNs };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
	dfb_flush(session);
	Log("load %u: bundle checked (%u Daggerfall files, hp %d/%d, map %s), Doom frozen", loadTxn, info.files, info.hp, info.hpMax, info.map.GetChars());
}

void SendLoadDone(bool ok)
{
	dfb_event e{};
	e.kind = DFB_KIND_LOAD_DONE;
	e.tic = gametic;
	const dfb_save_done body{ loadTxn, ok ? 1u : 0u };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
	dfb_flush(session);
}

void LoadRestoreDoom()
{
	hpMirroredPawn = nullptr;
	bool ok = false;
	try
	{
		if (gamestate == GS_LEVEL) P_UnPredictClient(); // The drawn prediction must not outlive the level it points into.
		ok = G_DDLoadNow(loadFile.GetChars());
	}
	catch (const CRecoverableError &error)
	{
		Printf(PRINT_HIGH, "%s\n", error.GetMessage());
	}
	LoadRemoveStage();
	// Before the done event, so Daggerfall knows which side of the door Doom restored before it resumes.
	int doorAction, doorTarget;
	double doorX, doorY;
	if (ok && DDTreadmill_CurrentDoor(doorAction, doorX, doorY, doorTarget)) DD_BridgeTransition(doorAction, doorX, doorY, doorTarget);
	SendLoadDone(ok);
	if (!ok)
	{
		LoadBreak("Doom could not restore its half");
		return;
	}
	player_t &player = players[consoleplayer];
	if (player.mo && loadReply.hp_current > 0) player.health = player.mo->health = loadReply.hp_current; // Daggerfall's value.
	loadState = LoadWaitResume;
	Log("load %u: Doom restored map %s at tic %d, hp %d", loadTxn, primaryLevel->MapName.GetChars(), gametic, player.health);
}

void HandleLoadReady(const dfb_event &e)
{
	dfb_save_reply body;
	memcpy(&body, e.payload, sizeof(body));
	if (loadState != LoadWaitDf || body.txn != loadTxn) return;
	if (body.status == DFB_SAVE_REFUSED) { LoadRefuse("Daggerfall rejected its half of the save"); return; }
	if (body.status != DFB_SAVE_OK) { SendLoadDone(false); LoadBreak("Daggerfall could not restore its half"); return; }
	loadReply = body;
	LoadRestoreDoom();
}

void HandleLoadResume(const dfb_event &e)
{
	dfb_save_done body;
	memcpy(&body, e.payload, sizeof(body));
	if (loadState != LoadWaitResume || body.txn != loadTxn) return;
	loadState = LoadIdle;
	loadBroken = atTitle = flowHold = false;
	campaignId = loadCampaign;
	deathState = DeathNone;
	pauseext = false;
	M_ClearMenus();
	DD_ItemsResync();
	DD_MonstersResync();
	DD_LocationsResync();
	DD_NpcsResync();
	DD_TownsfolkResync();
	Log("load %u: both games resumed, %.1f ms frozen, %s", loadTxn, (dfb_now_ns() - loadStartNs) / 1e6, WhereForLog().GetChars());
}

// The newest save in the save folder that passes every check.
bool NewestBundle(FString &out)
{
	std::vector<std::pair<fs::file_time_type, fs::path>> found;
	std::error_code error;
	const FString folder = G_GetSavegamesFolder();
	for (fs::directory_iterator it(SavePath(folder.GetChars()), error), end; !error && it != end; it.increment(error))
		if (it->is_regular_file() && it->path().extension() == ".zds") found.emplace_back(it->last_write_time(), it->path());
	std::sort(found.begin(), found.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
	for (const auto &entry : found)
	{
		const std::u8string text = entry.second.generic_u8string();
		const FString name(reinterpret_cast<const char *>(text.c_str()));
		BundleInfo info;
		FString why;
		if (BundleCheck(name.GetChars(), info, why, nullptr))
		{
			if (campaignId.IsNotEmpty() && info.campaign.Compare(campaignId.GetChars())) continue; // Another character's save.
			out = name;
			return true;
		}
		Log("load: skipping %s: %s", name.GetChars(), why.GetChars());
	}
	return false;
}

void PumpDeath(int64_t now)
{
	if (loadState != LoadIdle) return;
	if (loadBroken && gamestate == GS_LEVEL) pauseext = true;
	if (atTitle && !loadBroken) return;
	const player_t &player = players[consoleplayer];
	if (deathState == DeathNone && gamestate == GS_LEVEL && SaveOnDaggerfallMap() && player.mo &&
		(player.playerstate == PST_DEAD || player.playerstate == PST_REBORN))
	{
		deathState = DeathView;
		deathAtNs = now + DeathViewNs;
		Log("death: showing Doom's death view");
	}
	if (deathState == DeathView && now >= deathAtNs) deathState = DeathMenu;
	if (deathState == DeathMenu && !menuactive && gameaction == ga_nothing)
	{
		M_StartControlPanel(false);
		M_SetMenu(FName("DoomerfallDeathMenu"), -1);
		Log("death: showing the death menu");
	}
}

void PumpLoad(int64_t now)
{
	if (loadState == LoadPending && saveState == SaveIdle && !saveStartPending && uiState == UiClosed)
	{
		if (peerSeen && !peerStale) LoadStart();
		else if (now - loadStartNs > LoadPeerWaitNs) LoadRefuse("Daggerfall is not responding");
	}
	if (loadState == LoadWaitDf || loadState == LoadWaitResume)
	{
		pauseext = true;
		// Daggerfall's load blocks its main thread for seconds (its scene build), as a new character's does (NgStallNs).
		if (now - loadStartNs > LoadTimeoutNs || (peerStale && now - peerStaleAt > LoadStallNs))
		{
			SendLoadDone(false);
			LoadBreak("Daggerfall stopped responding");
		}
	}
	PumpDeath(now);
}
}

bool DD_BridgeBlocksNewGame()
{
	if (!session || !atTitle) return false;
	if (ngState == NgDifficulty)
	{
		ngState = NgLoading;
		ngDeadline = dfb_now_ns() + 60000000000LL;
		Log("new game: difficulty chosen, loading the start map");
		return false;
	}
	Printf(PRINT_HIGH, "Load a save to continue.\n");
	Log("title: refused a new game, no Daggerfall game is loaded");
	return true;
}

// DoReborn on a Daggerfall map: the player stays dead until the death screen loads a save.
bool DD_BridgeDeathHold(int playernum)
{
	if (!session || playernum != consoleplayer || !SaveOnDaggerfallMap()) return false;
	players[playernum].playerstate = PST_DEAD;
	return true;
}

// G_LoadGame. True means the bridge took the load, or refused it with a message.
bool DD_BridgeLoadBegin(const char *filename)
{
	if (!session) return false;
	bool bundle = false, doomerfallMap = false;
	try
	{
		std::unique_ptr<FResourceFile> res(FResourceFile::OpenResourceFile(filename, true));
		if (res)
		{
			bundle = res->FindEntry("doomerfall/manifest.json") >= 0;
			FString map;
			if (!bundle && G_DDCheckSave(res.get(), map)) doomerfallMap = DDTreadmill_FindLevelInfo(map.GetChars()) != nullptr;
		}
	}
	catch (const std::exception &) {}
	if (!bundle)
	{
		if (!doomerfallMap && !SaveOnDaggerfallMap() && !flowHold && deathState == DeathNone) return false; // A regular WAD loads normally.
		Log("load: refused %s, not a Doomerfall save", filename);
		Printf(PRINT_HIGH, "Cannot load that save: it is not a Doomerfall save.\n");
		return true;
	}
	if (loadState != LoadIdle || saveState != SaveIdle || saveStartPending || uiState != UiClosed || ngState != NgIdle)
	{
		Printf(PRINT_HIGH, "Cannot load right now.\n");
		return true;
	}
	loadFile = filename;
	loadState = LoadPending;
	loadStartNs = dfb_now_ns();
	return true;
}

CCMD(dd_death_loadlast)
{
	if (!session || deathState == DeathNone || loadState != LoadIdle) return;
	FString newest;
	if (!NewestBundle(newest))
	{
		Printf(PRINT_HIGH, "No usable Doomerfall save was found.\n");
		Log("death: no usable save for Load Last Save");
		return;
	}
	M_ClearMenus();
	Log("death: loading the newest save, %s", newest.GetChars());
	DD_BridgeLoadBegin(newest.GetChars());
}

static void ReturnToTitle();

CCMD(dd_death_mainmenu)
{
	if (!session || deathState == DeathNone || loadState != LoadIdle) return;
	ReturnToTitle();
}

// Doom's End Game option in a Doomerfall game. Daggerfall holds, so neither half runs on alone.
bool DD_BridgeEndGame()
{
	if (!session || !flowMode) return false;
	if (!atTitle && loadState == LoadIdle && saveState == SaveIdle && ngState == NgIdle) ReturnToTitle();
	return true;
}

static void ReturnToTitle()
{
	dfb_event e{};
	e.kind = DFB_KIND_HOLD;
	e.tic = gametic;
	const uint64_t hold = 1;
	memcpy(e.payload, &hold, sizeof(hold));
	dfb_send(session, &e);
	dfb_flush(session);
	M_ClearMenus();
	deathState = DeathNone;
	loadBroken = false;
	atTitle = flowHold = true;
	pauseext = false;
	campaignId = "";
	Log("death: returning to the title, Daggerfall held until a save is loaded");
	D_StartTitle();
}

//==========================================================================
// New Game. Only runs with -dfflow.
//==========================================================================

void M_DDOpenSkillMenu();
void M_DDConfirmAbandon(bool plain);

namespace
{
void NgFreeze(bool on)
{
	player_t &player = players[consoleplayer];
	if (!player.mo) return;
	if (on) player.cheats |= CF_TOTALLYFROZEN | CF_GODMODE;
	else player.cheats &= ~(CF_TOTALLYFROZEN | CF_GODMODE);
}

void NgSendArrived(bool ok)
{
	dfb_event e{};
	e.kind = DFB_KIND_NEWGAME_ARRIVED;
	e.tic = gametic;
	const uint64_t value = ok ? 1 : 0;
	memcpy(e.payload, &value, sizeof(value));
	dfb_send(session, &e);
	dfb_flush(session);
}

void NgFail(const char *why)
{
	Log("new game: FAILED, %s", why);
	Printf(PRINT_HIGH, "Could not start the game: %s.\n", why);
	const bool started = ngState >= NgDifficulty || ngHaveWorld || ngResult;
	const bool inLevel = ngState >= NgLoading && gamestate == GS_LEVEL;
	if (inLevel) NgFreeze(false);
	if (started) NgSendArrived(false);
	ngState = NgIdle;
	ngHaveWorld = ngResult = ngPlain = false;
	atTitle = flowHold = true;
	M_ClearMenus();
	if (inLevel) D_StartTitle();
}

// Which live monsters the new character starts near, and whether the nearest can see the player.
void LogMonstersNearStart()
{
	AActor *pmo = players[consoleplayer].mo;
	if (!pmo) return;
	constexpr double Radius = 1024;	// Doom units
	int near = 0, seen = 0, total = 0;
	AActor *nearest = nullptr;
	double best = 1e30;
	auto it = primaryLevel->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (!(mo->flags3 & MF3_ISMONSTER) || mo->health <= 0) continue;
		total++;
		const double d = (mo->Pos() - pmo->Pos()).Length();
		if (d > Radius) continue;
		near++;
		if (P_CheckSight(mo, pmo, SF_IGNOREVISIBILITY)) seen++;
		if (d < best) { best = d; nearest = mo; }
	}
	Log("new game: %d monsters on the map, %d within %.0f units of the start, %d of those can see the player%s%s%s", total, near, Radius, seen,
		nearest ? ", nearest " : "", nearest ? nearest->GetClass()->TypeName.GetChars() : "", nearest ? FStringf(" at %.0f", best).GetChars() : "");
}

// Plain load: Doom is in the saved place. Daggerfall gets the starter gun facts, then the arrival.
void PlainArrived()
{
	double x = 0, y = 0, z = 0, yaw = 0;
	int target = -1;
	if (plainWorld.context == DFB_WORLD_EXTERIOR)
	{
		DDTreadmill_PlayerWorld(x, y, z, yaw);
		Log("plain load: Doom player at %.1f,%.1f yaw %.1f outdoors, %.1f units from the save", x, y, yaw,
			sqrt((x - plainWorld.world_x) * (x - plainWorld.world_x) + (y - plainWorld.world_z) * (y - plainWorld.world_z)));
	}
	else if (DDTreadmill_PlayerSpace(x, y, z, yaw, target))
		Log("plain load: Doom player at %.1f,%.1f,%.1f yaw %.1f in space %d, %.1f units from the save", x, y, z, yaw, target,
			sqrt((x - plainWorld.start_x) * (x - plainWorld.start_x) + (y - plainWorld.start_y) * (y - plainWorld.start_y)));
	DD_ItemsSendStarter();
	NgSendArrived(true);
	ngState = NgWaitGo;
}

void PumpNewGame(int64_t now)
{
	if (!flowMode) return;
	if (ngState == NgIdle) return;
	if (ngState != NgWaitDf && peerStale)
	{
		if (uiState == UiClosed && now - peerStaleAt > NgStallNs) NgFail("Daggerfall stopped responding");
		return;
	}
	if (ngState >= NgLoading)
	{
		if (now > ngDeadline) { NgFail("the start location did not load"); return; }
		if (gamestate == GS_LEVEL) NgFreeze(true);
	}
	switch (ngState)
	{
	case NgWaitDf:
		if (peerSeen && !peerStale && peerState.df_phase != DFB_DF_PHASE_BOOT && peerState.df_phase != DFB_DF_PHASE_LOADING) // After a death it may still report play or dead.
		{
			ngState = NgCreating;
			ngHaveWorld = ngResult = false;
			M_ClearMenus();
			OpenUi(ngPlain ? DFB_UI_LOAD_GAME : DFB_UI_NEW_GAME);
		}
		else if (now > ngDeadline) NgFail("Daggerfall is not ready");
		return;
	case NgCreating:
		if (uiState != UiClosed) return;
		if (ngHaveWorld)
		{
			ngState = NgDifficulty;
			ngAskedAbandon = false;
			ngPromptAt = now;
			M_DDOpenSkillMenu();
			Log("new game: asking for a difficulty");
		}
		else if (!ngResult)
		{
			ngState = NgIdle;
			Log(ngPlain ? "plain load: closed Daggerfall's Load window without loading, at the title" : "new game: backed out of character creation, at the title");
			ngPlain = false;
		}
		else if (now > ngDeadline) NgFail("Daggerfall did not place the character");
		return;
	case NgDifficulty:
		if (!menuactive && gameaction == ga_nothing)
		{
			// Escape closed the prompt without a choice. Ask before dropping the character; after No, ask for a difficulty again.
			// An Escape in the prompt's first second is a late one meant for the cinematics, so the prompt just comes back.
			if (!ngAskedAbandon && now < ngPromptAt + NgEscapeGraceNs)
			{
				M_DDOpenSkillMenu();
				Log("new game: Escape right after the difficulty prompt opened, showing it again");
				return;
			}
			ngAskedAbandon = !ngAskedAbandon;
			if (ngAskedAbandon) M_DDConfirmAbandon(ngPlain);
			else M_DDOpenSkillMenu();
			Log(ngAskedAbandon ? "new game: Escape at the difficulty prompt, asking whether to return to the title" : "new game: asking for a difficulty again");
		}
		return;
	case NgLoading:
		if (gamestate == GS_LEVEL && gameaction == ga_nothing && !DDTreadmill_HandoffPending() && primaryLevel->maptime >= 2 &&
			(ngPlain ? DDTreadmill_RequestTravel(plainWorld.world_x, plainWorld.world_z, plainWorld.yaw_degrees)
				: DDTreadmill_RequestTravel(ngWorld.world_x, ngWorld.world_z, ngWorld.yaw_degrees)))
		{
			ngState = NgTravel;
			ngTravelAt = now + 1000000000LL;
			if (ngPlain) Log("plain load: travelling to %.1f,%.1f", plainWorld.world_x, plainWorld.world_z);
			else Log("new game: travelling to pixel %d,%d", ngWorld.map_pixel_x, ngWorld.map_pixel_y);
		}
		return;
	case NgTravel:
		if (now < ngTravelAt || gamestate != GS_LEVEL || gameaction != ga_nothing || DDTreadmill_HandoffPending() || primaryLevel->maptime < 2) return;
		if (ngPlain)
		{
			if (plainWorld.context == DFB_WORLD_EXTERIOR)
			{
				PlainArrived();
				return;
			}
			if (primaryLevel->MapName.CompareNoCase("DDOVER01") == 0) return; // Still on the overworld.
			const double start[4] = { plainWorld.start_x, plainWorld.start_y, plainWorld.start_z, plainWorld.start_yaw };
			if (plainWorld.context == DFB_WORLD_DUNGEON)
			{
				Log("plain load: at the entrance in %s, going inside dungeon %d", primaryLevel->MapName.GetChars(), plainWorld.dungeon_map_id);
				DDTreadmill_RequestDungeon(plainWorld.dungeon_map_id, start);
			}
			else
			{
				Log("plain load: in %s, going into the building whose door is at %.1f,%.1f", primaryLevel->MapName.GetChars(), plainWorld.world_x, plainWorld.world_z);
				DDTreadmill_RequestBuilding(plainWorld.world_x, plainWorld.world_z, 256, start);
			}
			ngState = NgDoor;
			return;
		}
		if (ngWorld.dungeon_map_id < 0)
		{
			NgSendArrived(true);
			ngState = NgWaitGo;
			return;
		}
		if (primaryLevel->MapName.CompareNoCase("DDOVER01") == 0) return; // Still on the overworld.
		{
			Log("new game: at the entrance in %s, going inside dungeon %d", primaryLevel->MapName.GetChars(), ngWorld.dungeon_map_id);
			// Daggerfall's start marker. Without one (not a number), Doom keeps the map start, the entrance.
			const double start[4] = { ngWorld.start_x, ngWorld.start_y, ngWorld.start_z, ngWorld.start_yaw };
			const bool haveStart = std::isfinite(start[0]) && std::isfinite(start[1]) && std::isfinite(start[2]) && std::isfinite(start[3]);
			if (haveStart) Log("new game: Daggerfall's start point is %.1f,%.1f,%.1f yaw %.1f", start[0], start[1], start[2], start[3]);
			else Log("new game: Daggerfall sent no start point, using the map start");
			DDTreadmill_RequestDungeon(ngWorld.dungeon_map_id, haveStart ? start : nullptr);
		}
		ngState = NgDoor;
		return;
	case NgDoor:
	{
		if (gamestate != GS_LEVEL || gameaction != ga_nothing || DDTreadmill_HandoffPending() || primaryLevel->maptime < 2) return;
		double x, y, z, yaw;
		const DDPlayerArea area = DDTreadmill_PlayerWorld(x, y, z, yaw);
		if (ngPlain)
		{
			if (area != (plainWorld.context == DFB_WORLD_DUNGEON ? DD_AREA_DUNGEON : DD_AREA_INTERIOR)) return;
			PlainArrived();
			return;
		}
		if (area != DD_AREA_DUNGEON) return;
		int target;
		if (DDTreadmill_PlayerSpace(x, y, z, yaw, target))
			Log("new game: Doom player at %.1f,%.1f,%.1f yaw %.1f in dungeon %d, %.1f units from Daggerfall's start point", x, y, z, yaw, target,
				std::isfinite(ngWorld.start_x) ? sqrt((x - ngWorld.start_x) * (x - ngWorld.start_x) + (y - ngWorld.start_y) * (y - ngWorld.start_y)) : -1.0);
		LogMonstersNearStart();
		Log("new game: Doom is inside the dungeon on %s, telling Daggerfall", primaryLevel->MapName.GetChars());
		NgSendArrived(true);
		ngState = NgWaitGo;
		return;
	}
	default:
		return;
	}
}

void HandleNewGameGo()
{
	if (ngState != NgWaitGo) return;
	NgFreeze(false);
	ngState = NgIdle;
	if (ngPlain) Log("plain load: Daggerfall resumed the loaded save, Doom starts with its default class");
	ngHaveWorld = ngResult = ngPlain = false;
	atTitle = flowHold = false;
	campaignId.Format("%016llx", (unsigned long long)dfb_now_ns() ^ (unsigned long long)(uintptr_t)&ngWorld);
	Log("new game: both games running, campaign %s, hp %d/%d", campaignId.GetChars(), peerState.hp_current, peerState.hp_max);
	ngSave = NgsWaiting;
	ngSaveAttempts = 0;
	ngSaveQuietSince = 0;
	ngSaveGoNs = dfb_now_ns();
	ngSaveFile = G_BuildSaveName(DD_BridgeSlotName("newgame").GetChars());
}

// After New Game, makes one normal synchronized save at the start point, once Daggerfall's opening messages are
// done: nothing open in either game for NgSaveQuietNs. The file name carries the new campaign id, so it never
// replaces another save; an existing file is left alone.
constexpr int64_t NgSaveQuietNs = 2000000000LL;	// Daggerfall asks for its own windows 0.25 s after opening them.
constexpr int64_t NgSaveGiveUpNs = 600000000000LL;
constexpr int NgSaveMaxAttempts = 3;

void PumpNewGameSave(int64_t now)
{
	if (ngSave == NgsNone || ngSave == NgsDone) return;
	player_t &player = players[consoleplayer];
	if (atTitle || loadState != LoadIdle || campaignId.IsEmpty() || now - ngSaveGoNs > NgSaveGiveUpNs)
	{
		Log("new game save: dropped, %s", atTitle ? "back at the title" : loadState != LoadIdle ? "a save is loading" : "it never became quiet");
		ngSave = NgsNone;
		return;
	}
	if (ngSave == NgsWriting)
	{
		if (saveState != SaveIdle || saveStartPending) return;
		std::error_code error;
		if (fs::exists(SavePath(ngSaveFile.GetChars()), error))
		{
			ngSave = NgsDone;
			Log("new game save: written to %s, hp %d at %.1f,%.1f", ngSaveFile.GetChars(), ngSaveHp, ngSavePos[0], ngSavePos[1]);
			return;
		}
		ngSave = ++ngSaveAttempts < NgSaveMaxAttempts ? NgsWaiting : NgsNone;
		ngSaveQuietSince = 0;
		Log("new game save: attempt %d failed%s", ngSaveAttempts, ngSave == NgsNone ? ", giving up" : ", trying again");
		return;
	}
	if (player.playerstate != PST_LIVE || player.health <= 0)
	{
		Log("new game save: dropped, the player died first");
		ngSave = NgsNone;
		return;
	}
	const bool quiet = gamestate == GS_LEVEL && SaveReady() && SaveOnDaggerfallMap() && saveState == SaveIdle && !saveStartPending &&
		!autosaveHeld && gameaction == ga_nothing && !menuactive && !paused;
	if (!quiet) { ngSaveQuietSince = 0; return; }
	if (!ngSaveQuietSince) ngSaveQuietSince = now;
	if (now - ngSaveQuietSince < NgSaveQuietNs) return;
	std::error_code error;
	if (fs::exists(SavePath(ngSaveFile.GetChars()), error))
	{
		Log("new game save: %s already exists, left alone", ngSaveFile.GetChars());
		ngSave = NgsNone;
		return;
	}
	double yaw;
	int space;
	if (!DDTreadmill_PlayerSpace(ngSavePos[0], ngSavePos[1], ngSavePos[2], yaw, space)) // Inside: dungeon or building space.
		DDTreadmill_PlayerWorld(ngSavePos[0], ngSavePos[1], ngSavePos[2], yaw);
	ngSaveHp = peerState.hp_current;
	ngSave = NgsWriting;
	Log("new game save: opening messages done, saving to %s", ngSaveFile.GetChars());
	SaveQueue(ngSaveFile.GetChars(), FStringf("New game %s", myasctime()).GetChars(), true);
}
}

void M_DDConfirmNewGame();

static void NgBegin()
{
	ngState = NgWaitDf;
	ngDeadline = dfb_now_ns() + 30000000000LL;
	M_ClearMenus();
	Log("new game: chosen in Doom's menu");
}

// Called for the first menu in Doom's new game chain. True means this flow took it.
bool DD_BridgeNewGameMenu()
{
	if (!session || !flowMode || ngState == NgDifficulty) return false;
	if (ngState != NgIdle || loadState != LoadIdle) return true;
	if (atTitle) NgBegin();
	else if (saveState == SaveIdle && !saveStartPending) M_DDConfirmNewGame(); // As stock Doom: confirm, then start over.
	return true;
}

// Yes to the New Game question in a running game: the game is dropped unsaved, both games go to the title as End
// Game does (Daggerfall held), and New Game starts from there. Character creation resets Daggerfall's side and
// entering DDOVER01 resets Doom's world table.
void DD_BridgeNewGameFromGame()
{
	if (!session || !flowMode || atTitle || ngState != NgIdle || loadState != LoadIdle || saveState != SaveIdle || saveStartPending) return;
	Log("new game: chosen in a running game, campaign %s dropped", campaignId.IsEmpty() ? "-" : campaignId.GetChars());
	if (gamestate == GS_LEVEL) P_UnPredictClient();
	ngSave = NgsNone;
	ReturnToTitle();
	NgBegin();
}

// Escape's main menu stays shut while New Game or a plain load is under way: Daggerfall's screens, the difficulty
// prompt, and the trip to the start each answer Escape themselves.
bool DD_BridgeBlocksMainMenu()
{
	if (!session || !flowMode || ngState == NgIdle) return false;
	Log("new game: kept Doom's main menu closed, new game step %d", int(ngState));
	return true;
}

// Yes to the question Escape at the difficulty prompt asks: Daggerfall drops the held character, and both games
// stay at the title, where New Game starts over.
void DD_BridgeAbandonCharacter()
{
	if (!session || ngState != NgDifficulty) return;
	NgSendArrived(false);
	Log(ngPlain ? "plain load: returned to the title from the difficulty prompt, Daggerfall's save was not resumed"
		: "new game: returned to the title from the difficulty prompt, the character was dropped");
	ngState = NgIdle;
	ngHaveWorld = ngResult = ngPlain = ngAskedAbandon = false;
	atTitle = flowHold = true;
}

// Loads a plain Daggerfall save (one with no Doom half) from Daggerfall's own Load window. Doom then starts its default
// class in the saved place, as New Game does. Only at Doom's title in a -dfflow session.
CCMD(dd_load_daggerfall)
{
	if (!session || !flowMode) return;
	if (ngState != NgIdle || !atTitle || loadState != LoadIdle)
	{
		Printf(PRINT_HIGH, "End the current game before loading a Daggerfall save.\n");
		return;
	}
	ngPlain = true;
	ngState = NgWaitDf;
	ngDeadline = dfb_now_ns() + 30000000000LL;
	M_ClearMenus();
	Log("plain load: chosen, opening Daggerfall's Load window");
}

// The next map for G_DoNewGame, or null for Doom's own.
const char *DD_BridgeNewGameMap()
{
	return session && ngState == NgLoading ? "DDOVER01" : nullptr;
}

// Keeps each character's auto and quick slots apart. Unchanged outside a Doomerfall campaign.
FString DD_BridgeSlotName(const char *slot)
{
	if (!session || campaignId.IsEmpty()) return slot;
	return FStringf("%s-%s", campaignId.GetChars(), slot);
}

// True when a save or load could start now and none is in flight (dd_facetest.cpp).
bool DD_BridgeSaveIdle() { return SaveReady() && loadState == LoadIdle && saveState == SaveIdle && !saveStartPending; }

// Read-only state and a few actions for the bridge test drivers (dd_bridge_test.cpp).
void DD_BridgeTestView(DDBridgeTestView &v)
{
	v.peerSeen = peerSeen;
	v.dfPhase = peerState.df_phase;
	v.hpValid = (peerState.hp_flags & DFB_HPF_VALID) != 0;
	v.hpDead = (peerState.hp_flags & DFB_HPF_DEAD) != 0;
	v.hpCurrent = peerState.hp_current;
	v.hpMax = peerState.hp_max;
	v.hpApplied = peerState.hp_applied_event;
	v.hpSent = hpNextEvent - 1;
	v.flowMode = flowMode;
	v.atTitle = atTitle;
	v.ngIdle = ngState == NgIdle;
	v.ngDifficulty = ngState == NgDifficulty;
	v.ngPlain = ngPlain;
	v.flowHold = flowHold;
	v.settled = loadState == LoadIdle && saveState == SaveIdle && !saveStartPending;
	v.saveIdle = saveState == SaveIdle;
	v.saveReady = SaveReady();
	v.uiClosed = uiState == UiClosed;
	v.daggerfallUiOpen = uiId == DFB_UI_DAGGERFALL && uiState == UiOpen;
	v.death = int(deathState);
	v.ngSaveDone = ngSave == NgsDone;
	v.ngSaveBusy = ngSave == NgsWaiting || ngSave == NgsWriting;
	v.ngSaveHp = ngSaveHp;
	memcpy(v.ngSavePos, ngSavePos, sizeof(v.ngSavePos));
	v.loadFile = loadFile.GetChars();
	std::error_code ignored;
	v.loadedNewGameSave = loadFile.IsNotEmpty() && ngSaveFile.IsNotEmpty() &&
		fs::equivalent(SavePath(loadFile.GetChars()), SavePath(ngSaveFile.GetChars()), ignored);
}
void DD_BridgeTestHit(int amount, const char *source) { HpSend(DFB_HP_HIT, amount, source); }
void DD_BridgeTestSendText(const char *text) { SendText(text); }
void DD_BridgeTestCloseUi() { if (uiState != UiClosed) SendUiCommand(DFB_KIND_UI_CLOSE, uiId); }
void DD_BridgeTestForceLog() { nextLogNs = 0; }

void DD_BridgeInit()
{
	if (session) return;
	const char *id = Args->CheckValue(FArg_dfbridge);
	if (!id) return;

	const int rc = dfb_attach(id, DFB_SIDE_UZ, &session);
	if (rc != DFB_OK)
		I_FatalError("Could not attach to Doomerfall bridge session '%s' (error %d)", id, rc);
	dd_bridge_session = true; // door locks hold (door_objects.zs DFDoorHandler.LocksHold)

	if (const char *path = Args->CheckValue(FArg_dfbridgelog))
		logFile = fopen(path, "ab");
	saveTestFail = Args->CheckValue(FArg_dfsavetestfail);
	flowMode = Args->CheckParm(FArg_dfflow) != 0;
	if (flowMode) atTitle = flowHold = true; // No game exists until New Game or Load Game makes one.
	if (const char *count = Args->CheckValue(FArg_dfuitest)) uiTestRemaining = atoi(count);
	else uiTestRemaining = -1;
	Log("attached to session %s, protocol %u, layout %016llx", id, dfb_protocol_version(),
		(unsigned long long)dfb_layout_hash());

	dfb_event hello{};
	hello.kind = DFB_KIND_HELLO;
	dfb_hello body{};
	body.side = DFB_SIDE_UZ;
	body.now_ns = dfb_now_ns();
	memcpy(hello.payload, &body, sizeof(body));
	dfb_send(session, &hello);
	SendText("hello from UZDoom");
	if (gameaction == ga_loadgame || gameaction == ga_loadgamehidecon) // -loadgame ran before the bridge attached.
	{
		const FString startup = savename;
		const gameaction_t action = gameaction;
		gameaction = ga_nothing;
		if (!DD_BridgeLoadBegin(startup.GetChars())) gameaction = action;
	}
}

void DD_QaFrame(); // [Doomerfall] QA bot (dd_qa.cpp), inactive without -ddqa
void DD_BridgeFrame()
{
	DD_QaFrame();
	if (!session) return;

	const int64_t now = dfb_now_ns();
	dfb_event e;
	while (dfb_receive(session, &e) == DFB_GOT) HandleEvent(e, dfb_now_ns()); // stamp after receipt

	if (dfb_read_state(session, &peerState, sizeof(peerState)) == DFB_GOT)
		stateAge.Add(dfb_now_ns() - peerState.published_ns);
	RefreshSheet();
	HpTrackConfirmations();

	if (int(peerState.df_phase) != *dd_sync_df_phase) dd_sync_df_phase = int(peerState.df_phase);
	PublishPosition();
	DD_ItemsFrame(session, ownState.world_context, ownState.space_valid != 0, ownState.space_target);
	DD_MonstersFrame(session, ownState.world_context, ownState.space_valid != 0, ownState.space_target);
	DD_LocationsFrame(session);
	DD_NpcsFrame(session, ownState.world_context, ownState.space_valid != 0, ownState.space_target);
	DD_TownsfolkFrame(session, ownState.world_context);
	DD_ClimbFrame(session);
	DD_FacesFrame(session);
	DD_GuardsFrame(session, ownState.world_context, ownState.space_valid != 0, ownState.space_target);
	DD_DoorsFrame(ownState.world_context, ownState.space_valid != 0, ownState.space_target);
	DD_LookFrame(session);

	ownState.uz_heartbeat++;
	ownState.uz_tic = gametic;
	ownState.demo_value = gametic;
	ownState.uz_phase = (paused || pauseext) ? DFB_UZ_PHASE_PAUSED
		: gamestate == GS_LEVEL ? DFB_UZ_PHASE_PLAY : DFB_UZ_PHASE_BOOT;
	dfb_publish_state(session, &ownState, sizeof(ownState));

	const int64_t age = dfb_peer_state_age_ns(session);
	const bool alive = age >= 0 && age < StaleNs;
	if (alive && !peerSeen)
	{
		peerSeen = true;
		Log("Daggerfall is live");
	}
	if (peerSeen && alive == peerStale)
	{
		peerStale = !alive;
		if (!alive) peerStaleAt = now;
		Log(alive ? "Daggerfall heartbeat resumed" : "Daggerfall heartbeat stale (logged only, gameplay unchanged)");
	}

	if (alive && now >= nextPingNs)
	{
		nextPingNs = now + PingIntervalNs;
		dfb_event ping{};
		ping.kind = DFB_KIND_PING;
		ping.tic = gametic;
		dfb_ping body{};
		body.id = nextPing++;
		body.sent_ns = dfb_now_ns();
		memcpy(ping.payload, &body, sizeof(body));
		dfb_send(session, &ping);
	}
	PumpUi(now);
	PumpSave(now);
	PumpLoad(now);
	PumpNewGame(now);
	PumpNewGameSave(now);
	RunUiTest(now);
	DD_BridgeTestFrame(now); // Test only, does nothing without a test flag (dd_bridge_test.cpp).
	dfb_flush(session);

	if (now >= nextLogNs)
	{
		nextLogNs = now + LogIntervalNs;
		dfb_stats stats;
		dfb_get_stats(session, &stats);
		char a[96], b[96], c[96], d[96];
		rtt.Format(a, sizeof(a));
		oneWayOut.Format(b, sizeof(b));
		oneWayIn.Format(c, sizeof(c));
		stateAge.Format(d, sizeof(d));
		Log("tic=%d maptime=%d paused=%d pauseext=%d menu=%d heartbeat=%llu df_frame=%u df_value=%u answered=%llu pongs=%llu gaps=%llu unknown=%llu outbox=%u",
			gametic, primaryLevel ? primaryLevel->maptime : -1, paused, (int)pauseext, (int)menuactive,
			(unsigned long long)ownState.uz_heartbeat, peerState.df_frame, peerState.demo_value,
			(unsigned long long)pingsAnswered, (unsigned long long)pongsReceived, (unsigned long long)stats.seq_gaps,
			(unsigned long long)unknownKinds, stats.outbox_count);
		Log("latency rtt %s | uz->df %s | df->uz %s | df state age %s", a, b, c, d);
		if (peerState.hp_flags & DFB_HPF_VALID)
		{
			char h[96];
			hpConfirm.Format(h, sizeof(h));
			Log("hp: shown=%d confirmed=%d/%d dead=%d sent=%u applied=%u hits=%llu heals=%llu direct=%llu refused=%llu kills=%llu | event to confirmed %s",
				players[consoleplayer].health, peerState.hp_current, peerState.hp_max, (peerState.hp_flags & DFB_HPF_DEAD) ? 1 : 0,
				hpNextEvent - 1, peerState.hp_applied_event, (unsigned long long)hpHits, (unsigned long long)hpHeals,
				(unsigned long long)hpDirect, (unsigned long long)hpSendFailed, (unsigned long long)hpKills, h);
			hpConfirm.count = hpConfirm.next = 0;
		}
		rtt.count = rtt.next = oneWayOut.count = oneWayOut.next = 0; // each line covers one window
		oneWayIn.count = oneWayIn.next = stateAge.count = stateAge.next = 0;
	}
}
