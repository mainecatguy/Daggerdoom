## 2026-11-25: Are DRLA's kill-counter pickups exempt from "summoned and revived monsters drop nothing"?

- **Verdict:** Leans exempt. **Overruled by the owner (2026-11-26): not exempt.** Summoned and revived kills do not
  count in the PDA bestiary; regular kills do. The owner is fine with that.
- **Answer:** Exempt `RLMonsterKillIncrementer` and its subclasses, so summoned and revived kills still count toward
  DRLA's kill stats, as in stock DRLA.
- **Rests on:** the owner's ruling "2026-11-25: Which monsters drop loot when they were not placed by Daggerfall?",
  which is framed as a loot question. `MonsterKillCounters.txt`: the counters are "USED BY THE PDA TO KEEP TRACK OF
  KILLS, AND LEARN ENEMY STATS". They are invisible `TNT1` items with no pickup message. In ExtractedData, `KillCounter`
  is referenced only by the DRLA Monsters actor files and DRLA Arsenal's `ACS_PDA.acs` and `bestiary.pdap`. DRLA's
  danger level reads the separate `RLDangerLevel` item, so the counters do not feed it.
- **Challenge:** The ruling's answer says "drop nothing", not "drop no loot", and the owner may have meant it
  literally. Exempting the counters lets a Pain Elemental's endless Lost Souls farm bestiary unlocks, but stock DRLA
  already allows that, and it gives no gear or loot. No object appears or vanishes in the world, nothing scales, and no
  Daggerfall loot rule is touched. The literal wording keeps this a lean, not Follows clearly. Kept as Leans.
