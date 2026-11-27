## 2026-11-26: May time-passing services run inside Doom while Doom's monsters stay frozen? (recheck of 2026-11-24) [20261124-002144]

- **Verdict:** Follows clearly, as interim behavior.
- **Answer:** Yes. Paid services that pass time advance Daggerfall's clock while Doom stays frozen, until the owner
  designs anything that moves monsters through skipped time.
- **Rests on:** `gamedesign.md`: "The calendar ... govern the world" (Daggerfall owns time); "We intend to recreate all
  of Daggerfall's systems (owner, 2026-11-24)"; milestone hurdle 4 in `AGENTS.md`: Daggerfall's 3D world is off while
  its logic and 2D UI keep running. Daggerfall's own time skips do not move monsters either.
- **Options struck:** "Block services while in Doom": they are Daggerfall systems the design keeps, and with
  Daggerfall's 3D world off they can only be reached from Doom. "Simulate monsters during the skip": that is a new
  system, and the related off-window monster question is on hold by the owner, so it cannot be chosen here. One option
  is left for now.
- **Challenge:** The old challenge feared a tavern room could bypass the rest block. It cannot: in Daggerfall, renting a
  room only grants permission, and the actual rest still goes through the rest menu, which refuses when enemies are near
  (`DaggerfallRestWindow.cs:403`), and the owner made rest in Doom "exactly as in Daggerfall". Frozen monsters during a
  skip do not break object permanence; nothing appears or vanishes. Whether monsters should ever act during skipped time
  stays with the owner's on-hold off-window question and is not decided here. Upgraded from Leans to Follows clearly
  (interim).
