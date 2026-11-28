## 2026-11-27: Whose kills roll the Luck drop?

- **Verdict:** Follows clearly / Leans / Not determined.
- **Answer:** Follows clearly: summoned and revived monsters never roll. Leans: every placed-monster death rolls whoever
  killed it (player, infighting, faction fights, hazards), as built. Not determined: whether town guard kills roll. They
  stay "never" for now, because guards are bot players and not monsters.
- **Rests on:** `gamedesign.md` Loot & Economy: "Summoned and resurrected monsters drop nothing on Daggerfall maps", and
  `20261125-unplaced-monster-loot.md`. The lean rests on World logic and Systemic cause and effect: what a monster drops
  when it dies does not depend on who killed it, and infighting is a system interaction the design favors. That is
  inference, because Luck is the player's attribute and could be read as applying only to the player's own kills.
- **Challenge:** Is a player stat applying to kills the player did not make a stretch? A Luck bonus is arguably about the
  player's fortune, which a hazard kill elsewhere could still count for, so the build is not clearly wrong. But
  "player-only" is not struck either. Guard bots carry Daggerfall's own NPC loot, and adding Luck ammo to them is a new
  rule the design does not give. The performance concern in the killdrops report (up to about half of all kills leaving
  pickups at Luck 100) is engineering, not design. Kept.
- **Owner question:** Luck drops now roll on every placed-monster death, whoever killed it, and never on guards. Should
  only your own kills count, and should guard kills roll?
