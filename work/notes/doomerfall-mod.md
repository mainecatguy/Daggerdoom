# Doomerfall mod and keybind menu

## What was built
- `mods/doomerfall/src/` is the mod source: `MENUDEF.txt` (adds a "Doomerfall Controls" submenu to Options > Customize Controls, with two unbound actions; `KEYCONF.txt` is gone, so nothing is added to the main controls list), `MAPINFO.txt` (registers the event handler, `gameinfo { AddEventHandlers }`), `ZSCRIPT.txt` and `zscript/Doomerfall.zs` (the handler `Doomerfall_Events`; each action logs a line).
- `scripts/doomerfall/build_pk3.py [out.pk3]` zips it. `--smoke` builds the test-only trigger pk3 from `mods/doomerfall/smoke-src/`.
- `scripts/doomerfall/smoke.py` runs DOOM.WAD E1M1 in three setups with a private config and `-stdout`: mod only, DRLA set only, DRLA set plus mod. The pk3 files are not committed.
- No engine changes (stitch build used as is).

## Adding an action
1. Add `Control "Label", "netevent df_<name>"` to the `DoomerfallControlsMenu` in `MENUDEF.txt`.
2. Add a branch for `df_<name>` in `Doomerfall_Events.NetworkProcess`.
Events use a `df_` prefix so they never collide with DRLA's (`DRLAX_*`).

## Verified (smoke.py, all three pass)
- Mod only: loads, zero script errors, both actions log "Doomerfall: action fired: ..." when fired by netevent.
- DRLA set only: DRLA prints 766 error lines on every launch (unknown DRPG/Midas classes, a bad translation). These exist without our mod.
- DRLA set plus mod: same 766 lines, none new; our mod loads and both actions fire.
- Not verified by test: that the netevent route equals a real key press. The bind goes through the engine's standard `AddMenuKey`, which runs the same command, but see below.

## Needs a human (use review/doomerfall-controls-submenu/play.bat)
- Options > Customize Controls ends with a "Doomerfall Controls" entry. Opening it shows "Open Fast Travel" and "Open Inventory", both unbound.
- Bind each to a key, press it in game, and check the console shows the "action fired" line.
- With DRLA: DRLA's own controls (the DRLA controls menu, its keybind sections such as the PDA key) and its HUD and main-menu entries are still present and working. Only the log was compared, not the menus.
- Placement: the entry is appended after "Reset to defaults" at the end of the Controls menu (AddOptionMenu cannot insert earlier). Check that looks acceptable.

## Known gaps
- Actions only log. No Daggerfall connection, no default keys, no conflict resolution (as specified).
- The 766 DRLA error lines are DRLA's own, not addressed here.

## Controls submenu (agent/doomerfall-controls-submenu)
- Verified with a test-only handler that dumps the live `CustomizeControls` and `DoomerfallControlsMenu` item labels (smoke.py now checks it): the entry exists, the actions appear only in the submenu, and DRLA's entries (DoomRL Arsenal header, Use PDA, ...) are identical and in the same order with and without our mod. DRLA errors stay at 766 with and without the mod; mod alone has 0.
- Persistence: bound F9 to `netevent df_inventory`, quit, the config file held `F9=netevent df_inventory` and it was restored on relaunch. Not tested through the menu UI itself (bind by key press in the menu).
- Nothing is bound by default (no default binding in source).
- Human still needs to: open the submenu, bind and press both actions, confirm the key shows after restart, and confirm DRLA's own menus, HUD and keys still work (only labels and logs were compared). Demo: review/doomerfall-controls-submenu/play.bat.
