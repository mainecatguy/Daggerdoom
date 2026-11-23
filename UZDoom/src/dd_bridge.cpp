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
#include "v_video.h"

void G_SaveGame(const char *filename, const char *description, bool quick);
extern FString savename;

FARG_ADVANCED(dfbridge, "Doomerfall", "session", "Attaches to the Doomerfall bridge session created by the launcher.");
FARG_ADVANCED(dfbridgelog, "Doomerfall", "file", "Appends Doomerfall bridge traffic and latency to a log file.");
FARG_ADVANCED(dfuitest, "Doomerfall", "count", "Bridge test only: opens the fast travel menu this many times.");
FARG_ADVANCED(dfbridgetestpause, "Doomerfall", "ext|game|menu", "Bridge test only: enters a pause state for six seconds.");

FARG_ADVANCED(dfsavetest, "Doomerfall", "file|autoN", "Save test only: makes one synchronized save to this file, or N real autosaves, then quits.");
FARG_ADVANCED(dfsavetestfail, "Doomerfall", "uz_zip|uz_commit|uz_crash", "Save test only: fails the save at this step.");

FARG_ADVANCED(dfloadtest, "Doomerfall", "mode:file", "Load test only: cycle, death, menu, or bad, using this save file.");

FARG_ADVANCED(dfhptest, "Doomerfall", "basic|monsters", "HP sync test only: scripts hits, heals, and a lethal hit.");

CVAR(Int, dd_sync_df_phase, 0, CVAR_NOSAVE) // Read by the position sync test route.
CVAR(Int, dd_ui_test_hold, 0, CVAR_NOSAVE | CVAR_MOD) // Test only: a route holds -dfuitest until it reaches the place to open the menu.

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
Samples rtt, oneWayOut, oneWayIn, stateAge;
uint32_t nextPing = 1;
uint64_t pingsAnswered, pongsReceived, unknownKinds;
int64_t nextPingNs, nextLogNs;
bool peerSeen, peerStale;

void Log(const char *format, ...)
{
	char line[512];
	va_list args;
	va_start(args, format);
	vsnprintf(line, sizeof(line), format, args);
	va_end(args);
	Printf(PRINT_NONOTIFY, "[bridge] %s\n", line);
	if (logFile)
	{
		fprintf(logFile, "%.3f %s\n", dfb_now_ns() / 1e9, line);
		fflush(logFile);
	}
}

// Test only (-dfbridgetestpause): enters a real pause state, holds it, and leaves it.
const char *testPause;
int testPhase;
int64_t testAtNs;

void SetTestPause(bool on)
{
	if (!strcmp(testPause, "ext")) pauseext = on;
	else if (!strcmp(testPause, "game")) C_DoCommand("pause");
	else if (!strcmp(testPause, "menu")) C_DoCommand(on ? "menu_main" : "closemenu");
}

void RunTestPause(int64_t now)
{
	if (!testPause || testPhase == 2 || !peerSeen || gamestate != GS_LEVEL) return;
	if (!testAtNs) testAtNs = now + 5000000000LL;
	if (now < testAtNs) return;
	const bool begin = testPhase == 0;
	Log("test pause %s: %s", testPause, begin ? "begin" : "end");
	SetTestPause(begin);
	testPhase++;
	testAtNs = now + 6000000000LL;
	nextLogNs = 0;
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
void HandleSaveReply(const dfb_event &e);
void HandleLoadReady(const dfb_event &e);
void HandleLoadResume(const dfb_event &e);
bool flowHold; // A load is running, or a failed load or the title left no game both halves agree on.

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
	case DFB_KIND_SAVE_PREPARED:
		HandleSaveReply(e);
		break;
	case DFB_KIND_LOAD_READY:
		HandleLoadReady(e);
		break;
	case DFB_KIND_LOAD_RESUME:
		HandleLoadResume(e);
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
		Log("message from Daggerfall: \"%s\" (seq %u)", text, e.seq);
		break;
	}
	case DFB_KIND_HELLO:
		Log("hello from Daggerfall (seq %u)", e.seq);
		break;
	default:
		unknownKinds++; // contract rule 7: skip, never fatal
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

void SendUiCommand(uint16_t kind, uint32_t id)
{
	dfb_event e{};
	e.kind = kind;
	e.tic = gametic;
	const dfb_ui_command body{ id, 0, dfb_now_ns() };
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

void OpenUi(uint32_t id)
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
	SendUiCommand(DFB_KIND_UI_OPEN, id);
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
	FinishUi(body.reason < 5 ? reasons[body.reason] : "unknown");
}

void HandleUiResult(const dfb_event &e)
{
	dfb_ui_result body;
	memcpy(&body, e.payload, sizeof(body));
	body.name[sizeof(body.name) - 1] = 0;
	Log("ui: fast travel destination chosen: %s at map pixel %d,%d (not applied)", body.name, body.map_pixel_x, body.map_pixel_y);
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
	if (peerStale)
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

void RunUiTest(int64_t now)
{
	if (uiTestRemaining <= 0 || dd_ui_test_hold || uiState != UiClosed || gamestate != GS_LEVEL || peerState.df_phase != DFB_DF_PHASE_PLAY) return;
	if (!uiTestAtNs) uiTestAtNs = now + 3000000000LL;
	if (now < uiTestAtNs) return;
	uiTestRemaining--;
	uiTestAtNs = 0;
	C_DoCommand("netevent df_fast_travel");
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

bool IsFastTravelKey(long long lParam)
{
	int key = int((lParam >> 16) & 0xFF);
	if ((lParam >> 24) & 1) key |= 0x80;
	return Bindings.GetBinding(key).CompareNoCase("netevent df_fast_travel") == 0;
}
}

bool DD_BridgeUiActive() { return uiState != UiClosed; }
bool DD_BridgeSaveActive();

bool DD_BridgeNetEvent(const char *name)
{
	if (session && !strcmp(name, "df_hp_damage")) // Demo only: stands in for a Daggerfall-side attacker
	{
		SendText("hptest damage 15");
		return true;
	}
	if (!session || strcmp(name, "df_fast_travel")) return false;
	if (uiState != UiClosed)
	{
		SendUiCommand(DFB_KIND_UI_CLOSE, uiId);
		return true;
	}
	if (gamestate != GS_LEVEL || flowHold || players[consoleplayer].health <= 0 || DDTreadmill_HandoffPending() || DD_BridgeSaveActive()) return true; // Not while going through a door or map seam, or saving.
	if (!peerSeen || peerStale || peerState.df_phase != DFB_DF_PHASE_PLAY)
	{
		Printf("Daggerfall is not ready to show the travel map.\n");
		Log("ui: open refused, Daggerfall phase %u", peerState.df_phase);
		return true;
	}
	OpenUi(DFB_UI_TRAVEL_MAP);
	return true;
}

void DD_BridgeDrawUi()
{
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
		if (IsFastTravelKey(lParam))
		{
			SendUiCommand(DFB_KIND_UI_CLOSE, uiId);
			return true;
		}
		SendUiInput(DFB_UI_INPUT_KEY_DOWN, SidedVirtualKey(wParam, lParam));
		return true;
	case WmSysKeyUp:
	case WmKeyUp:
		SendUiInput(DFB_UI_INPUT_KEY_UP, SidedVirtualKey(wParam, lParam));
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
Samples hpConfirm;
AActor *hpMirroredPawn;
int hpMirrored;
bool hpAllowKill;
int hpTestPending; // Test only: a step that must run inside a tic. Outside a tic the player is a prediction copy.
void HpTestTicStep();

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
}

// P_DamageMobj, where the player's health would drop. True means the hit was reported and Doom must not
// change the player's health or run its own death.
bool DD_BridgeHpHit(player_t *player, int damage)
{
	if (!HpActive() || !HpIsBridgedPlayer(player) || damage <= 0) return false;
	HpSend(DFB_HP_HIT, damage, "damage");
	return true;
}

// P_GiveBody. True means the heal was reported instead of applied; *accepted is what P_GiveBody returns.
bool DD_BridgeHpHeal(player_t *player, int num, int max, bool *accepted)
{
	if (!HpActive() || !HpIsBridgedPlayer(player)) return false;
	max = std::min(max, peerState.hp_max); // Do not consume a pickup Daggerfall could not use.
	int amount = 0;
	if (num < 0)
	{
		const int target = max * -num / 100; // Strife style: raise to a percentage of full health
		if (player->health < target) amount = target - player->health;
	}
	else if (num > 0 && player->health < max)
	{
		num = std::max(1, int(num * G_SkillProperty(SKILLP_HealthFactor)));
		amount = std::min(num, max - player->health);
	}
	*accepted = amount > 0;
	if (amount > 0) HpSend(DFB_HP_HEAL, amount, "heal");
	return true;
}

// Start of P_PlayerThink: report health changes made by paths with no hook of their own (a script that
// assigns health, for example), then show Daggerfall's confirmed HP. Kills the pawn once Daggerfall says dead.
void DD_BridgeHpThink(player_t *player)
{
	if (!HpActive()) { hpMirroredPawn = nullptr; return; } // Re-adopt Daggerfall's value if it comes back
	if (!HpIsBridgedPlayer(player) || !player->mo || player->playerstate != PST_LIVE) return;
	if (hpTestPending) HpTestTicStep();
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
// Test only (-dfhptest basic|monsters): drives hits, heals, rapid hits, Daggerfall-side damage, a direct
// health assignment, and a lethal hit through Doom's real code, logging what the player shows at each step.
//==========================================================================

namespace
{
const char *hpTestMode;
int hpTestStep;
int64_t hpTestNextNs;

void HpTestLog(const char *what)
{
	const player_t &p = players[consoleplayer];
	Log("hp test: %s | shown=%d confirmed=%d/%d state=%d sent=%u applied=%u", what, p.health, peerState.hp_current,
		peerState.hp_max, int(p.playerstate), hpNextEvent - 1, peerState.hp_applied_event);
}

void RunHpTest(int64_t now)
{
	if (!hpTestMode || hpTestStep < 0 || gamestate != GS_LEVEL || !(peerState.hp_flags & DFB_HPF_VALID) || !players[consoleplayer].mo) return;
	if (hpTestPending) return;
	if (!hpTestNextNs) hpTestNextNs = now + 2000000000LL;
	if (now < hpTestNextNs) return;
	const bool settled = peerState.hp_applied_event + 1 >= hpNextEvent;
	if (!settled && now < hpTestNextNs + 3000000000LL) return; // Wait for Daggerfall to confirm the last step.
	if (!strcmp(hpTestMode, "monsters"))
	{
		if (hpTestStep == 0)
		{
			C_DoCommand("summon DoomImp");
			C_DoCommand("summon DoomImp");
			C_DoCommand("summon DoomImp");
			HpTestLog("summoned three imps");
		}
		else if (hpTestStep % 4 == 0) HpTestLog("monsters");
		hpTestStep++;
		hpTestNextNs = now + 500000000LL;
		return;
	}

	if (hpTestStep >= 1 && hpTestStep <= 7)
	{
		hpTestPending = hpTestStep; // Done at the next player tic by HpTestTicStep
		return;
	}
	switch (hpTestStep)
	{
	case 0: HpTestLog("start"); break;
	case 8: HpTestLog("after Daggerfall reported death"); break;
	case 9: HpTestLog("finished"); hpTestStep = -1; C_DoCommand("quit"); return;
	}
	hpTestStep++;
	hpTestNextNs = now + (hpTestStep == 8 ? 1500000000LL : 600000000LL);
}

void HpTestTicStep()
{
	player_t &p = players[consoleplayer];
	AActor *mo = p.mo;
	char note[96];
	switch (hpTestPending)
	{
	case 1: P_DamageMobj(mo, nullptr, nullptr, 40, NAME_None); HpTestLog("after one hit of 40 (same tic)"); break;
	case 2: P_GiveBody(mo, 25, 100); HpTestLog("after a heal of 25 (same tic)"); break;
	case 3:
		for (int i = 0; i < 20; i++) P_DamageMobj(mo, nullptr, nullptr, 1 + i % 3, NAME_None);
		HpTestLog("after 20 rapid hits in one tic");
		break;
	case 4: SendText("hptest damage 15"); HpTestLog("asked Daggerfall for 15 damage"); break;
	case 5: p.health -= 6; HpTestLog("after a direct health assignment of -6"); break;
	case 6: C_DoCommand("give medikit"); HpTestLog("queued give medikit"); break;
	case 7:
		P_DamageMobj(mo, nullptr, nullptr, 500, NAME_None);
		snprintf(note, sizeof(note), "after a lethal hit of 500 (same tic), player alive=%d", p.playerstate == PST_LIVE);
		HpTestLog(note);
		break;
	}
	hpTestStep = hpTestPending + 1;
	hpTestPending = 0;
	hpTestNextNs = dfb_now_ns() + (hpTestStep == 8 ? 1500000000LL : 600000000LL);
}
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
const char *saveTestFile, *saveTestFail;
bool saveTestStarted;
int64_t saveTestAtNs;
int saveTestAutos; // Autosaves still to trigger in an autoN test.
bool saveIsAuto, autosaveHeld, saveStartPending, savePendingAuto;
FString savePendingFile, savePendingDescription;
int64_t autosaveHeldUntil, saveReplyNs;
constexpr int64_t AutosaveHoldNs = 60000000000LL;

bool SaveOnDaggerfallMap()
{
	double x, y, z, yaw;
	return gamestate == GS_LEVEL && DDTreadmill_PlayerWorld(x, y, z, yaw) != DD_AREA_NONE;
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
	Log("save %u: %s%s (%s), %.1f ms frozen, Daggerfall %.1f ms, Doom %.1f ms", saveTxn, saveIsAuto ? "autosave " : "",
		committed ? "committed" : "FAILED, previous save untouched", why, (endNs - saveStartNs) / 1e6,
		saveReplyNs ? (saveReplyNs - saveStartNs) / 1e6 : 0.0, saveReplyNs ? (endNs - saveReplyNs) / 1e6 : 0.0);
	if (!committed) Printf(PRINT_HIGH, "Save failed: %s. Your previous save is unchanged.\n", why);
	if (saveTestFile && saveTestAutos <= 0) C_DoCommand("quit"); // An autoN test continues after a failure, to prove play resumes.
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

void PumpSave(int64_t now)
{
	// Here no game tic is running, so nothing can happen in Doom between its final state and the request.
	if (saveStartPending && saveState == SaveIdle)
	{
		saveStartPending = false;
		SaveStart(savePendingFile.GetChars(), savePendingDescription.GetChars(), savePendingAuto);
	}
	if (saveTestFile && !strncmp(saveTestFile, "auto", 4))
	{
		// Goes through the same net command as a real autosave.
		if (!saveTestStarted && gamestate == GS_LEVEL && SaveReady())
		{
			saveTestStarted = true;
			saveTestAutos = std::max(atoi(saveTestFile + 4), 1);
			saveTestAtNs = now + 2000000000LL;
		}
		if (saveTestAutos > 0 && saveState == SaveIdle && now >= saveTestAtNs && gamestate == GS_LEVEL && SaveReady())
		{
			saveTestAutos--;
			saveTestAtNs = now + 1500000000LL;
			for (int i = 0; i < 5; i++) HpSend(DFB_HP_HIT, 1, "autosave test");
			Net_WriteInt8(DEM_CHECKAUTOSAVE);
		}
	}
	else if (saveTestFile && !saveTestStarted && peerSeen && gamestate == GS_LEVEL && peerState.df_phase == DFB_DF_PHASE_PLAY)
	{
		if (!saveTestAtNs) saveTestAtNs = now + 2000000000LL;
		if (now >= saveTestAtNs)
		{
			saveTestStarted = true;
			for (int i = 0; i < 20; i++) HpSend(DFB_HP_HIT, 1, "save test"); // In flight when the request is sent.
			G_SaveGame(saveTestFile, "Doomerfall save test", false);
		}
	}
	// An autosave that came while Daggerfall was busy runs as soon as it is ready.
	if (autosaveHeld && saveState == SaveIdle)
	{
		if (now > autosaveHeldUntil || !SaveOnDaggerfallMap())
		{
			autosaveHeld = false;
			Log("save: dropped a held autosave");
		}
		else if (SaveReady() && gameaction == ga_nothing && !paused && !pauseext && players[consoleplayer].playerstate == PST_LIVE)
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
	if (saveState == SaveIdle && !saveStartPending && SaveReady()) return false;
	if (!autosaveHeld) Log("save: holding an autosave until Daggerfall is ready");
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

// G_SaveGame, for a save from the menu or console. True means the bridge took it, or refused it with a message.
bool DD_BridgeSaveBegin(const char *filename, const char *description)
{
	if (!session || (!SaveOnDaggerfallMap() && !saveTestFile)) return false; // A regular WAD saves normally.
	return SaveQueue(filename, description, false);
}

namespace
{
bool SaveStart(const char *filename, const char *description, bool isAuto)
{
	if (saveState != SaveIdle) { Printf("A save is already in progress.\n"); return true; }
	if (gamestate != GS_LEVEL || players[consoleplayer].health <= 0 || !SaveReady())
	{
		Printf(PRINT_HIGH, "Cannot save right now. Daggerfall is not ready.\n");
		Log("save: refused before starting, Daggerfall phase %u, stale %d", peerState.df_phase, int(peerStale));
		return true;
	}
	saveIsAuto = isAuto;
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
	dfb_send(session, &e);
	dfb_flush(session);
	Log("save %u: Doom frozen at tic %d, requested Daggerfall's save", saveTxn, gametic);
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
		"\"df_world\":[%d,%d],\"doom_world\":[%.3f,%.3f,%.3f],\"yaw\":%.3f,\"context\":%u,\"map_pixel\":[%d,%d],\"map\":\"%s\",\"files\":[%s]}\n",
		SaveFormat, saveTxn, saveReply.hp_current, saveReply.hp_max, saveReply.hp_applied, players[consoleplayer].health,
		saveReply.world_x, saveReply.world_z, ownState.world_x, ownState.world_z, ownState.world_height, ownState.yaw_degrees,
		ownState.world_context, ownState.map_pixel_x, ownState.map_pixel_y, primaryLevel->MapName.GetChars(), list.GetChars());
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
constexpr int64_t LoadTimeoutNs = 30000000000LL, LoadPeerWaitNs = 15000000000LL, DeathViewNs = 2500000000LL;
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
const char *loadTestMode;
FString loadTestFile;
int loadTestStep, loadTestSavedHp;
double loadTestPos[3];
int64_t loadTestAtNs;

struct BundleInfo
{
	int hp = 0, hpMax = 0, x = 0, z = 0;
	uint32_t files = 0;
	FString map;
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
	deathState = DeathNone;
	pauseext = false;
	M_ClearMenus();
	Log("load %u: both games resumed, %.1f ms frozen", loadTxn, (dfb_now_ns() - loadStartNs) / 1e6);
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
		if (BundleCheck(name.GetChars(), info, why, nullptr)) { out = name; return true; }
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

void RunLoadTest(int64_t now);

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
		if (now - loadStartNs > LoadTimeoutNs || peerStale)
		{
			SendLoadDone(false);
			LoadBreak("Daggerfall stopped responding");
		}
	}
	PumpDeath(now);
	RunLoadTest(now);
}

void LoadTestLog(const char *what)
{
	const player_t &p = players[consoleplayer];
	double x = 0, y = 0, z = 0, yaw = 0;
	const bool world = gamestate == GS_LEVEL && DDTreadmill_PlayerWorld(x, y, z, yaw) != DD_AREA_NONE;
	Log("load test: %s | doom hp %d, Daggerfall hp %d dead %d, world %d at %.1f,%.1f, gamestate %d, death %d, hold %d, menu %d", what, p.health, peerState.hp_current,
		(peerState.hp_flags & DFB_HPF_DEAD) ? 1 : 0, int(world), x, y, int(gamestate), int(deathState), int(flowHold), int(menuactive));
}

// Test only (-dfloadtest mode:file). Drives the same save, load, and death entry points the menus use.
void RunLoadTest(int64_t now)
{
	if (!loadTestMode || loadTestStep < 0 || now < loadTestAtNs) return;
	const bool settled = loadState == LoadIdle && saveState == SaveIdle && !saveStartPending;
	const bool bad = !strcmp(loadTestMode, "bad"), death = !strcmp(loadTestMode, "death"), menu = !strcmp(loadTestMode, "menu");
	const player_t &player = players[consoleplayer];
	double x = 0, y = 0, z = 0, yaw = 0;
	const auto finish = [&]()
	{
		const bool world = gamestate == GS_LEVEL && DDTreadmill_PlayerWorld(x, y, z, yaw) != DD_AREA_NONE;
		const double moved = std::hypot(x - loadTestPos[0], y - loadTestPos[1]);
		const bool pass = world && !flowHold && deathState == DeathNone && player.playerstate == PST_LIVE &&
			player.health == loadTestSavedHp && peerState.hp_current == loadTestSavedHp && !(peerState.hp_flags & DFB_HPF_DEAD) && moved < 2.0;
		LoadTestLog(pass ? "PASS" : "FAIL");
		Log("load test: moved %.2f from the saved position", moved);
		loadTestStep = -1;
		C_DoCommand("quit");
	};
	switch (loadTestStep)
	{
	case 0:
		if (gamestate != GS_LEVEL || !SaveReady() || !(peerState.hp_flags & DFB_HPF_VALID)) return;
		if (!loadTestAtNs) { loadTestAtNs = now + 2000000000LL; return; }
		LoadTestLog("start");
		if (bad)
		{
			loadTestSavedHp = player.health;
			DDTreadmill_PlayerWorld(loadTestPos[0], loadTestPos[1], loadTestPos[2], yaw);
			G_LoadGame(loadTestFile.GetChars());
			loadTestStep = 10;
			loadTestAtNs = now + 3000000000LL;
			return;
		}
		HpSend(DFB_HP_HIT, 13, "load test setup");
		loadTestStep = 1;
		loadTestAtNs = now + 700000000LL;
		return;
	case 1:
		if (peerState.hp_applied_event + 1 != hpNextEvent) return;
		loadTestSavedHp = peerState.hp_current;
		G_SaveGame(loadTestFile.GetChars(), "Doomerfall load test", false);
		loadTestStep = 2;
		loadTestAtNs = now + 1000000000LL;
		return;
	case 2:
		if (!settled || !SaveReady()) return;
		DDTreadmill_PlayerWorld(loadTestPos[0], loadTestPos[1], loadTestPos[2], yaw);
		LoadTestLog("saved");
		if (death || menu) HpSend(DFB_HP_HIT, 100000, "load test lethal");
		else
		{
			HpSend(DFB_HP_HIT, 17, "load test change");
			P_UnPredictClient();
			if (AActor *mo = players[consoleplayer].mo) mo->SetOrigin(mo->Pos() + DVector3(96, 0, 0), false);
		}
		loadTestStep = death || menu ? 4 : 3;
		loadTestAtNs = now + 1500000000LL;
		return;
	case 3:
		LoadTestLog("changed");
		G_LoadGame(loadTestFile.GetChars());
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	case 4:
		if (deathState != DeathMenu || !menuactive) return;
		LoadTestLog("death menu open");
		C_DoCommand("screenshot");
		loadTestStep = 5;
		loadTestAtNs = now + 5000000000LL; // Longer than Daggerfall's own restart timer.
		return;
	case 5:
		LoadTestLog("still dead after Daggerfall's restart time");
		if (menu)
		{
			C_DoCommand("dd_death_mainmenu");
			loadTestStep = 6;
			loadTestAtNs = now + 2000000000LL;
			return;
		}
		C_DoCommand("dd_death_loadlast");
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	case 6:
		LoadTestLog("at the title");
		C_DoCommand("map DDT09183"); // Must be refused while no game is loaded.
		loadTestStep = 7;
		loadTestAtNs = now + 1500000000LL;
		return;
	case 7:
		LoadTestLog("after trying a new game from the title");
		G_LoadGame(loadTestFile.GetChars());
		loadTestStep = 8;
		loadTestAtNs = now + 500000000LL;
		return;
	case 8:
		if (!settled || flowHold) return;
		loadTestStep = 9;
		loadTestAtNs = now + 2000000000LL; // Both games run together for a moment before the check.
		return;
	case 9:
		finish();
		return;
	case 10:
		if (!settled) return;
		finish();
		return;
	}
}
}

bool DD_BridgeBlocksNewGame()
{
	if (!session || !atTitle) return false;
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
	if (loadState != LoadIdle || saveState != SaveIdle || saveStartPending || uiState != UiClosed)
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

CCMD(dd_death_mainmenu)
{
	if (!session || deathState == DeathNone || loadState != LoadIdle) return;
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
	Log("death: returning to the title, Daggerfall held until a save is loaded");
	D_StartTitle();
}

void DD_BridgeInit()
{
	if (session) return;
	const char *id = Args->CheckValue(FArg_dfbridge);
	if (!id) return;

	const int rc = dfb_attach(id, DFB_SIDE_UZ, &session);
	if (rc != DFB_OK)
		I_FatalError("Could not attach to Doomerfall bridge session '%s' (error %d)", id, rc);

	if (const char *path = Args->CheckValue(FArg_dfbridgelog))
		logFile = fopen(path, "ab");
	testPause = Args->CheckValue(FArg_dfbridgetestpause);
	hpTestMode = Args->CheckValue(FArg_dfhptest);
	saveTestFile = Args->CheckValue(FArg_dfsavetest);
	saveTestFail = Args->CheckValue(FArg_dfsavetestfail);
	if (const char *test = Args->CheckValue(FArg_dfloadtest))
	{
		static std::string mode(test);
		const size_t colon = mode.find(':');
		if (colon != std::string::npos)
		{
			loadTestFile = mode.substr(colon + 1).c_str();
			mode.resize(colon);
			loadTestMode = mode.c_str();
		}
	}
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

void DD_BridgeFrame()
{
	if (!session) return;

	const int64_t now = dfb_now_ns();
	dfb_event e;
	while (dfb_receive(session, &e) == DFB_GOT) HandleEvent(e, dfb_now_ns()); // stamp after receipt

	if (dfb_read_state(session, &peerState, sizeof(peerState)) == DFB_GOT)
		stateAge.Add(dfb_now_ns() - peerState.published_ns);
	HpTrackConfirmations();

	if (int(peerState.df_phase) != *dd_sync_df_phase) dd_sync_df_phase = int(peerState.df_phase);
	PublishPosition();

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
	RunUiTest(now);
	RunHpTest(now);
	dfb_flush(session);
	RunTestPause(now);

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
