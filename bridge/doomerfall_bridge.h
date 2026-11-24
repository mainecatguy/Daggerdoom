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
//
// THIS HEADER IS THE ONLY DEFINITION OF THE BRIDGE. After changing it, run:
//     python bridge/generate_bindings.py
// That rewrites the C# constants, structs, and imports (DoomerfallBridge.g.cs) and the compile-time
// checks (doomerfall_bridge_check.g.h). Builds fail while they are stale. Never edit those files.
// An event kind's "payload: dfb_x" comment is read by the generator and creates its typed C# view.
// Daggerfall handles events in DoomerfallBridge.DrainEvents, and UZDoom in UZDoom/src/dd_bridge.cpp.

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
#define DFB_PROTOCOL_VERSION 6u

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
#define DFB_KIND_HELLO      1   /* both ways; sent once after attach; payload: dfb_hello */
#define DFB_KIND_PING       2   /* both ways; latency probe; payload: dfb_ping */
#define DFB_KIND_PONG       3   /* both ways; echoed with the replier's receive time; payload: dfb_ping */
#define DFB_KIND_TEXT       4   /* both ways; logs and test commands; up to 48 bytes of UTF-8, not terminated if full */
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
#define DFB_KIND_HOLD          19  /* UZ to DF; the payload's first 8 bytes are 1 to hold Daggerfall paused at Doom's title, 0 to release */
#define DFB_KIND_TRAVEL        20  /* DF to UZ; Daggerfall finished a fast travel, sent before the menu closes; payload: dfb_travel */
#define DFB_KIND_TRANSITION    21  /* UZ to DF; the player went through a door, or a load restored this place; payload: dfb_transition */
#define DFB_KIND_NEWGAME       22  /* DF to UZ; a character is made and Daggerfall is held at its start; payload: dfb_new_game */
#define DFB_KIND_NEWGAME_ARRIVED 23 /* UZ to DF; the payload's first 8 bytes are 1 when Doom is in the same place, 0 if it could not get there */
#define DFB_KIND_NEWGAME_GO    24  /* DF to UZ; Daggerfall started its quests and clock, so both games run */

/* World items. Daggerfall owns them: it lists what is in the current space and performs every pickup. */
#define DFB_KIND_ITEMS_BEGIN   40  /* DF to UZ; starts one full list for a space; payload: dfb_world_items */
#define DFB_KIND_ITEM          41  /* DF to UZ; one pile in that list; payload: dfb_world_item */
#define DFB_KIND_ITEMS_END     42  /* DF to UZ; the list is complete, and anything not in it is gone; payload: dfb_world_items */
#define DFB_KIND_ITEM_TAKE     43  /* UZ to DF; the player pressed Interact on a pile; payload: dfb_item_take */
#define DFB_KIND_ITEM_RESULT   44  /* DF to UZ; what Daggerfall did with that request; payload: dfb_item_result */
#define DFB_KIND_ITEMS_REQUEST 45  /* UZ to DF; send the current list again; payload: dfb_world_items */

/* Monsters. A monster id is 64 bits: tag (3, value 5) | placement hash (53) | pack member (8).
   Every member of one placement shares the hash, so a pack needs no new id format. */
#define DFB_KIND_MONSTER_DEATH     50  /* UZ to DF; a tagged monster died; payload: dfb_monster_death */
#define DFB_KIND_MONSTERS_BEGIN    51  /* DF to UZ; starts one full list for a dungeon; payload: dfb_world_items */
#define DFB_KIND_MONSTER           52  /* DF to UZ; one quest foe to place, or one dead id; payload: dfb_monster */
#define DFB_KIND_MONSTERS_END      53  /* DF to UZ; the list is complete; payload: dfb_world_items */
#define DFB_KIND_MONSTERS_REQUEST  54  /* UZ to DF; send the current list again; payload: dfb_world_items */

/* NPCs. An NPC id is 64 bits: tag (3, value 6) | hash of its Daggerfall layout record (61). Doom draws every NPC in a
   generated map. Inside buildings Daggerfall lists who is present, because closed shops and owned houses are empty. */
#define DFB_KIND_NPCS_BEGIN    60  /* DF to UZ; starts one full list for an interior; payload: dfb_world_items */
#define DFB_KIND_NPC           61  /* DF to UZ; one NPC present in that interior; payload: dfb_npc */
#define DFB_KIND_NPCS_END      62  /* DF to UZ; the list is complete, and anyone not in it is absent; payload: dfb_world_items */
#define DFB_KIND_NPCS_REQUEST  63  /* UZ to DF; send the current list again; payload: dfb_world_items */

#define DFB_NPC_TAG             6u
#define DFB_NPC_TAG_SHIFT       61u

#define DFB_MONSTER_TAG         5u
#define DFB_MONSTER_TAG_SHIFT   61u
#define DFB_MONSTER_MEMBER_BITS 8u
#define DFB_MONSTER_PLACE  1u  /* a living quest foe that Doom must have at this position */
#define DFB_MONSTER_DEAD   2u  /* Daggerfall has this id as dead */

#define DFB_ITEM_TAKEN     0u  /* everything in the pile moved to the player */
#define DFB_ITEM_PARTIAL   1u  /* some moved; the rest stays in the pile */
#define DFB_ITEM_TOO_HEAVY 2u  /* nothing moved, because of the weight limit */
#define DFB_ITEM_GONE      3u  /* no such pile here */
#define DFB_ITEM_REFUSED   4u  /* Daggerfall cannot do this now, or the player is too far away */

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

/* Character sheet. Daggerfall writes this bulk slot as a flat array of DFB_SHEET_INTS int32 values whenever one
   changes, and Doom only reads it. Each group is indexed in Daggerfall's own enum order. "Base" excludes active
   effects and "live" includes them. While VALID is 0 every other value except FORMAT and EPOCH is zero. EPOCH
   changes whenever the character may have been replaced, so a reader must drop anything it derived from an older one. */
#define DFB_SHEET_SLOT   0u
#define DFB_SHEET_FORMAT_VERSION 1
#define DFB_SHEET_INTS   150
#define DFB_SHEET_FORMAT 0    /* DFB_SHEET_FORMAT_VERSION */
#define DFB_SHEET_EPOCH  1
#define DFB_SHEET_VALID  2    /* 1 when this describes the current, fully loaded character */
#define DFB_SHEET_LEVEL  3
#define DFB_SHEET_FATIGUE_CURRENT 4  /* Daggerfall's internal units, 64 per displayed point */
#define DFB_SHEET_FATIGUE_MAX     5
#define DFB_SHEET_MAGICKA_CURRENT 6
#define DFB_SHEET_MAGICKA_MAX     7
#define DFB_SHEET_MAGIC_RESIST    8  /* added to saving throws; live Willpower / 10 */
#define DFB_SHEET_ARMOR_INCREASE  9  /* effect modifier added to every armor value; lower armor values protect more */
#define DFB_SHEET_ARMOR_DECREASE  10
#define DFB_SHEET_STATS_BASE   16   /* 8: DFCareer.Stats */
#define DFB_SHEET_STATS_LIVE   24   /* 8 */
#define DFB_SHEET_SKILLS_BASE  32   /* 35: DFCareer.Skills */
#define DFB_SHEET_SKILLS_LIVE  67   /* 35 */
#define DFB_SHEET_ARMOR_BASE   102  /* 7: BodyParts; 100 is unarmored */
#define DFB_SHEET_ARMOR_LIVE   109  /* 7: the value Daggerfall's hit formula uses */
#define DFB_SHEET_RESIST_BASE  116  /* 5: DFCareer.Elements */
#define DFB_SHEET_RESIST_LIVE  121  /* 5 */
#define DFB_SHEET_RESIST_ACTIVE 126 /* 5: 1 while an effect grants a resistance roll */
#define DFB_SHEET_RESIST_CHANCE 131 /* 5: that roll's percent chance */
#define DFB_SHEET_TOLERANCE    136  /* 7: DFCareer.Tolerance for paralysis, magic, poison, fire, frost, shock, disease */
#define DFB_SHEET_RACE_RESIST  143  /* DFCareer.EffectFlags of the live race */
#define DFB_SHEET_RACE_IMMUNE  144
#define DFB_SHEET_RACE_LOW     145
#define DFB_SHEET_RACE_CRITICAL 146
#define DFB_SHEET_BIO_MAGIC    147  /* biography saving throw modifiers */
#define DFB_SHEET_BIO_POISON   148
#define DFB_SHEET_BIO_DISEASE  149

/* Daggerfall screens Doom can ask for. Add new menus here. */
#define DFB_UI_NONE        0u
#define DFB_UI_TRAVEL_MAP  1u
#define DFB_UI_INVENTORY   2u
#define DFB_UI_MAP         3u  /* the map for where the player is; dfb_ui_command.context is Doom's DFB_WORLD_* */
#define DFB_UI_NEW_GAME    4u  /* Daggerfall's character creation and new game cinematics */

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
	uint32_t context;
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

/* Where a new character starts. World units inside the start map pixel. dungeon_map_id is -1 outdoors. */
typedef struct dfb_new_game
{
	double world_x;
	double world_z;
	float yaw_degrees;
	int32_t map_pixel_x;
	int32_t map_pixel_y;
	int32_t dungeon_map_id;
} dfb_new_game;

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

/* One list of world items for one space. target is the space id Doom reports in dfb_uz_state.space_target. */
typedef struct dfb_world_items
{
	uint32_t generation;
	uint32_t context;     /* DFB_WORLD_* */
	int32_t target;
	uint32_t count;
} dfb_world_items;

/* One pile. Position and size are Doom units within the space; the position is the sprite's center. */
typedef struct dfb_world_item
{
	uint64_t id;
	uint32_t generation;
	int32_t archive;
	int32_t record;
	int32_t item_count;
	float x;
	float y;
	float z;
	float width;
	float height;
	uint32_t pad;
} dfb_world_item;

typedef struct dfb_item_take
{
	uint64_t id;
	uint32_t request;
	uint32_t pad;
} dfb_item_take;

typedef struct dfb_item_result
{
	uint64_t id;
	uint32_t request;
	uint32_t status;      /* DFB_ITEM_* */
	int32_t taken;
	int32_t remaining;
	char name[24];        /* UTF-8, terminated: the first item taken */
} dfb_item_result;

/* Position is Doom units within the space. target is the space id from dfb_uz_state.space_target. */
typedef struct dfb_monster_death
{
	uint64_t id;
	uint32_t context;     /* DFB_WORLD_* */
	int32_t target;
	float x;
	float y;
	float z;
	uint32_t pad;
} dfb_monster_death;

typedef struct dfb_monster
{
	uint64_t id;
	uint32_t generation;
	uint32_t state;       /* DFB_MONSTER_PLACE or DFB_MONSTER_DEAD */
	float x;
	float y;
	float z;
	uint32_t pad;
} dfb_monster;

/* One NPC present in the listed interior. */
typedef struct dfb_npc
{
	uint64_t id;
	uint32_t generation;
	uint32_t pad;
} dfb_npc;

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
	/* Indoors: the Doom player in the space's own Daggerfall units (doom / 0.75), x east, y north, z up.
	   Daggerfall's interior or dungeon local position is (x, z, y) / 40. */
	double space_x;
	double space_y;
	double space_z;
	float space_yaw;          /* Doom angle within the space */
	int32_t space_target;     /* the target of the door event for this space */
	uint32_t space_valid;     /* 0 outdoors and between maps */
	uint32_t pad1;
	uint8_t reserved[DFB_STATE_BYTES - 120];
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
DFB_API uint64_t dfb_schema_hash(void); /* hash of this header's definitions; C# compares it with its generated copy */
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
