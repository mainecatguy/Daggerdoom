# Lightweight location record (replaces location ledger cards 2-3)

**Status:** started 2026-11-24 in its own session, by the owner's request. Card 1 of the location ledger branch is
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
- Doors, switches, lifts and Daggerfall action objects keep their state.
- Monsters spawned during play (lost souls, summons) are not kept when the player leaves. Doom's snapshot of the
  current map may keep them across a save and load in that map.
- Items the player drops must be kept (see open items).
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
6. Monster drops are rerolled from the seed on each rebuild (see `drla-fixed-drop-seed.md`). DoomerfallAmmo rolls its
   tier at spawn, so a placed item is never swapped into a tombstone plus a new row.
7. The converter cache gets a converter version stamp so old files rebuild.
8. Fix the town leak where every Doom pickup is stored as changed on each departure (card 3 notes).
9. Compact format: a small binary blob per place (base64 in JSON is fine).

## Open items

- Player drops: confirm every player drop goes through a Daggerfall loot pile (ammo dropped from the inventory window
  already does). If Doom has its own drop path, route it into a pile.
- Check DRLA monster drop lists for more than 15 slots.
- Doors: list which door, lift and action states exist on converted Daggerfall maps.

## Related

- `drla-fixed-drop-seed.md` (needed for rerolled drops).
- `rebuild-load.md`: with this record, rebuilding the current map on load becomes much simpler. It still needs the
  player's Doom gear restorable from Daggerfall (ammo is settled in `architecture.md`; gun mods and magazines are not).
- `overworld-monsters-outside-the-loaded-window.md` (on hold): with these rules, living off-window monsters could be
  rebuilt from their seed.
