# Lockpick door locks: ownership review (2026-11-26)

A read-only architecture review of `agent/lockpick-20261126-114215`, asked for by the owner after three runs failed
verification on door action ordering. The owner approved its recommendation (below).

## Why the current design is complicated

The lock lives in Daggerfall (`DaggerfallActionDoor.CurrentLockValue`), Doom keeps a mirror (`DFDoor.lockState`)
refreshed by a polled, hashed locked-door list, and Doom runs Daggerfall's action records (`action_objects.zs`).
Daggerfall's `DaggerfallActionDoor.Open` (lines 258-281) does, synchronously: first-use DoorText, lock check,
door-triggered record (`ExecuteActionOnToggle`), swing. The branch splits that order across the async bridge, so each
verifier round found a new ordering gap. Two copies of the lock also need the hash poll, list resends, a "stale list,
open it" reply, `DD_DoorsResync`, and leave a window where Doom acts on a stale lock after a type 16 record.

## Approved split: Doom owns the live lock; Daggerfall owns the rules and the player's picks

- Each `DFDoor` sets `lockState` from `startingLock` (already exported). 20 or more is magic (`IsMagicallyHeld`).
  Arm locks only in a bridge session, so a converted map without Daggerfall has no unopenable doors; stock WADs are
  unaffected.
- Action records 16/17/18/20 change Doom's lock locally with `DaggerfallAction`'s rules (lock to 16, unlock to 0, open
  clears, close restores the starting lock). No bridge message.
- `TryUse` reproduces `Open`'s order in one place: DoorText, lock check, door trigger, swing. A pick hit calls the same
  toggle past the lock. Ordering cases become a Doom-only harness.
- Daggerfall is asked only about the player: `LOCK_ASK(id, lockValue)` returns the chance or a refusal text (no picks,
  magic); `LOCKPICK(result)` makes Daggerfall tally the skill, break a pick or not, and send the text. On a hit Doom
  opens at once (the hit used Daggerfall's chance). The look label answers from the lock value in the request.
- Persistence: Doom's snapshot already saves `lockState`; add an "unlocked" bit beside the open bit in the location
  record's door fact (`DFDoorHandler.Distill`/`Restore`).

Removed: the locked-list protocol (`LIST_BEGIN`/`END`, `DOORS_REQUEST`, hash poll, `dfdoor_clear`, `DD_DoorsResync`),
`DOOR_ACTION`/`OnAction`, the stale-list "open" reply, the `locked` parameter and `DoorOpenedUnlocked`,
`DoomerfallLocks.Find` over hidden objects, `-dflocktestmagic`.
Kept: the Lockpick item and loot, the minigame, `Chance`/`ApplyAttempt`/`Label`, labels, the converter's LoadID and
lock export, the paired test setup.

Risks: Daggerfall's hidden lock copy goes stale; only the Lock and Open spells (`Lock.cs:116`, `Open.cs:120`, out of
scope) write it, and they will need one "set lock" message later. The Wayrest throne-room exception
(`DaggerfallAction.cs:268-283`) must be handled in Doom.

Data: 34 converted dungeons, 4,506 doors, 1,870 records. Door-triggered records on doors are only DoorText (99),
no-op chain starts (30) and text (11); no door-triggered 16/17/18 anywhere. Chain-reached door records do occur
(unlock 27, lock 17, open 71, close 13), so lever-driven lock changes must be local and cheap.

Rough size: `DoomerfallDoors.cs` 206 to about 60 lines, `dd_doors.cpp` 120 to about 50, about 80 lines of ZScript
changed, bridge header trimmed. About -350 / +200 lines.
