# Fixed drops finish: merge card 05, revived monsters, DRLA's Monster-flagged spawners

Owner rules: `gamedesign/decisions.md`, "2026-11-25: Which monsters drop loot when they were not placed by Daggerfall?".
Continues `work/notes/20261125-202715.md` (card 05, branch `agent/fixeddrops-20261125-202715`).

## 1. Merge of card 05

`git merge --no-ff refs/heads/agent/fixeddrops-20261125-202715`. Conflicts in `actor.h` and `dd_treadmill.cpp` were
both "keep both sides" (integration's squeeze radius and `DDTreadmill_Place` beside the branch's `ddNoDrops` and
`DDTreadmill_OnDaggerfallMap`).

Merge fix (found at merge, in the same commit): the branch's last fix treated any id with bit 63 (`DYNAMIC_BIT`) as
summoned. Daggerfall monster, NPC and townsperson ids are tags 5-7 in the top three bits, so they all have bit 63:
every placed monster would have dropped nothing. It also no longer compiled against integration's `dd_lootrng.cpp`
(which has `SESSION_ID`, not `DYNAMIC_BIT`). `DD_LootDied` now tests for a session id, tag 4 with bit 60, as
integration's floor item ids (`5082f596`) and the treadmill's `IsSessionId` do, and only for monsters. Floor items keep
their session-shaped ids; a placed monster never has one (placed ids are tags 5-7, seed ids, map item ids).

## 2. Revived monsters drop nothing

- `AActor::ddDied` (saved as `dddied`): set by `DD_LootDied` when a monster's seeded loot is rolled. `Revive` keeps it.
  On a later death, on a Daggerfall map in a bridge session, the monster goes the summoned way (marked, its loose drops
  removed). Outside that, behaviour is unchanged.
- The treadmill keeps the mark: a living monster with `ddDied` counts as touched (so it is stored, not rebuilt), and
  its row carries the death label `Revived`, which goes through the world table save and Daggerfall's location record
  as a name, so no format changed. `Restore` sets `ddDied` for such a row and for every corpse row, so a corpse an
  Arch-vile raises after a park/restore also drops nothing again.
- DRLA "Reborn" forms are new actors without an id: summoned already (card 05).

## 3. DRLA's Monster-flagged spawners

Finding: Doomerfall's encounter planner does not go through DRLA's skill `ReplaceActor` swaps. It spawns concrete
classes with `NO_REPLACE` (`SpawnMook(..., false)`, `dd_monsters.cpp` SpawnPass), and its pool excludes `RLAdaptive*`
and non-counted classes such as `RLTheHungrySpawner` (`doomerfall_encounters.txt`). Replacements apply only on the
stock-roster fallback (`replace` true, when the planner or the facts are missing) and on overworld seeds (which do not
use `SpawnMook`). Fixed anyway, as asked.

The fix, all in `UZDoom/src/dd_monsters.cpp` (block at lines 125-170, marked `[Doomerfall]`):
- `DD_IsDrlaSpawner` (line 141): an ISMONSTER actor that `IsKindOf("RLAdaptiveSpawner")` or `IsKindOf("RLTheHungrySpawner")`,
  in a bridge session. By class name only, so without DRLA it is always false and no DRLA class is needed.
- `SpawnMook` (line 297): such a spawner gets the id as `ddHandoffId` (new field, saved as `ddhandoffid`), never as
  `ddRecordId`, so it is never a mook.
- `DD_SpawnerHandoff` (line 147), called once from `ConstructActor` next to `DD_LootInherit` (`p_mobj.cpp`): if the
  actor whose state action, PostBeginPlay or death is running (`DD_ActingActor`, now tracked by `DDLootScope(AActor *)`
  in `dd_lootrng.h/.cpp`) holds a handoff, a non-monster child (RLTheHungrySingleSpawner, a RandomSpawner) carries it
  on; the first monster child takes it as its `ddRecordId` (another identified spawner, Adaptive's Armageddon Lost Soul
  being RLTheHungrySpawner, takes it as its handoff). When a later monster comes from a carrier and some actor already
  holds the id, every carrier lets go and that monster stays id-less (summoned, no drops). A monster that A_SpawnItemEx
  destroys at once (blocked) holds nothing afterwards, so the next one takes the id. One id, one drop set.
- The spawner never counts as a monster: `RunClaims` never claims one, `MakeRecord` skips it (`dd_treadmill.cpp`), and
  the encounter `present` set includes ids still held as handoffs, so a re-plan in those tics does not spawn a second.
- Not carried over: the Civil War side and stance (`RigFaction`) for a spawner's monster. Only the planner sets a side,
  and the planner never spawns these classes.

## Test tooling

- `tools/fixed_drops/rules.py` / `rules.zs` (new, test only; static event handler so it survives the dungeon exit).
  `revisit` (DRLA, skill 3, real New Game) and `adaptive<N>` / `armageddon<N>` (DRLA skill by menu index, with a sibling
  play folder whose `doomerfall.pk3` has the planner class renamed, so placements use the stock roster).
- `paired.py`: `EXTRA_UZ` list for extra UZDoom arguments.
- `dd_bridge_test.cpp`: test-only `-dfnewgameskill <index>` for `-dfnewgametest` (default 2 as before).

## Results

Play folder `D:\dev\DoomDaggerfall-loop\review\fixeddrops-finish-play`: integration's Daggerfall Unity build
(`CliBuild result: Succeeded`, 20:43, no C# changed since), the main checkout's bridge and launcher builds (no bridge
header change), this UZDoom (`D:\dev\DoomDaggerfall-build\uzdoom`), data copied from `review\locked-doors` with
`ddruntime.pk3` rebuilt by this checkout's converter (`--runtime-assets`) and its converter. Area level 10.

- Startup: `uzdoom.exe -iwad DOOM.WAD -norun -nosound -stdout` exits 1337, stock and with the DRLA set.
- **Paired series `fresh save load`: `PAIRED FIXED DROPS PASS`** (`review\fixeddrops-finish-paired-series.txt`,
  `review\fixeddrops-finish-paired\result-*.txt`): 112 killed, 183 drops, the same gun (`RLDoubleShotgunPickup` seed
  84321393, Steel, floor id `9f4f7d065b7d6e95`) in all three, identical to card 05's results. Summoned phase: 13/11/11
  deaths, 0 drops.
- **`rules.py revisit`: passed** (`review\fixeddrops-finish-rules\result-revisit.txt`, `log-revisit.txt`). Two placed
  monsters killed (3 seeded drops); a stock `Archvile` raised both (`RaiseActor`, which is `Revive`); the first, killed
  again, died with seed 0 and dropped nothing (`DDLOOT revived RLEliteCaptainTristarBlaster dies: no drops`). The second
  (raised, alive), a Pain Elemental's `RLLostSoulPE` (alive) and an id-less `RLAdaptiveFormerHuman` held in its first
  state were left; the player left through the exit (`DDTM left MAP01: 56 stored`) and came back through the door
  (`DDLOC D187853213: Doom's cache matches Daggerfall's record`). Back inside: the soul and the raised monster were
  where they were left, no Adaptive spawner was brought back (`adaptive 0 heldspot 0`); both killed: seed 0, 0 drops.
- **`rules.py adaptive1` and `adaptive2` (Adaptive skill, stock roster): passed.** 42 placements, 42 lines
  `DDMON spawner ... gave` in each run, 42 deaths with a seed (the other 3 deaths were a placed Pain Elemental's Lost
  Souls). 12 Adaptive spawners stay alive in their `BossWait` loop while their monster lives; they are skipped by the
  claims and the world table. **Not the same across the two runs:** a few placements were a different class (for
  example `RLArchvile` and `RLArmageddonDemon` in one, `RLArmageddonImp` in the other), so their drops differ. DRLA's
  ACS picker (`RLAdaptiveSpawnPicker`) chooses the variant with ACS `Random`, which no fixed seed covers. The ids and
  death seeds of the same placements are the same. This was so before this work too.
- **`rules.py armageddon1` (Armageddon skill, stock roster): passed.** 2 Lost Soul placements gave 2 handoffs (from an
  `RLTheHungrySingleSpawner` to its `RLArmageddonLostSoul`); 2 Armageddon Lost Souls died with a seed, the other 17 of
  their swarms with seed 0 (summoned, drops removed); all 42 placements died with a seed; 12 drops, guns all seeded.
- **E1M1 without Daggerfall** (`tools/fixed_drops/e1m1_drops.py <exe> finish`): stock 6 killed, 4 `Clip`; DRLA 6 killed,
  3 `RLPistolPickup` and 1 `RLBattleRiflePickup`; no `DDLOOT` lines. Same as card 05's check. DRLA's own menudef
  "Script error" appears as on every build.

## Not verified / known gaps

- The Adaptive variant choice is random per game (above). Fixing it would mean seeding DRLA's ACS picker from the
  handoff id; not done (outside the owner's "surgical" scope).
- Overworld seeds (`dd_treadmill.cpp`, about line 1044) give the id straight to whatever `Spawn` returns with
  `ALLOW_REPLACE`. With DRLA at skill 3 that is a RandomSpawner, so the real monster is id-less and (card 05) drops
  nothing; on Adaptive it is an Adaptive spawner. Not changed here; reported as an oversight.
- A Civil War side is not carried through a spawner (above).
- The paired harness fixes the summon spot at the New Game start; the spawner handoff was tested only through the
  stock roster fallback, since the planner never places these classes.

## Play-test list

1. DRLA New Game in Privateer's Hold: kill a monster, note its drops. Let an Arch-vile raise it (or find one that
   does), kill it again: nothing drops.
2. Leave a raised monster and a Pain Elemental's Lost Soul alive, leave the dungeon, come back, kill them: nothing drops.
3. Normal placed monsters still drop their usual items; plain DOOM.WAD with DRLA drops as stock.
