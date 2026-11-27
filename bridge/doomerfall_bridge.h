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
#define DFB_PROTOCOL_VERSION 7u

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
#define DFB_KIND_UI_ASK        25  /* DF to UZ; Daggerfall opened a window by itself, such as a quest message, and is paused behind it; Doom opens DFB_UI_DAGGERFALL when it can; payload: dfb_ui_command */

/* World items. Daggerfall owns them: it lists what is in the current space and performs every pickup. */
#define DFB_KIND_ITEMS_BEGIN   40  /* DF to UZ; starts one full list for a space; payload: dfb_world_items */
#define DFB_KIND_ITEM          41  /* DF to UZ; one pile in that list; payload: dfb_world_item */
#define DFB_KIND_ITEMS_END     42  /* DF to UZ; the list is complete, and anything not in it is gone; payload: dfb_world_items */
#define DFB_KIND_ITEM_TAKE     43  /* UZ to DF; the player pressed Interact on a pile; payload: dfb_item_take */
#define DFB_KIND_ITEM_RESULT   44  /* DF to UZ; what Daggerfall did with that request; payload: dfb_item_result */
#define DFB_KIND_ITEMS_REQUEST 45  /* UZ to DF; send the current list again; payload: dfb_world_items */
#define DFB_KIND_CONTAINER     80  /* DF to UZ; one furniture container in an item list, between ITEMS_BEGIN and ITEMS_END; payload: dfb_world_container */

/* Info. Doom's Info control on something it can name. Daggerfall runs its own Info interaction and sends back each
   message it showed. Piles and containers do not use this: Daggerfall's Info on them is the same as Grab, so Doom sends ITEM_TAKE. */
#define DFB_KIND_INFO          90  /* UZ to DF; payload: dfb_info_request */
#define DFB_KIND_INFO_TEXT     91  /* DF to UZ; one message for that request; payload: dfb_info_text; DFB_INFO_MORE in flags when the text goes on in the next event */
#define DFB_KIND_INFO_NAME     92  /* UZ to DF; a monster's Doom name, sent just before its DFB_KIND_INFO; payload: dfb_info_text */
/* The label under the crosshair. Doom asks once per target it cannot name itself (an NPC, a townsperson, a pile, a
   building door); Daggerfall answers with the name it knows, without running any interaction or changing any state. */
#define DFB_KIND_LOOK          93  /* UZ to DF; payload: dfb_info_request, target DFB_INFO_NPC, _TOWNSPERSON, _PILE, _BUILDING or _DOOM_GUN */
#define DFB_KIND_LOOK_TEXT     94  /* DF to UZ; the label for that request, empty for none; payload: dfb_info_text; DFB_INFO_MORE as on INFO_TEXT */
/* A message Daggerfall shows on its HUD by itself, not as an answer: every AddHUDText, PopupMessage and
   SetMidScreenText outside an Info or Use capture, and the level-up line. Doom shows it once no Daggerfall menu is open. */
#define DFB_KIND_HUD_TEXT      95  /* DF to UZ; payload: dfb_info_text, request = ms Daggerfall holds the line, 0 for its default; DFB_INFO_MORE as on INFO_TEXT */

/* Doom items held by Daggerfall. A Doom item is named by the Doom world pickup class the player took. Daggerfall
   keeps the record in its inventory and save; Doom draws the sprite and applies the item when it is used. */
#define DFB_KIND_DOOM_ITEM_TAKE    140  /* UZ to DF; the player pressed Use on a Doom item, which waits for the answer; payload: dfb_doom_item */
#define DFB_KIND_DOOM_ITEM_RESULT  141  /* DF to UZ; status DFB_ITEM_TAKEN, DFB_ITEM_TOO_HEAVY, or DFB_ITEM_REFUSED; payload: dfb_doom_item */
#define DFB_KIND_DOOM_ITEM_USE     142  /* DF to UZ; the player used this item in Daggerfall's inventory; payload: dfb_doom_item */
#define DFB_KIND_DOOM_ITEM_USED    143  /* UZ to DF; status DFB_ITEM_TAKEN when Doom applied it, else DFB_ITEM_REFUSED; payload: dfb_doom_item */
#define DFB_KIND_DOOM_ITEM_ART_REQUEST 144 /* DF to UZ; send the sprite and name for this class; payload: dfb_doom_item */
#define DFB_KIND_DOOM_ITEM_ART     145  /* UZ to DF; DFB_ITEM_ART_SLOT holds the answer, or status DFB_ITEM_GONE for no such class; payload: dfb_doom_item */
#define DFB_ITEM_ART_SLOT   5u   /* bulk slot written by UZ: one dfb_item_art header, then width * height BGRA pixels, top row first */
#define DFB_ITEM_ART_HEADER 464u
#define DFB_KIND_DOOM_ITEM_GUN_STATE 146 /* UZ to DF; one state line (status amount, cls class) the gun in the next DOOM_ITEM_TAKE with this request carried, such as a DRLA modded pickup's mods */
#define DFB_KIND_DOOM_ITEM_ID      147  /* UZ to DF; the floor item's lasting id (map item, or a drop from a fixed loot roll), sent just before the DOOM_ITEM_TAKE with this request when it has one; Daggerfall seeds the item's rolls (gun material) with it; payload: dfb_item_take, mode 0 */
/* In DFB_KIND_DOOM_ITEM_TAKE, status DFB_DOOM_ITEM_GUN marks a gun, DFB_DOOM_ITEM_ARMOR armor (Weapons & Armor tab),
   DFB_DOOM_ITEM_WEARABLE armor or boots Daggerfall cannot put on yet (DRLA's). For a gun, the bits under
   DFB_DOOM_ITEM_SLOT_MASK hold its Doom weapon slot plus 1 (0: no slot). */
#define DFB_DOOM_ITEM_GUN   1u
#define DFB_DOOM_ITEM_ARMOR 2u
#define DFB_DOOM_ITEM_WEARABLE 4u
#define DFB_DOOM_ITEM_SLOT_SHIFT 8u
#define DFB_DOOM_ITEM_SLOT_MASK 0xf00u

/* Weapon hotkeys. Daggerfall holds every gun and the hotkey table. Doom holds only the active gun. A gun's per-class
   Doom inventory (DRLA's magazine RL<Weapon>Clip, mods, mod limit) travels as GUN_STATE lines: request, status is the
   amount, cls is the Doom inventory class. All payloads: dfb_doom_item. */
#define DFB_KIND_HOTKEY        150  /* UZ to DF; a hotkey press on a generated map; request is the key 0-9, status DFB_HOTKEY_PLAIN, _CTRL, or _ALT */
#define DFB_KIND_GUN_STATE     151  /* both ways; one state line of the gun named by the next GUN_EQUIP (DF to UZ) or GUN_STASHED (UZ to DF) with the same request */
#define DFB_KIND_GUN_EQUIP     152  /* DF to UZ; take every gun Doom holds and give this one (a world pickup class), without changing ammo; status DFB_GUN_* */
#define DFB_KIND_GUN_STASHED   153  /* UZ to DF; Doom took this gun (pickup class) away; its GUN_STATE lines came just before */
#define DFB_KIND_GUN_KEPT      154  /* UZ to DF; DFB_GUN_ADOPT kept Doom's ready gun (pickup class) as the active one */
#define DFB_KIND_GUN_EQUIPPED  155  /* UZ to DF; the request is done; status DFB_ITEM_TAKEN, or DFB_ITEM_REFUSED when Doom could not give the gun */
#define DFB_HOTKEY_PLAIN 0u
#define DFB_HOTKEY_CTRL  1u
#define DFB_HOTKEY_ALT   2u
#define DFB_GUN_GIVE   0u  /* give cls */
#define DFB_GUN_ADOPT  1u  /* cls is empty; keep the ready gun as the active one and take the rest */
#define DFB_GUN_CLEAR  2u  /* cls is empty; take every gun */
#define DFB_GUN_SELECT 3u  /* Doom already holds cls as the active gun; raise it */
#define DFB_GUN_FIST   4u  /* cls is empty; raise the fist (given if missing); the active gun stays in Doom, lowered */

/* Climbing. Doom runs the climb with the DFB_SHEET_CLIMB_* chances and reports each skill roll it made. */
#define DFB_KIND_CLIMB_USES    170  /* UZ to DF; Daggerfall tallies this many Climbing skill uses; payload: dfb_climb_uses */

/* Reserve ammo. Daggerfall holds it as stacked inventory items; Doom's ammo inventory is the live counter that guns
   spend. Doom reports each count when it changes, and Daggerfall sends its own changes (drops, trades, piles) as
   numbered deltas. Payloads: dfb_doom_item, cls is Doom's ammo class (Clip, Shell, RocketAmmo, Cell). */
#define DFB_KIND_AMMO          171  /* UZ to DF; status is Doom's count; request is the last AMMO_ADD Doom applied */
#define DFB_KIND_AMMO_ADD      172  /* DF to UZ; status is a signed 32-bit delta to add (Doom's count stops at 0) */
#define DFB_KIND_AMMO_READY    173  /* UZ to DF; the ready weapon changed; cls is the reserve ammo class it uses, or empty for none */
#define DFB_KIND_AMMO_TAKE     174  /* UZ to DF; the player touched a tiered ammo pickup; cls is the reserve class, status the rounds, request the tier (0 Regular to 9 Daedric) */
#define DFB_KIND_AREA_LEVEL_REQUEST 175 /* UZ to DF; request is a map pixel, y * 1000 + x; Daggerfall answers with AREA_LEVEL */
#define DFB_KIND_AREA_LEVEL    176  /* DF to UZ; request is the map pixel, status the area level there (Doom rolls ammo drop tiers with it) */
/* The change ammo key. Daggerfall picks the next tier it holds for the ready gun, asks Doom to empty that gun's magazine
   (AMMO_UNLOAD), puts the emptied rounds back as the old tier, then loads the new tier through AMMO_ADD. */
#define DFB_KIND_AMMO_CHANGE   177  /* UZ to DF; the player pressed the change ammo key */
#define DFB_KIND_AMMO_UNLOAD   178  /* DF to UZ; request is a number; status 1 is automatic (refused while the magazine holds rounds); cls is the reserve class */
#define DFB_KIND_AMMO_UNLOADED 179  /* UZ to DF; request echoes AMMO_UNLOAD; status is the rounds taken out of the magazine, or 0xFFFFFFFF refused */
#define DFB_KIND_AMMO_LOADED   180  /* DF to UZ; request is the loaded tier (0xFFFFFFFF none), status the ammo type (0 Clip to 3 Cell); cls is the ammo's tags, comma separated */

/* Locked doors. Doom owns each live lock on the current map (its door's lock value: the converted map's starting lock,
   then action records and picks) and runs Daggerfall's door order itself. Daggerfall owns the rules and the player: it is
   asked about an attempt (chance or refusal) and does the pick bookkeeping. Lock changes (picks, levers) are kept in the
   location record's door fact (door_objects.zs DFDoorHandler.Distill), like the open doors.
   id is Daggerfall Unity's LoadID for a dungeon door (DFB_DOOR_DUNGEON). */
#define DFB_KIND_DOOR_USE      190  /* UZ to DF; Use on a shut door Doom holds locked; state is its live lock value; payload: dfb_door */
#define DFB_KIND_DOOR_STATE    191  /* DF to UZ; an answer to DOOR_USE (flags DFB_DOOR_PICK or _OPEN); payload: dfb_door */
#define DFB_KIND_LOCKPICK      192  /* UZ to DF; the minigame result for a DFB_DOOR_PICK answer; state is DFB_PICK_*; Doom opens the door itself on a hit; payload: dfb_door */
#define DFB_KIND_DOOR_TEXT     194  /* DF to UZ; a HUD message about a door (Daggerfall's words); payload: dfb_info_text; DFB_INFO_MORE as on INFO_TEXT */
#define DFB_DOOR_DUNGEON   1u
#define DFB_PICK_MISS      0u  /* dfb_door.state on DFB_KIND_LOCKPICK */
#define DFB_PICK_HIT       1u
#define DFB_PICK_CANCEL    2u
#define DFB_DOOR_OPEN      1u  /* dfb_door.flags: unlock this door and open it, not as the player's toggle (Castle Daggerfall's foyer doors) */
#define DFB_DOOR_PICK      2u  /* start the minigame with chance; picks is the count held */

/* A plain Daggerfall save (no Doom half) loaded from DFB_UI_LOAD_GAME. Daggerfall holds the game; Doom starts a game of
   its default class through the New Game chain, goes to the saved place, sends STARTER, then DFB_KIND_NEWGAME_ARRIVED.
   Daggerfall answers DFB_KIND_NEWGAME_GO and gives the starting weapon (the owner's rules, 2026-11-24). */
#define DFB_KIND_PLAIN_LOAD    220  /* DF to UZ; payload: dfb_plain_load */
#define DFB_KIND_STARTER       221  /* UZ to DF; the starter gun; payload: dfb_doom_item, cls the pistol's world pickup class (empty for none), request its weapon slot (low 8 bits, 255 for none) plus (reserve ammo type + 1) << 8 (0 Clip to 3 Cell), status the class's start amount of that ammo */

/* Use on an NPC Doom draws. Daggerfall runs its own activation of that NPC (Grab, or Steal while crouching). Any HUD
   message it shows comes back as DFB_KIND_INFO_TEXT with the same request number. */
#define DFB_KIND_NPC_USE        100 /* UZ to DF; payload: dfb_npc_use */
#define DFB_KIND_NPC_USE_RESULT 101 /* DF to UZ; payload: dfb_npc_use_result */

/* Monsters. A monster id is 64 bits: tag (3, value 5) | placement hash (49) | pack member (12).
   Every member of one placement shares the hash, so a pack needs no new id format. 12 member bits allow 4,096
   mooks per placement, enough for the encounter planner's heaviest swarm packs. */
#define DFB_KIND_MONSTER_DEATH     50  /* UZ to DF; a tagged monster died; payload: dfb_monster_death */
#define DFB_KIND_MONSTERS_BEGIN    51  /* DF to UZ; starts one full list for a dungeon; payload: dfb_world_items */
#define DFB_KIND_MONSTER           52  /* DF to UZ; one quest foe to place, or one dead id; payload: dfb_monster */
#define DFB_KIND_MONSTERS_END      53  /* DF to UZ; the list is complete; payload: dfb_world_items */
#define DFB_KIND_MONSTERS_REQUEST  54  /* UZ to DF; send the current list again; payload: dfb_world_items */
/* Encounters: the area facts the encounter planner needs, sent inside each monster list (between BEGIN and END).
   Each Daggerfall enemy is one encounter whose leader is member 0; only the leader's death counts for drops and quests. */
#define DFB_KIND_ENCOUNTER_AREA    55  /* DF to UZ; one per list; payload: dfb_encounter_area */
#define DFB_KIND_ENCOUNTER_TEXT    56  /* DF to UZ; one name for that list's area; payload: dfb_encounter_text */
#define DFB_ENCOUNTER_LOCATION_NAME 1u /* dfb_encounter_text.field */
#define DFB_ENCOUNTER_REGION_NAME   2u
#define DFB_ENCOUNTER_DUNGEON_TYPE  3u /* the DFRegion.DungeonTypes name, such as VampireHaunt */

/* NPCs. An NPC id is 64 bits: tag (3, value 6) | hash of its Daggerfall layout record (61). Doom draws every NPC in a
   generated map. Inside buildings Daggerfall lists who is present, because closed shops and owned houses are empty. */
#define DFB_KIND_NPCS_BEGIN    60  /* DF to UZ; starts one full list for an interior; payload: dfb_world_items */
#define DFB_KIND_NPC           61  /* DF to UZ; one NPC present in that interior; payload: dfb_npc */
#define DFB_KIND_NPCS_END      62  /* DF to UZ; the list is complete, and anyone not in it is absent; payload: dfb_world_items */
#define DFB_KIND_NPCS_REQUEST  63  /* UZ to DF; send the current list again; payload: dfb_world_items */

/* Townspeople: Daggerfall generates each town's wanderers from a seed and world time, and lists the ones near the
   player with their motion. A townsperson id is tag (3, value 7) | hash of map id and roster index (61). */
#define DFB_KIND_TOWNSFOLK_BEGIN   64  /* DF to UZ; starts one full list for the town around the player; payload: dfb_townsfolk */
#define DFB_KIND_TOWNSPERSON       65  /* DF to UZ; one visible townsperson; payload: dfb_townsperson */
#define DFB_KIND_TOWNSFOLK_END     66  /* DF to UZ; the list is complete, and anyone not in it is out of sight; payload: dfb_townsfolk */
#define DFB_KIND_TOWNSPERSON_DEATH 67  /* UZ to DF; a townsperson died; payload: dfb_townsperson_death */
#define DFB_KIND_TOWNSFOLK_REQUEST 68  /* UZ to DF; send the current list again; payload: dfb_townsfolk */

/* Guards: Daggerfall spawned a city guard. Its own copy stays inert, and Doom runs a hostile bot in its place.
   A guard id is tag (3, value 4) | Daggerfall's spawn serial (61). One event per guard; index and count describe the group. */
#define DFB_KIND_GUARD_SPAWN   160  /* DF to UZ; payload: dfb_guard_spawn */
#define DFB_KIND_GUARD_DEATH   161  /* UZ to DF; that guard's Doom bot died; payload: dfb_guard_death */
#define DFB_GUARD_TAG           4u

#define DFB_NPC_TAG             6u
#define DFB_NPC_TAG_SHIFT       61u
#define DFB_TOWNSPERSON_TAG     7u
#define DFB_TOWNSPERSON_GUARD   1u  /* dfb_townsperson.flags: idles with the guard record */

#define DFB_MONSTER_TAG         5u
#define DFB_MONSTER_TAG_SHIFT   61u
#define DFB_MONSTER_MEMBER_BITS 12u
#define DFB_MONSTER_PLACE  1u  /* a living quest foe's encounter; the id is its leader (member 0), standing at this position */
#define DFB_MONSTER_DEAD   2u  /* Daggerfall has this id as dead */

#define DFB_ITEM_TAKEN     0u  /* everything in the pile moved to the player */
#define DFB_ITEM_PARTIAL   1u  /* some moved; the rest stays in the pile */
#define DFB_ITEM_TOO_HEAVY 2u  /* nothing moved, because of the weight limit */
#define DFB_ITEM_GONE      3u  /* no such pile here */
#define DFB_ITEM_REFUSED   4u  /* Daggerfall cannot do this now, or the player is too far away */
#define DFB_ITEM_WINDOW    5u  /* Daggerfall will show its own window for this container; Doom opens DFB_UI_LOOT */
#define DFB_TAKE_GRAB      0u  /* Daggerfall's Grab interaction */
#define DFB_TAKE_STEAL     1u  /* Daggerfall's Steal interaction; the player is crouching */

#define DFB_INFO_NPC       1u  /* dfb_info_request.id is an NPC id */
#define DFB_INFO_BUILDING  2u  /* world_x and world_z are the point on the building Doom's view ray hit */
#define DFB_INFO_MONSTER   3u  /* a Doom monster, named by the DFB_KIND_INFO_NAME just before */
#define DFB_INFO_TOWNSPERSON 4u /* DFB_KIND_LOOK: dfb_info_request.id is a townsperson id */
#define DFB_INFO_PILE      5u  /* DFB_KIND_LOOK: dfb_info_request.id is a world item (pile or container) id */
#define DFB_INFO_DOOM_GUN  6u  /* DFB_KIND_LOOK: a Doom gun on the floor, its pickup class in the DFB_KIND_INFO_NAME just before (same request); id is its lasting floor id (DFB_KIND_DOOM_ITEM_ID) or 0, world_x the Daggerfall material it carries plus 1 (its DoomerfallGunMaterial token, a gun dropped from the inventory) or 0 */
#define DFB_INFO_DOOR      7u  /* DFB_KIND_LOOK: dfb_info_request.id is a locked door's live lock value (Doom's) */
#define DFB_INFO_HUD       0u  /* dfb_info_text.style: Daggerfall's scrolling HUD message */
#define DFB_INFO_MID       1u  /* dfb_info_text.style: Daggerfall's mid-screen message */
#define DFB_INFO_MORE      1u  /* dfb_event.flags on DFB_KIND_INFO_TEXT */

#define DFB_NPC_USE_WINDOW   0u  /* Daggerfall will activate the NPC once Doom opens DFB_UI_TALK */
#define DFB_NPC_USE_DONE     1u  /* Daggerfall handled it without a window, such as "You are too far away" */
#define DFB_NPC_USE_GONE     2u  /* Daggerfall has no such NPC loaded */
#define DFB_NPC_USE_REFUSED  3u  /* Daggerfall cannot do this now */

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
#define DFB_PLF_SLOWFALL      1u  /* dfb_df_state.player_flags: a Slowfall effect is active, so a fall starts over each frame (AcrobatMotor.ApplyGravity) */
#define DFB_PLF_OUTDOOR_WATER 2u  /* the player is outdoors over a water tile (PlayerTileMapIndex 0), where a landing does no damage (AcrobatMotor.CheckFallingDamage) */

/* Character sheet. Daggerfall writes this bulk slot as a flat array of DFB_SHEET_INTS int32 values whenever one
   changes, and Doom only reads it. Each group is indexed in Daggerfall's own enum order. "Base" excludes active
   effects and "live" includes them. While VALID is 0 every other value except FORMAT and EPOCH is zero. EPOCH
   changes whenever the character may have been replaced, so a reader must drop anything it derived from an older one. */
/* Quest follower faces (card questfaces). Daggerfall owns the face list of its HUD (EscortingNPCFacePanel: quests'
   "add face" and "drop face", its saves and loads) and rewrites this bulk slot whenever that list changes. Doom keeps no
   faces of its own: it draws exactly what the newest version holds. Layout: one dfb_faces, then for each face one
   dfb_face followed by width * height BGRA pixels, top row first. Doom ignores a format it does not know. */
#define DFB_FACES_SLOT   1u
#define DFB_FACES_FORMAT_VERSION 1u
#define DFB_FACES_MAX    3u   /* Daggerfall's HUD shows at most three faces */
#define DFB_FACE_MAX_SIDE 64u

typedef struct dfb_faces
{
	uint32_t format;      /* DFB_FACES_FORMAT_VERSION */
	uint32_t count;       /* 0 to DFB_FACES_MAX, in Daggerfall's order, top face first */
} dfb_faces;

typedef struct dfb_face
{
	uint32_t width;           /* pixels that follow, each side at most DFB_FACE_MAX_SIDE */
	uint32_t height;
	uint32_t display_width;   /* the size Daggerfall draws it, in its 320x200 HUD units */
	uint32_t display_height;
} dfb_face;

#define DFB_SHEET_SLOT   0u
#define DFB_SHEET_FORMAT_VERSION 7  /* 3: skill slots 4-6 are the gun skills, 7-12 unused; 4: slot 7 is Pistols; 5: slot 8 is Rifles; 6: slots 9-10 are Energy Weapons and Melee; 7: Automatics perk rules */
#define DFB_SHEET_INTS   162
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
/* Skill indices into SKILLS_BASE and SKILLS_LIVE. Doomerfall removed the monster languages: their slots 4-10 hold the
   weapon skills and slots 11-12 are unused (always some small value, never shown or raised). Other slots keep
   Daggerfall's meaning, for example 30 Hand-to-Hand, 33 Archery, 34 Critical Strike (kept but unused). */
#define DFB_SKILL_SHOTGUNS     4
#define DFB_SKILL_AUTOMATICS   5
#define DFB_SKILL_EXPLOSIVES   6
#define DFB_SKILL_PISTOLS      7
#define DFB_SKILL_RIFLES       8
#define DFB_SKILL_ENERGY       9   /* Energy Weapons */
#define DFB_SKILL_MELEE        10
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
#define DFB_SHEET_CLIMB_CHANCE 150  /* 4: percent chances from FormulaHelper.CalculateClimbingChance, in DFB_CLIMB_* order */
#define DFB_SHEET_CLIMB_ENHANCED 154 /* 1 while a Climbing effect doubles climbing speed */
#define DFB_CLIMB_START    0   /* start from the ground; Daggerfall's base 70 */
#define DFB_CLIMB_GRASP    1   /* grab a wall while airborne; base 40 */
#define DFB_CLIMB_CONTINUE 2   /* keep climbing; base 50 */
#define DFB_CLIMB_REGAIN   3   /* regain a hold while slipping; base 20 */
/* Automatics skill rules (work/backlog/skills-in-doom.md), from the live Automatics skill. Daggerfall decides
   them and Doom applies them to guns whose skill is Automatics. 0 means that rule is off. */
#define DFB_SHEET_AUTO_DAMAGE_BP      155  /* damage bonus in 1/10000ths (+0% to +60% by skill) */
#define DFB_SHEET_AUTO_BURST_BP       156  /* burst fire: this much more damage ... */
#define DFB_SHEET_AUTO_BURST_SHOTS    157  /* ... on the first this many shots of a burst ... */
#define DFB_SHEET_AUTO_BURST_RESET_MS 158  /* ... which restarts this long after the last shot */
#define DFB_SHEET_AUTO_SHOTS_PER_AMMO 159  /* one ammo per this many shots; 1 or 0 is normal use */
#define DFB_SHEET_AUTO_SUNDER_BP      160  /* each hit makes the enemy take this much more damage from all sources ... */
#define DFB_SHEET_AUTO_SUNDER_MAX_BP  161  /* ... permanently, up to this much */

/* Daggerfall screens Doom can ask for. Add new menus here. */
#define DFB_UI_NONE        0u
#define DFB_UI_TRAVEL_MAP  1u
#define DFB_UI_INVENTORY   2u
#define DFB_UI_MAP         3u  /* the map for where the player is; dfb_ui_command.context is Doom's DFB_WORLD_* */
#define DFB_UI_NEW_GAME    4u  /* Daggerfall's character creation and new game cinematics */
#define DFB_UI_LOOT        5u  /* the window for the container Daggerfall just answered DFB_ITEM_WINDOW for */
#define DFB_UI_TALK        6u  /* whatever Daggerfall opens for the NPC it just answered DFB_NPC_USE_WINDOW for */
#define DFB_UI_DAGGERFALL  7u  /* the window Daggerfall opened by itself and asked for with DFB_KIND_UI_ASK */
#define DFB_UI_LOAD_GAME   8u  /* Daggerfall's own Load window, from Doom's title; a save loaded there has no Doom half (DFB_KIND_PLAIN_LOAD) */
#define DFB_UI_JOURNAL     9u  /* Daggerfall's quest journal; dfb_ui_command.context is Doom's DFB_WORLD_* (travel from it only outdoors) */
#define DFB_UI_REST       10u  /* Daggerfall's rest window; dfb_ui_command.context is DFB_REST_* bits from Doom's state */

#define DFB_REST_MONSTERS_NEAR 1u /* a hostile Doom monster sees the player or is within Daggerfall's resting distance */
#define DFB_REST_NOT_GROUNDED  2u /* Doom's player is in the air or swimming */

#define DFB_UI_CLOSED      0u
#define DFB_UI_OPENED      1u
/* Open, and a Daggerfall text box takes typing: Doom sends every key unchanged, and its own controls do not close
   the menu. Daggerfall sends DFB_UI_OPENED again when the text box goes away. */
#define DFB_UI_TYPING      2u

/* On a close: game time passed while the menu was open (a rest, loiter or rented room), so people stand elsewhere now.
   Daggerfall sent its fresh townsfolk and NPC lists just before this close; Doom holds its view until it has placed them. */
#define DFB_UI_CLOSED_TIME_PASSED 1u

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
#define DFB_UZ_PHASE_LOADING 1   /* a loading hold (UZDoom dd_loading.cpp); Daggerfall pauses while it lasts */
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
	uint32_t flags;           /* DFB_UI_CLOSED_*, on a close */
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

/* Where a new character starts. World units inside the start map pixel. dungeon_map_id is -1 outdoors.
   In a dungeon, start_* is the marker Daggerfall placed the character at, in Daggerfall units relative to the
   dungeon (Doom's space coordinates: x east, y north, z up), and start_yaw is the facing in Doom degrees. */
typedef struct dfb_new_game
{
	double world_x;
	double world_z;
	float yaw_degrees;
	int32_t map_pixel_x;
	int32_t map_pixel_y;
	int32_t dungeon_map_id;
	float start_x;
	float start_y;
	float start_z;
	float start_yaw;
} dfb_new_game;

/* Where a loaded plain Daggerfall save has the player (DFB_KIND_PLAIN_LOAD). context is DFB_WORLD_*. Outdoors world_x/z
   and yaw_degrees are the exact position and facing (Doom degrees). In a dungeon, world_x/z is the middle of its map
   pixel and dungeon_map_id names it. In a building, world_x/z is the building's door in Daggerfall world units.
   Indoors, start_* is the player's feet in Daggerfall units relative to the space (Doom's space coordinates: x east,
   y north, z up) and start_yaw the facing in Doom degrees. */
typedef struct dfb_plain_load
{
	double world_x;
	double world_z;
	float yaw_degrees;
	int32_t dungeon_map_id;
	uint32_t context;
	float start_x;
	float start_y;
	float start_z;
	float start_yaw;
	uint32_t pad;
} dfb_plain_load;

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

/* A container without a sprite, such as a shop shelf or a wardrobe. Doom units within the space: the box Doom's Use aims at. */
typedef struct dfb_world_container
{
	uint64_t id;
	uint32_t generation;
	uint32_t pad;
	float min_x;
	float min_y;
	float min_z;
	float max_x;
	float max_y;
	float max_z;
} dfb_world_container;

typedef struct dfb_item_take
{
	uint64_t id;
	uint32_t request;
	uint32_t mode;        /* DFB_TAKE_* */
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

/* World units, as in dfb_transition. */
typedef struct dfb_info_request
{
	uint32_t request;
	uint32_t target;      /* DFB_INFO_* */
	uint64_t id;
	double world_x;
	double world_z;
} dfb_info_request;

typedef struct dfb_info_text
{
	uint32_t request;
	uint32_t style;       /* DFB_INFO_HUD or DFB_INFO_MID */
	char text[40];        /* UTF-8, terminated unless full */
} dfb_info_text;

/* request numbers each exchange from 1, per sender. cls is the Doom class name, UTF-8, terminated. */
typedef struct dfb_doom_item
{
	uint32_t request;
	uint32_t status;      /* DFB_ITEM_*, on answers */
	char cls[40];
} dfb_doom_item;

/* See DFB_KIND_DOOR_USE. */
typedef struct dfb_door
{
	uint64_t id;
	uint32_t kind;        /* DFB_DOOR_DUNGEON */
	uint32_t state;       /* the lock value, or DFB_PICK_* on LOCKPICK */
	int32_t chance;       /* Daggerfall's lockpicking chance, 5 to 95 */
	int32_t picks;        /* Lockpicks the player holds */
	uint32_t flags;       /* DFB_DOOR_OPEN, _PICK, _ARM, _FACT */
	uint32_t pad;
} dfb_door;

/* Header of DFB_ITEM_ART_SLOT. tag is the item's display name, UTF-8, terminated. For a weapon, types names the weapon
   skills it counts as ("Energy, Shotgun"; empty for none) and brief is a short description from the mod's data (empty
   when it has none), both UTF-8 and terminated, for Daggerfall's item description. */
typedef struct dfb_item_art
{
	uint32_t request;
	uint32_t width;
	uint32_t height;
	uint32_t pad;
	char cls[64];
	char tag[64];
	char types[64];
	char brief[256];
} dfb_item_art;

typedef struct dfb_climb_uses
{
	uint32_t uses;        /* skill rolls since the last event, pass or fail */
	uint32_t pad;
} dfb_climb_uses;

typedef struct dfb_npc_use
{
	uint64_t id;          /* the NPC id, as in dfb_npc */
	uint32_t request;
	uint32_t mode;        /* DFB_TAKE_GRAB or DFB_TAKE_STEAL */
	double distance;      /* Daggerfall classic units from Doom's eye to where its view ray meets the NPC */
} dfb_npc_use;

typedef struct dfb_npc_use_result
{
	uint64_t id;
	uint32_t request;
	uint32_t status;      /* DFB_NPC_USE_* */
} dfb_npc_use_result;

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
	int32_t enemy_type;   /* DFB_MONSTER_PLACE: the quest foe's Daggerfall MobileTypes value */
} dfb_monster;

/* Daggerfall's facts about the dungeon a monster list is for. generation matches the list's. */
typedef struct dfb_encounter_area
{
	uint32_t generation;
	int32_t map_id;
	int32_t dungeon_index;  /* fixed index among Daggerfall's dungeons, in region then map table order; seeds the genome */
	int32_t location_id;
	int32_t region_index;
	float world_x;          /* world map position in map pixels */
	float world_y;
	int32_t dungeon_type;   /* DFRegion.DungeonTypes */
	int32_t area_level;     /* Daggerfall's computed area level */
	int32_t seed_offset;    /* 0: fixed dungeons */
	uint32_t pad0;
	uint32_t pad1;
} dfb_encounter_area;

typedef struct dfb_encounter_text
{
	uint32_t generation;
	uint32_t field;         /* DFB_ENCOUNTER_* */
	char text[40];          /* UTF-8, terminated unless full */
} dfb_encounter_text;

/* Location ledger: Daggerfall keeps the permanent record of what happened in each place, and Doom builds the place
   from it. Doom sends a place's whole record when the player leaves it and when it saves there (BEGIN, NAMEs,
   PLANs, FACTs, END); END replaces Daggerfall's record of that place. When the player enters a place, Doom sends
   PLACE_REQUEST, and Daggerfall answers with the same sequence, whose generation echoes the request's. Facts are
   changes from what the map, the encounter plan, or a Daggerfall placement rebuilds: dead (with the corpse), alive
   but moved or hurt, taken (gone), and dropped. Positions are Daggerfall units in the place's own frame (Doom map
   units / 0.75). A dungeon is keyed by its map id, a building interior by map id and building key, and the exterior
   (towns and the overworld alike) by world chunk: 32 x 32 tiles, 8192 Daggerfall units a side, with positions in
   the chunk's frame (x and y from the chunk's corner, z the world height). Exterior chunk records are sent for every
   chunk whose facts changed, on leaving an exterior map and with every save; Doom asks for all of them at once
   (PLACE_WORLD) after a load, and Daggerfall answers with one record per chunk and then an empty PLACE_WORLD record. */
#define DFB_KIND_PLACE_BEGIN    200  /* both ways; starts one place's record; payload: dfb_place */
#define DFB_KIND_PLACE_NAME     201  /* both ways; one class or death label of that record; a repeated index appends text; payload: dfb_place_name */
#define DFB_KIND_PLACE_FACT     202  /* both ways; one fact; payload: dfb_place_fact */
#define DFB_KIND_PLACE_PLAN     203  /* both ways; one line of the dungeon's first encounter request; payload: dfb_place_plan */
#define DFB_KIND_PLACE_END      204  /* both ways; the record is complete; payload: dfb_place */
#define DFB_KIND_PLACE_REQUEST  205  /* UZ to DF; the player entered this place; payload: dfb_place */
#define DFB_PLACE_DUNGEON       1u   /* dfb_place.place_kind; map_id is Daggerfall's dungeon map id */
#define DFB_PLACE_INTERIOR      2u   /* map_id is the location's map id, key the building key */
#define DFB_PLACE_CHUNK         3u   /* exterior world chunk: map_id is the chunk's x, key its y */
#define DFB_PLACE_WORLD         4u   /* a request for every exterior chunk; also the empty record that ends the answer */
#define DFB_CHUNK_UNITS         8192 /* Daggerfall units on a side of an exterior chunk (32 tiles) */
#define DFB_PLACE_KNOWN         1u   /* dfb_place.flags: Daggerfall has a record of this place (it was visited) */
#define DFB_PLACE_ON_SAVE       2u   /* dfb_place.flags: sent for a save while the player is inside */
#define DFB_FACT_MONSTER        0u   /* dfb_place_fact.kind: alive, but moved or hurt */
#define DFB_FACT_CORPSE         1u   /* dead, lying here */
#define DFB_FACT_ITEM           2u   /* an item lying here: moved, changed, or dropped */
#define DFB_FACT_GONE           3u   /* taken or destroyed */
#define DFB_FACT_DOORS          4u   /* a dungeon's hinged doors: death is the name "<stamp> <hex bits>" (door_objects.zs), id 0 */
#define DFB_FACT_DROPPED        1u   /* dfb_place_fact.flags: Doom's MF_DROPPED */
#define DFB_FACT_SESSION        2u   /* dfb_place_fact.flags: the id is Doom's own for this session (a drop), not a Daggerfall id */
#define DFB_PLACE_NO_NAME       65535u

typedef struct dfb_place
{
	uint32_t generation;
	uint32_t place_kind;    /* DFB_PLACE_* */
	int32_t map_id;
	uint32_t flags;         /* DFB_PLACE_KNOWN, DFB_PLACE_ON_SAVE */
	uint32_t facts;
	uint32_t names;
	uint32_t plan_lines;
	int32_t key;            /* DFB_PLACE_INTERIOR: building key; DFB_PLACE_CHUNK: chunk y; otherwise 0 */
} dfb_place;

typedef struct dfb_place_name
{
	uint32_t generation;
	uint16_t index;
	uint16_t pad;
	char text[40];          /* UTF-8, terminated unless full */
} dfb_place_name;

typedef struct dfb_place_fact
{
	uint64_t id;            /* a Daggerfall-derived id (mook, map pickup), or a session id with DFB_FACT_SESSION */
	uint32_t generation;
	float x;                /* Daggerfall units in the place's frame */
	float y;
	float z;
	float height;           /* a corpse's height in Doom units */
	int32_t health;
	int32_t amount;         /* an item's amount */
	uint16_t cls;           /* name index of the Doom class */
	uint16_t death;         /* name index of a corpse's death label, or DFB_PLACE_NO_NAME */
	uint16_t angle;         /* 65536 per turn */
	uint8_t kind;           /* DFB_FACT_* */
	uint8_t flags;          /* DFB_FACT_DROPPED, DFB_FACT_SESSION */
	uint32_t pad;
} dfb_place_fact;

/* header 1: value is the planned mook count. header 0: one quest placement of the first request (Doom units). */
typedef struct dfb_place_plan
{
	uint64_t placement;
	uint32_t generation;
	uint32_t header;
	float x;
	float y;
	float z;
	int32_t value;          /* header 1: mook count; header 0: the quest foe's enemy type */
} dfb_place_plan;

/* One NPC present in the listed interior. */
typedef struct dfb_npc
{
	uint64_t id;
	uint32_t generation;
	uint32_t pad;
} dfb_npc;

/* One townsfolk list. Rows are Daggerfall world units relative to origin, so floats keep their precision.
   An interior list (space DFB_TOWNSFOLK_INTERIOR) holds the people at home in the building the player is in; its rows
   are Doom map units in that interior's map, and the origin is unused. */
#define DFB_TOWNSFOLK_STREETS  0u
#define DFB_TOWNSFOLK_INTERIOR 1u
typedef struct dfb_townsfolk
{
	uint32_t generation;
	uint32_t count;
	int32_t map_id;       /* the town's Daggerfall map id, or 0 for an empty list away from towns */
	uint32_t space;       /* DFB_TOWNSFOLK_STREETS or DFB_TOWNSFOLK_INTERIOR */
	double origin_x;      /* Daggerfall world units */
	double origin_z;
} dfb_townsfolk;

/* A visible townsperson. Velocity is Daggerfall units per real second; Doom extrapolates between lists. */
typedef struct dfb_townsperson
{
	uint64_t id;
	uint32_t generation;
	uint16_t archive;     /* Daggerfall's mobile billboard archive */
	uint16_t flags;       /* DFB_TOWNSPERSON_* */
	float x;              /* east of origin_x */
	float y;              /* north of origin_z */
	float vx;
	float vy;
	float facing;         /* Doom angle in degrees: 0 is east, counterclockwise */
	float z;              /* interior lists: Doom height of the spot, so the right storey is found; else 0 */
} dfb_townsperson;

/* Position is Daggerfall world units, for logs. */
typedef struct dfb_townsperson_death
{
	uint64_t id;
	double world_x;
	double world_z;
} dfb_townsperson_death;

/* One guard Daggerfall spawned. For DFB_WORLD_INTERIOR, x and y are Doom units in that interior's map, like an item;
   target is the interior's space target. Other contexts are not relayed yet. */
typedef struct dfb_guard_spawn
{
	uint64_t id;
	uint32_t context;     /* DFB_WORLD_* */
	int32_t target;
	double x;
	double y;
	uint16_t mobile_type; /* Daggerfall's MobileTypes, 146 for the city watch */
	uint16_t index;
	uint16_t count;
	uint16_t pad;
} dfb_guard_spawn;

typedef struct dfb_guard_death
{
	uint64_t id;
} dfb_guard_death;

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
	/* The player's damage bonus, which Daggerfall tabulates (gamedesign/damage.md): 1/10000ths over base damage, so 0
	   is none and 10000 is +100%. Doom multiplies the damage the player deals by 1 + bp / 10000. */
	int32_t damage_bonus_bp;
	uint32_t player_flags;     /* DFB_PLF_*: Daggerfall's falling damage exemptions, which Doom applies to its falls */
	uint8_t reserved[DFB_STATE_BYTES - 56];
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
