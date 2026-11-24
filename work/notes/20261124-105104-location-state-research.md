# Does Daggerfall need to own permanent location state?

Research only. No code changed. Run 20261124-105104, branch `agent/locationstate-20261124-105104`.

## The answer

**Yes. Daggerfall should hold the permanent record. But moving the record alone does not fix the real problem, and
Doom should still work out the physical details.**

- **The real problem:** a Doom `.zds` save is tied to the exact mod list, mod order, and map bytes it was made with.
  Change any of these and the save will not load. That holds wherever the world table lives, because the current map's
  snapshot and the player's Doom inventory are also in the `.zds`. A bundled save with a broken Doom half is lost
  completely: Daggerfall restores its half first, and when Doom's half then fails, the load is abandoned
  (`dd_bridge.cpp:1741` `LoadBreak`). I reproduced three of these breaks with real loads (below).
- **What Daggerfall must own:** a small, versioned record of *facts* about each place. Facts are what died, what was
  taken, what was dropped and where, and what was unlocked. Each fact is keyed by ids made from Daggerfall's own data,
  and only changes from the seeded starting state are stored. Daggerfall already does exactly this for dungeon monster
  deaths (`DoomerfallMonsters.cs`), containers (`DoomerfallItems.cs`), and townspeople (`DoomerfallTownspeople.cs`).
  The design asks for the same thing everywhere.
- **What Doom keeps:** the physics and the presentation. It still decides where a corpse fell and how a pack
  is built from its seed. It reports facts to Daggerfall as they become final, and it rebuilds a place from
  Daggerfall's facts when the player enters.
- **The step that makes it pay off:** a *rebuild load*. When Doom's snapshot cannot load, because of a mod change, a
  changed map, or a missing snapshot, Doom starts the map fresh at Daggerfall's position and applies Daggerfall's
  facts. The `.zds` snapshot then becomes a fast, exact restore that is nice to have, not the only copy of the player's
  history. Without this step, moving the record to Daggerfall gains little, because the save still dies with its Doom half.

Recommended option: **C, "Daggerfall ledger of location facts, Doom builds from it"**, done in stages, with the
rebuild load as a later stage. Details are in sections 4 and 5.

## Class map

### Doom side (UZDoom)

| File / class | Role in location history |
|---|---|
| `UZDoom/src/playsim/dd_treadmill.cpp`: `Record`, `table`, `buckets` (lines 105-217) | **The world table.** One row per actor id: class, position in Daggerfall world units, angle, height, health, kind (monster, corpse, item, gone), item amount, and the corpse's final state as owner class plus state index. |
| `dd_treadmill.cpp` `Park` (572) | Turns a live monster or item into a row when it leaves the overworld window, or when the player leaves any map (`BeginHandoff`, 1325-1333). Untouched *seeded overworld* monsters are dropped. Everything else is stored, including untouched dungeon and town monsters and map-placed items. Projectiles are destroyed. |
| `dd_treadmill.cpp` `Restore` (633) | Spawns an actor from a row. A row whose class no longer exists is **silently skipped** (`if (!cls) return;`). A corpse is set to `owner->GetStates() + stateIdx`. |
| `dd_treadmill.cpp` `Reconcile` / `MarkGone` (501-543) | Anything with an id that disappeared, such as a picked-up item, becomes a `KGone` tombstone. Ids with bit 63 set are treated as dynamic and **erased** instead. |
| `dd_treadmill.cpp` `StartTown` (1633) | On entering a town, building, or dungeon: on a revisit, it destroys what the map places by default, then restores every row near the place. |
| `dd_treadmill.cpp` `PlaceSpace` / `SpaceOfMap` / `SpaceMapName` (939-1003) | Gives each interior or dungeon a private block of world-table coordinates, keyed by **space id**. An interior's id is `1000000 + group*1024 + building index`. A dungeon's id is `17000000 + DDDUNGN load order`. |
| `dd_treadmill.cpp` `EncodeState` / `DecodeState` / `DDTreadmill_Serialize` (1776-1885) | Writes the whole table as text into the `.zds` (`ddoverworld`). It also writes the return point and the visited-space names (`ddspaces`). |
| `UZDoom/src/playsim/dd_towncache.cpp` | Disk cache of converted locations (`T<group>.ddt`, magic `DDT3`). Its header says it is disposable and holds no progress. It has **no converter version check**, and it evicts the least recently used files above 2 GB (`TrimDisk`, 151). |
| `UZDoom/src/dd_monsters.cpp` | Gives each placed dungeon monster its Daggerfall id (`ddRecordId`) from the DDMONST lump, on the first visit only. Reports each death to Daggerfall once (`DD_MonsterDied`). Removes a live monster that Daggerfall lists as dead (`ApplyRows`). Places quest foes. |
| `UZDoom/src/dd_townsfolk.cpp`, `dd_npcs.cpp`, `dd_guards.cpp` | Same id pattern for townspeople, stationary NPCs (id in `args[0..1]`), and guards. Deaths go to Daggerfall through `DD_BridgeMonsterDied` (`dd_bridge.cpp:733`, hooked from `p_interaction.cpp:321`). |
| `UZDoom/src/dd_items.cpp` | Draws Daggerfall's loot piles and containers and forwards Use. It holds no history. Daggerfall's ledger does. |
| `UZDoom/src/dd_bridge.cpp` save code (1138-1780) | **The bundled save.** Doom freezes. Daggerfall writes its save and ledgers into a staging folder. Doom writes one `.zds` with both halves and a manifest, checks it, and replaces the old file atomically. On load, Daggerfall restores first, then Doom (`LoadRestoreDoom`). If Doom fails, both games are left unusable (`LoadBreak`). |
| `UZDoom/src/p_saveg.cpp:924-930`, `g_game.cpp:2139-2160`, `serializer.cpp:866-925` | Stock UZDoom load checks. The level's TEXTMAP MD5 and its line, side, and sector counts must match. Every saved class must exist. The ACS module list must match. SAVEVER must be within range. Any failure stops the load. |

### Daggerfall side (Daggerfall Unity)

| File / class | Role |
|---|---|
| `Assets/Scripts/Doomerfall/DoomerfallMonsters.cs` | **Death ledger** (`DoomerfallMonsters.json`, `fsObject v1`). Key: monster id = tag 5, placement hash (53 bits) from map, block, and marker, and an 8-bit pack member. Stores map id, position, and the rolled drop. Updates quest foes, rolls loot with a fixed seed, shows drop piles, and publishes the dead list for the current dungeon to Doom. **Dungeons only.** |
| `DoomerfallItems.cs` | **Container ledger** (`DoomerfallItems.json`): what is left in each opened pile or container, plus restock dates. |
| `DoomerfallTownspeople.cs` | **Townspeople ledger** (`DoomerfallTownspeople.json`): who has died. |
| `DoomerfallSave.cs` | Daggerfall's half of the bundled save. Calls `SaveLoadManager.SaveToFolder` and writes the three ledgers into the staging folder. On load it reads the ledgers, then `LoadFromFolder`. |
| `Game/Serialization/SaveLoadManager.cs`, `SerializableStateManager.cs` | Daggerfall Unity's own save. It is versioned (`SaveData_v1`) and keeps a scene cache keyed by stable `LoadID`s from block data. Daggerfall's 3D world is inert in Doomerfall, so this cache does not see anything Doom does. It is the model to copy: stable ids from game data, and versioned records. |

### How one kill travels today (a placed dungeon monster)

1. Doom: `AActor::Die` → `DD_BridgeMonsterDied` → `DD_MonsterDied` sends `DFB_KIND_MONSTER_DEATH` with the id and position.
2. Daggerfall: `DoomerfallMonsters.OnDeath` writes `ledger.deaths[id]`, updates the quest foe, and later rolls and shows the drop.
3. Doom: the corpse stays a live actor. When the player leaves, `BeginHandoff` → `Park` stores a `KCorpse` row with
   the final state's owner class and index.
4. Save: Doom freezes. Daggerfall writes its save plus `DoomerfallMonsters.json`. Doom writes the `.zds`, which holds
   the current map's full snapshot and the world table as text, and Daggerfall's staged files go into the same zip.
5. Load: Daggerfall reads its ledgers and save, then Doom loads its snapshot (`G_DDLoadNow`). The table comes back
   through `DecodeState`. On entering the dungeon, Daggerfall publishes its dead list, and Doom destroys any live
   monster that Daggerfall says is dead.

A kill of anything *without* a Daggerfall id, such as a seeded overworld pack, a dynamic spawn, or a pack member other
than the claimed one, reaches only Doom's table. Daggerfall never hears about it.

## 1. What the design requires

From `gamedesign.md` ("Total Persistence", "In-engine object permanence", "Fixed seeds"), `designgoals.md` ("state
persistence of everything the player does"), AGENTS.md (Daggerfall is "mediator and controller of most permanent game
state"), and `architecture.md` row "Monsters": "DFU sends each area's facts: … dead mook IDs. It owns deaths". In
practice:

1. **Nothing the player did is ever lost.** That includes a save made before an update.
2. **One authority per fact.** Daggerfall decides what a fact means: quest kills, loot, crime. Doom decides physical
   outcomes, such as where a body fell.
3. **Store changes from the seed, not snapshots.** The place itself comes from fixed seeds. Only the player's
   changes are history (owner's decision on the held card).
4. **Stable keys.** A fact must still point at the same thing after the converter, the mods, or UZDoom change.

### Each reason, checked against the code

| Reason given for moving the history | Verdict | Evidence |
|---|---|---|
| UZDoom `.zds` saves break when mods change | **Proved** | Test T1: an old DRLA save loaded without DRLA Monsters gives `Unknown object class 'RLImp' in savegame … Failed to load savegame`. Test T3: the same mods in a different order give `Level was saved with a different set or order of ACS modules`. |
| `.zds` saves break when the converter changes a map | **Proved for TEXTMAP changes; the frequency is mixed** | Test T2: one thing's angle changed in E1M1 gives `Savegame is from a different level`. The check hashes TEXTMAP only (`p_openmap.cpp:406-421`). Five converter builds from the last 19 hours gave the *same* TEXTMAP for town group 7154, and one added an empty DDMONST lump, which is not hashed. But interiors and dungeons changed today (`git log`: "converter places 1-2 seeded health or cheap ammo markers per room"), and the converter has changed about 50 times since 2026-11-22. The cache has no version stamp, so the break comes later, when the cache file is evicted (2 GB least-recently-used cap) or cleared and rebuilt by a newer converter. |
| `.zds` saves break when UZDoom changes | **Not today** | Test T0: a 2026-11-23 save from another lane's build loads with today's build (`STOCKLOADED`). Only a SAVEVER bump (`version.h:68-72`) or a change to a saved class would break it. Doomerfall has done neither. |
| Daggerfall needs the history for its own rules | **Partly** | Quests and loot need *deaths* (they already reach Daggerfall for dungeon placements and quest foes). Crime needs townsperson deaths (Daggerfall has them). Containers are already Daggerfall's. No Daggerfall rule reads corpse poses, Doom pickups, or the positions of Doom-dropped items. Quest foes in towns, buildings, or the overworld, and kills of encounter-pack members, are not covered yet (only `WORLD_DUNGEON` is handled in `DoomerfallMonsters.Update`). |
| The bundled save already keeps both games consistent | **True at save time** | One zip, verified, replaced atomically (`dd_bridge.cpp:1141`). On load, `ApplyRows` removes any live monster that Daggerfall says is dead. But consistency is not durability: if either half fails, the whole save is lost. |

## 2. What goes wrong if nothing changes

| # | Failure | Evidence | Likelihood |
|---|---|---|---|
| F1 | **Every save is lost after a mod list or mod order change**, such as a DRLA update, adding a mod, or a Doomerfall PK3 that renames or removes a class. Daggerfall's half is fine but unusable, because the load is all or nothing. | T1, T3. `LoadBreak` at `dd_bridge.cpp:1662`. | High during development. Medium after release, because any patch to `doomerfall.pk3` that removes a class can do it. |
| F2 | **A save made in a place whose map changed will not load** once that place's cache file is rebuilt by a newer converter. | T2. `TrimDisk` evicts files. No converter version in `DDT3`. | Medium for interiors and dungeons, where the output changes often. Low for towns, where TEXTMAP was stable across five builds. |
| F3 | **Silent loss or corruption of history after a mod update**, even when the load succeeds. A row whose class is gone is skipped with no log. A corpse's `stateIdx` points at a different frame if the mod's state list changed. The bounds check only prevents a crash. | `dd_treadmill.cpp:635-648`. | Medium for any DRLA update. |
| F4 | **History attached to the wrong building or dungeon.** Interior space ids come from the converter's group order and RMB subrecord order. Dungeon ids come from DDDUNGN load order. If either changes, the rows and the visited-space names (`DDS…`, `MAP01`) point elsewhere. Daggerfall identifies buildings by map id and building key, which does not change. | `SiteExport.cs:3-4`, `dd_treadmill.cpp:942,969`. | Low to medium. The grouping changed on 2026-11-22 ("handle wide location groups"), and runtime dungeons will change the dungeon numbering. |
| F5 | **History Daggerfall never sees**: overworld kills, kills of pack members without an id, Doom pickups taken, Doom-dropped items. No Daggerfall rule can use them, and they die with the `.zds` (F1, F2). | `DD_MonsterDied` only reports `IsMonsterId` ids. `Park` gives everything else dynamic ids. | Certain, by construction. It matters when quests, crime, or the encounter planner need these facts. |
| F6 | **The table grows with every place visited**, because `Park` stores every non-seeded monster and item, including untouched ones. Slaughter-sized packs times hundreds of dungeons, at about 120 bytes of text per row, adds up to tens or hundreds of MB per save. `StartTown` also scans the whole table on every entry. | `dd_treadmill.cpp:582,1659`. | Grows with play. It will matter once the encounter planner spawns large packs. Estimate only, not measured. |
| F7 | Latent: Daggerfall's tags 4-7 occupy bits 61-63, so every Daggerfall-identified actor has the table's `DYNAMIC_BIT` (bit 63). `MarkGone` erases its row instead of writing a tombstone. Today Daggerfall's dead list covers this for placed monsters. If a later system rebuilds tagged actors from seeds on every entry, a vanished one could come back. | `doomerfall_bridge.h:198-207`, `dd_treadmill.cpp:101,504`. | Low today. Not reproduced. |

## 3. The options

### A. Keep it in Doom, fix the keys

Change space ids to Daggerfall's map id plus building key, store only changes from the seed, log missing classes, and
store "dead" instead of a state index.
- **Cost:** small, all in `dd_treadmill.cpp` and the converter's naming.
- **Fixes:** F3, F4, F6.
- **Leaves:** F1, F2, and F5. History still dies with the `.zds`, and Daggerfall still cannot read it. It goes against
  the "Daggerfall mediates permanent state" pillar.

### B. Keep it in Doom, and also write a stable copy into the bundle

Doom writes a versioned `doomerfall/locations.json` next to the `.zds` and adds a rebuild path that reads it.
- **Cost:** medium. The schema, writer, reader, and rebuild path all live in vendored engine code.
- **Fixes:** F1 to F4 and F6, once the rebuild exists.
- **Leaves:** F5. Daggerfall still cannot use the facts. It also duplicates Daggerfall's death ledger, and puts a
  persistence system inside UZDoom, against "keep vendored engine changes small".

### C. Daggerfall holds the facts, and Doom builds from them (recommended)

Generalise the existing ledgers into one Daggerfall **location ledger**. Doom reports facts and Daggerfall stores them.
On entry, Daggerfall sends the facts for the place and Doom applies them. Doom's world table becomes a cache for the
session only.
- **Cost:** medium. Most of the pattern already exists: the death report, the per-place list with generations
  (`DFB_KIND_MONSTERS_BEGIN/…/END`), the ledger files in the bundle, and `ApplyRows`. New work: an event for each fact
  kind (or one bulk transfer per place on exit), a Daggerfall ledger class, and Doom's apply-on-entry code in place of
  `Restore` from its own table.
- **Fixes:** F3 to F6 directly. F1 and F2 too, once the rebuild load (stage 4) exists.
- **Risk:** the bridge traffic on exit and save. A dungeon of 1,000 corpses at about 48 bytes each is about 48 KB.
  That is fine through the existing bulk slot (`dfb_bulk_write`) and needs measuring. Ordering against the save
  request is already guaranteed by the ordered ring. Positions are still Doom's physics, reported as final values.

## 4. Recommendation

**Do C in stages.** Reasons:

1. It matches the owner's design. Daggerfall owns deaths and the permanent record (`architecture.md` row 89, AGENTS.md
   pillar). Doom owns physics and composition. Store changes from the seed only (held card).
2. It reuses what works. The death ledger, the container ledger, and the per-place list protocol are proven in tests.
   A new system would duplicate them.
3. It is the only option where a fact survives a Doom-side change. A fact is keyed by Daggerfall's own data and
   stored in Daggerfall's versioned save, not in Doom's class and state tables.
4. It keeps vendored engine changes small. The schema and the store live in Daggerfall's C#. Doom gets narrow
   "report" and "apply" hooks in Doomerfall files (`dd_*.cpp`), not in stock UZDoom files.

### What the ledger holds (all keyed by Daggerfall-derived ids)

- **Place key:** dungeon map id, building (map id plus building key), or overworld chunk. Never Doom's space id or map name.
- **Actor key:** the existing monster ids (placement hash plus member), quest foe hash, townsperson and NPC ids, and
  seeded overworld ids (chunk plus index, once the encounter planner gives them a Daggerfall-side seed).
- **Facts:**
  - dead, with the corpse position in Daggerfall units and no state index (Doom puts the class into its final
    death frame on restore);
  - moved and alive but hurt (only if the owner wants it kept; see the questions);
  - taken (Doom pickups by placement id);
  - dropped (a Doom item class or Daggerfall item at a position);
  - unlocked or opened (doors, once locks exist).

### Classes it would touch

- **Daggerfall:** a new `DoomerfallLocations.cs`. It holds the ledger and is written by `DoomerfallSave` like the
  others. Over time it absorbs or wraps the death part of `DoomerfallMonsters.cs`. The same file can grow to cover
  towns and the overworld.
- **Bridge:** `bridge/doomerfall_bridge.h` gets fact kinds plus a per-place fact list, reusing the
  `dfb_world_items` generation header.
- **Doom:** `dd_treadmill.cpp`:
  - `Park` and `Reconcile` report facts instead of being the store;
  - `StartTown` applies Daggerfall's list in place of the table scan;
  - `DDTreadmill_Serialize` stops being the authority (it may keep a cache for an exact resume).

  `dd_monsters.cpp` generalises `ApplyRows`.
- **Converter:** emit Daggerfall building keys (map id plus building key) alongside space ids, so Doom can name places
  in Daggerfall's terms.
- **Later, the rebuild load:** `dd_bridge.cpp` `LoadRestoreDoom` gets a fallback. If `G_DDLoadNow` fails, or the
  bundle says the snapshot does not match the current mods or map, Doom starts the map from Daggerfall's position and
  applies the ledger. This **depends on the player's Doom inventory being restorable from Daggerfall**, meaning guns,
  ammo, and armor. That is outside this goal and not yet true: ammo counts are live in Doom (open question
  20261124-075147).

### Rough task breakdown

1. **Stable place keys.** The converter emits Daggerfall building keys. Doom's table keys interiors and dungeons by
   them. This fixes F4 on its own.
2. **Changes only, and robust restores.** Don't park untouched monsters that a seed or Daggerfall placement rebuilds.
   Corpses store "dead", not a state index. Log skipped classes. This fixes F3 and F6.
3. **The location ledger in Daggerfall.** Add a fact report on exit and on save, and the per-place fact list on entry,
   for dungeons first, then interiors, towns, and the overworld. Doom's table becomes a cache. This fixes F5 and makes
   Daggerfall the authority.
4. **The rebuild load.** Depends on 3 and on the player inventory being restorable from Daggerfall. This fixes F1 and F2.
5. **Tests.** A paired save in a dungeon and in a town with kills, takes, and drops. Then: (a) a normal load;
   (b) a load after clearing the town cache with a changed converter; (c) a load with one mod removed. Expected
   results are (a) exact, (b) and (c) rebuilt with all facts present. Use the harness from this run (below) for the
   stock failure checks.

Stages 1 and 2 are small and help whichever option is chosen. Stage 3 is the real change. Stage 4 is what makes the
saves durable.

## 5. Proved versus assumed

**Proved here (commands and logs below):**
- A mod removed from the list fails the load (T1).
- A mod order change fails the load (T3).
- One changed thing in the current map's TEXTMAP fails the load (T2).
- An older build's save loads with today's build when nothing else changed (T0).
- The converter is byte-for-byte deterministic within one build (group 7154 converted twice, with every lump identical).
- Town TEXTMAP was identical across five converter builds from 2026-11-23 16:07 to 2026-11-24 10:57.

**From reading the code, not run:**
- `LoadBreak` leaves both games unusable when Doom's half fails.
- The cache has no version check and evicts files above 2 GB.
- Space ids depend on group order, RMB order, and DDDUNGN order.
- `Restore` silently skips missing classes.
- The corpse `stateIdx` is fragile.
- The DYNAMIC_BIT overlap (F7).
- Only dungeon placements and quest foes report deaths to Daggerfall.

**Assumed or estimated:**
- Table growth (F6) is an estimate from the row size, not measured.
- The bridge cost of fact lists (about 48 KB per 1,000 facts) is not measured.
- How often interior and dungeon TEXTMAP changes in a release build is unknown.
- That the rebuild load is practical depends on the player inventory work.

## How the tests were run

All under the scratchpad (`C:\Users\Patrick\AppData\Local\Temp\claude\53516abec93c28ab\836cf885-cb5f-4eae-9aa7-6154cac0c80f\scratchpad\`),
with a private config and save folder, launched minimized through `quiet_run.py --timeout 30`, and `+wait 175;quit`.

- **The save:** `review\synchronized-loading\test\stock-drla\saves\save00.zds`, made 2026-11-23 by that lane's build
  on E1M1 with DOOM.WAD, DRLA Arsenal 1.1.5, DRLA Monsters 7.3, DRLAX 1.2b, and that test's `control.pk3`.
- **The engine:** `D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe` (today's shared build).
- **The script:** `tools\run_save_tests.py` (scratchpad).

| Test | Change | Result (log line) |
|---|---|---|
| T0 | none | loaded; the control harness printed `STOCKLOADED` |
| T1 | DRLA Monsters left out | `Unknown object class 'RLImp' in savegame` … `Failed to restore all objects in savegame` / `Failed to load savegame` |
| T2 | plus a PWAD of E1M1 with thing 0 turned 90° (`tools\make_e1m1_variant.py`) | `Savegame is from a different level` |
| T3 | Arsenal and Monsters swapped in the load order | `Level was saved with a different set or order of ACS modules. (Have DRLAMONS, save has DRLALIB)` |

- **Converter checks:** `tools\convert_twice.py` and `tools\textmap_versions.py` ran
  `dotnet DungeonConverter.dll --group 7154 …` with builds from `converter-encounters`, `demo-combined`,
  `npc-converter`, `door-routes/conv_base`, and `trapdoors/conv`.
  - All TEXTMAPs matched: `e59cae8245d9391885cfbf4ee20a0535`, 20,890,576 bytes.
  - The only MAPWAD difference was an extra empty `DDMONST` lump in the newer build.

A paired bridged save and load with a changed converter was not run. It needs the launcher, two fresh builds, and a
cache rebuild. Stage 5 above covers it.
