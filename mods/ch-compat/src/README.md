# ch-compat: Colourful Hell 1.04 with DRLA

A small patch that lets Colourful Hell 1.04 load and run next to DRLA Arsenal 1.1.5,
DRLA Monsters Beta 7.3, and DRLAX 1.2b.

## Load order

```
-iwad DOOM2.WAD -file ColourfulHell_1_04.pk3 DoomRL_Arsenal_1.1.5.pk3 DoomRL_Monsters_Beta_7.3.pk3 drlax_1.2b.pk3 ch-compat.pk3 [doomerfall.pk3]
```

Colourful Hell must load before DRLA:

- When both mods use a sprite or sound lump name, the file loaded later wins. DRLA wins,
  so the player's weapons and DRLA's monsters always look and sound right.
- Both mods replace the stock monster projectiles. DRLA Arsenal's versions win, so stock
  projectiles keep `+THRUGHOST` for DRLA's Phaseshift armor set bonus.
- Both mods replace `Blood` and `BloodSplatter`. DRLA Monsters' Nash gore versions win.

`ch-compat.pk3` loads after all of them.

## Build

```
python scripts/ch-compat/build_pk3.py [--ch path\to\ColourfulHell_1_04.pk3] [out.pk3]
```

Output defaults to `D:\dev\DoomDaggerfall-build\ch-compat.pk3`. The script reads the
local Colourful Hell PK3, which is never committed.

## Fixes

1. **Sprite name clashes (generated at build time).** Colourful Hell uses ten sprite
   names that DRLA also uses for different art. Because DRLA wins, Colourful Hell's
   monsters would show DRLA's frames:

   | Colourful Hell | Clashes with | New name |
   |---|---|---|
   | `AMIN` Abyss Mastermind | Arsenal assault minigun pickup | `XCAM` |
   | `TSHO` Cyberdemon projectile | Arsenal tactical shotgun frames | `XCTS` |
   | `SMK2` small smoke | DRLA's large smoke | `XCSK` |
   | `CIMP` Cyan Imp | Monsters' cybernetic imp | `XCCI` |
   | `CACO` cacodemon gib frames | Monsters and DRLAX cacodemon walk frames | `XCCA` |
   | `HMZP` zombie | DRLAX Sweeper class | `XCHZ` |
   | `GIB1` `GIB2` `GIB4` `GIB5` gibs | Monsters' smaller gibs | `XCG1` `XCG2` `XCG4` `XCG5` |

   The build script copies those Colourful Hell sprite lumps under the new names, and
   writes copies of the six Colourful Hell DECORATE files that use them (`Gibs`,
   `decorate/Imps`, `Shotgunners`, `Cacodemons`, `CYBIES`, `MASTERMINDS`) with only the
   sprite name on each state line changed. These copies have the same paths as Colourful
   Hell's files, so its own `#include` lines load them instead. All of this is derived
   from Colourful Hell's data, so it exists only in the built PK3, never in the repo.

   Other shared sprite names were compared pixel by pixel. Their art is identical, or
   almost identical (`TERM`, `FBRS`), so they were left alone.

2. **Sound name clashes (`SNDINFO.txt`).** Colourful Hell's `superbaron/*`,
   `weapons/hellex`, and `ClericFlameExplode` sounds use lump names that DRLA Monsters
   also ships. They now point to Colourful Hell's own files by full path. The four stock
   super shotgun lumps are overridden by both mods, and DRLA's versions are kept.

## Not changed

- **Stock monster replacement.** DRLA Monsters replaces stock monsters through skill
  `ReplaceActor` lines in MAPINFO, and the engine applies those before any DECORATE
  `replaces`. So ordinary Doom maps spawn DRLA monsters, and Colourful Hell's
  `Colourset` random spawners are never used. Colourful Hell monsters can still be
  spawned directly by class name.
- **Colourful Hell wrapper classes.** Names such as `BrownCaco` or `GrayCybie` are
  selectors. They read a Colourful Hell CVar and then spawn either the real monster
  (`BrownCaco2`, `GrayCybie2`) or a random `Colourset` spawner. With the default CVars,
  the Brown, Gray, Cyan, Abyss, and FireBlu tiers are off, so the wrapper spawns a random
  monster. Spawn the real `...2` class when a fixed result is needed.
- Colourful Hell's Abyss Mastermind uses frames `AMIN K-M`, which Colourful Hell never
  shipped. With this patch those frames are missing, the same as with Colourful Hell
  alone.
