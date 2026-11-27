## 2026-11-26: Skill XP rate (owner answer to the skillresearch 02 proposal)

- **Verdict:** Owner decided.
- **Answer:** 1 Skill XP per 100 HP of damage, summed across all enemies. Overkill gives nothing: each enemy counts at
  most its max HP. Doom accumulates the damage and the remainder below 100; the remainder is not saved. XP reports to
  Daggerfall must not spam the message bus. The same rate applies at every area level. Prices are still open.
- **Owner's words:** "1XP per HP everywhere. Overkill doesn't give xp it's up to max enemy hp of damage. How much XP
  stuff costs is the real question, it will be a lot. These numbers will get big. very big. ... Let's call it 1xp per
  100hp damage total dealt across alll enemies if that's not hard to do as that just makes the numbers less crazy. we
  don't need to save/load the remainder. doom would keep track of that and accumulate all the damage the player deals.
  one other thing is we do need to be careful not to spam the message bus with XP gains we should do something smart
  with that."
- **Rests on:** `work/notes/20261126-010200.md` option A, scaled by 1/100.
