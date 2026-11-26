# Revisit damage and resistances

**Waiting on:** initial release.

The initial release design in `gamedesign.md` is not final. Revisit how DRLA resistances, Daggerfall's damage rules, and armor work together.

## Schism damage types and freezing (owner, 2026-11-25)

Fold Schism into this rework if Schism is supported. Viability notes: `work/notes/20261125-schism-viability.md`.

**Damage types differ between the mods.** Counts are uses in the extracted mods under `GameMods/ExtractedData/`.

- **DRLA Arsenal** uses few types: mostly `plasma` (82) and `fire` (61), plus a handful of `piercing`, `bullet`, `rigelblast`, `holy`/`unholy`, `slime`, `neuralstun`, `acid` and `lightning`. DRLA armor resists by DamageFactor on `bullet`, `melee`, `fire`, `plasma`, `slime`, `holy`, `radiation`, `piercing` and a few others. DRLAX adds only `fire` and `melee`. DRLA Monsters adds `ice` once and `lightning` twice.
- **Schism** has real elements DRLA lacks: `freeze` (50) and `lightning` (88), next to `fire` (107), `plasma`, `explosive`, `cut`, `saw`, `bullet`, `railgun`, `desintegrate` and more.
- **Many Schism "damage types" are not damage.** `blood`, `blueblood`, `greenblood`, `avoid`, `killme`, `trample`, `teleportremover`, `gibremoving` and the `causesplash...` types are signals for gore and splash effects. Any mapping must ignore them.

**Daggerfall's elements already match Schism's well.** Daggerfall has fire, frost and shock (plus poison and magic). `DoomerfallSheet.cs` already sends the player's resistances and tolerances for all of them to Doom, but Doom only logs them today (`UZDoom/src/dd_bridge.cpp:734`). So the rework needs one table that maps every damage type, from stock Doom, DRLA and Schism, to a Daggerfall element or to "physical", and applies Daggerfall resistances to it. Candidates: `freeze`/`ice` to frost, `lightning` to shock, `fire`/`burn` to fire. Where `plasma` goes is a design question, because DRLA's main energy type has no Daggerfall element.

**Freezing as an effect.** Schism's freeze has two parts, both written separately for each Schism monster:

- On hit (`Pain.Freeze`), the `SlowingFreeze` ACS script permanently sets movement speed to 2/3, once per monster.
- On a freeze kill (`Death.Freeze`/`Ice`/`Frost`), the monster becomes a statue with hand-drawn frozen sprites (46 kinds, `Actors/Monsters/Frozen.txt`). The statue shatters when shot, or thaws after about 15 s into a wounded version of the monster.

It only works on Schism's own monsters. A generic freeze for every monster is possible:

- **Freeze kill:** UZDoom's built-in ice death, `GenericFreezeDeath` (`UZDoom/wadsrc/static/zscript/actors/actor.zs:1895`), freezes and shatters any monster killed by `Ice` damage that has no ice death of its own. It needs no art.
- **Temporary freeze or slow:** a small ZScript item could hold any monster in place or slow it, tint it blue, and wear off.

This ties to Daggerfall frost damage and Paralyze (`magic-effects-on-enemies.md`). Freeze length, boss resistance and how frost resistance reduces it are owner design decisions.
