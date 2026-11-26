# Schism 0.97D: does it run in UZDoom, and how far is it from our system?

Investigation only. Nothing in the mod or the game code was changed.

## Files

- `GameMods/Schism_097D.zip` and `GameMods/Schism_097D_Patch.0.1_Public.pk3.2.zip` each wrap a single pk3. Both were extracted next to the zips:
  `GameMods/Schism_097D.pk3` (288 MB, 36,398 lumps) and `GameMods/Schism_097D_Patch.0.1_Public.pk3` (5 MB). Load the patch after the main pk3.
- Readable copies: `GameMods/ExtractedData/Schism_097D/` and `GameMods/ExtractedData/Schism_097D_Patch_0.1/`. The pk3 has both a `TEXTURES` lump and a `Textures/` folder, which Windows cannot hold side by side, so the extracted lump is named `TEXTURES.__lump`. The pk3 itself is untouched.

## 1. Does it run in UZDoom? Yes.

Command (quiet_run, private desktop):
`uzdoom.exe -iwad DOOM2.WAD -file Schism_097D.pk3 Schism_097D_Patch.0.1_Public.pk3 -skill 3 +map MAP01`, then summoned DoomImp, Demon, Revenant and Archvile, ran `give all`, took screenshots, and quit. Exit 0.

- MAP01 loads and plays. Schism's spawners replace the summoned monsters, and its HUD, boss health bar ("REVENANT"), gore and weapons all show.
- Startup prints 175 script warnings, mostly classes Schism references but never defines (`MudBloodSplasher`, `MinimalFlameTrails`, `SSGAmmo` and so on). These are the mod's own leftovers and do not stop it.
- One runtime error: `acs/lfshitem: invalid ACS module`. The script for the shield sphere artifact will not run.
- The startup check (`-norun`, expect 1337) can't be used right now: our current build exits 57 even for bare DOOM2 with no mods (see "Suspected oversights").
- Not tested: Schism's own maps, the Heretic and Hexen modes, vehicles, and performance with large packs.

## 2. How far is it from our system?

### What Schism is

Schism is an all-in-one, Brutal Doom style mod, written only in DECORATE and ACS (no ZScript), like DRLA. It replaces:

- **Player classes**: `clearplayerclasses`, then Ranger, Paladin, Sorcerer and Corvus. Sorcerer and Paladin use mana.
- **Weapons**: about 80, in slots 0 to 9. It covers Doom, Heretic and Hexen weapons, plus the MP40 and similar guns.
- **Monsters**: through Doom, Heretic and Hexen replacements.
- **Other**: decorations, the HUD (SBARINFO), and numbered `puke` keybinds (kick 301, reload 303, grenade 315, spell type 363). It also adds bots, vehicles and 7 maps.

**It can't be loaded together with DRLA.** Both clear the player classes and replace the stock weapons and ammo. So there are two possible ways to support it.

### Option A: Schism monsters with the DRLA arsenal

- We would need a cut-down Schism with only the monsters: no player classes, weapons, HUD or keybinds. 49 monster files check for inventory or class (executions, gore tokens, kicks), so they lean on Schism's player. Splitting them out means repacking a 37,000-file mod and fixing what breaks. That is a large job and hard to keep up to date with Schism's patches.
- The encounter side fits well. `doomerfall_encounters.txt` already sorts monsters into kinds by class-name pattern and ancestry, as was done for Colourful Hell. Schism would need its own `kindname` rules and point estimates (data work).
- **Spawner problem.** Each `Schism_*Spawner` (`Actors/Spawner/MonsterSpawners.txt`) stays alive after spawning its monster. It is an invisible `+ISMONSTER +SHOOTABLE` actor that gives the monster a TID and calls ACS (`Live_Check`, `Get_Spawner_Status`) every 5 tics until the monster dies. Its "boss presence changes spawning" logic uses map-wide ACS state.
  - For slaughter-sized packs that doubles the actor count and adds ACS calls on every one.
  - The spawners would also count as monsters for us.
  - Our planner would have to spawn the real monster classes directly, the way `DoomerfallPickups.zs` skips DRLA's random spawners.
  - Check that Schism's TID use doesn't clash with ours.
- **Unmeasured risk: Brutal-style gore with hundreds of monsters.** That is the first thing to test before committing to either option.

### Option B: Schism as the arsenal instead of DRLA

The engine code depends on DRLA less than expected:

- `DoomerfallAmmo.zs`: names ammo `Clip/RLClip`, `Shell/RLShell` and so on. Schism's ammo replaces the stock classes without inheriting from them (`Clip2`, `AmmoShell`, `AmmoRocket`, `AmmoCell`), so it needs new name entries.
- `DoomerfallPickups.zs`: 3 marker pairs, DRLA class or stock class.
- `DoomerfallReload.zs`: DRLA only. Without DRLA it does nothing.
- `DoomerfallGuns.zs`: 2 run-time lookups (`RLDeselectionFunction`, `RLWeaponLimit`), which fall back when they're missing.
- Daggerfall C# (`Assets/Scripts/Doomerfall/`): handles Doom items by class name. Its DRLA mentions are comments, tests, and the "modded pickup" gun-state line.

**The design is the real blocker.** `gamedesign.md` builds loot on DRLX gear (weapon mod packs, DRLA armor and boots, DRLA resistances with Daggerfall rules on top). Material tiers are built on four ammo types. Schism has:

- no mod-pack system
- magazine ammo per gun (`DoubleRifleAmmo`, `MP40Ammo` and others)
- many special ammo types (cryo shells, plasma, grenades, gas, rail)
- mana-based classes, which overlap with Daggerfall owning magic

Mapping Daggerfall weapons, tiers and prices onto Schism would mean redesigning the loot and ammo systems. That is the owner's call.

### Summary

| | Runs in UZDoom | Code work | Design work | Main risk |
|---|---|---|---|---|
| A: Schism monsters + DRLA guns | yes | large (monster-only repack, skip spawners) | small (kinds, points) | performance of gore at slaughter scale; keeping the repack current |
| B: Schism instead of DRLA | yes | small to medium (ammo names, pickups, guns) | large (loot, ammo tiers, mods, mana classes) | loses the DRLA design the game is built on |

## Next test, if we continue

A performance check: Schism on a large open map with a few hundred monsters, compared with DRLA Monsters + Colourful Hell on the same map and the same count, on a real desktop for real frame rates. It settles Option A cheaply before any repack work.

## Suspected oversights

- **The startup check is broken in the current build.** `uzdoom.exe -iwad DOOM2.WAD -norun -stdout` (no mods, build dated 2026-11-25 06:07) exits 57 instead of 1337 and prints a stray `f 2` after `D_CheckNetGame`. AGENTS.md lists 1337 as the success check, so automated checks that rely on it will fail. Confidence: high that it happens. The cause was not investigated.
