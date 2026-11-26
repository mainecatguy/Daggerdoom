## 2026-11-24: Should ammo touch pickups be refused when the player is over Daggerfall's weight limit? [20261124-075147]

- **Verdict:** Not determined (downgraded from Leans in challenge).
- **Answer:** None. It goes to the owner.
- **Rests on:** `gamedesign.md`: "There may be limits on how much ammo the player can carry. That is a future system."
  Also the Movement row: "modified by Daggerfall's encumbrance".
- **Challenge:** The "future system" line is about ammo-specific caps, not weight. Doom items taken with Use are
  already "checked against Daggerfall's carry limit" (CHANGELOG `e97c3c5`), so consistency argues for refusing. The
  documents point both ways.
