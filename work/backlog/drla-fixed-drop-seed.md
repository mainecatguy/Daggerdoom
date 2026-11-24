# DRLA drops from a fixed Daggerfall seed

**Waiting on:** the lightweight location record (replacement for location ledger cards 2-3), which rebuilds monster
drops from a seed instead of storing them. Not started. Owner asked for this item on 2026-11-24.

## Why

The planned location record does not store monster drops. On a revisit, each dead mook's drop slots are rolled again
from a seed made from the mook's Daggerfall ID, which includes the place's map ID. Taken drops are 1 bit per slot.
This only works if a drop rolls the same way every time it is rebuilt.

DRLA's drop spawners may read facts that change during a game, such as the player's class, what the player already
owns, or Doom's RNG. If they do, a revisit could show a different item than the one that dropped. A taken bit could
then hide an item the player never saw, or an item could change into something else.

## What to do

1. Check DRLA's monster drop lists and random spawners (`GameMods/ExtractedData/`, DRLA Monsters and DRLA Arsenal) for
   inputs other than the drop roll: player class, owned items, difficulty, global counters, and RNG calls.
2. Have Daggerfall give Doom a fixed seed for each drop (per area, derived from the place's map ID and the mook and slot
   ID). When DRLA is detected, its spawners use that seed instead of Doom's RNG. Without DRLA, stock drops use the same
   seed.
3. If a spawner depends on player state, either add that state to the seed or fix the result at first death and
   store it. Fixing it costs bytes per drop, so prefer the seed.
4. Also roll DoomerfallAmmo's tier at spawn from the same seed, so a drop is never replaced a few tics later (today that
   writes a tombstone plus a new row for each replaced item).
5. Test: kill the same mook in two separate game sessions, and leave and re-enter, and confirm identical drops each time.

## Related

- Location state research: `work/notes/20261124-105104-location-state-research.md`.
- Location ledger cards: branch `agent/locationledger-20261124-141035`, notes `work/notes/20261124-133643.md` (drops
  were half of a level-30 dungeon's facts).
- Fixed loot seeds already cover Doom drops in Daggerfall's loot rolls. Check how far that reaches before building
  anything new.
