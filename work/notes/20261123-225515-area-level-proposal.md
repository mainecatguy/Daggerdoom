# Area level proposal

Status: approved by the owner on 2026-11-23. Built in Daggerfall as `Doomerfall/DoomerfallAreaLevels.cs`
(see `work/notes/20261123-233755.md`); the enemy drops read it. Keep the script and the C# port in step.

Script: `tools/area_level/area_level.py` (reader in `tools/area_level/dfdata.py`).
It reads `MAPS.BSA` and `POLITIC.PAK`, gives every classic location a level, and prints
the summaries quoted below. It runs in about 4 seconds:

```
python tools/area_level/area_level.py [--csv OUT.csv]
```

The CSV is derived from game data. Write it outside the repo. Nothing generated is committed.

## Summary

- **Dungeons** (all 4,232 locations with a dungeon, including graveyards) each get a level
  from a score made of four parts: region lean, a smooth map-wide noise field, dungeon type
  lean, and per-place noise with rare large "exceptions". The score is turned into 1 to 30
  by rank, so every level is exactly equally common.
- **Everything else** (towns, homes, temples, taverns) and the **open wilderness** get a
  "terrain level" from only the region lean and the smooth field, ranked over every land map
  pixel. A town and the countryside around it agree, and the wilderness has a level for
  overworld encounters at no extra cost.
- All randomness is a 32-bit integer hash of fixed seeds and the location's `MapId` (or map
  pixel). Same level in every game, and the hash ports to C# exactly.

## Formula

```
raw   = 0.85 * region_lean     hand table per region, -2 .. +2
      + 0.9  * geo_field(x,y)  two octaves of value noise, cells of 48 and 16 map pixels
      + 0.8  * type_lean       hand table per dungeon type, -1.5 .. +2
      + 1.0  * place_noise     bell-shaped, plus a 7% chance of a +/-2.5..5 "exception" kick
level = 1 + floor(30 * rank(raw) / count)    ranked within the dungeon's size class
```

Size classes are labyrinth (including the 3 cities with dungeons), keep, ruin, and graveyard.
Ranking within each class means small ruins come at level 30 as often as big labyrinths, and
big labyrinths at level 1 as often as small ruins. Size and difficulty stay independent, which
is another axis of choice for the player.

Terrain level is `0.85 * region_lean + 0.9 * geo_field`, ranked over all land map pixels.

### Region lean (hand table, in the script)

| Lean | Regions |
|---|---|
| -2 | Daggerfall, Glenpoint, Tulune, Glenumbra Moors, Betony, Northmoor |
| -1 | Ilessan Hills, Shalgora, Anticlere, Ykalon, Daenia, Abibon-Gora, Kairou, Myrkwasa, Pothago |
| 0 | Sentinel, Urvaius, Phrygias, Bhoriane, Kambria, Dwynnen, Ayasofya, Tigonus, Antiphyllos, Bergama, Cybiades |
| +1 | Wayrest, Lainlyn, Koegria, Alcaire, Menevia, Kozanset, Satakalaam, Totambu, Mournoth, Santaki, Gavaudon, Dak'fron, Ephesus |
| +2 | Alik'r Desert, Dragontail Mountains, Wrothgarian Mountains, Orsinium Area, Isle of Balfiera, High Rock sea coast |

The reasoning: the game starts in Privateer's Hold and Daggerfall city, so western High Rock
is gentlest. The main quest then pulls the player to Sentinel, then Wayrest and Orsinium.
Mountains, the desert, and remote isles are the wild frontier.

### Type lean (hand table, in the script)

Natural cave and mine -1.5; harpy and spider nests -1; crypt, scorpion nest, and prison -0.5;
human, orc, and barbarian strongholds and ruined castles 0; desecrated temple +0.5; giant
stronghold, coven, and laboratory +1; vampire haunt and volcanic caves +1.5; dragon's den +2.
Cemeteries are 0, because graveyards are ranked in their own class and are all cemeteries,
so a lean would do nothing.

### Overrides

Privateer's Hold is fixed at level 1, because every new character wakes up there with
nothing. Other story dungeons use the formula for now (see the questions).

## Why it meets each goal

| Goal | How | Evidence (script output) |
|---|---|---|
| Levels 1 to 30, all equally common | Rank mapping within each size class | Every level has 140 to 145 dungeons. Each class varies by at most 3 per level. |
| Region leans, but not forced like an MMO | Region lean is one input of four, and exceptions break the pattern | Lean -2 median 6 (quartiles 3 to 10). Lean +2 median 22 (15 to 27). 1.6% of starting-area dungeons are 26-30 (about 9 dungeons). 3.1% of hardest-region dungeons are 1-5. Daggerfall, Glenpoint, and Northmoor each span 1 to 28 or more. |
| Encounter type has some input | Type lean | With the region removed, natural caves average 4.2 levels below their region, and dragon's dens 5.7 above. |
| Many themes at many levels | Type lean is moderate | Every dungeon type appears in every five-level band, 19 of 19. Dragon's dens range from 1 (Jubithiva's Den, Daggerfall) to 30 (The Fortress of Ashham, also Daggerfall). |
| Random per location | Per-place noise keyed by `MapId` | |
| Geographic clustering | Smooth map-wide field shared by neighbours | The nearest other dungeon (median 4 map pixels away) differs by 6.8 levels on average, against 10.0 for a random pair. |
| Fixed seeds | Integer hash of fixed seeds and `MapId` | Two runs give byte-identical CSVs (md5 `807eef93...`). |
| Player agency | Region and type are learnable leans. Size is independent. | A player who wants easy content goes west and picks caves. A player who wants a fight goes to the mountains or picks a vampire haunt. Rumours of a level 30 dragon in Daggerfall are true and memorable. |

## Distribution by region lean (dungeons)

```
lean -2: n= 571  quartiles (3, 6, 10)   1-5 47.1%   26-30  1.6%
lean -1: n= 782  quartiles (4, 8, 14)   1-5 34.8%   26-30  2.6%
lean  0: n= 664  quartiles (8, 14, 19)  1-5 13.3%   26-30  8.1%
lean +1: n= 960  quartiles (14, 20, 25) 1-5  4.1%   26-30 24.7%
lean +2: n=1255  quartiles (15, 22, 27) 1-5  3.1%   26-30 30.6%
```

The upper leans hold more dungeons (Wrothgarian Mountains alone has 685), so the hard end
of the map is big. Starting regions have fewer places in total.

## Examples

| Place | Region | Kind | Level | Terrain |
|---|---|---|---|---|
| Privateer's Hold | Daggerfall | labyrinth, human stronghold | 1 (override) | 1 |
| Daggerfall (city) | Daggerfall | city dungeon | 7 | 2 |
| Castle Necromoghan | Daggerfall | labyrinth, vampire haunt | 19 | 4 |
| Tristore Laboratory | Betony | labyrinth, laboratory | 18 | 4 |
| Castle Llugwych | Ykalon | labyrinth, human stronghold | 11 | 6 |
| Sentinel (city) | Sentinel | city dungeon | 25 | 24 |
| Wayrest (city) | Wayrest | city dungeon | 16 | 9 |
| Woodborne Hall | Wayrest | labyrinth, human stronghold | 28 | 21 |
| Lysandus' Tomb | Menevia | labyrinth, crypt | 14 | 11 |
| Scourg Barrow | Dragontail Mountains | labyrinth, crypt | 14 | 17 |
| Direnni Tower | Isle of Balfiera | labyrinth, vampire haunt | 28 | 25 |
| Shedungent | Wrothgarian Mountains | labyrinth, laboratory | 28 | 29 |
| Orsinium | Orsinium Area | labyrinth, orc stronghold | 29 | 30 |
| Mantellan Crux | High Rock sea coast (off-map) | labyrinth | 23 | 1 |

Random dungeons in Daggerfall region: Garenor Hall (vampire haunt) 4, Kinghart's Hold (keep,
laboratory) 5, Castle Vladivon (vampire haunt) 12, Castle Corroghar (vampire haunt) 16,
The Citadel of Wickston (ruined castle) 19, and graveyards from 1 to 10.

## Engineering notes for when this is built

- **Rank stability.** Ranks depend on the whole set of locations. Daggerfall Unity can add
  locations through mods. The runtime should rank only classic locations (Daggerfall Unity's
  `ReadLocationCount` exists for exactly this), and give added locations a level by placing
  their score among the classic scores. Levels of classic places then never change.
- **Cost.** Ranking 4,232 dungeons and 500,000 pixels at load is cheap in C#. The pixel
  ranking can be cached in memory, or replaced by 29 score cutoffs computed at startup.
- **Hash.** `lowbias32` with `uint` arithmetic. Python and C# give the same bits.
- Mantellan Crux sits at map pixel (1, 1), outside the real map, so its terrain level is
  meaningless. It should get an override.

## Choices for the owner to confirm

1. Region lean table. The tiers above are my reading of the game's progression.
2. Strength of the region versus variety. Currently about 1 in 60 starting-area dungeons is
   26-30. Raising `EXCEPTION_CHANCE` or lowering `REGION_W` gives more surprises. Raising
   `REGION_W` gives more predictability.
3. Type lean table, and whether dragon's dens and vampire haunts should lean harder still.
4. Ranking within size class, so size and difficulty are independent. The alternative is
   letting labyrinths lean harder.
5. Towns and the wilderness use the terrain level with no per-place noise. The alternative
   is giving towns their own noise.
6. Story dungeon levels. Only Privateer's Hold is fixed now.
