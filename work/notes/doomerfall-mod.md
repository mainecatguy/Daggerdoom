# Doomerfall mod and keybind menu

## What was built
- `mods/doomerfall/src/` is the mod source: `KEYCONF.txt` (a "Doomerfall" controls section with two unbound actions), `MAPINFO.txt` (registers the event handler, `gameinfo { AddEventHandlers }`), `ZSCRIPT.txt` and `zscript/Doomerfall.zs` (the handler `Doomerfall_Events`; each action logs a line).
- `scripts/doomerfall/build_pk3.py [out.pk3]` zips it. `--smoke` builds the test-only trigger pk3 from `mods/doomerfall/smoke-src/`.
- `scripts/doomerfall/smoke.py` runs DOOM.WAD E1M1 in three setups with a private config and `-stdout`: mod only, DRLA set only, DRLA set plus mod. The pk3 files are not committed.
- No engine changes (stitch build used as is).

## Adding an action
1. Add `AddMenuKey "Label" "netevent df_<name>"` to `KEYCONF.txt`.
2. Add a branch for `df_<name>` in `Doomerfall_Events.NetworkProcess`.
Events use a `df_` prefix so they never collide with DRLA's (`DRLAX_*`).

## Verified (smoke.py, all three pass)
- Mod only: loads, zero script errors, both actions log "Doomerfall: action fired: ..." when fired by netevent.
- DRLA set only: DRLA prints 766 error lines on every launch (unknown DRPG/Midas classes, a bad translation). These exist without our mod.
- DRLA set plus mod: same 766 lines, none new; our mod loads and both actions fire.
- Not verified by test: that the netevent route equals a real key press. The bind goes through the engine's standard `AddMenuKey`, which runs the same command, but see below.

## Needs a human (use review/doomerfall-mod/play.bat)
- Options > Customize Controls shows a "Doomerfall" section with "Open Fast Travel" and "Open Inventory", both unbound.
- Bind each to a key, press it in game, and check the console shows the "action fired" line.
- With DRLA: DRLA's own controls (the DRLA controls menu, its keybind sections such as the PDA key) and its HUD and main-menu entries are still present and working. Only the log was compared, not the menus.
- The section's position in the control list (it appears with the sections added by other mods; order depends on load order).

## Known gaps
- Actions only log. No Daggerfall connection, no default keys, no conflict resolution (as specified).
- The 766 DRLA error lines are DRLA's own, not addressed here.
