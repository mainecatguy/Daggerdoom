# Drop labels: verification and landing

Verified branch `agent/droplabel-20261125-221820` (card `work/queue/droplabel/01.opus.dropped-gun-material-label.md`,
lane notes `work/notes/20261125-221820.md`) on `verify/droplabel` = current `integration` + a merge of the branch, then
landed it on `integration`.

## Review

- Meets the card: monster drops (fixed-drop floor id), script-spawned guns (lasting id issued at first look, take or
  park), guns dropped from Daggerfall's inventory (carried `DoomerfallGunMaterial` token), leave/return (gun facts kept
  with their id in the location record) and save/load. No Daggerfall map places a gun (checked by the lane).
- Daggerfall stays the authority: Doom only picks an identity (floor id) or hands back the material Daggerfall itself
  put on the token. The label (`FloorGunLabel`) and the take (`OnTake`) use the same `RollMaterial(FloorSeed(...))`
  inside a `LootSeed.Scope`, which restores Unity's shared generator, so a look changes no state.
- Inert without a bridge session: `DD_LookFrame` needs a session, the take needs `useRules` and a session, the treadmill
  only runs in bridge sessions, and `ddLootId` is only set in them. E1M1 below confirms it.
- Side effects: a look gives an id-less gun a lasting id (saved as `ddlootid`); a look may ask Doom for the class's art.
  Both intended. Bridge schema hash changed (all four parts rebuilt together). Fixed-drop gun floor ids gain bit 58, so
  their materials moved (owner accepts seed changes): the paired series gun is now Adamantium, floor id `974f7d065b7d6e95`
  (was Steel, `9f4f7d065b7d6e95`; same low bits).
- **Behaviour for the owner:** the material roll uses `WorldLevel.Current`, the area level where the *player* stands, not
  where the gun lies. A gun on an area-level border can roll differently depending on where it is taken (and the label,
  re-asked every 35 tics, follows the player too). Label and take still agree at any moment. Not changed.

## Fix made during verification (`d880b11d`)

The first droplabel save run **failed**: Daggerfall's look answers were all empty and the inventory named guns
"Iron RLBattleRiflePickup". The machine was heavily loaded (about ten paired game pairs from other lanes running);
`save-df.log` shows df->uz latency p50 2.0-2.8 s and `doomitems: no art for "RLBattleRiflePickup" in time` (the art
request times out after 2 s). A timed-out class was never asked again (`requested` stayed true) and the late answer was
dropped, so the gun's display name, which the label needs, never arrived for the rest of the session. Pre-existing, but
it made this feature fail. Fix in `DoomerfallDoomItems.cs`: a timeout clears `requested` (asked again when next drawn or
looked at) and remembers the request, and `OnArt` still accepts a late answer to it (the art slot's request check
already guards against a newer answer). Also tidied a garbled comment in `dd_lootrng.h`. The re-run passed, but art
arrived in time in that run, so the late-answer path itself was not exercised.

## Tests (build from `verify/droplabel`)

Builds: `cmake --build` of `../DoomDaggerfall-build/{bridge,launcher,uzdoom}` (exit 0; logs
`../DoomDaggerfall-build/verify-droplabel-{bridge,launcher,uzdoom}.log`); Daggerfall Unity windowed through
`quiet_run.py`, `CliBuild result: Succeeded` (twice, before and after the fix). Play folder
`D:\dev\DoomDaggerfall-build\verify-droplabel\play`, assembled from those trees (data and `dfitems.pk3` copied from the
lane's play folder, unchanged code paths; `doomerfall.pk3` rebuilt).

| Test | Result |
|---|---|
| `uzdoom.exe -iwad DOOM.WAD -norun -nosound -stdout`, stock | exit 1337 |
| same with DRLA set + `doomerfall.pk3` | exit 1337 |
| `tools/fixed_drops/e1m1_drops.py <uzdoom> verify-droplabel2` stock | 6 killed, 4 `Clip`, 0 `DDLOOT` lines |
| same, DRLA | 6 killed, 3 `RLPistolPickup` + 1 `RLBattleRiflePickup`, 0 `DDLOOT` (DRLA's usual "Script error"); same as the lane |
| `tools/droplabel/droplabel.py <play> save/load --area 25 --out droplabel-results2`, `check` | **DROP LABELS PASS** (A Iron Battle Rifle, C/D Silver Shotgun, D carried through the drop, B/D/E same after leave/return, B/D same after load) |
| `tools/fixed_drops/paired.py <play> series fresh save load` | **PAIRED FIXED DROPS PASS**: 112 killed, 183 drops, 0 unseeded, same gun in all three |
| `tools/fixed_drops/overworld.py <play> verify` | 13 + 7 died, 0 without a seed, 0 unseeded drops, 72 `DDMON spawner gave`, 0 summoned; same as `20261125-230756` |

The first E1M1 DRLA attempt (`verify-droplabel`) timed out at 40 s during the concurrent Unity builds; the re-run after
them passed. The first droplabel run is kept in `verify-droplabel\droplabel-results` (the failure above).

Results: `D:\dev\DoomDaggerfall-build\verify-droplabel\` (`droplabel-results2`, `fixed-drops-paired`,
`overworld-drops`), E1M1 logs `D:\dev\DoomDaggerfall-loop\review\summoned-e1m1\log-verify-droplabel2-*.txt`.

## Play-test list

1. New Game, kill the Privateer's Hold gunners, look at a dropped gun: the label names its material; take it and the
   inventory shows the same name.
2. Drop a gun from the inventory, look at it, take it back: same material.
3. Leave a gun on the floor, leave and return, save and load: the label stays the same.
4. Judge the brief plain name ("Battle Rifle") shown before Daggerfall's answer arrives.
5. Inventory names right after a take can show the class name ("Adamantium RLDoubleShotgunPickup", seen in the paired
   series log) until the art arrives; check the inventory window shows the proper name.
