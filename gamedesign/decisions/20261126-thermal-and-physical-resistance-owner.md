## 2026-11-26: Thermal damage, and Frost resistance becomes physical resistance

- **Verdict:** Owner decided.
- **Answer:** Nothing deals Frost damage to the player anymore. Fire damage becomes Thermal damage (it would also
  cover cold, should anything ever deal it), and Fire Resistance becomes Thermal Resistance. Frost resistance instead
  gives physical resistance equal to 1/5 of it, capped at 25%, multiplied with other sources (armor and so on). Armor's
  damage reduction is lowered a little to compensate. A Nord gets about 10% physical resistance. Frost spells stay
  (Destruction is the one rare frost source, and that is not damage the player takes).
- **Owner's words:** "keep it but it's physical resistance, weaken armor a little, players would need some physical
  resistance as well, physical resistance is multiplicative with other sources, it caps at 25%, physical resistance =
  1/5 of frost resistance ... being a Nord = 10% physical resistance". "Nothing deals frost damage anymore. Fire is
  now Thermal damage in case we ever deal frost damage at some point and something resists it. Fire Resistance is now
  Thermal Resistance." "Keep in mind we're fighting doom monsters and Destruction magic with Frost is the one rare
  exception ... but even then that's not damage the player takes".
- **Product owner's reading, to confirm:** the Baron's and Hell Knight's "half frost" become half Thermal.
- **Later the same day (owner):** everything Frost converts to physical at 1/5: the race trait (the Nord's +30 is
  the only race Frost bonus, so a Nord gets 6%; if Nords turn out to have no Frost bonus, they get no physical
  resistance), class traits, Resist Frost potions and spells, and spellmaker Frost resistance. All sources add up and
  the total caps at 25%. Baron and Hell Knight projectiles are Magic damage (Daggerfall's `Elements.Magic`, verified
  in `DFCareer.cs:505-513`: Fire, Frost, DiseaseOrPoison, Shock, Magic), replacing the half shock, half frost split.
  Owner: "Yes resist frost is Resist physical at 1/5 magnitude same for spell making and resist frost spells if they
  exist. Everything gets converted at 1/5th. Barons and HKs are now Magic damage".
- **2026-11-27 (owner):** the armor DR table in `work/notes/20261127-armor-dr-table.md` (Daedric 80% at L1 to 72% at
  L30, lower tiers strong at low levels) and the damage proposal are approved; all factors multiply. "Very good let's
  run with this proposal for damage". Area-level-dependent DR is a starting system, to revisit.
