## 2026-11-24: After a load, should Daggerfall's ammo count win over Doom's when they disagree? [20261124-075147]

- **Verdict:** Owner answered (2026-11-24).
- **Answer:** Split ownership. Doom owns the live ammo its guns spend (the loaded tier, and magazines), because it has
  the most accurate picture of it, and reports every change, losses included. Daggerfall owns all other ammo and keeps
  an exact mirror of Doom's live counts. On a normal load Doom's live count stands; if Doom's half cannot be restored,
  Daggerfall's mirror is used. `architecture.md` updated.
- **Rests on:** AGENTS.md: Daggerfall owns saves and "most permanent game state". `gamedesign.md`: "Daggerfall can
  tell Doom that the player has more than Doom's max ammo".
- **Challenge:** The merged ammo card made "Doom's ammo ... the live counter" (CHANGELOG `0699292`). The max-ammo line
  is about caps, not which engine wins a conflict. Which engine is authoritative on load is part of the save and load
  sync hurdle, a consequential architecture decision.
