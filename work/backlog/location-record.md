# Lightweight location record (replaces location ledger cards 2-3)

**Status (2026-11-24, branch `worktree-agent-aaac61bc76d3610ff`, notes `work/notes/20261124-190017.md`):** cards 1-4
and 6 built and proven in paired runs; card 5 (doors only, owner 2026-11-25) built 2026-11-25 (dungeon doors; city gates not
covered, see the notes' "Card 5"). Remaining: the open items below.

Started 2026-11-24 in its own session, by the owner's request. Card 1 of the location ledger branch is
merged into integration (`69a48fd`); cards 2-3 (`agent/locationledger-20261124-141035`) are replaced by this design.
Designed with the owner on 2026-11-24. The high-level rules are in `architecture.md`, "State ownership: live and
permanent".

## Why

The location ledger branch (`agent/locationledger-20261124-141035`, notes `work/notes/20261124-130536.md`, `-133643`,
`-141035`) stores each place as full rows (class, position, angle, health, state) in two copies: Doom's world table in
the `.zds` and Daggerfall's `DoomerfallLocations.json`, plus the death ledger. One cleared level-30 dungeon measured
about 930 KB raw in those three stores; 50 such dungeons would be about 23-140 MB raw. It also needs compare and
rebuild logic, paced transfers and 5 s waits.

This design rebuilds every place from the seed and stores only what differs from it, in one copy, owned by Daggerfall.
Target: a cleared high-level dungeon about 16-20 KB, an untouched one about a dozen bytes, 50 dungeons under 1 MB.

## Scope

Daggerfall maps only. Doom maps (later, through Oblivion gates) use normal Doom saves.

## Who owns what (owner, 2026-11-24)

Doom is the authority on moment-to-moment combat state; Daggerfall is the authority on permanent world state and on
every place the player is not in. (Same pattern as ammo: Doom owns the live loaded count, Daggerfall the rest.)

- **The current map:** Doom's `.zds` snapshot is the authority. A save and load restores it exactly: monsters where
  they stood, projectiles in flight, summoned monsters, everything. The record is never applied on top of it.
- **Every other place:** Daggerfall's record. When the player leaves a map, Doom distills it into record entries.
- **At save time** Doom also sends the current place's record entries (small), so if the snapshot cannot be restored
  (mod or map change), the place can still be rebuilt from the record, losing only live combat details.
- **Daggerfall objects on the current map** (loot piles, containers, NPCs, townspeople) stay Daggerfall's even there.
  Doom only draws their markers (picture, position, count; `dd_items.cpp` 710-737) and forwards Use. On load they
  must follow Daggerfall's list, not the snapshot. Not yet checked: whether a pile emptied before a save can come back
  from the snapshot.
- **The snapshot skips what Doom generates from Daggerfall's data.** On the overworld 88% of a save is the
  treadmill's terrain sectors (`ddover01.map.json`: 4.77 MB of 5.45 MB raw, 1.33 MB packed, measured in
  `review/locledger2/run/saves/resume.zds`). Those are regenerated on load like they are while walking. Needs a small
  hook in UZDoom's save code.

## Rules (owner, 2026-11-24)

- A mook with no entry is alive, unhurt, asleep, on its spawn spot.
- Tracked mooks: dead, wounded, and awake (alerted). No despawn of corpses.
- Corpses stay where they fell, at low resolution.
- Quest enemies never change the seeded army (`gamedesign.md`, encounters). Quest foes are added on top with their own
  IDs.
- Map things used up (pickups taken, barrels exploded, keys used) are kept.
- Hinged doors keep their position (owner, 2026-11-25). Lifts, platforms, switches, lever chains, riddles and traps
  (`DFAction`) reset on each visit: a wrong saved state there could softlock a dungeon permanently. Keeping them
  waits on QA (see `work/future-ideas.md`).
- Monsters spawned during play (lost souls, summons) are not kept when the player leaves. Doom's snapshot of the
  current map may keep them across a save and load in that map.
- Items the player drops must be kept, as Doom items, never piles (owner decisions below).
- Guards and hostile NPCs use the same scheme with their Daggerfall IDs.

## Record per place

```
place header: format version, plan version, area level at first visit (if area level can change), last-visit day
mooks:        sorted u64 entries, one per mook that differs from its seed
pickups:      bitset, map things used up, indexed in an order taken from Daggerfall's data
doors:        bitset or 2 bits each, doors, switches, lifts, actions
exceptions:   short list (partial amounts, anything not covered above)
```

Mook entry (u64):

```
mook index 14 | dead 1 | x 13 | y 13 | height band 6 | then
  dead:  death look 2 | drop slots taken 15
  alive: damage 6 | awake 1 | facing 3 | 7 spare
```

- x, y are cells in the place's bounding box. Height band picks the floor; the body settles onto it.
- Class, sprite, max health, death frame, drops and spawn spots are never stored. They come from the map, the seed and
  the plan.
- Seeds: `hash(world seed, purpose, map ID, block, marker, member, drop slot)`. Map ID, not location name. Loot and
  encounter purposes stay separate.

## Engineering rules

1. One copy. Daggerfall's record is the only saved state for places. Doom's world table and `ddplans` are not saved;
   the death ledger's position and rolled drop merge into the record.
2. One entry path. First visit, revisit and load all run: converted map from the disk cache, plan from the seed, apply
   the record. No cache comparison.
3. The planner is a pure function of place, seed, area level and plan version.
4. Deaths and pickups are reported as they happen (they already are). Living mooks' entries (wounded, awake) are sent
   on leaving a place and before each save; at worst about 17 KB, one bulk transfer.
5. The place record is built from live actors at departure, so a mook an Arch-vile raised shows as alive.
6. Monster drops are stored, not rerolled (owner, 2026-11-24): they go in the place's loose item list with player
   drops. A placed ammo pickup keeps its map pickup index through the tier swap, so it is never a tombstone plus a row.
7. The converter cache gets a converter version stamp so old files rebuild.
8. Fix the town leak where every Doom pickup is stored as changed on each departure (card 3 notes).
9. Compact format: a small binary blob per place (base64 in JSON is fine).

## Owner decisions (2026-11-24, after the step 1 review)

- **Placer on the bare map.** While placing, players, monsters, `DFDoorBlocker` and `DFActionCell` are non-solid;
  static decorations stay solid; mooks stay off the start and end spots of every `DFAction` mover. Plan version bumped.
- **Quest foes are a separate planner request** after the seeded army. Armies of dungeons in old saves may change.
- **No Daggerfall piles for Doom items.** Loose Doom items (player drops, monster drops, moved items) are one stored list
  per place in Daggerfall: a u64 per entry (class index into the place's name table, x, y, height band, amount), plus
  an optional `GunState`-format string for carried inventory (DRLA gun mods). Restore gives that inventory to the
  pickup (safe: DRLA `GetWeaponMods` terminates when the pickup has no master). Monster drops are stored, not seeded,
  so `drla-fixed-drop-seed` is not needed for this record.
- **`dfi_clear` from `DD_ItemsResync`** (ghost pile fix).
- **Map pickups:** a used-up bitset in converter order. The tiered ammo pickup inherits its marker's index; jackpot
  members get their own bits or go in the loose list. Area level at first visit goes in the place header.
- **Hinged doors keep their position** (owner, 2026-11-25: doors only), 1 bit each (closed or open) in `DFDOORS` order,
  applied after the plan, mid-move snapped to the destination, sight blockers and collision restored. A converter
  version stamp in the place record drops the door bits after a re-convert. `DFAction` objects reset.
- **Switching Doom mods ends a save.** A mod-set stamp check on load is a follow-up, not part of this work.

## Decisions added while building (2026-11-24)

- **Dropped Daggerfall piles** (coordinator): each place's record keeps its dropped piles in their own section (id,
  position in the place frame, texture archive and record, `ItemData_v1` list), updated when a pile changes and on
  save. On entry, or for an exterior chunk within one chunk of the player, a missing pile is recreated with
  Daggerfall's dropped-loot creation unless one with that id exists. Exterior piles use the `O<chunk>` key.
- **Doom items dropped from Daggerfall's inventory** (owner): each becomes its own Doom pickup in the loose list; its
  stored gun state becomes the pickup's carried inventory and picks the plain or `PickupModded` class. Daggerfall
  removes the item only when Doom confirms the spawn.
- **Corpse look from the class** (owner bug, DRLA): a dead mook is always kept as a corpse; its look comes from its
  class and death label, following DRLA's by-name jumps to the class's frames, because DRLA corpses loop and never rest.
- **Followers in the death ledger:** a follower whose death the record keeps is left out of
  `DoomerfallMonsters.json` and restored from the record on read. Leaders stay, with their rolled drops.

## Results (paired runs, details in the notes)

- Cleared level-30 Privateer's Hold: dungeon blob 24 KB (1,162-1,165 corpses, 781 loose items); `DoomerfallLocations.json`
  33 KB raw / 20 KB packed (was 134 / 37 KB); `DoomerfallMonsters.json` 185 KB raw / 11 KB packed (was 282 / 24 KB),
  mostly leaders' drop `ItemData`. The `.zds` keeps 12-20 bytes of treadmill state.
- Leave, return, and save and load in a new launch keep counts (95 alive, 1,165 dead, 781 items); exterior chunks, a
  house and the wilderness match after a load.
- DRLA set: corpses from fire, plain, barrel and gib kills keep count and look through leave, return and load.

## Open items

- Card 5 left city gates (`DFGATES` in town maps, exterior chunk records) resetting; they need their own stamp and a
  chunk key, and Daggerfall's gates may follow their own open hours.
- Leaders' drop `ItemData` is most of the death ledger's size; moving it into the loose list needs an owner call.
- FireMelt's stretched scale is not kept; a burned DRLA corpse comes back at its normal scale.
- Check DRLA monster drop lists for more than 15 slots (only matters if drops are ever seeded again).

## Related

- `drla-fixed-drop-seed.md` (no longer needed for this record: drops are stored).
- `rebuild-load.md`: with this record, rebuilding the current map on load becomes much simpler. It still needs the
  player's Doom gear restorable from Daggerfall (ammo is settled in `architecture.md`; gun mods and magazines are not).
- `overworld-monsters-outside-the-loaded-window.md` (on hold): with these rules, living off-window monsters could be
  rebuilt from their seed.
