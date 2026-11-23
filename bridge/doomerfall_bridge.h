// Doomerfall bridge: shared-memory transport between Daggerfall Unity (DF) and UZDoom (UZ).
//
// One source (doomerfall_bridge.cpp) with a C ABI. It is statically linked into UZDoom and the
// launcher, and built as a DLL for Unity. Every call is non-blocking.
//
// Lanes (see work/notes/bridge-contract.md, sections 3 and 4.1):
//   E-DF / E-UZ  two SPSC rings of 64-byte events, one per direction, with a local outbox on overflow
//   S-DF / S-UZ  two fixed state halves, one writer each, each in a triple buffer
//   B            versioned bulk slots holding opaque bytes, one writer per slot
//
// The launcher creates the session and passes its ID to both games. Both sides check the magic
// value, protocol version, and layout hash when they attach.

#ifndef DOOMERFALL_BRIDGE_H
#define DOOMERFALL_BRIDGE_H

#include <stdint.h>

#if defined(_WIN32) && defined(DFB_BUILD_DLL)
#define DFB_API __declspec(dllexport)
#else
#define DFB_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define DFB_MAGIC            0x42464444u /* "DDFB" */
#define DFB_PROTOCOL_VERSION 1u

#define DFB_RING_SLOTS     4096u   /* power of two */
#define DFB_OUTBOX_SLOTS   16384u  /* local, per process; hard cap before a bridge fault */
#define DFB_BULK_SLOTS     8u      /* 0-3 written by DF, 4-7 written by UZ */
#define DFB_BULK_BYTES     65536u
#define DFB_STATE_BYTES    256u    /* each state half; may grow to 4 KiB with a protocol bump */

/* Sides */
#define DFB_SIDE_DF 1
#define DFB_SIDE_UZ 2

/* Result codes. Negative values are errors. */
#define DFB_OK              0
#define DFB_EMPTY           0
#define DFB_GOT             1
#define DFB_QUEUED          2    /* ring full, kept in the local outbox */
#define DFB_ERR_ARG        -1
#define DFB_ERR_NO_SESSION -2    /* no shared mapping with that ID */
#define DFB_ERR_MAGIC      -3
#define DFB_ERR_VERSION    -4
#define DFB_ERR_LAYOUT     -5
#define DFB_ERR_OS         -6
#define DFB_ERR_OUTBOX_FULL -7   /* reliable event refused: caller must treat as a bridge fault */
#define DFB_ERR_BUSY       -8    /* bulk slot being written, try again later */
#define DFB_ERR_SIDE       -9    /* this side is not the writer of that lane or slot */
#define DFB_ERR_SIZE       -10

/* Event kinds. Unknown kinds must be skipped by the receiver, never treated as fatal. */
#define DFB_KIND_NONE       0
#define DFB_KIND_HELLO      1   /* sent once after attach; payload: dfb_hello */
#define DFB_KIND_PING       2   /* payload: dfb_ping */
#define DFB_KIND_PONG       3   /* payload: dfb_ping, echoed with the replier's receive time */
#define DFB_KIND_TEXT       4   /* payload: up to 48 bytes of UTF-8, not terminated if full */

/* Phases (contract 4.1) */
#define DFB_DF_PHASE_BOOT    0
#define DFB_DF_PHASE_MENU    1
#define DFB_DF_PHASE_LOADING 2
#define DFB_DF_PHASE_PLAY    3
#define DFB_DF_PHASE_DEAD    4
#define DFB_UZ_PHASE_BOOT    0
#define DFB_UZ_PHASE_LOADING 1
#define DFB_UZ_PHASE_PLAY    2
#define DFB_UZ_PHASE_PAUSED  3
#define DFB_UZ_PHASE_SAVING  4

/* 64-byte event record: u32 seq, u32 tic, u16 kind, u16 flags, u32 reserved, 48-byte payload.
   seq is stamped by dfb_send, per direction, starting at 1. tic is the sender's clock (Doom
   gametic, or a Daggerfall frame count). */
typedef struct dfb_event
{
	uint32_t seq;
	uint32_t tic;
	uint16_t kind;
	uint16_t flags;
	uint32_t reserved;
	uint8_t payload[48];
} dfb_event;

typedef struct dfb_ping
{
	uint32_t id;
	uint32_t pad;
	int64_t sent_ns;      /* sender's dfb_now_ns() */
	int64_t replier_ns;   /* PONG only: replier's dfb_now_ns() when it received the PING */
} dfb_ping;

typedef struct dfb_hello
{
	uint32_t pid;
	uint32_t side;
	int64_t now_ns;
} dfb_hello;

/* State half written by Daggerfall (S-DF). Fixed size, explicit padding. */
typedef struct dfb_df_state
{
	uint32_t publish_seq;     /* stamped by dfb_publish_state */
	uint32_t df_phase;
	uint64_t df_heartbeat;    /* increments every Daggerfall frame */
	int64_t published_ns;     /* stamped by dfb_publish_state */
	uint32_t df_frame;
	uint32_t demo_value;      /* bridge demo only: a value Daggerfall changes for Doom to read */
	uint8_t reserved[DFB_STATE_BYTES - 32];
} dfb_df_state;

/* State half written by UZDoom (S-UZ). */
typedef struct dfb_uz_state
{
	uint32_t publish_seq;
	uint32_t uz_phase;
	uint64_t uz_heartbeat;    /* increments every UZDoom frame */
	int64_t published_ns;
	uint32_t uz_tic;          /* gametic */
	uint32_t demo_value;      /* bridge demo only */
	uint8_t reserved[DFB_STATE_BYTES - 32];
} dfb_uz_state;

typedef struct dfb_stats
{
	uint64_t sent;            /* events accepted by dfb_send */
	uint64_t received;        /* events returned by dfb_receive */
	uint64_t queued_overflow; /* events that went through the outbox */
	uint64_t seq_gaps;        /* received events whose seq skipped a value */
	uint32_t outbox_count;    /* events waiting in the outbox */
	uint32_t outbox_peak;
	uint32_t ring_used_out;   /* events in our outgoing ring not yet read by the peer */
	uint32_t ring_used_in;    /* events in our incoming ring not yet read by us */
	uint32_t peer_pid;        /* pid of the attached peer, 0 if none or it closed cleanly */
	uint32_t peer_attach_count;
} dfb_stats;

typedef struct dfb_session dfb_session;

/* Library identity, for the attach check on the Unity side (struct sizes must match its own). */
DFB_API uint32_t dfb_protocol_version(void);
DFB_API uint64_t dfb_layout_hash(void);
DFB_API uint32_t dfb_struct_size(int which); /* 0 event, 1 df_state, 2 uz_state, 3 stats, 4 ping */

/* Monotonic clock in nanoseconds, comparable across processes on the same machine. */
DFB_API int64_t dfb_now_ns(void);

/* Launcher: create the shared session. The creator must keep it open while the games run. */
DFB_API int dfb_create(const char *session_id, dfb_session **out);

/* Games: attach to an existing session as one side. */
DFB_API int dfb_attach(const char *session_id, int side, dfb_session **out);
DFB_API void dfb_close(dfb_session *session);

/* Events. dfb_send never blocks. If the ring is full the event goes to the local outbox and
   DFB_QUEUED is returned. If the outbox is also full, DFB_ERR_OUTBOX_FULL: a bridge fault. */
DFB_API int dfb_send(dfb_session *session, const dfb_event *event);
/* Moves outbox events into the ring. Returns how many remain in the outbox. */
DFB_API int dfb_flush(dfb_session *session);
/* Returns DFB_GOT and fills *out, or DFB_EMPTY. Delivery is at-least-once across a consumer
   crash: an event being read when the consumer died may be read again by its replacement. */
DFB_API int dfb_receive(dfb_session *session, dfb_event *out);

/* State. Each side publishes its own half and reads the peer's half.
   DF publishes dfb_df_state and reads dfb_uz_state; UZ the reverse. size must match.
   dfb_read_state returns DFB_GOT if a newer state was taken, DFB_EMPTY if unchanged
   (out still receives the latest state), or DFB_ERR_* . Before the peer's first publish the
   state reads as zeros. */
DFB_API int dfb_publish_state(dfb_session *session, const void *state, uint32_t size);
DFB_API int dfb_read_state(dfb_session *session, void *out, uint32_t size);

/* Bulk slots. Slots 0-3 are written by DF, 4-7 by UZ. Version 0 means never written.
   dfb_bulk_read returns DFB_GOT, DFB_EMPTY (never written), or DFB_ERR_BUSY. */
DFB_API int dfb_bulk_write(dfb_session *session, uint32_t slot, const void *data, uint32_t size, uint32_t *version_out);
DFB_API int dfb_bulk_read(dfb_session *session, uint32_t slot, void *out, uint32_t capacity, uint32_t *size_out, uint32_t *version_out);
DFB_API uint32_t dfb_bulk_version(dfb_session *session, uint32_t slot);

DFB_API int dfb_get_stats(dfb_session *session, dfb_stats *out);

/* Peer liveness, for logging only: nanoseconds since the peer last published state, or -1. */
DFB_API int64_t dfb_peer_state_age_ns(dfb_session *session);

#ifdef __cplusplus
}
#endif

#endif
