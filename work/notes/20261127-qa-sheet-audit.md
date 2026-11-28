# Q&A sheet audit (2026-11-27)

What each open item on `work/notes/20261127-owner-qa.md` ties to. I checked `work/todo.md`, `work/refinement/`,
active and held cards in `work/queue/`, `work/backlog.md` and `work/backlog/`, the item's linked decision file, and
`CHANGELOG.md`, using grep only.
Closed and left out: 23, 41, 42, 72-76.

Classes: **BLOCKS** means an active card waits on the answer. **BACKLOG** means it belongs to a backlog item.
**MERGED** means a keep-or-change question about built work. **ORPHAN** means I found no card, backlog item or built feature.

| # | Topic | Class | Linked to |
|---|---|---|---|
| 1 | Gun skill stats and rates | MERGED | skillcore 01 |
| 2 | Guild lists hold gun skills | MERGED | skillcore 01/06; backlog skills-in-doom |
| 3 | Old language enchantments | BACKLOG | revisit-languages |
| 4 | Item maker "Enhances <gun skill>" | BACKLOG | revisit-languages |
| 5 | Reroute collision | MERGED | skillcore 06 (with 87) |
| 6 | Fall damage curve | MERGED | skillperks 01 |
| 7 | Mid-air jumps train Jumping | MERGED | skillperks 01 |
| 8 | Double jump after walking off an edge | MERGED | skillperks 01 |
| 9 | Automatics band numbers (not built) | ORPHAN | rest of done skillperks 02; no card |
| 10 | Dodge feedback | MERGED | attributes (Agility dodge) |
| 11 | Explosives direct-hit bonus | MERGED | skillperks 03 |
| 12 | Inpulsa blast radius | MERGED | skillperks 03 |
| 13 | Inpulsa gets Explosives bonus | MERGED | skillperks 03 |
| 14 | Shotgun slam damage | MERGED | skillperks 04 |
| 15 | Shotgun slowness measure | MERGED | skillperks 04 |
| 16 | Slowness knockback scale | MERGED | skillperks 04 |
| 17 | Shotguns 100 reload | MERGED | skillperks 04 |
| 18 | Projectile shotgun extra balls | MERGED | skillperks 04 |
| 19 | Four unclear DRLA guns | MERGED | skillcore 07 / weapontypes |
| 20 | Nanomachic generator | MERGED | skillcore 07 / weapontypes |
| 21 | Shredder Pistol | MERGED | skillcore 07 / weapontypes |
| 22 | Plain save gives a pistol | BACKLOG | convert-daggerfall-save (partly answered) |
| 24 | DRLA X gizmos in another form | ORPHAN | none (spawn stop settled in q07) |
| 25 | Auriel's Shield reward | BACKLOG | spellbreaker-ring / shield-support |
| 26 | Doom player body and voice | MERGED | noclass 01/02 |
| 27 | Dungeon brightness | MERGED | visualparity |
| 28 | Eye height and field of view | MERGED | visualparity |
| 29 | Outdoor flats in flat daylight | MERGED | visualparity |
| 30 | Outdoor monsters in flat daylight | MERGED | visualparity |
| 31 | Favourite "affordable" threshold | MERGED | encounters 08 |
| 32 | Dear favourite spike | MERGED | encounters 08 |
| 33 | Daggerfall creatures spawn in Doom | ORPHAN | townscorpse 01 shows them, but nothing spawns them |
| 34 | Health leans per dungeon | MERGED | dungeonpickups 01 |
| 35 | How common hard leans are | MERGED | dungeonpickups 01 |
| 36 | Ammo tier prices | MERGED | ammotiers |
| 37 | Weapon value cap | MERGED | weaponvalues |
| 38 | Weapon weight ignores material | BACKLOG | doom-item-weights |
| 39 | Keep refusing ship travel | MERGED | traveloptions 01 |
| 40 | How ship boarding should work | BACKLOG | ship-boarding |
| 43 | Slow first visit to a dungeon | ORPHAN | none |
| 44 | Leaning-wall stop, one slow step | BLOCKS | todo `dungeonedges` 01 ("accept?") |
| 45 | Daggerfall always sends rule numbers | ORPHAN | none (affects coming perk cards) |
| 46 | Exact shot-source hook | MERGED | shotsource 01 (notes 20261127-080929) |
| 47 | Lanes' own UZDoom build folder | ORPHAN | none (lane setup) |
| 48 | Loose PNG texture packs enough | BACKLOG | support-texture-packs-and-lighting-mods |
| 49 | Another weapon value check | MERGED | weaponvalues |
| 50 | Season swap hitch | BACKLOG | held todo `daynight` first-town season |
| 51 | Inventory-window gun drops become piles | ORPHAN | none |
| 52 | Doom poison skips death rules | ORPHAN | none |
| 53 | Travel from level-up sheet desyncs | ORPHAN | none |
| 54 | Agility dodges scripted kills | MERGED | attributes (Agility dodge) |
| 55 | Locks and pickups reset before record | BACKLOG | location-record / rebuild-load |
| 56 | New game drops queued record | BACKLOG | location-record |
| 57 | Untaken ammo bloats record | BACKLOG | location-record |
| 58 | Schism pickups not guns | BACKLOG | mod-compatibility-research |
| 59 | Outdoor water is solid | ORPHAN | none (Swimming is a placeholder in skills-in-doom) |
| 60 | Interiors have no lockable doors | BACKLOG | locked-doors-with-daggerfalls-requirements |
| 61 | Dragonslayer does no damage | ORPHAN | none |
| 62 | ZScript pattern crashes startup | ORPHAN | none |
| 63 | Shared build folders change under lanes | ORPHAN | none (lane setup) |
| 64 | Bridge version check always fails | ORPHAN | none |
| 65 | Perk lanes claim the same sheet slots | ORPHAN | none; matters when refinement skillperks-05 merges |
| 66 | New Game test driver stalls at popups | ORPHAN | none (test harness) |
| 67 | Hidden-desktop tests check blank frames | ORPHAN | none (test harness) |
| 68 | Parallel UZDoom builds fail | ORPHAN | none (lane setup) |
| 69 | Perk tests use real HP, silent exits | ORPHAN | none (test harness) |
| 70 | Greensmith Tower entrance | BACKLOG | audit-and-fix-dungeons |
| 71 | Jump height saved pre-scaled | MERGED | skillperks 01 |
| 77 | Luck drop ammo type | MERGED | killdrops 01 |
| 78 | Whose kills roll Luck drops | MERGED | killdrops 01 |
| 79 | Popup rows in upper case | MERGED | menufont 01 |
| 80 | Painted buttons stay pictures | MERGED | menufont 01 |
| 81 | Replacement font on Doom HUD | MERGED | menufont 01 |
| 82 | Pistol fire-rate gaps | BLOCKS | refinement `skillperks-05` |
| 83 | Multipliers on the 100 pool | BLOCKS | refinement `skillperks-05` |
| 84 | Shrapnel V, range, pool spend | BLOCKS | refinement `skillperks-05` |
| 85 | Energy splash per hit or per gun | MERGED | skillperks 06 |
| 86 | Burn flinch rate | MERGED | todo `skillperks` 07 (built on branch; card says "leave burn pain as built") |
| 87 | Custom class reroute map | MERGED | skillcore 06 |
| 88 | Sleeping NPCs stand | MERGED | built town NPCs (20261124-004803) |
| 89 | Off-window monsters (on hold) | BACKLOG | overworld-monsters-outside-the-loaded-window |

## Counts (81 open)

- BLOCKS: 4 (44, 82-84)
- BACKLOG: 15
- MERGED: 43 (nothing waits on these; they change built work only if the owner says so)
- ORPHAN: 19

## Orphans

- 9 Automatics bands: make a backlog item "Automatics fire-rate bands" under skills-in-doom.
- 24 DRLA X gizmos: drop and note "later" in `work/future-ideas.md` (option d).
- 33 Daggerfall creatures spawning: drop by answering (a). Or move it to future-ideas.
- 43 Dungeon first-visit wait: attach to backlog revisit-performance-of-generating-fresh-cities.
- 45 Rule numbers from Daggerfall: make a backlog item. Answer it before skillperks-05 and skillbasics add more perks.
- 47, 63, 68 Lane builds and folders: make one lane-setup backlog item, or take it as an orchestrator task. It is not game work.
- 51 Inventory-window gun drops: make a backlog bug item (risks losing Doom gun state).
- 52 Poison skips death rules: make a backlog bug item (breaks Daggerfall's ownership of deaths).
- 53 Level-up sheet travel desync: make a backlog bug item.
- 59 Outdoor water solid: attach to the Swimming placeholder in skills-in-doom, or make a backlog item.
- 61 Dragonslayer: make a small backlog fix (stop it dropping, or patch it).
- 62 ZScript crash pattern: drop. Record it as a known engine gotcha in agent notes.
- 64 Bridge version check: make a small backlog fix.
- 65 Sheet slot collisions: attach as a merge note to `work/refinement/skillperks-05.md`.
- 66, 67, 69 Test harness issues: make one test-harness backlog item.
