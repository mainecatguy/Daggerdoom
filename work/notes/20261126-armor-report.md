# Armor: Daggerfall's system and a damage-reduction port to Doom

Owner's request (2026-11-26): about as protective as in Daggerfall, but as damage reduction instead of a chance to
avoid. Research only; nothing changed. This builds on section 8 of `work/notes/20261125-skills-armor-proposal.md`
and corrects its table, which left out the enemy's Critical Strike bonus.

## 1. How Daggerfall Unity armor works

Paths are under `daggerfall-unity-master/Assets/Scripts/`.

- **Armor value per body part.** There are 7 parts. Each starts at 100, and lower values protect more. An equipped
  piece subtracts 5 x its material value from its own part (`Game/Entities/DaggerfallEntity.cs:595-618`). The material
  values are in `Game/Items/DaggerfallUnityItem.cs:1029-1080`: Leather 3, Chain 6, Iron 7, Steel and Silver 9,
  Elven 11, Dwarven 13, Mithril and Adamantium 15, Ebony 17, Orcish 19, Daedric 21. Armor artifacts count half.
  Below, **A** means armor points (5 x material), so a full suit gives A from 15 (leather) to 105 (Daedric).
- **Shields.** Their material does not matter. Each subtracts 5 x (Buckler 1, Round 2, Kite 3, Tower 4) from the
  parts it covers (`DaggerfallUnityItem.cs:1083-1115`, `DaggerfallEntity.cs:620-641`). The Buckler covers the left
  arm and hands, Round and Kite add the legs, and the Tower adds the head as well.
- **Hit location.** Each attack picks one part, weighted out of 20: head 2, right arm 3, left arm 3, chest 4,
  hands 4, legs 3, feet 1 (`Game/Formulas/FormulaHelper.cs:866-873`).
- **Chance to hit.** It is the attacker's skill, plus the struck part's armor value, plus the attacker's Critical
  Strike / 10, plus the Luck and Agility differences / 10, plus Adrenaline Rush, minus the target's Dodging / 4, minus
  the biography modifier, minus 50, clamped to 3-97% (`FormulaHelper.cs:799-830, 1153-1163, 1194-1224, 1236-1245`).
  An enemy's skills, including Critical Strike, are all 30 + 5 x level, capped at 100 (`Game/Entities/EnemyEntity.cs:323-331`).
  Monsters must also pass a separate reflexes roll first (`FormulaHelper.cs:658-660`). That roll does not involve armor.
- **Spells and enchantments.** *Strengthens Armor* adds 5 armor points to every part and *Weakens Armor* removes 5
  (`Game/MagicAndEffects/Effects/Enchanting/StrengthensArmor.cs:25`, `WeakensArmor.cs:25`). Only the strongest of
  each counts (`DaggerfallEntity.cs:400-416`). The *Shield* spell is not armor. It is a pool that absorbs damage
  (`Effects/Alteration/Shield.cs:60-70`). Armor never affects spells, which go through resistances instead.
- **Condition and wear.** Wear happens only when the attacker hits **with a weapon**: the struck piece, or the
  shield if it covers that part, loses (10 x damage + 50) / 100 condition (`FormulaHelper.cs:1083-1140`). A monster's
  natural attack never wears armor. Condition never changes an armor value, because values change only on equip and
  unequip, and a broken mundane piece stays on. So in Daggerfall, wear costs repairs, not protection.

## 2. What Doomerfall does today

- **Daggerfall armor has no effect in bridged play.** `DoomerfallSheet.cs:152-169` publishes the base and live value
  of each part, plus the enchantment modifiers (`DFB_SHEET_ARMOR_BASE/LIVE/INCREASE/DECREASE`). Doom's only use of
  them is a log line (`UZDoom/src/dd_bridge.cpp:751`). Doom's hits reach `Doomerfall/DoomerfallHp.cs:42-43`, which
  applies them with `SetHealth` and no changes ("no armor or scaling yet"). Daggerfall's `DecreaseHealth` path, which
  would apply the Shield spell, is skipped.
- **Doom armor.** Doom tags taken armor (`UZDoom/src/dd_items.cpp:292-294`). Stock Doom armor and DRLA bonus pickups
  become `|armor|` items, used up when used. DRLA armor and boots become `|wear|` items that "cannot be worn yet"
  (`Doomerfall/DoomerfallDoomItems.cs:39-51`). DRLA armor's role is still open in `work/backlog/drla-armor-role.md`.
  This report does not decide it.

## 3. How protective Daggerfall armor is

For a full suit, the damage it prevents is 1 - P(hit with armor) / P(hit without). This assumes equal Luck and
Agility, no Dodging, and an enemy with Critical Strike equal to its skill. The hit rate is
P = clamp(1.1 x S + 50 - A, 3, 97).

| Suit (A) | Enemy level 1 | Level 5 | Level 10 | Level 14+ | Average, levels 1-20 | Damage-weighted average |
|---|---|---|---|---|---|---|
| Leather (15) | 17% | 2% | 0% | 0% | 3% | 1% |
| Chain (30) | 34% | 18% | 0% | 0% | 8% | 2% |
| Iron (35) | 40% | 23% | 0% | 0% | 10% | 3% |
| Steel (45) | 51% | 33% | 4% | 0% | 15% | 6% |
| Elven (55) | 62% | 43% | 14% | 0% | 20% | 9% |
| Dwarven (65) | 74% | 54% | 25% | 2% | 28% | 14% |
| Mithril (75) | 85% | 64% | 35% | 12% | 38% | 25% |
| Ebony (85) | 97% | 74% | 45% | 23% | 49% | 35% |
| Orcish (95) | 97% | 85% | 56% | 33% | 58% | 45% |
| Daedric (105) | 97% | 95% | 66% | 43% | 67% | 55% |

The damage-weighted column weights each enemy level by the level, as a stand-in for its damage.

- Because hit chance adds up and is clamped, Daggerfall armor swings a lot. Against weak enemies it gives near
  immunity. From level 10 up, armor below Steel does nothing, because the hit chance is already capped at 97% and the
  armor only cuts into the overflow.
- A shield adds to the average A: Buckler +1.75, Round +5, Kite +7.5, Tower +12. Missing one piece removes that
  part's weight share: a full Daedric suit without a helmet averages A = 94.5. Strengthens Armor adds +5 and Dodging
  60 adds +15.

## 4. Proposal: damage reduction with the same average protection

**Armor points.** A = sum over parts of (weight x (100 - live value)) / 20, using the existing
`DFB_SHEET_ARMOR_LIVE`. That already includes enchantments and shields. Doom has no hit locations, so the weighted
average gives the same expected damage as Daggerfall's random part. Optionally add Dodging / 4, as in the earlier
proposal.

**Curve.** This one fits the "average, levels 1-20" column within about 4 points:

> **DR = 67% x (A / 105)^1.6**, capped at 75% from all armor sources.

| Suit | Leather | Chain | Iron | Steel | Elven | Dwarven | Mithril | Ebony | Orcish | Daedric | Daedric + Tower |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DR | 3% | 9% | 12% | 17% | 24% | 31% | 39% | 48% | 57% | 67% | 75% (cap; uncapped 80%) |

- **Order on each player hit.** Doom's raw damage, after DRLA's own resistances as now, then Daggerfall armor DR, then
  Daggerfall resistances, then the Shield spell pool, then the Willpower final multiplier (x1.2 at Willpower 0 down to
  x0.8 at 100; card `work/queue/attributes/03`), then HP. Willpower stays outside the armor cap, so the best case is
  Daedric with a Tower Shield at Willpower 100: 0.25 x 0.8 = 80% total reduction. Every hit still deals at least 1
  in 5 points of damage, so slaughter packs stay deadly. Effective HP is at most about 5x.
- **Many small hits.** Keep the fractional remainder from hit to hit, or round at random, so a 3-damage hitscan
  zombie at 67% DR deals 1 on average instead of always 1 or always 0.
- **Damage types.** To match Daggerfall, armor applies only to physical hits: melee, bullets, and physical
  projectiles. Elements and spells go to resistances, and the environment (slime, falling, crushing) ignores armor.
  See fork 2.
- **Wear.** Keep Daggerfall's formula, (10 x damage before armor + 50) / 100 condition on one part chosen by weight,
  with the fraction carried over. Protection stays full until the piece breaks, as in Daggerfall. See fork 4.
- **Engineering.** All of this can live Daggerfall-side in `DoomerfallHp`, which owns HP and already has the live
  armor. It needs Doom to send the damage type with each hit. No engine change.

## 5. Forks for the owner

1. **Curve shape.** (a) The power curve above, which matches Daggerfall's average over enemy levels 1-20. (b) Lower
   protection, matching the damage-weighted average (Daedric 55%), because strong enemies do most of the damage.
   (c) Flatter, with A / (A + 80) (the earlier lean): cheap armor matters more (Chain 27%) and Daedric matters less
   (57%). (d) Faithful by area level: plugging area level into the formula as the enemy's level brings back
   Daggerfall's swing, where cheap armor is near useless in deep areas. Lean (a).
2. **What armor stops.** Physical hits only, as in Daggerfall, or everything, as Doom armor does? Lean physical only.
3. **DRLA armor.** Its role is still the open backlog item. If DRLA armor is allowed, does it multiply with this under
   the 75% cap, or keep only its resistances and specials? This needs answering with `drla-armor-role`.
4. **Wear.** Faithful Daggerfall: only weapon hits wear armor, and broken armor still protects. Or should every
   physical Doom hit wear armor, and should a broken piece stop counting? Slaughter-scale hit counts make this an
   economy question as well.
5. **Cap.** Is 75% from armor, with Willpower on top (80% best case), the right ceiling for slaughter maps? Or
   should it be lower, around 66%?
