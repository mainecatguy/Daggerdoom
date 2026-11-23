// Doomerfall: UZDoom's side of the bridge. Does nothing unless started with -dfbridge <session>.
//
// The pump runs once per D_DoomLoop iteration rather than from G_Ticker, because TryRunTics
// returns before G_Ticker and P_RunClientSideLogic while pauseext is set.

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "c_dispatch.h"
#include "doomstat.h"
#include "engineerrors.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "i_interface.h"
#include "m_argv.h"
#include "menu.h"
#include "printf.h"

FARG_ADVANCED(dfbridge, "Doomerfall", "session", "Attaches to the Doomerfall bridge session created by the launcher.");
FARG_ADVANCED(dfbridgelog, "Doomerfall", "file", "Appends Doomerfall bridge traffic and latency to a log file.");
FARG_ADVANCED(dfbridgetestpause, "Doomerfall", "ext|game|menu", "Bridge test only: enters a pause state for six seconds.");

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

void HandleEvent(const dfb_event &e, int64_t now)
{
	switch (e.kind)
	{
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
}

void DD_BridgeFrame()
{
	if (!session) return;

	const int64_t now = dfb_now_ns();
	dfb_event e;
	while (dfb_receive(session, &e) == DFB_GOT) HandleEvent(e, dfb_now_ns()); // stamp after receipt

	if (dfb_read_state(session, &peerState, sizeof(peerState)) == DFB_GOT)
		stateAge.Add(dfb_now_ns() - peerState.published_ns);

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
		rtt.count = rtt.next = oneWayOut.count = oneWayOut.next = 0; // each line covers one window
		oneWayIn.count = oneWayIn.next = stateAge.count = stateAge.next = 0;
	}
}
