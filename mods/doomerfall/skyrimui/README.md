# Skyrim UI menus

Menu SWFs from the owner's SkyrimUi-60FPS copy (`GameMods/SkyrimUi-60FPS/interface/`). They are committed here by the
owner's exception to the "never commit `GameMods/`" rule (2026-11-27: "we need to bundle it with our application. It
needs to become a generated resource ... move it into a game folder, commit it, and include it with any distributed
builds"). The exception covers the files in this folder only.

The SWFs are not loaded by the game. `scripts/doomerfall/build_pk3.py` converts each menu listed in `menus.txt` with
`tools/skyrim_ui/convert.py` into one PNG per vector shape and a display-list lump, and puts them in `doomerfall.pk3`,
so every build that ships the pk3 (`scripts/play/install.py` and the review demos) carries them.
`zscript/DoomerfallSwfMenu.zs` draws a converted menu; each menu's behaviour (the SWF's ActionScript) is a ZScript
menu class, such as `zscript/DoomerfallTweenMenu.zs`.

| File | Root symbol | Used by |
|---|---|---|
| `tweenmenu.swf` | `TweenMenuObj` | The Tab menu (`DoomerfallTweenMenu`) |

To add a menu: copy its SWF here, add a line to `menus.txt`, and write its menu class. Shapes, gradients, sprites,
frames and text fields convert; bitmaps, masks, filters and fonts do not (text is drawn with a Doom font). Menus that
will be shown in Daggerfall's UI instead (backlog `skyrimify-ui`) can reuse the converter's PNGs and lump the same way.
