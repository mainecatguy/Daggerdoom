# Main quest dungeons get levels from the main quest order (20261124-202353)

Goal: Privateer's Hold rolls its army and loot at area level 1 with a humanoid theme in a paired New Game, and a
proposed level (and theme where obvious) for every other main quest dungeon, in main quest order, for the owner.

## Plan

1. Check what Privateer's Hold gets today. Done: it was already fixed at area level 1 (`DoomerfallAreaLevels.Overrides`,
   same in `tools/area_level/area_level.py` OVERRIDES), and its Daggerfall dungeon type is already HumanStronghold.
   But a dungeon type is only a leaning (design section 4.1): about 70% of genes follow it and the army can contain
   anything. Its plan (genes 703) also rolls Civil War.
2. Make "humanoid theme" hold: a story theme that admits only humanoid monsters.
3. Daggerfall keeps the main quest table (level, story theme) and sends the story theme to Doom.
4. Planner test, then a paired New Game run into Privateer's Hold.
5. Research the main quest order and propose the table.

## What was built

- `doomerfall_encounters.txt`: new theme key `only=1` and a story theme row
  `theme Humanoid kinds=ZombieMan,ShotgunGuy,ChaingunGuy placement=chokepoints awareness=sentries only=1`.
  The nudges are the same as HumanStronghold's, so the dungeon keeps playing the way it did; only the kinds become a rule.
- `EncounterPlanner.zs`: `theme.only`; `Usable()` now also asks `ThemeAllows()`, so anchor, core, support, wildcard,
  guarantee, family spread, escorts, squads, the lone brute and the regional favourite kind all stay inside the theme.
  `EncounterBudget.zs`: the fallback cheapest monster uses `Usable()` (same test as before plus the theme), and EX titans
  must match an only-theme too. The regional favourite kind is still chosen from all kinds, so neighbouring dungeons keep
  sharing it. When it falls outside a story theme, the army reports it as `excluded` instead of adding it. Nothing changes for dungeons without `only=1`; the planner test's ENCPLAN lines for
  all other plans are unchanged in kind (the existing checks all pass).
- `DoomerfallAreaLevels.cs`: `StoryThemes` (MapId to theme row name) beside the level `Overrides`, and `StoryTheme()`.
  `DoomerfallMonsters.BuildArea` sends the story theme in the existing dungeon type text field
  (`ENCOUNTER_DUNGEON_TYPE`) in place of the type name. The integer `dungeon_type` stays Daggerfall's real type.
  No bridge header change, so the layout hash and every other lane's test folders are unaffected.
- Loot: drops, treasure and enemy loot already read `DoomerfallDrops.AreaLevel`, which is the same fixed level 1.

Engineering calls made:
- **Strict, not a leaning.** The owner said its theme "is humanoid enemies". A leaning would still let about a third of
  the genes pick demons, and HumanStronghold already was that leaning, so a strict story theme is the reading that
  changes something. Civil War still happens when the genome rolls it: then both sides are humanoid (pirates fighting
  pirates). Side B of a Civil War was already exempt from leanings, but not from `only=1`.
- **Humanoid = the Former Human kinds** (ZombieMan, ShotgunGuy, ChaingunGuy and everything DRLA and Colourful Hell map to
  them: Elite, Stealth, Commando, Captain, Shocktrooper and so on). Stock Wolfenstein SS is not in the pool. Nothing
  else in Doom's roster is a person.
- **The story theme travels in the existing text field**, not a new bridge field, to avoid a layout hash change.

## Verification

- Planner test (`tools/encounter_planner/run_test.py`, stock, DRLA, DRLA skill 1), extended with 35 Humanoid plans
  (Privateer's Hold's real facts at levels 1, 8, 15, 22, 29, and 30 other indices at levels 1-30): **31/31 passed**,
  every army member of every Humanoid plan (both Civil War sides) is a Former Human kind, no planner warnings.
  Output: `D:\dev\DoomDaggerfall-loop\review\mainquestlevels\planner\`.
  Privateer's Hold, DRLA, level 1: side A anchor RLEliteSergeantDoubleShotgun, core RLEliteHumanBattleRifle, support
  Shocktrooper, Elite Captain, Commando; side B Commando minigun, Stealth Zombieman and Shotgunguy and others.
- Paired New Game: see the run section below.

## Paired New Game run

Builds: UZDoom incremental in `D:\dev\DoomDaggerfall-build\uzdoom-items` (configured from this worktree, version
2edeb607), Daggerfall Unity CliBuild (`CliBuild result: Succeeded`), doomerfall.pk3 from this worktree. Launcher, bridge
DLL, dfitems.pk3 and map data were copied from `review\newgameesc\play` (built after the last bridge header change,
b48037d5, so the layout matches). Assembled by `review\mainquestlevels\assemble.py`.

The Daggerfall Unity build ran through quiet_run with `--user-desktop`, because another lane reported that Unity's
license check fails on a private desktop.

Command (the whole run on one private desktop; a passthrough stands in for the inner quiet_run so the driver can see
Doom's window there, and adds `-dfmute -nosound`):
`quiet_run.py --timeout 200 -- python tools\demo_combined\retarget.py review\mainquestlevels\play --play-mods
--set QUIET=<scratchpad passthrough.py> --set TIMEOUT=90 tools\new_game\run_new_game.py create`

Result: `reached`. A real character was made (Baafylte), the cinematics were skipped, difficulty 2 was chosen, and the
player arrived at Privateer's Hold's start point (0.0 units off). Logs: `review\mainquestlevels\play\run-tests\test-run\`.

- Daggerfall (`create-df.log`): `monsters: Privateer's Hold has 42 placements at area level 1` and
  `encounters: facts map 187853213 ... type 2 theme Humanoid areaLevel 1`; `ammo: area level ... in the dungeon is 1`.
- Doom (`create-uz.log`): `DDENC plan genes 703 theme Humanoid civilwar 1 pool 14700 spent 14705 mooks 73`, placer
  `unplaced 0`, `dropped-points 0`, `stuck-leaders 1` (the known 19-unit marker a1d3482238564000).
- All 42 leaders placed are Former Human classes: RLEliteHumanBattleRifle 16, RLStealthZombieman 14,
  RLEliteSergeantDoubleShotgun 5, RLStealthShotgunguy 2, RLEliteCommandoMinigun 2, RLFormerCyborgBattleRifle 2,
  RLFormerHumanPistol 1. Doom logs only the leaders. The 31 escorts come from the same armies through `Usable()`, and the
  planner test covers those armies.
- Pool 14700 at level 1 is the same pool as before this change (an earlier log showed `pool 14700` for HumanStronghold at
  level 1), so the level was already right and the army size is unchanged.

Engine regression check, built UZDoom: `DOOM.WAD -warp 1 1` reaches `E1M1 - Hangar` stock, and with DRLA Arsenal,
Monsters, DRLAX and doomerfall.pk3 (only DRLA's own `Midas_Statue_Fatality` warnings). No engine source changed.

Demo: `D:\dev\DoomDaggerfall-loop\review\mainquestlevels\play.bat`.

## Main quest order and proposed table (for the owner)

### How the order was found

From Daggerfall Unity's classic quest scripts (`Assets/StreamingAssets/Quests/S0000*.txt`) and the place table
(`Assets/StreamingAssets/Tables/Quests-Places.txt`, which maps quest place names to location ids):

- `S0000999` (Main Quest Backbone) starts the seven first-stage quests. Each waits for the player to reach a level
  (`level N completed`) and for a noble's reputation: Morgiah's Wedding and Concern for Nulfaga at level 3, Prince
  Helseth's Blackmail at 4, The Werebeast and Missing Prince at 5, Elysana's Robe at 6, Freeing Medora at 8.
- Each quest's `start quest` lines give the chains after that, some with another level wait:
  Morgiah's Wedding → Lich's Soul (level 7); Concern for Nulfaga → Mynisera's Letters; Missing Prince (then level 7)
  → Wayrest Painting → Stronghold of the Blades (level 8); Helseth's Blackmail → Barenziah's Book (level 9);
  Werebeast → Emperor's Courier → Orcish Treaty → Mantella Revealed → Elysana's Betrayal;
  Freeing Medora → Dust of Restful Death (level 10) → Lysandus' Revelation → Lysandus' Revenge → Who Gets the Totem
  → Journey to Aetherius.
- Each quest's `Place ... permanent` lines name its fixed dungeons. Current levels and types were read with
  `tools/area_level` (same formula as `DoomerfallAreaLevels`).

Quests with only random dungeons (Helseth's Blackmail and Elysana's Robe use a random fortress) have no fixed place.
Missing Prince picks one of Castle Faallem or the Fortress of Fhojum per game (`randompermanent`), so both get one level.

### Proposed table

Levels spread the classic level gates (3 to 10, then the finale) over Doomerfall's 1-30. A place used by several
quests takes the level of its **first** main quest visit (one fixed level per place, as for every place).

| Order | Dungeon (region, MapId) | First main quest use (classic gate) | Today | Proposed level | Theme |
|---|---|---|---|---|---|
| 0 | Privateer's Hold (Daggerfall, 187853213) | New Game | 1 | **1 (built)** | **Humanoid (built)** |
| 1 | Scourg Barrow (Dragontail Mountains, 701948302) | Morgiah's Wedding (level 3); again in Barenziah's Book | 14, Crypt | 5 | keep type (Crypt, undead) |
| 1 | Shedungent (Wrothgarian Mountains, 728811286) | Concern for Nulfaga (level 3); again in Freeing Medora, the Totem and the finale | 28, Laboratory | 5 | keep type |
| 2 | Castle Necromoghan (Daggerfall, 9570447) | Mynisera's Letters (after Nulfaga) | 19, VampireHaunt | 8 | keep type |
| 3 | Direnni Tower (Isle of Balfiera, 43196334) | Missing Prince (level 5) | 28, VampireHaunt | 10 | keep type (or Coven, the Direnni are mages) |
| 3 | Castle Faallem (Sentinel, 325404) / Fortress of Fhojum (Sentinel, 5585279) | Missing Prince (level 5), one of the two | 11 / 28, RuinedCastle | 10 | keep type |
| 3 | Tristore Laboratory (Betony, 2352284) | The Werebeast (level 5) | 18, Laboratory | 10 | keep type |
| 4 | Castle Llugwych (Ykalon, 336619236) | Stronghold of the Blades (level 8) | 11, HumanStronghold | 17 | Humanoid (the Blades) |
| 4 | Lysandus' Tomb (Menevia, 207828842) | Stronghold of the Blades (level 8) | 14, Crypt | 17 | keep type (Crypt, undead) |
| 5 | Orsinium (Orsinium Area, 19021260) | Barenziah's Book (level 9); Orcish Treaty; Dust of Restful Death (level 10) | 29, OrcStronghold | 21 | Humanoid (orcs) |
| 6 | Woodborne Hall (Wayrest, 83032363) | Lysandus' Revenge (after level 10) | 28, HumanStronghold | 24 | Humanoid (Lord Woodborne's men) |
| 7 | Mantellan Crux (1001) | Journey to Aetherius (finale) | 23, HarpyNest | 30 | none obvious |
| – | Castle Daggerfall, Castle Wayrest, Castle Sentinel (the city dungeons of Daggerfall 1291010263, Wayrest 630439035, Sentinel 6634853) | audiences throughout; Wayrest Painting and Lich's Soul (level 7), the Totem | 7 / 16 / 25 (city dungeon level) | 3 / 14 / 14 | Humanoid if they get armies at all |

Notes on the table:
- Proposed levels are suggestions; the shape is "gate 3 → 5, gate 5 → 10, gate 8 → 17, gate 9-10 → 21, late → 24,
  finale → 30". Most of these places drop a lot from today's ranked level (Shedungent, Direnni Tower, Orsinium and
  Woodborne Hall are 28-29 today).
- Shedungent and Scourg Barrow come back later in the quest at a much higher classic gate. With first-visit levels the
  finale's trip through Shedungent is at level 5.
- The three palaces are where the player meets the nobles. Whether they should hold an army at all depends on the open
  passive castle guard question (20261124-104520 / 20261124-130608); their level only matters if they do.
- Mantellan Crux already has an open question for its level (20261123-233755); 30 is the proposal here.
- Region names come from MAPS.BSA as read by `tools/area_level/dfdata.py`; Lysandus' Tomb and Castle Llugwych read as
  Menevia and Ykalon there.

## Failed approaches and findings

- `--set 'QUIET=r"..."'` from PowerShell lost its inner quotes (SyntaxError); `r\"...\"` works.
- `+map E1M1 +wait 105 +quit` quits during startup before the map loads; `-warp 1 1` with quiet_run's timeout works.
- The planner itself had no failures. Privateer's Hold already had level 1 and the HumanStronghold leaning, so the visible change is that its
  armies are now humanoid only.

## Play-test list

- New Game, explore Privateer's Hold: every enemy should be a Former Human type (zombiemen, sergeants, commandos and
  their DRLA variants); none should be a demon. Does it still play as well as before? Humanoid-only armies are mostly
  hitscan.
- If the genome rolls Civil War here (it does with the current seed), two humanoid armies fight each other. Does that
  read as pirates fighting, or is it confusing?
