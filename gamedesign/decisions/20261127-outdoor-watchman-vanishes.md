## 2026-11-27: A shot outdoor town watchman vanishes after the blood splash [20261127-084126, 20261127-100846]

- **Verdict:** Deferred (held: inside the owner's "do not raise" guard item).
- **Answer:** None. Daggerfall turns a hit watchman into a live city watch knight, but Doom relays guard spawns only
  in interiors (`dd_guards.cpp`), so outdoors the watchman disappears. Options: (a) outdoor watch knights as Doom
  guard bots; (b) the watchman just dies and leaves a human corpse.
- **Rests on:** `gamedesign.md` Crime row: "Daggerfall governs reputation, bounties ...; hostile guards pursue and
  fight like Doom bots". Earlier decision `20261124-outdoor-guards.md` (Deferred). Backlog
  `guard-behavior-and-pathfinding.md`: "Delayed indefinitely ... Do not raise", which already holds the outdoor guard
  bot question.
- **Options struck:** (b) as a lasting answer: it replaces Daggerfall's own assault response (watchman becomes a
  hostile knight) with a death, which contradicts "Daggerfall governs" crime rules and "hostile guards ... fight like
  Doom bots". That leaves (a), which is the held item.
- **Challenge:** The vanishing breaks object permanence ("They don't disappear"), which argues for fixing it now. But the
  only fix the design allows is outdoor guard bots, the very thing the owner held. The same root cause means crimes in
  town call guards that never reach Doom (agent oversight 20261127-084126). Record the defect under the held backlog
  item. Do not put it in questions.md. Kept as Deferred.
