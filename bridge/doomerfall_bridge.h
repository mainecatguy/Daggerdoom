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
#define DFB_PROTOCOL_VERSION 4u

#define DFB_RING_SLOTS     4096u   /* power of two */
#define DFB_OUTBOX_SLOTS   16384u  /* local, per process; hard cap before a bridge fault */
#define DFB_BULK_SLOTS     8u      /* 0-3 written by DF, 4-7 written by UZ */
#define DFB_BULK_BYTES     65536u
#define DFB_STATE_BYTES    256u    /* each state half; may grow to 4 KiB with a protocol bump */
#define DFB_SURFACE_MAX_W  1920u   /* UI surface: a separate mapping holding three BGRA frames */
#define DFB_SURFACE_MAX_H  1200u

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
#define DFB_KIND_AREA       5   /* UZ to DF, sent at once when the context or map pixel changes; payload: dfb_area */
#define DFB_KIND_UI_OPEN    6   /* UZ to DF; payload: dfb_ui_command */
#define DFB_KIND_UI_CLOSE   7   /* UZ to DF; payload: dfb_ui_command */
#define DFB_KIND_UI_INPUT   8   /* UZ to DF; payload: dfb_ui_input */
#define DFB_KIND_UI_STATE   9   /* DF to UZ; payload: dfb_ui_state */
#define DFB_KIND_UI_RESULT  10  /* DF to UZ; payload: dfb_ui_result */
#define DFB_KIND_HP         11  /* UZ to DF; one numbered hit or heal on the player; payload: dfb_hp_event */
#define DFB_KIND_SAVE_REQUEST  12  /* UZ to DF; Doom is frozen, and this is ordered after all its earlier events; payload: dfb_save_request */
#define DFB_KIND_SAVE_PREPARED 13  /* DF to UZ; Daggerfall's answer, ordered after all its earlier events; payload: dfb_save_reply */
#define DFB_KIND_SAVE_DONE     14  /* UZ to DF; the transaction ended and Daggerfall may resume; payload: dfb_save_done */
#define DFB_KIND_LOAD_REQUEST  15  /* UZ to DF; Doom is frozen and the staged save is checked; payload: dfb_load_request */
#define DFB_KIND_LOAD_READY    16  /* DF to UZ; Daggerfall restored the save, or left its game untouched; payload: dfb_save_reply */
#define DFB_KIND_LOAD_DONE     17  /* UZ to DF; Doom restored its half, or could not; payload: dfb_save_done */
#define DFB_KIND_LOAD_RESUME   18  /* DF to UZ; both games are ready and play continues; payload: dfb_save_done */
#define DFB_KIND_HOLD          19  /* UZ to DF; p0 is 1 to hold Daggerfall paused at Doom's title, 0 to release */
#define DFB_KIND_TRAVEL        20  /* DF to UZ; Daggerfall finished a fast travel, sent before the menu closes; payload: dfb_travel */
#define DFB_KIND_TRANSITION    21  /* UZ to DF; the player went through a door, or a load restored this place; payload: dfb_transition */

#define DFB_TRANSITION_ENTER_BUILDING 1u
#define DFB_TRANSITION_EXIT_BUILDING  2u
#define DFB_TRANSITION_ENTER_DUNGEON  3u
#define DFB_TRANSITION_EXIT_DUNGEON   4u

#define DFB_SAVE_OK      0u
#define DFB_SAVE_REFUSED 1u  /* Daggerfall cannot save right now */
#define DFB_SAVE_FAILED  2u  /* Daggerfall tried and could not write its save */
#define DFB_SAVE_PATH_SLOT 4u /* bulk slot: UTF-8 staging folder for Daggerfall's files, written before the request */

#define DFB_HP_HIT    1u
#define DFB_HP_HEAL   2u
#define DFB_HPF_VALID 1u  /* dfb_df_state.hp_current and hp_max describe a live Daggerfall player */
#define DFB_HPF_DEAD  2u  /* Daggerfall reports the player dead */

/* Daggerfall screens Doom can ask for. Add new menus here. */
#define DFB_UI_NONE        0u
#define DFB_UI_TRAVEL_MAP  1u
#define DFB_UI_INVENTORY   2u

#define DFB_UI_CLOSED      0u
#define DFB_UI_OPENED      1u

#define DFB_UI_REASON_NONE     0u
#define DFB_UI_REASON_USER     1u  /* the player closed it in Daggerfall */
#define DFB_UI_REASON_REFUSED  2u  /* Daggerfall could not open it here */
#define DFB_UI_REASON_RESULT   3u  /* closed after sending a dfb_ui_result */
#define DFB_UI_REASON_DOOM     4u  /* Doom asked it to close */

#define DFB_UI_INPUT_MOVE        1u /* a, b: surface pixels, origin top left */
#define DFB_UI_INPUT_BUTTON_DOWN 2u /* a: 0 left, 1 right, 2 middle */
#define DFB_UI_INPUT_BUTTON_UP   3u
#define DFB_UI_INPUT_WHEEL       4u /* a: notches, positive is up */
#define DFB_UI_INPUT_KEY_DOWN    5u /* a: Windows virtual key, with left and right modifiers separated */
#define DFB_UI_INPUT_KEY_UP      6u
#define DFB_UI_INPUT_CHAR        7u /* a: UTF-16 code unit */
#define DFB_UI_INPUT_RELEASE_ALL 8u /* Doom lost focus */

/* Where the Doom player is. Position alone cannot move Daggerfall indoors: INTERIOR and DUNGEON are
   reserved for the explicit transition work, and Daggerfall holds its position while they are set. */
#define DFB_WORLD_NONE     0u  /* not on a Daggerfall map, so Daggerfall ignores the position */
#define DFB_WORLD_EXTERIOR 1u
#define DFB_WORLD_INTERIOR 2u
#define DFB_WORLD_DUNGEON  3u

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

typedef struct dfb_area
{
	uint32_t world_context;
	int32_t map_pixel_x;
	int32_t map_pixel_y;
	uint32_t area_seq;
	int64_t sent_ns;
} dfb_area;

typedef struct dfb_ui_command
{
	uint32_t ui_id;
	uint32_t pad;
	int64_t sent_ns;
} dfb_ui_command;

typedef struct dfb_ui_input
{
	uint32_t type;
	int32_t a;
	int32_t b;
	uint32_t pad;
	int64_t sent_ns;
} dfb_ui_input;

typedef struct dfb_ui_state
{
	uint32_t ui_id;
	uint32_t state;
	uint32_t reason;
	uint32_t surface_width;
	uint32_t surface_height;
	uint32_t pad;
} dfb_ui_state;

typedef struct dfb_ui_result
{
	uint32_t ui_id;
	int32_t map_pixel_x;
	int32_t map_pixel_y;
	char name[36];        /* UTF-8, terminated */
} dfb_ui_result;

/* Where Daggerfall placed the player. World units, with Doom's yaw. */
typedef struct dfb_travel
{
	double world_x;
	double world_z;
	float yaw_degrees;
	int32_t map_pixel_x;
	int32_t map_pixel_y;
	uint32_t pad;
} dfb_travel;

/* The outside door used, in Daggerfall world units. target is Doom's interior space or dungeon map id, for logs. */
typedef struct dfb_transition
{
	uint32_t action;      /* DFB_TRANSITION_* */
	uint32_t seq;
	double door_x;
	double door_z;
	int32_t target;
	uint32_t pad;
} dfb_transition;

/* Describes one frame in the UI surface. Pixels are BGRA, top row first, width * 4 bytes per row. */
typedef struct dfb_surface_frame
{
	uint32_t width;
	uint32_t height;
	uint32_t frame_id;
	uint32_t pad;
	int64_t captured_ns;  /* when Daggerfall asked the GPU for this frame */
	int64_t input_ns;     /* sent_ns of the newest input applied before this frame was drawn, or 0 */
	int64_t published_ns;
} dfb_surface_frame;

/* Player HP (MVP). Doom numbers each hit or heal from 1 and sends it unchanged. Daggerfall applies them in
   order and publishes the number of the last one it applied in dfb_df_state.hp_applied_event. */
typedef struct dfb_hp_event
{
	uint32_t event_no;
	uint32_t type;        /* DFB_HP_HIT or DFB_HP_HEAL */
	int32_t amount;       /* always positive */
	uint32_t pad;
	int64_t sent_ns;
} dfb_hp_event;

/* Synchronized save. Doom picks the transaction number and the staging folder. */
typedef struct dfb_save_request
{
	uint32_t txn;
	uint32_t hp_sent_through; /* number of the last dfb_hp_event sent before the freeze */
	int64_t sent_ns;
} dfb_save_request;

typedef struct dfb_save_reply
{
	uint32_t txn;
	uint32_t status;      /* DFB_SAVE_* */
	int32_t hp_current;
	int32_t hp_max;
	uint32_t hp_applied;
	uint32_t file_count;
	int32_t world_x;      /* Daggerfall's saved position */
	int32_t world_z;
	uint64_t total_bytes;
} dfb_save_reply;

typedef struct dfb_load_request
{
	uint32_t txn;
	int32_t hp;           /* The manifest's values, which Daggerfall's half must match */
	int32_t hp_max;
	int32_t world_x;
	int32_t world_z;
	uint32_t file_count;
	int64_t sent_ns;
} dfb_load_request;

typedef struct dfb_save_done
{
	uint32_t txn;
	uint32_t committed;   /* 1 if the bundle replaced the save file */
} dfb_save_done;

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
	int32_t hp_current;       /* Daggerfall's confirmed player HP; meaningful when DFB_HPF_VALID is set */
	int32_t hp_max;
	uint32_t hp_applied_event;/* event_no of the last dfb_hp_event Daggerfall applied */
	uint32_t hp_flags;        /* DFB_HPF_* */
	uint8_t reserved[DFB_STATE_BYTES - 48];
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
	double world_x;           /* player position in Daggerfall world units: doom / 0.75 + window origin */
	double world_z;           /* Daggerfall's north axis, which is Doom's +Y */
	double world_height;      /* Daggerfall units; informational, Daggerfall stands on its own terrain */
	float yaw_degrees;        /* Doom angle: 0 is east, counterclockwise */
	uint32_t world_context;   /* DFB_WORLD_* */
	int32_t map_pixel_x;
	int32_t map_pixel_y;      /* Daggerfall convention: 499 - floor(world_z / 32768) */
	uint32_t area_seq;        /* increments with each DFB_KIND_AREA */
	uint32_t pad0;
	uint8_t reserved[DFB_STATE_BYTES - 80];
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

/* UI surface, a triple buffer with one writer (DF) and one reader (UZ).
   dfb_surface_write copies one BGRA frame. flip_y reverses the rows while copying.
   dfb_surface_acquire returns DFB_GOT with a newer frame, or DFB_EMPTY with the current one. The
   pixel pointer stays valid until the next acquire. Before the first write, *pixels is null. */
DFB_API int dfb_surface_write(dfb_session *session, const void *bgra, uint32_t width, uint32_t height,
	uint32_t frame_id, int64_t captured_ns, int64_t input_ns, int flip_y);
DFB_API int dfb_surface_acquire(dfb_session *session, dfb_surface_frame *frame, const void **pixels);

DFB_API int dfb_get_stats(dfb_session *session, dfb_stats *out);

/* Flushes temp_path to disk, then atomically replaces final_path with it. Paths are UTF-8.
   On failure final_path is unchanged and temp_path is left for the caller to remove. */
DFB_API int dfb_atomic_replace(const char *temp_path, const char *final_path);

/* Peer liveness, for logging only: nanoseconds since the peer last published state, or -1. */
DFB_API int64_t dfb_peer_state_age_ns(dfb_session *session);

#ifdef __cplusplus
}
#endif

#endif
