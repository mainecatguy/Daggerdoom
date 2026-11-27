## 2026-11-27: Several towns on one Doom map [triage G35]

- **Verdict:** Follows clearly (upgraded from Leans).
- **Answer:** Each town keeps its own town level (Daggerfall 20, Ripwych Commons 5), even on a shared Doom map.
- **Rests on:** Owner `20261126-shops-towns-restocks-owner.md`: "a town's danger level is the higher of its terrain level
  and its class level". AGENTS.md pillar: Daggerfall owns the world. `gamedesign.md`: levels are "facts about the world".
- **Challenge:** A shared map is a converter grouping, not a fact about the world; Daggerfall keeps the two as separate
  places. Using the group's maximum would let an engine artifact change a place's level. Upgraded.
