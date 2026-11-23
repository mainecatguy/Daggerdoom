// Stress test for the bridge transport, using real separate processes as stand-ins for the games.
// Usage: bridge_stress            run everything; exit code 0 only if every test passes
//        bridge_stress child ...  internal

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "doomerfall_bridge.h"

namespace
{
const uint16_t KindData = 100, KindStop = 101;
int failures = 0;

void Check(bool ok, const char *what)
{
	if (!ok) { failures++; printf("  FAIL: %s\n", what); fflush(stdout); }
}

void Report(const char *name, int before)
{
	printf("%s %s\n", failures == before ? "PASS" : "FAIL", name);
	fflush(stdout);
}

std::string NewId(const char *tag)
{
	static int n = 0;
	char id[64];
	snprintf(id, sizeof(id), "stress-%lu-%s-%d", GetCurrentProcessId(), tag, n++);
	return id;
}

void Fill(dfb_event &e, uint64_t value)
{
	e = {};
	e.kind = KindData;
	uint64_t words[6];
	for (int i = 0; i < 6; i++) words[i] = (value + i) * 0x9E3779B97F4A7C15ULL;
	words[0] = value;
	memcpy(e.payload, words, sizeof(words));
}

bool Valid(const dfb_event &e, uint64_t *valueOut = nullptr)
{
	uint64_t words[6];
	memcpy(words, e.payload, sizeof(words));
	for (int i = 1; i < 6; i++)
		if (words[i] != (words[0] + i) * 0x9E3779B97F4A7C15ULL) return false;
	if (valueOut) *valueOut = words[0];
	return true;
}

HANDLE Spawn(const std::string &args)
{
	char self[MAX_PATH];
	GetModuleFileNameA(nullptr, self, MAX_PATH);
	std::string line = std::string("\"") + self + "\" child " + args;
	STARTUPINFOA si{};
	si.cb = sizeof(si);
	PROCESS_INFORMATION pi{};
	if (!CreateProcessA(self, line.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi))
		return nullptr;
	CloseHandle(pi.hThread);
	return pi.hProcess;
}

DWORD WaitExit(HANDLE process, DWORD ms)
{
	if (WaitForSingleObject(process, ms) != WAIT_OBJECT_0)
	{
		TerminateProcess(process, 99);
		WaitForSingleObject(process, 2000);
		CloseHandle(process);
		return 99;
	}
	DWORD code = 1;
	GetExitCodeProcess(process, &code);
	CloseHandle(process);
	return code;
}

void Kill(HANDLE process)
{
	TerminateProcess(process, 77);
	WaitForSingleObject(process, 2000);
	CloseHandle(process);
}

//==========================================================================
// Child roles
//==========================================================================

// Reads until a stop event. Exit 0 if every payload is intact and seq never moves backward by
// more than the one possible redelivery or skips.
int ChildConsume(const char *id)
{
	dfb_session *s = nullptr;
	if (dfb_attach(id, DFB_SIDE_UZ, &s) != DFB_OK) return 10;
	dfb_event e;
	uint32_t last = 0;
	const ULONGLONG deadline = GetTickCount64() + 25000;
	for (;;)
	{
		int rc = dfb_receive(s, &e);
		if (rc == DFB_EMPTY)
		{
			if (GetTickCount64() > deadline) return 11;
			YieldProcessor();
			continue;
		}
		if (rc != DFB_GOT) return 12;
		if (e.kind == KindStop) break;
		if (!Valid(e)) return 13;
		if (last && e.seq != last + 1 && e.seq != last) return 14;
		last = e.seq;
	}
	dfb_close(s);
	return 0;
}

int ChildProduce(const char *id, uint64_t start)
{
	dfb_session *s = nullptr;
	if (dfb_attach(id, DFB_SIDE_UZ, &s) != DFB_OK) return 10;
	dfb_event e;
	for (uint64_t v = start;; v++)
	{
		Fill(e, v);
		while (dfb_send(s, &e) == DFB_ERR_OUTBOX_FULL) dfb_flush(s);
		dfb_flush(s);
	}
}

int ChildEcho(const char *id)
{
	dfb_session *s = nullptr;
	if (dfb_attach(id, DFB_SIDE_UZ, &s) != DFB_OK) return 10;
	dfb_event e;
	for (;;)
	{
		if (dfb_receive(s, &e) != DFB_GOT) { YieldProcessor(); continue; }
		if (e.kind == KindStop) break;
		dfb_ping p;
		memcpy(&p, e.payload, sizeof(p));
		p.replier_ns = dfb_now_ns();
		memcpy(e.payload, &p, sizeof(p));
		e.kind = DFB_KIND_PONG;
		dfb_send(s, &e);
	}
	dfb_close(s);
	return 0;
}

void FillState(dfb_uz_state &st, uint32_t value)
{
	memset(&st, 0, sizeof(st));
	st.demo_value = value;
	memset(st.reserved, (int)(value & 0xFF), sizeof(st.reserved));
}

int ChildState(const char *id)
{
	dfb_session *s = nullptr;
	if (dfb_attach(id, DFB_SIDE_UZ, &s) != DFB_OK) return 10;
	dfb_uz_state st;
	for (uint32_t v = GetTickCount();; v++)
	{
		FillState(st, v);
		dfb_publish_state(s, &st, sizeof(st));
	}
}

int ChildBulk(const char *id)
{
	dfb_session *s = nullptr;
	if (dfb_attach(id, DFB_SIDE_UZ, &s) != DFB_OK) return 10;
	std::vector<uint8_t> data(DFB_BULK_BYTES);
	for (uint32_t v = 1;; v++)
	{
		const uint32_t size = 16 + (v * 2654435761u) % (DFB_BULK_BYTES - 16);
		memset(data.data(), (int)(v & 0xFF), size);
		dfb_bulk_write(s, 4, data.data(), size, nullptr);
	}
}

//==========================================================================
// Tests
//==========================================================================

void TestAttachChecks()
{
	const int before = failures;
	dfb_session *s = nullptr;
	Check(dfb_attach("no-such-session-x", DFB_SIDE_DF, &s) == DFB_ERR_NO_SESSION, "missing session is refused");
	Check(dfb_attach("bad id!", DFB_SIDE_DF, &s) == DFB_ERR_ARG, "invalid ID is refused");

	const std::string id = NewId("attach");
	dfb_session *owner = nullptr;
	Check(dfb_create(id.c_str(), &owner) == DFB_OK, "create");
	dfb_session *dup = nullptr;
	Check(dfb_create(id.c_str(), &dup) == DFB_ERR_ARG, "duplicate session ID is refused");

	const std::string name = "Local\\DoomerfallBridge-" + id;
	HANDLE h = OpenFileMappingA(FILE_MAP_ALL_ACCESS, FALSE, name.c_str());
	auto *raw = static_cast<uint8_t *>(MapViewOfFile(h, FILE_MAP_ALL_ACCESS, 0, 0, 64));
	const struct { size_t off; int expect; const char *what; } cases[] = {
		{ 0, DFB_ERR_MAGIC, "wrong magic is refused" },
		{ 4, DFB_ERR_VERSION, "wrong protocol version is refused" },
		{ 8, DFB_ERR_LAYOUT, "wrong layout hash is refused" },
	};
	for (const auto &c : cases)
	{
		raw[c.off] ^= 0xFF;
		Check(dfb_attach(id.c_str(), DFB_SIDE_DF, &s) == c.expect, c.what);
		raw[c.off] ^= 0xFF;
	}
	Check(dfb_attach(id.c_str(), DFB_SIDE_DF, &s) == DFB_OK, "correct header attaches");
	dfb_close(s);
	UnmapViewOfFile(raw);
	CloseHandle(h);
	dfb_close(owner);
	Report("attach checks (missing, invalid ID, duplicate, magic, version, layout)", before);
}

void TestOverflow()
{
	const int before = failures;
	const std::string id = NewId("overflow");
	dfb_session *owner = nullptr, *tx = nullptr, *rx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &tx);
	dfb_attach(id.c_str(), DFB_SIDE_UZ, &rx);

	dfb_event e;
	int ok = 0, queued = 0, full = 0;
	const uint64_t attempts = DFB_RING_SLOTS + DFB_OUTBOX_SLOTS + 100;
	for (uint64_t v = 0; v < attempts; v++)
	{
		Fill(e, ok + queued);
		int rc = dfb_send(tx, &e);
		if (rc == DFB_OK) ok++;
		else if (rc == DFB_QUEUED) queued++;
		else if (rc == DFB_ERR_OUTBOX_FULL) full++;
	}
	Check(ok == (int)DFB_RING_SLOTS, "ring accepts exactly its capacity");
	Check(queued == (int)DFB_OUTBOX_SLOTS, "outbox accepts exactly its capacity");
	Check(full == 100, "sends beyond the outbox are refused, not dropped");

	uint64_t expected = 0;
	uint32_t lastSeq = 0;
	bool ordered = true;
	for (;;)
	{
		int rc = dfb_receive(rx, &e);
		if (rc == DFB_EMPTY)
		{
			dfb_stats pending;
			dfb_get_stats(tx, &pending);
			if (!pending.outbox_count) break;
			dfb_flush(tx);
			continue;
		}
		uint64_t value = 0;
		if (!Valid(e, &value) || value != expected || (lastSeq && e.seq != lastSeq + 1)) ordered = false;
		lastSeq = e.seq;
		expected++;
	}
	Check(ordered, "all events arrive in order with contiguous seq after overflow");
	Check(expected == DFB_RING_SLOTS + DFB_OUTBOX_SLOTS, "every accepted event arrives exactly once");
	dfb_close(tx); dfb_close(rx); dfb_close(owner);
	Report("overflow to outbox, hard cap, ordered recovery", before);
}

void TestWraparound()
{
	const int before = failures;
	const std::string id = NewId("wrap");
	dfb_session *owner = nullptr, *tx = nullptr, *rx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &tx);
	dfb_attach(id.c_str(), DFB_SIDE_UZ, &rx);
	dfb_event e;
	uint64_t sent = 0, got = 0;
	bool good = true;
	const uint64_t total = 5000000;
	while (got < total)
	{
		const int batch = 1 + (int)(got % 4000);
		for (int i = 0; i < batch && sent < total; i++)
		{
			Fill(e, sent);
			if (dfb_send(tx, &e) < 0) { good = false; break; }
			sent++;
		}
		dfb_flush(tx);
		while (dfb_receive(rx, &e) == DFB_GOT)
		{
			uint64_t v;
			if (!Valid(e, &v) || v != got) good = false;
			got++;
		}
		if (!good) break;
	}
	Check(good && got == total, "5M events across many ring wraps stay intact and ordered");
	dfb_stats st;
	dfb_get_stats(rx, &st);
	Check(st.seq_gaps == 0, "no seq gaps");
	dfb_close(tx); dfb_close(rx); dfb_close(owner);
	Report("ring wraparound (5M events)", before);
}

void TestCrossProcess()
{
	const int before = failures;
	const std::string id = NewId("stream");
	dfb_session *owner = nullptr, *tx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &tx);
	HANDLE child = Spawn("consume " + id);
	Check(child != nullptr, "spawn");
	const uint64_t total = 10000000;
	const int64_t t0 = dfb_now_ns();
	dfb_event e;
	for (uint64_t v = 0; v < total; v++)
	{
		Fill(e, v);
		while (dfb_send(tx, &e) == DFB_ERR_OUTBOX_FULL) { dfb_flush(tx); YieldProcessor(); }
	}
	while (dfb_flush(tx) > 0) YieldProcessor();
	e = {}; e.kind = KindStop;
	while (dfb_send(tx, &e) == DFB_ERR_OUTBOX_FULL) dfb_flush(tx);
	while (dfb_flush(tx) > 0) YieldProcessor();
	const DWORD code = WaitExit(child, 25000);
	const double secs = (dfb_now_ns() - t0) / 1e9;
	Check(code == 0, "consumer verified every event");
	printf("  %.1f million events/s across processes (exit %lu)\n", total / secs / 1e6, code);
	dfb_close(tx); dfb_close(owner);
	Report("cross-process stream (10M events, checked payloads)", before);
}

void TestStateTearing()
{
	const int before = failures;
	const std::string id = NewId("state");
	dfb_session *owner = nullptr, *rx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &rx);
	uint64_t reads = 0, fresh = 0, torn = 0;
	// Several writer lifetimes: each is force-killed mid-publish and replaced.
	for (int cycle = 0; cycle < 12; cycle++)
	{
		HANDLE child = Spawn("state " + id);
		const ULONGLONG end = GetTickCount64() + 250;
		dfb_uz_state st;
		while (GetTickCount64() < end)
		{
			int rc = dfb_read_state(rx, &st, sizeof(st));
			reads++;
			if (rc == DFB_GOT) fresh++;
			if (!st.publish_seq) continue;
			const uint8_t want = (uint8_t)(st.demo_value & 0xFF);
			for (uint8_t b : st.reserved) if (b != want) { torn++; break; }
		}
		Kill(child);
	}
	printf("  %llu reads, %llu fresh, %llu torn, across 12 killed writers\n", reads, fresh, torn);
	Check(fresh > 1000, "reader saw fresh states");
	Check(torn == 0, "no torn state, including across writer kills");
	dfb_close(rx); dfb_close(owner);
	Report("triple buffer tearing with killed writers", before);
}

void TestBulk()
{
	const int before = failures;
	const std::string id = NewId("bulk");
	dfb_session *owner = nullptr, *rx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &rx);
	uint32_t v = 0;
	Check(dfb_bulk_write(rx, 4, "x", 1, &v) == DFB_ERR_SIDE, "DF cannot write a UZ slot");
	HANDLE child = Spawn("bulk " + id);
	std::vector<uint8_t> buf(DFB_BULK_BYTES);
	uint64_t got = 0, busy = 0, torn = 0;
	const ULONGLONG end = GetTickCount64() + 2000;
	while (GetTickCount64() < end)
	{
		uint32_t size = 0, version = 0;
		int rc = dfb_bulk_read(rx, 4, buf.data(), (uint32_t)buf.size(), &size, &version);
		if (rc == DFB_ERR_BUSY) { busy++; continue; }
		if (rc != DFB_GOT) continue;
		got++;
		for (uint32_t i = 1; i < size; i++) if (buf[i] != buf[0]) { torn++; break; }
	}
	Kill(child);
	printf("  %llu good reads, %llu busy, %llu torn\n", got, busy, torn);
	Check(got > 0, "reader got bulk data");
	Check(torn == 0, "no torn bulk payload");
	dfb_close(rx); dfb_close(owner);
	Report("bulk slots under continuous rewrite", before);
}

void TestKillConsumer()
{
	const int before = failures;
	const std::string id = NewId("killrx");
	dfb_session *owner = nullptr, *tx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &tx);
	HANDLE child = Spawn("consume " + id);
	dfb_event e;
	uint64_t v = 0;
	const ULONGLONG killAt = GetTickCount64() + 300;
	while (GetTickCount64() < killAt)
	{
		Fill(e, v);
		if (dfb_send(tx, &e) >= 0) v++;
		dfb_flush(tx);
	}
	Kill(child);

	// With no consumer the sender must fill up and get a clean refusal, never block.
	int64_t worst = 0;
	int refused = 0;
	for (int i = 0; i < 40000 && !refused; i++)
	{
		Fill(e, v);
		const int64_t t = dfb_now_ns();
		const int rc = dfb_send(tx, &e);
		worst = std::max(worst, dfb_now_ns() - t);
		if (rc == DFB_ERR_OUTBOX_FULL) refused = 1; else v++;
	}
	Check(refused == 1, "sender reaches a clean refusal with a dead consumer");
	printf("  worst dfb_send with dead consumer: %.1f us\n", worst / 1000.0);

	// A replacement consumer picks up the backlog and verifies it.
	child = Spawn("consume " + id);
	while (dfb_flush(tx) > 0) Sleep(1);
	e = {}; e.kind = KindStop;
	while (dfb_send(tx, &e) == DFB_ERR_OUTBOX_FULL) { dfb_flush(tx); Sleep(1); }
	while (dfb_flush(tx) > 0) Sleep(1);
	Check(WaitExit(child, 20000) == 0, "replacement consumer drained an intact backlog");
	dfb_close(tx); dfb_close(owner);
	Report("consumer killed mid-stream, then replaced", before);
}

void TestKillProducer()
{
	const int before = failures;
	const std::string id = NewId("killtx");
	dfb_session *owner = nullptr, *rx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &rx);
	dfb_event e;
	uint64_t got = 0, corrupt = 0;
	for (int cycle = 0; cycle < 6; cycle++)
	{
		HANDLE child = Spawn("produce " + id + " " + std::to_string(cycle * 1000000000ULL));
		const ULONGLONG end = GetTickCount64() + 200;
		while (GetTickCount64() < end)
			if (dfb_receive(rx, &e) == DFB_GOT) { got++; if (!Valid(e)) corrupt++; }
		Kill(child);
		while (dfb_receive(rx, &e) == DFB_GOT) { got++; if (!Valid(e)) corrupt++; }
	}
	printf("  %llu events across 6 killed producers, %llu corrupt\n", got, corrupt);
	Check(got > 0, "events arrived");
	Check(corrupt == 0, "a killed producer never exposes a half-written event");
	dfb_close(rx); dfb_close(owner);
	Report("producer killed mid-stream, repeatedly", before);
}

void TestLatency()
{
	const int before = failures;
	const std::string id = NewId("latency");
	dfb_session *owner = nullptr, *tx = nullptr;
	dfb_create(id.c_str(), &owner);
	dfb_attach(id.c_str(), DFB_SIDE_DF, &tx);
	HANDLE child = Spawn("echo " + id);
	const int samples = 200000;
	std::vector<int64_t> rtt;
	rtt.reserve(samples);
	dfb_event e{};
	for (int i = 0; i < samples; i++)
	{
		dfb_ping p{};
		p.id = (uint32_t)i;
		p.sent_ns = dfb_now_ns();
		e = {};
		e.kind = DFB_KIND_PING;
		memcpy(e.payload, &p, sizeof(p));
		dfb_send(tx, &e);
		const ULONGLONG deadline = GetTickCount64() + 2000;
		bool got = false;
		while (!got && GetTickCount64() < deadline)
		{
			if (dfb_receive(tx, &e) == DFB_GOT && e.kind == DFB_KIND_PONG)
			{
				rtt.push_back(dfb_now_ns() - p.sent_ns);
				got = true;
			}
		}
		if (!got) break;
	}
	e = {}; e.kind = KindStop;
	dfb_send(tx, &e);
	WaitExit(child, 3000);
	Check((int)rtt.size() == samples, "every ping was answered");
	if (!rtt.empty())
	{
		std::sort(rtt.begin(), rtt.end());
		printf("  spin-polling round trip over %zu samples: p50 %.2f us, p99 %.2f us, p99.9 %.2f us, max %.1f us\n",
			rtt.size(), rtt[rtt.size() / 2] / 1000.0, rtt[rtt.size() * 99 / 100] / 1000.0,
			rtt[rtt.size() * 999 / 1000] / 1000.0, rtt.back() / 1000.0);
	}
	dfb_close(tx); dfb_close(owner);
	Report("transport latency (spin-polling stand-ins)", before);
}
}

int main(int argc, char **argv)
{
	if (argc >= 4 && !strcmp(argv[1], "child"))
	{
		const std::string role = argv[2];
		if (role == "consume") return ChildConsume(argv[3]);
		if (role == "produce") return ChildProduce(argv[3], argc > 4 ? _strtoui64(argv[4], nullptr, 10) : 0);
		if (role == "echo") return ChildEcho(argv[3]);
		if (role == "state") return ChildState(argv[3]);
		if (role == "bulk") return ChildBulk(argv[3]);
		return 2;
	}

	printf("protocol %u, layout hash %016llx\n", dfb_protocol_version(), dfb_layout_hash());
	TestAttachChecks();
	TestOverflow();
	TestWraparound();
	TestCrossProcess();
	TestStateTearing();
	TestBulk();
	TestKillConsumer();
	TestKillProducer();
	TestLatency();
	printf(failures ? "RESULT: %d check(s) failed\n" : "RESULT: all passed\n", failures);
	return failures ? 1 : 0;
}
