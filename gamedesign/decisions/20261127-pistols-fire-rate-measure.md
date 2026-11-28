## 2026-11-27: Pistols 25 and 75 fire-rate multipliers: how is fire rate measured, on which gun state, and which rates are fast and slow? [20261127-115755]

- **Verdict:** Leans (measure) / Not determined (unmodified or modded gun) / Not determined (fast and slow cut-offs and
  scaling).
- **Answer:** Measure: probably the tics between shots with the trigger held, leaving out magazine reloads, counted the
  same way for every pistol. Whether it is read from the unmodified gun or from the gun as currently modded, and which
  tic counts are "fast" and "slow" and how the multipliers scale between them, go to the owner. Data for the owner: the
  build measures stock Pistol, DRLA Pistol and Handcannon at 19 tics and Marksman Pistol at 16, so the suggested fast 10 /
  slow 30 puts all of them in the middle (about x2.05-2.2 at 25). The research note counted Pistol 14 and Handcannon 16
  (to `A_ReFire`), so the counting point differs by a few tics and must match whatever cut-offs are chosen. The research
  model used fast 4 / slow 35 and found the combined 25 x 75 multiplier spans only about 3.75-4.6 whatever the anchors, so
  the cut-offs matter mostly between skill 25 and 74.
- **Rests on:** Card 05 (owner design): "Fast-firing pistols deal about 2.5x damage, scaling down to 1.5x for slow-firing
  ones. This multiplies damage only. The gun does not fire faster." Card 05 holds "which fire rates count as fast and
  slow, and how the multipliers scale between them" for the owner. Inference for the measure: "fire rate" is shots over
  time, and tics between shots is the same quantity in Doom's unit; leaving out reloads keeps the 20/40/60% faster
  reloads (same card) from changing the multiplier, which the card keeps separate from rate.
- **Challenge:** Linear in tics and linear in shots per second give different numbers, so the unit is not a minor detail;
  that difference is folded into the open scaling question, which keeps the measure itself at Leans. Live versus
  unmodified: Systemic cause and effect (owner, 2026-11-27: systems "are allowed to interact") hints at live, but
  "allowed" does not strike reading the base gun, and the two differ in what the player sees when modding. No option is
  struck. Not Deferred: Daggerfall already sends the two cut-offs; no new system. Kept as answered.
