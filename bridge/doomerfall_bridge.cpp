// Doomerfall bridge implementation. See doomerfall_bridge.h.
//
// Memory model: each lane has exactly one writer process. Rings are classic SPSC with
// acquire/release indices. State halves are lock-free triple buffers. Bulk slots use a version
// counter that is odd while the writer copies (a seqlock), so a reader may see DFB_ERR_BUSY but
// never a torn payload.
//
// OS-specific code is limited to the "OS seam" section: opening the shared mapping, the clock,
// and the process ID.

#include "doomerfall_bridge.h"

#include <atomic>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#endif

static_assert(sizeof(dfb_event) == 64, "event record must be 64 bytes");
static_assert(sizeof(dfb_ping) <= sizeof(((dfb_event *)nullptr)->payload), "ping payload too large");
static_assert(sizeof(dfb_hello) <= sizeof(((dfb_event *)nullptr)->payload), "hello payload too large");
static_assert(sizeof(dfb_ui_command) <= sizeof(((dfb_event *)nullptr)->payload), "ui command payload too large");
static_assert(sizeof(dfb_ui_input) <= sizeof(((dfb_event *)nullptr)->payload), "ui input payload too large");
static_assert(sizeof(dfb_ui_state) <= sizeof(((dfb_event *)nullptr)->payload), "ui state payload too large");
static_assert(sizeof(dfb_ui_result) <= sizeof(((dfb_event *)nullptr)->payload), "ui result payload too large");
static_assert(sizeof(dfb_df_state) == DFB_STATE_BYTES, "df state size");
static_assert(sizeof(dfb_uz_state) == DFB_STATE_BYTES, "uz state size");
static_assert((DFB_RING_SLOTS & (DFB_RING_SLOTS - 1)) == 0, "ring slots must be a power of two");
static_assert(std::atomic<uint64_t>::is_always_lock_free, "64-bit atomics must be lock-free to live in shared memory");
static_assert(std::atomic<uint32_t>::is_always_lock_free, "32-bit atomics must be lock-free to live in shared memory");

namespace
{
//==========================================================================
// OS seam
//==========================================================================

struct OsMapping
{
	void *view = nullptr;
	size_t size = 0;
#ifdef _WIN32
	HANDLE handle = nullptr;
#else
	int fd = -1;
	bool owner = false;
	char name[96] = {};
#endif
};

#ifdef _WIN32
void OsMappingName(const char *id, char *out, size_t cap)
{
	snprintf(out, cap, "Local\\DoomerfallBridge-%s", id);
}

int OsCreate(const char *id, size_t size, OsMapping &m)
{
	char name[128];
	OsMappingName(id, name, sizeof(name));
	HANDLE h = CreateFileMappingA(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE,
		(DWORD)((uint64_t)size >> 32), (DWORD)(size & 0xFFFFFFFFu), name);
	if (!h) return DFB_ERR_OS;
	if (GetLastError() == ERROR_ALREADY_EXISTS)
	{
		CloseHandle(h);
		return DFB_ERR_ARG; // session IDs must be fresh
	}
	void *view = MapViewOfFile(h, FILE_MAP_ALL_ACCESS, 0, 0, size);
	if (!view)
	{
		CloseHandle(h);
		return DFB_ERR_OS;
	}
	m.handle = h;
	m.view = view;
	m.size = size;
	return DFB_OK;
}

int OsOpen(const char *id, size_t size, OsMapping &m)
{
	char name[128];
	OsMappingName(id, name, sizeof(name));
	HANDLE h = OpenFileMappingA(FILE_MAP_ALL_ACCESS, FALSE, name);
	if (!h) return DFB_ERR_NO_SESSION;
	void *view = MapViewOfFile(h, FILE_MAP_ALL_ACCESS, 0, 0, 0);
	if (!view)
	{
		CloseHandle(h);
		return DFB_ERR_OS;
	}
	MEMORY_BASIC_INFORMATION info{};
	if (!VirtualQuery(view, &info, sizeof(info)) || info.RegionSize < size)
	{
		UnmapViewOfFile(view);
		CloseHandle(h);
		return DFB_ERR_LAYOUT;
	}
	m.handle = h;
	m.view = view;
	m.size = size;
	return DFB_OK;
}

void OsClose(OsMapping &m)
{
	if (m.view) UnmapViewOfFile(m.view);
	if (m.handle) CloseHandle(m.handle);
	m = OsMapping{};
}

int64_t OsNowNs()
{
	static const int64_t freq = [] { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return (int64_t)f.QuadPart; }();
	LARGE_INTEGER c;
	QueryPerformanceCounter(&c);
	const int64_t q = c.QuadPart / freq, r = c.QuadPart % freq;
	return q * 1000000000LL + r * 1000000000LL / freq;
}

uint32_t OsPid() { return (uint32_t)GetCurrentProcessId(); }

#else // POSIX. Written for portability; not built or tested yet.

int OsCreate(const char *id, size_t size, OsMapping &m)
{
	snprintf(m.name, sizeof(m.name), "/doomerfall-%s", id);
	int fd = shm_open(m.name, O_RDWR | O_CREAT | O_EXCL, 0600);
	if (fd < 0) return DFB_ERR_ARG;
	if (ftruncate(fd, (off_t)size) != 0)
	{
		close(fd);
		shm_unlink(m.name);
		return DFB_ERR_OS;
	}
	void *view = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (view == MAP_FAILED)
	{
		close(fd);
		shm_unlink(m.name);
		return DFB_ERR_OS;
	}
	m.fd = fd;
	m.view = view;
	m.size = size;
	m.owner = true;
	return DFB_OK;
}

int OsOpen(const char *id, size_t size, OsMapping &m)
{
	snprintf(m.name, sizeof(m.name), "/doomerfall-%s", id);
	int fd = shm_open(m.name, O_RDWR, 0600);
	if (fd < 0) return DFB_ERR_NO_SESSION;
	struct stat st{};
	if (fstat(fd, &st) != 0 || (size_t)st.st_size < size)
	{
		close(fd);
		return DFB_ERR_LAYOUT;
	}
	void *view = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (view == MAP_FAILED)
	{
		close(fd);
		return DFB_ERR_OS;
	}
	m.fd = fd;
	m.view = view;
	m.size = size;
	return DFB_OK;
}

void OsClose(OsMapping &m)
{
	if (m.view) munmap(m.view, m.size);
	if (m.fd >= 0) close(m.fd);
	if (m.owner) shm_unlink(m.name);
	m = OsMapping{};
}

int64_t OsNowNs()
{
	timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

uint32_t OsPid() { return (uint32_t)getpid(); }
#endif

//==========================================================================
// Shared layout
//==========================================================================

constexpr uint32_t Fresh = 4; // triple buffer: set in `middle` when it holds an unread publish

struct alignas(64) Ring
{
	alignas(64) std::atomic<uint64_t> head;      // written by the producer
	alignas(64) std::atomic<uint64_t> tail;      // written by the consumer
	alignas(64) std::atomic<uint32_t> nextSeq;   // producer only; kept here so a restart continues
	alignas(64) std::atomic<uint32_t> lastSeq;   // consumer only
	alignas(64) dfb_event slots[DFB_RING_SLOTS];
};

struct alignas(64) TripleBuffer
{
	alignas(64) std::atomic<uint32_t> middle;    // index 0-2, plus Fresh
	std::atomic<uint32_t> publishSeq;
	std::atomic<int64_t> lastPublishNs;
	alignas(64) std::atomic<uint32_t> back;      // writer only
	alignas(64) std::atomic<uint32_t> front;     // reader only
	alignas(64) uint8_t buffers[3][DFB_STATE_BYTES];
};

struct alignas(64) BulkSlot
{
	std::atomic<uint32_t> version;               // odd while being written; published version = value / 2
	std::atomic<uint32_t> size;
	alignas(64) uint8_t data[DFB_BULK_BYTES];
};

struct alignas(64) Header
{
	std::atomic<uint32_t> magic;                 // written last by the creator
	uint32_t protocolVersion;
	uint64_t layoutHash;
	uint64_t totalSize;
	int64_t createdNs;
	std::atomic<uint32_t> pid[3];                // indexed by side
	std::atomic<uint32_t> attachCount[3];
};

struct Shared
{
	Header header;
	Ring rings[2];          // 0: DF to UZ (E-DF), 1: UZ to DF (E-UZ)
	TripleBuffer states[2]; // 0: S-DF, 1: S-UZ
	BulkSlot bulk[DFB_BULK_SLOTS];
};

// The UI surface lives in its own mapping, so the event and state lanes keep their small footprint.
// The OS commits its pages only when a menu first writes them.
constexpr size_t SurfaceFrameBytes = size_t(DFB_SURFACE_MAX_W) * DFB_SURFACE_MAX_H * 4;

struct alignas(64) SurfaceShared
{
	alignas(64) std::atomic<uint32_t> middle;    // index 0-2, plus Fresh
	alignas(64) std::atomic<uint32_t> back;      // writer only
	alignas(64) std::atomic<uint32_t> front;     // reader only
	alignas(64) dfb_surface_frame frames[3];
	alignas(64) uint8_t pixels[3][SurfaceFrameBytes];
};

uint64_t Fnv(uint64_t h, const void *data, size_t size)
{
	const uint8_t *p = static_cast<const uint8_t *>(data);
	for (size_t i = 0; i < size; i++) h = (h ^ p[i]) * 1099511628211ULL;
	return h;
}

uint64_t FnvU64(uint64_t h, uint64_t v) { return Fnv(h, &v, sizeof(v)); }

uint64_t ComputeLayoutHash()
{
	// Any change to a shared struct's size or field placement changes this value.
	uint64_t h = 1469598103934665603ULL;
	const char tag[] = "doomerfall-bridge-v1";
	h = Fnv(h, tag, sizeof(tag));
	const uint64_t values[] = {
		sizeof(Shared), sizeof(Header), sizeof(Ring), sizeof(TripleBuffer), sizeof(BulkSlot),
		offsetof(Shared, rings), offsetof(Shared, states), offsetof(Shared, bulk),
		DFB_RING_SLOTS, DFB_BULK_SLOTS, DFB_BULK_BYTES, DFB_STATE_BYTES,
		sizeof(dfb_event), offsetof(dfb_event, seq), offsetof(dfb_event, tic), offsetof(dfb_event, kind),
		offsetof(dfb_event, flags), offsetof(dfb_event, reserved), offsetof(dfb_event, payload),
		sizeof(dfb_df_state), offsetof(dfb_df_state, publish_seq), offsetof(dfb_df_state, df_phase),
		offsetof(dfb_df_state, df_heartbeat), offsetof(dfb_df_state, published_ns),
		offsetof(dfb_df_state, df_frame), offsetof(dfb_df_state, demo_value),
		sizeof(dfb_uz_state), offsetof(dfb_uz_state, publish_seq), offsetof(dfb_uz_state, uz_phase),
		offsetof(dfb_uz_state, uz_heartbeat), offsetof(dfb_uz_state, published_ns),
		offsetof(dfb_uz_state, uz_tic), offsetof(dfb_uz_state, demo_value),
		offsetof(dfb_uz_state, world_x), offsetof(dfb_uz_state, world_z), offsetof(dfb_uz_state, world_height),
		offsetof(dfb_uz_state, yaw_degrees), offsetof(dfb_uz_state, world_context), offsetof(dfb_uz_state, map_pixel_x),
		offsetof(dfb_uz_state, map_pixel_y), offsetof(dfb_uz_state, area_seq), sizeof(dfb_area),
		sizeof(dfb_ping), sizeof(dfb_hello), sizeof(SurfaceShared), sizeof(dfb_surface_frame),
		sizeof(dfb_ui_command), sizeof(dfb_ui_input), sizeof(dfb_ui_state), sizeof(dfb_ui_result),
		DFB_SURFACE_MAX_W, DFB_SURFACE_MAX_H,
	};
	for (uint64_t v : values) h = FnvU64(h, v);
	return h;
}

const uint64_t LayoutHash = ComputeLayoutHash();

bool ValidId(const char *id)
{
	if (!id || !*id) return false;
	size_t n = 0;
	for (const char *p = id; *p; p++, n++)
	{
		const char c = *p;
		const bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_';
		if (!ok || n >= 64) return false;
	}
	return true;
}
}

struct dfb_session
{
	OsMapping mapping;
	OsMapping surfaceMapping;
	SurfaceShared *surface = nullptr;
	Shared *shared = nullptr;
	int side = 0;        // 0 for the creator
	Ring *out = nullptr; // ring we produce into
	Ring *in = nullptr;  // ring we consume from
	TripleBuffer *own = nullptr;
	TripleBuffer *peer = nullptr;
	dfb_event *outbox = nullptr; // local FIFO
	uint32_t outboxHead = 0, outboxCount = 0, outboxPeak = 0;
	uint64_t sent = 0, received = 0, queued = 0, gaps = 0;
};

namespace
{
void BindSide(dfb_session *s)
{
	Shared *sh = s->shared;
	const bool df = s->side == DFB_SIDE_DF;
	s->out = &sh->rings[df ? 0 : 1];
	s->in = &sh->rings[df ? 1 : 0];
	s->own = &sh->states[df ? 0 : 1];
	s->peer = &sh->states[df ? 1 : 0];
}

// After a writer restart, `back` in shared memory may be stale if the old process died between
// its exchange and storing the new index. The writer's buffer is always the one not held by
// `middle` or the reader's `front`. A reader swap exchanges those two, so the set is stable,
// except in the moment before the reader stores its new `front`; retry through that.
void RecoverWriterBack(TripleBuffer &tb)
{
	for (int tries = 0; tries < 100000; tries++)
	{
		const uint32_t mid = tb.middle.load(std::memory_order_acquire) & 3;
		const uint32_t front = tb.front.load(std::memory_order_acquire);
		if (mid != front && mid < 3 && front < 3)
		{
			tb.back.store(3 - mid - front, std::memory_order_relaxed);
			return;
		}
	}
}

// The reader's `front` can be stale the same way after a reader restart.
void RecoverReaderFront(TripleBuffer &tb)
{
	for (int tries = 0; tries < 100000; tries++)
	{
		const uint32_t mid = tb.middle.load(std::memory_order_acquire) & 3;
		const uint32_t back = tb.back.load(std::memory_order_acquire);
		if (mid != back && mid < 3 && back < 3)
		{
			tb.front.store(3 - mid - back, std::memory_order_relaxed);
			return;
		}
	}
}

bool PushRing(Ring &r, const dfb_event &e)
{
	const uint64_t head = r.head.load(std::memory_order_relaxed);
	const uint64_t tail = r.tail.load(std::memory_order_acquire);
	if (head - tail >= DFB_RING_SLOTS) return false;
	r.slots[head & (DFB_RING_SLOTS - 1)] = e;
	r.head.store(head + 1, std::memory_order_release);
	return true;
}

int FlushOutbox(dfb_session *s)
{
	while (s->outboxCount)
	{
		if (!PushRing(*s->out, s->outbox[s->outboxHead])) break;
		s->outboxHead = (s->outboxHead + 1) % DFB_OUTBOX_SLOTS;
		s->outboxCount--;
	}
	return (int)s->outboxCount;
}

bool SurfaceName(const char *id, char *out, size_t cap)
{
	const int n = snprintf(out, cap, "%s-surface", id);
	return n > 0 && size_t(n) < cap;
}

uint32_t StateSizeFor(int side) { return side == DFB_SIDE_DF ? (uint32_t)sizeof(dfb_df_state) : (uint32_t)sizeof(dfb_uz_state); }

bool OwnsBulkSlot(int side, uint32_t slot)
{
	return side == DFB_SIDE_DF ? slot < DFB_BULK_SLOTS / 2 : slot >= DFB_BULK_SLOTS / 2;
}
}

extern "C" {

DFB_API uint32_t dfb_protocol_version(void) { return DFB_PROTOCOL_VERSION; }
DFB_API uint64_t dfb_layout_hash(void) { return LayoutHash; }

DFB_API uint32_t dfb_struct_size(int which)
{
	switch (which)
	{
	case 0: return sizeof(dfb_event);
	case 1: return sizeof(dfb_df_state);
	case 2: return sizeof(dfb_uz_state);
	case 3: return sizeof(dfb_stats);
	case 4: return sizeof(dfb_ping);
	default: return 0;
	}
}

DFB_API int64_t dfb_now_ns(void) { return OsNowNs(); }

DFB_API int dfb_create(const char *session_id, dfb_session **out)
{
	if (!out || !ValidId(session_id)) return DFB_ERR_ARG;
	*out = nullptr;
	dfb_session *s = new (std::nothrow) dfb_session();
	if (!s) return DFB_ERR_OS;
	int rc = OsCreate(session_id, sizeof(Shared), s->mapping);
	if (rc != DFB_OK)
	{
		delete s;
		return rc;
	}
	char surfaceId[96];
	rc = SurfaceName(session_id, surfaceId, sizeof(surfaceId)) ? OsCreate(surfaceId, sizeof(SurfaceShared), s->surfaceMapping) : DFB_ERR_ARG;
	if (rc != DFB_OK)
	{
		OsClose(s->mapping);
		delete s;
		return rc;
	}
	s->surface = static_cast<SurfaceShared *>(s->surfaceMapping.view);
	s->surface->back.store(0, std::memory_order_relaxed);
	s->surface->middle.store(1, std::memory_order_relaxed);
	s->surface->front.store(2, std::memory_order_relaxed);
	Shared *sh = static_cast<Shared *>(s->mapping.view); // zero-filled by the OS
	sh->header.protocolVersion = DFB_PROTOCOL_VERSION;
	sh->header.layoutHash = LayoutHash;
	sh->header.totalSize = sizeof(Shared);
	sh->header.createdNs = OsNowNs();
	for (TripleBuffer &tb : sh->states)
	{
		tb.back.store(0, std::memory_order_relaxed);
		tb.middle.store(1, std::memory_order_relaxed);
		tb.front.store(2, std::memory_order_relaxed);
	}
	sh->header.magic.store(DFB_MAGIC, std::memory_order_release);
	s->shared = sh;
	*out = s;
	return DFB_OK;
}

DFB_API int dfb_attach(const char *session_id, int side, dfb_session **out)
{
	if (!out || !ValidId(session_id) || (side != DFB_SIDE_DF && side != DFB_SIDE_UZ)) return DFB_ERR_ARG;
	*out = nullptr;
	dfb_session *s = new (std::nothrow) dfb_session();
	if (!s) return DFB_ERR_OS;
	int rc = OsOpen(session_id, sizeof(Header), s->mapping);
	if (rc != DFB_OK)
	{
		delete s;
		return rc;
	}
	Shared *sh = static_cast<Shared *>(s->mapping.view);
	rc = DFB_OK;
	if (sh->header.magic.load(std::memory_order_acquire) != DFB_MAGIC) rc = DFB_ERR_MAGIC;
	else if (sh->header.protocolVersion != DFB_PROTOCOL_VERSION) rc = DFB_ERR_VERSION;
	else if (sh->header.layoutHash != LayoutHash || sh->header.totalSize != sizeof(Shared)) rc = DFB_ERR_LAYOUT;
	if (rc == DFB_OK)
	{
		// The header looked right; make sure the whole mapping is really there.
		OsMapping full;
		OsClose(s->mapping);
		rc = OsOpen(session_id, sizeof(Shared), full);
		s->mapping = full;
		sh = static_cast<Shared *>(s->mapping.view);
	}
	if (rc == DFB_OK)
	{
		char surfaceId[96];
		rc = SurfaceName(session_id, surfaceId, sizeof(surfaceId)) ? OsOpen(surfaceId, sizeof(SurfaceShared), s->surfaceMapping) : DFB_ERR_ARG;
		if (rc == DFB_OK) s->surface = static_cast<SurfaceShared *>(s->surfaceMapping.view);
	}
	if (rc == DFB_OK)
	{
		s->outbox = static_cast<dfb_event *>(std::calloc(DFB_OUTBOX_SLOTS, sizeof(dfb_event)));
		if (!s->outbox) rc = DFB_ERR_OS;
	}
	if (rc != DFB_OK)
	{
		OsClose(s->surfaceMapping);
		OsClose(s->mapping);
		delete s;
		return rc;
	}
	s->shared = sh;
	s->side = side;
	BindSide(s);
	RecoverWriterBack(*s->own);
	RecoverReaderFront(*s->peer);
	sh->header.pid[side].store(OsPid(), std::memory_order_relaxed);
	sh->header.attachCount[side].fetch_add(1, std::memory_order_release);
	*out = s;
	return DFB_OK;
}

DFB_API void dfb_close(dfb_session *s)
{
	if (!s) return;
	if (s->side) s->shared->header.pid[s->side].store(0, std::memory_order_relaxed);
	OsClose(s->surfaceMapping);
	OsClose(s->mapping);
	std::free(s->outbox);
	delete s;
}

DFB_API int dfb_send(dfb_session *s, const dfb_event *event)
{
	if (!s || !s->side || !event) return DFB_ERR_ARG;
	dfb_event e = *event;
	e.seq = s->out->nextSeq.fetch_add(1, std::memory_order_relaxed) + 1;
	if (FlushOutbox(s) == 0 && PushRing(*s->out, e))
	{
		s->sent++;
		return DFB_OK;
	}
	if (s->outboxCount >= DFB_OUTBOX_SLOTS)
	{
		s->out->nextSeq.fetch_sub(1, std::memory_order_relaxed); // the event was not accepted
		return DFB_ERR_OUTBOX_FULL;
	}
	s->outbox[(s->outboxHead + s->outboxCount) % DFB_OUTBOX_SLOTS] = e;
	s->outboxCount++;
	if (s->outboxCount > s->outboxPeak) s->outboxPeak = s->outboxCount;
	s->sent++;
	s->queued++;
	return DFB_QUEUED;
}

DFB_API int dfb_flush(dfb_session *s)
{
	if (!s || !s->side) return DFB_ERR_ARG;
	return FlushOutbox(s);
}

DFB_API int dfb_receive(dfb_session *s, dfb_event *out)
{
	if (!s || !s->side || !out) return DFB_ERR_ARG;
	Ring &r = *s->in;
	const uint64_t tail = r.tail.load(std::memory_order_relaxed);
	const uint64_t head = r.head.load(std::memory_order_acquire);
	if (tail == head) return DFB_EMPTY;
	*out = r.slots[tail & (DFB_RING_SLOTS - 1)];
	r.tail.store(tail + 1, std::memory_order_release);
	const uint32_t last = r.lastSeq.load(std::memory_order_relaxed);
	if (last != 0 && out->seq != last + 1) s->gaps++;
	r.lastSeq.store(out->seq, std::memory_order_relaxed);
	s->received++;
	return DFB_GOT;
}

DFB_API int dfb_publish_state(dfb_session *s, const void *state, uint32_t size)
{
	if (!s || !s->side || !state) return DFB_ERR_ARG;
	if (size != StateSizeFor(s->side)) return DFB_ERR_SIZE;
	TripleBuffer &tb = *s->own;
	const uint32_t back = tb.back.load(std::memory_order_relaxed);
	uint8_t *dst = tb.buffers[back];
	std::memcpy(dst, state, size);
	// Stamp the common header fields: publish_seq at offset 0, published_ns at offset 16.
	const uint32_t seq = tb.publishSeq.load(std::memory_order_relaxed) + 1;
	const int64_t now = OsNowNs();
	std::memcpy(dst + 0, &seq, sizeof(seq));
	std::memcpy(dst + 16, &now, sizeof(now));
	tb.publishSeq.store(seq, std::memory_order_relaxed);
	const uint32_t previous = tb.middle.exchange(back | Fresh, std::memory_order_acq_rel);
	tb.back.store(previous & 3, std::memory_order_release);
	tb.lastPublishNs.store(now, std::memory_order_release);
	return DFB_OK;
}

DFB_API int dfb_read_state(dfb_session *s, void *out, uint32_t size)
{
	if (!s || !s->side || !out) return DFB_ERR_ARG;
	const int peerSide = s->side == DFB_SIDE_DF ? DFB_SIDE_UZ : DFB_SIDE_DF;
	if (size != StateSizeFor(peerSide)) return DFB_ERR_SIZE;
	TripleBuffer &tb = *s->peer;
	int rc = DFB_EMPTY;
	uint32_t front = tb.front.load(std::memory_order_relaxed);
	if (tb.middle.load(std::memory_order_relaxed) & Fresh)
	{
		const uint32_t previous = tb.middle.exchange(front, std::memory_order_acq_rel);
		front = previous & 3;
		tb.front.store(front, std::memory_order_release);
		rc = DFB_GOT;
	}
	std::memcpy(out, tb.buffers[front], size);
	return rc;
}

DFB_API int dfb_bulk_write(dfb_session *s, uint32_t slot, const void *data, uint32_t size, uint32_t *version_out)
{
	if (!s || !s->side || slot >= DFB_BULK_SLOTS || (!data && size)) return DFB_ERR_ARG;
	if (!OwnsBulkSlot(s->side, slot)) return DFB_ERR_SIDE;
	if (size > DFB_BULK_BYTES) return DFB_ERR_SIZE;
	BulkSlot &b = s->shared->bulk[slot];
	uint32_t v = b.version.load(std::memory_order_relaxed);
	if (v & 1) v++; // a previous writer died mid-copy; move past it
	b.version.store(v + 1, std::memory_order_relaxed);
	std::atomic_thread_fence(std::memory_order_release);
	if (size) std::memcpy(b.data, data, size);
	b.size.store(size, std::memory_order_relaxed);
	b.version.store(v + 2, std::memory_order_release);
	if (version_out) *version_out = (v + 2) / 2;
	return DFB_OK;
}

DFB_API int dfb_bulk_read(dfb_session *s, uint32_t slot, void *out, uint32_t capacity, uint32_t *size_out, uint32_t *version_out)
{
	if (!s || !s->side || slot >= DFB_BULK_SLOTS) return DFB_ERR_ARG;
	BulkSlot &b = s->shared->bulk[slot];
	for (int tries = 0; tries < 4; tries++)
	{
		const uint32_t v1 = b.version.load(std::memory_order_acquire);
		if (v1 & 1) continue;
		if (v1 == 0)
		{
			if (size_out) *size_out = 0;
			if (version_out) *version_out = 0;
			return DFB_EMPTY;
		}
		const uint32_t size = b.size.load(std::memory_order_relaxed);
		if (size > capacity || (!out && size)) return DFB_ERR_SIZE;
		if (size) std::memcpy(out, b.data, size);
		std::atomic_thread_fence(std::memory_order_acquire);
		if (b.version.load(std::memory_order_relaxed) != v1) continue;
		if (size_out) *size_out = size;
		if (version_out) *version_out = v1 / 2;
		return DFB_GOT;
	}
	return DFB_ERR_BUSY;
}

DFB_API uint32_t dfb_bulk_version(dfb_session *s, uint32_t slot)
{
	if (!s || slot >= DFB_BULK_SLOTS) return 0;
	return s->shared->bulk[slot].version.load(std::memory_order_acquire) / 2;
}

DFB_API int dfb_surface_write(dfb_session *s, const void *bgra, uint32_t width, uint32_t height,
	uint32_t frame_id, int64_t captured_ns, int64_t input_ns, int flip_y)
{
	if (!s || !s->surface || !bgra || !width || !height) return DFB_ERR_ARG;
	if (s->side != DFB_SIDE_DF) return DFB_ERR_SIDE;
	if (width > DFB_SURFACE_MAX_W || height > DFB_SURFACE_MAX_H) return DFB_ERR_SIZE;
	SurfaceShared &surface = *s->surface;
	const uint32_t back = surface.back.load(std::memory_order_relaxed);
	const size_t row = size_t(width) * 4;
	const uint8_t *src = static_cast<const uint8_t *>(bgra);
	uint8_t *dst = surface.pixels[back];
	if (flip_y)
		for (uint32_t y = 0; y < height; y++) std::memcpy(dst + y * row, src + (height - 1 - y) * row, row);
	else
		std::memcpy(dst, src, row * height);
	surface.frames[back] = dfb_surface_frame{ width, height, frame_id, 0, captured_ns, input_ns, OsNowNs() };
	const uint32_t previous = surface.middle.exchange(back | Fresh, std::memory_order_acq_rel);
	surface.back.store(previous & 3, std::memory_order_release);
	return DFB_OK;
}

DFB_API int dfb_surface_acquire(dfb_session *s, dfb_surface_frame *frame, const void **pixels)
{
	if (!s || !s->surface || !frame || !pixels) return DFB_ERR_ARG;
	if (s->side != DFB_SIDE_UZ) return DFB_ERR_SIDE;
	SurfaceShared &surface = *s->surface;
	int rc = DFB_EMPTY;
	uint32_t front = surface.front.load(std::memory_order_relaxed);
	if (surface.middle.load(std::memory_order_relaxed) & Fresh)
	{
		const uint32_t previous = surface.middle.exchange(front, std::memory_order_acq_rel);
		front = previous & 3;
		surface.front.store(front, std::memory_order_release);
		rc = DFB_GOT;
	}
	*frame = surface.frames[front];
	*pixels = frame->width ? surface.pixels[front] : nullptr;
	return rc;
}

DFB_API int dfb_atomic_replace(const char *temp_path, const char *final_path)
{
	if (!temp_path || !final_path) return DFB_ERR_ARG;
#ifdef _WIN32
	wchar_t temp[1024], target[1024];
	if (!MultiByteToWideChar(CP_UTF8, 0, temp_path, -1, temp, 1024) || !MultiByteToWideChar(CP_UTF8, 0, final_path, -1, target, 1024))
		return DFB_ERR_ARG;
	HANDLE file = CreateFileW(temp, GENERIC_WRITE, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (file == INVALID_HANDLE_VALUE) return DFB_ERR_OS;
	const BOOL flushed = FlushFileBuffers(file);
	CloseHandle(file);
	if (!flushed) return DFB_ERR_OS;
	// Antivirus or the indexer can hold the target briefly.
	for (int attempt = 0; attempt < 10; attempt++)
	{
		if (MoveFileExW(temp, target, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) return DFB_OK;
		Sleep(20);
	}
	return DFB_ERR_OS;
#else
	int fd = open(temp_path, O_RDWR);
	if (fd < 0) return DFB_ERR_OS;
	const int synced = fsync(fd);
	close(fd);
	if (synced != 0 || rename(temp_path, final_path) != 0) return DFB_ERR_OS;
	return DFB_OK;
#endif
}

DFB_API int dfb_get_stats(dfb_session *s, dfb_stats *out)
{
	if (!s || !s->side || !out) return DFB_ERR_ARG;
	std::memset(out, 0, sizeof(*out));
	out->sent = s->sent;
	out->received = s->received;
	out->queued_overflow = s->queued;
	out->seq_gaps = s->gaps;
	out->outbox_count = s->outboxCount;
	out->outbox_peak = s->outboxPeak;
	out->ring_used_out = (uint32_t)(s->out->head.load(std::memory_order_acquire) - s->out->tail.load(std::memory_order_acquire));
	out->ring_used_in = (uint32_t)(s->in->head.load(std::memory_order_acquire) - s->in->tail.load(std::memory_order_acquire));
	const int peerSide = s->side == DFB_SIDE_DF ? DFB_SIDE_UZ : DFB_SIDE_DF;
	out->peer_pid = s->shared->header.pid[peerSide].load(std::memory_order_relaxed);
	out->peer_attach_count = s->shared->header.attachCount[peerSide].load(std::memory_order_acquire);
	return DFB_OK;
}

DFB_API int64_t dfb_peer_state_age_ns(dfb_session *s)
{
	if (!s || !s->side) return -1;
	const int64_t last = s->peer->lastPublishNs.load(std::memory_order_acquire);
	return last ? OsNowNs() - last : -1;
}

} // extern "C"
