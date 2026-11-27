# Skyrim-style UI, with SWF support in both engines

Waiting on: the owner moving it to todo; the Tab menu card (`tabmenu` 01) comes first.

Owner (2026-11-27): "We probably need to add SWF support to both daggerfall's and Doom's UI because we're taking a
backlog item to skyrimify the UI". Restyle Doomerfall's interface after Skyrim's menus, using the Skyrim UI files the
owner provided (`GameMods/SkyrimUi-60FPS/interface/`, committed and bundled as for the Tab menu). Step 1 is only the Tab
tween menu (`tabmenu` 01), as a Doom resource, built to be extensible. How (playing SWFs or converting them at build
time) is the working agent's call (owner, 2026-11-27: "let the agent doing the work decide"). Many later menus may
become Daggerfall resources in Daggerfall's UI (owner: "note that many other menus are going to become daggerfall
resources potentially"), so the approach should work in both engines. Then propose which menus to restyle and in what order.
