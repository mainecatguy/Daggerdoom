# Akimbo pistols

**Waiting on:** owner design and a go-ahead. Feasibility discussed 2026-11-25 (below).

Owner idea: with a pistol drawn, the hotkey of a different pistol draws it in the other hand. Both are Daggerfall
items, equipped as two pistols. Each keeps its own properties and logic. Each trigger pull fires the pistol that did
not fire last if it is ready, otherwise whichever pistol is ready, so mismatched fire rates both keep shooting.

Feasibility (orchestrator, 2026-11-25): feasible. UZDoom's weapon sprite layers have a writable caller, so two
weapons' states can run side by side. Two routes:
- **Generic akimbo host (lean, medium):** a Doomerfall weapon that draws both pistols (left one mirrored) and fires
  each with its own damage, rate, spread, sound, ammo, magazine and material bonus read from a table. Works for stock
  Doom and DRLA alike, but drops each DRLA pistol's own scripted behavior (unique effects, mod packs, special reloads).
- **Truly independent pistols (high):** each real pistol runs its own states on its own layer. DRLA's pistol code
  assumes it is the one ready weapon (DRLA `Pistol.txt` is 919 lines with about 290 inventory, script, mod and reload
  checks; ACS `GetWeapon()` reads only the ready weapon), so it needs an engine shim and per-pistol fixes and tests.
Also needed either way: Doom holding two guns at once (today it holds only the active one), both magazines through
save and load, a second ammo readout, reload rules, and leaving akimbo when a non-pistol hotkey is used.
