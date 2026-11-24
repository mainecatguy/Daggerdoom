# Handle Arch-vile resurrection

**Waiting on:** mook packs and death tracking, then owner design.

**Current rule (owner, 2026-11-23):** Arch-viles keep their resurrection, and no monster is excluded or changed for it. Doom has no way to tell Daggerfall that a mook came back to life, so Daggerfall does not know. A revived mook may be counted dead by Daggerfall, and it may not return after a save and reload.

Research how much of a problem this is for the proposed architecture, then propose better handling for the owner. Cover:

- **Normal raises:** the corpse keeps its old ID and team TID, but copies the Arch-vile's hatred (`UZDoom/src/playsim/p_enemy.cpp:2917`).
- **DRLA's Nightmare and Technophobia Arch-viles:** the corpse dies again and a new `*Reborn` actor replaces it (for example `DoomRL_Monsters_Beta_7.3/actors/monsters/uv/Imp.txt:125-141`). That actor has no mook identity at all.
- **Effects on:** the saved list of dead mooks, quest kill counts, "most of the pack is dead" death events, loot drops, factions in Civil War encounters, and stock Doom's Arch-vile when DRLA is absent.
- **Possible handling:** report revives to Daggerfall, treat revived monsters as temporary, or limit what can be raised.

Background: `work/notes/20261123-205402-fractal-encounter-variety.md`, sections 6.2 and 7.4.
