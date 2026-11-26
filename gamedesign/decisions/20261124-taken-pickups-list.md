## 2026-11-24: Should Daggerfall keep the list of taken pickups, the way it keeps dead monsters? [20261124-002311]

- **Verdict:** Deferred (upgraded from Leans in challenge).
- **Answer:** None. It goes to the owner.
- **Rests on:** AGENTS.md pillar: "its engine needs to be the mediator and controller of most permanent game state".
  "Shared by contract: ... loot creation. Doom may drop and place its own items."
- **Challenge:** The pillar says "most", not all, and Doom-placed items are explicitly Doom's to place. Pickups
  already persist through the bundled save. Moving the record changes which engine owns a class of saved state, which
  is a save-architecture decision in `architecture.md`'s engine ownership.
