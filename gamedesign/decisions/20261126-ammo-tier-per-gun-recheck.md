## 2026-11-26: Should the loaded ammo tier belong to each gun rather than each ammo type? (recheck of 2026-11-24) [20261124-101258]

- **Verdict:** Follows clearly.
- **Answer:** The loaded tier belongs to each gun, as merged at `3805d1e`.
- **Rests on:** `gamedesign.md`, Ammunition: "A system will let the player change the type of ammo loaded in a gun" and
  "A DRLA gun's loaded magazine is part of the gun and travels with it" (owner, 2026-11-24).
- **Options struck:** "per ammo type": a magazine that travels with its gun keeps the rounds it was loaded with, so a
  per-type tier would make a stored or dropped gun fire rounds of a tier it was never loaded with. One option is left.
- **Challenge:** The magazine line is about DRLA guns; stock Doom guns have no magazine and draw straight from the pool,
  so for them per type would also work and is simpler for the player. But the design words the choice as ammo "loaded
  in a gun", one gun at a time, and splitting stock and DRLA guns into two rules would add a rule the design does not
  contain. Kept, upgraded from Leans to Follows clearly.
