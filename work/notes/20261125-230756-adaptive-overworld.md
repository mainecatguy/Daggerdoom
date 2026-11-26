# Adaptive removed; overworld seeds with DRLA

Owner decision 2026-11-25 (`gamedesign/decisions.md`): remove DRLA's Adaptive difficulty ("The world shouldn't adapt to
the player"). Second task: the overworld seed bug reported in `work/notes/20261125-220115-fixeddrops-finish.md`.

## 1. Adaptive skill removed whenever the Doomerfall mod is loaded

MAPINFO can replace a skill by name (`ParseSkill` overwrites the entry with the same name, keeping its index and ACS
return) or clear all of them (`clearskills`), but cannot remove one. Re-declaring DRLA's other seven skills after a
`clearskills` would copy about 200 lines of DRLA data into our mod and break the mod without DRLA. So UZDoom got one
small generic MAPINFO keyword, and the Doomerfall mod uses it:

- `mods/doomerfall/src/MAPINFO.txt:17`: `removeskill adaptive`. DRLA is loaded before the mod, so its skills exist when
  the line is parsed. Without DRLA the name is unknown and nothing happens.
- `UZDoom/src/gamedata/g_mapinfo.cpp:2576` parses `removeskill <name>`; `UZDoom/src/gamedata/g_skill.cpp:47`
  `G_RemoveSkill` deletes the entry and fixes `DefaultSkill`.
- Adaptive is DRLA's last skill (index 7), so no other skill's index, key or ACS return changes: the bridge test's
  `-dfnewgameskill <index>` (menu index into the same list) and `-skill N` still pick the same skills.
- Fallback: `G_FallBackFromRemovedSkill` (`g_skill.cpp:63`): after a `removeskill`, a skill index past the end goes to
  the default skill (DRLA's is Hard, index 3). Called from `G_VerifySkill` (every new game, `-skill`, `+map`, the skill
  CVAR) and after a savegame's server CVARs are read (`g_game.cpp:2215`). Without a `removeskill` it does nothing, so
  stock behaviour (an out-of-range skill clamps to the last one) is unchanged.
- Skill menu: DRLA's `menudef.skillmenu` only sets the layout; the items come from the skill list, so Adaptive is gone.
- Launcher and play scripts: no Adaptive or skill-choice option exists (`launcher/`, `play_*.bat`, `scripts/`); they all
  pass `-skill 3`. Nothing to remove.
- `UZDoom/src/dd_monsters.cpp:140` `DD_IsDrlaSpawner` now matches only `RLTheHungrySpawner` (Armageddon's Lost Soul).
  `RLAdaptive*` classes are only reachable through the Adaptive skill's `ReplaceActor` lines (checked in ExtractedData:
  referenced only by `MonsterAdaptive.txt`, DRLA's mapinfo and its ACS), and the encounter pool already excludes them.
- Test tools: `tools/fixed_drops/rules.py` loses its `adaptive<N>` mode; `rules.zs` revisit holds an id-less
  `RLTheHungrySpawner` instead of an Adaptive spawner. Not re-run (see below).

## 2. Overworld seeds with DRLA: confirmed, fixed

Overworld packs spawn `ZombieMan,ShotgunGuy,DoomImp,Demon` (`DDWLDCFG`) with replacement on; under DRLA at skill 3 each
becomes a RandomSpawner, which got the seed id. It made its monster next tic and destroyed itself.

**Before (integration HEAD build)**, `tools/fixed_drops/overworld.py ... before`: every seeded monster died with seed 0
(`DDLOOT summoned` x140, 0 `DDMON spawner gave`), no loot dropped (only one kill counter), and leaving the area wrote 24
seed tombstones with no position (`DDLOC report ... 24 gone ... O0,0:24`) while all 24 id-less monsters and corpses were
stored as changed rows. On the second area every monster was stored too ("48 stored as changed, 0 unchanged").

**Fix** (`UZDoom/src/playsim/dd_treadmill.cpp`), reusing the dungeon spawner handoff (`DD_SpawnerHandoff`):
- line 1052: a seed whose spawned actor is not a monster (a RandomSpawner) or is a DRLA Monster-flagged spawner gets
  the id as `ddHandoffId`; the first monster it makes takes it as `ddRecordId` (one holder, one drop set).
- line 589: `Reconcile` counts an id still held as a handoff as live, so a seed is not tombstoned in the tic between the
  spawn and the spawner's PostBeginPlay. The spawner never becomes a record (`MakeRecord` skips non-monsters).

**After**, same test: 13 + 7 kills all with a seed, 0 summoned deaths; 72 `DDMON spawner gave` lines (24 home + 48
away seeds, one each); real seeded drops (first kill: 6 guns, second kill: 3 guns, all seeded, plus kill counters);
leaving: `34 stored as changed ... 0 gone` (7 monsters, 17 corpses, 10 items); the away area kept 20 untouched monsters
as unchanged (rebuilt from their seeds). Back home: the same 7 alive and 17 dead, no seed respawned (no new `gave`), no
duplicate.

## Results and commands

Play folder `D:\dev\DoomDaggerfall-loop\review\adaptive-overworld-play` (copy of `fixeddrops-finish-play`, this
UZDoom, `doomerfall.pk3` rebuilt by `scripts/doomerfall/build_pk3.py`). No Daggerfall Unity, bridge, launcher or
`ddruntime.pk3` change.

- Build: `cmake --build ../DoomDaggerfall-build/uzdoom --config Release --parallel 6` (VS 18's cmake), no errors.
- Startup (`-norun -nosound -stdout`): exit 1337 for stock DOOM.WAD, the DRLA set of `play_drlax.bat`, DRLA +
  Doomerfall, and stock + Doomerfall. Only DRLA's usual "Script error" lines (translation, menudef.monster,
  menudef.skillmenu), as on every build.
- Skill lists (a test-only event handler printing `AllSkills`, `-skill N +map E1M1`):
  - DRLA alone: `0=baby 1=easy 2=Normal 3=Hard 4=NIGHTMARE 5=technophobia 6=armageddon 7=adaptive`; `-skill 8` gives Adaptive (unchanged).
  - DRLA + Doomerfall: `0..6` the same, no adaptive. `-skill 8` gives skill 3 (Ultra-Violence, the default),
    `-skill 7` Armageddon, `-skill 3` skill 2 (Hurt me plenty).
  - Stock: `0=baby .. 4=NIGHTMARE`; `-skill 9` clamps to Nightmare as before.
- Overworld: `python scripts/overnight/quiet_run.py --timeout 260 -- python tools/fixed_drops/overworld.py <play> before|after`;
  results `D:\dev\DoomDaggerfall-loop\review\overworld-drops\` (`result-travelbefore.txt`, `log-travelbefore.txt`,
  `result-travelafter.txt`, `log-travelafter.txt`); `overworld.py <play> summary after` prints the summary.
  (A first try warped back into Daggerfall city and timed out: `review\overworld-drops-try1`.)
- **Paired fixed drops series `fresh save load`: `PAIRED FIXED DROPS PASS`**
  (`D:\dev\DoomDaggerfall-loop\review\adaptive-overworld-paired-series.txt`): 112 killed, 183 drops, the same gun
  (`RLDoubleShotgunPickup` seed 84321393, Steel, floor id `9f4f7d065b7d6e95`) in all three, identical to before.

## Not verified

- Loading a savegame made on Adaptive (index 7): the fallback call is there but no such save was made.
- `rules.py revisit` and `armageddon1` were not re-run after their edits (budget); the paired series covers the
  dungeon handoff path's unchanged behaviour.
- The 4 monsters dead at the overworld start (before the test's kill, in both runs) were not looked into; after the fix
  they die with a seed.

## Play-test list

1. With the Doomerfall launcher (DRLA), open New Game: the difficulty list ends at Armageddon; no Adaptive.
2. Plain DRLA (`play_drlax.bat`): Adaptive is still in the list.
3. Overworld with DRLA: kill a wilderness pack: its monsters drop guns and ammo. Walk far away and back: the dead stay
   dead with their loot, the living are still there, nothing doubles.
