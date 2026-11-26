## 2026-11-25: Should DRLA's Adaptive skill variant pick be seeded from the placement id?

- **Verdict:** Deferred. **Owner decision (2026-11-25): remove DRLA's Adaptive difficulty from Doomerfall completely.**
  In the owner's words: "The world shouldn't adapt to the player, thats a game design pillar of ours."
- **Answer:** None. It goes to the owner. If the owner keeps Adaptive as DRLA built it, seeding its `Random` draws from
  the placement id leans yes, but that alone cannot make a place the same across characters.
- **Rests on:** `gamedesign.md`, Randomness: "events are fixed and not randomized per save", and the owner (2026-11-25):
  "Our randomization is always seeded deterministically." Also "The world does not scale to the player" and "Never
  adapt to the player. Randomness uses only fixed facts about the place and its area level." DRLA's
  `RLAdaptiveSpawnPicker` (`DRLAMONS_MAB.acs`, lines 43-83) starts from player 1's `RLDangerLevel` (player progress),
  forces Armageddon at danger 50 or more, and only then rolls ACS `Random`. Scope: the encounter planner spawns concrete
  classes with `NO_REPLACE` and excludes `RLAdaptive*`, so Adaptive applies only on the stock-roster fallback and on
  overworld seeds (`work/notes/20261125-220115-fixeddrops-finish.md`).
- **Challenge:** The owner's "always seeded deterministically" reads strongly, and seeding the draws is a small
  engineering change, which argues for Follows clearly on the narrow question. But the question as asked ("the same
  every time") cannot be met by seeding, because the pick depends on the player's danger level. The real fix (area
  level in place of danger, disabling Adaptive on Daggerfall maps, or exempting it as a player-chosen option) changes
  how a difficulty mode plays. Whether picking Adaptive counts as a planned "custom option" that may be random is also
  the owner's call. Kept as Deferred.
