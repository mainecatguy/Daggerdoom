# Armor DR table, retuned to the owner's targets (2026-11-27)

Research only. This replaces the curve in `20261126-armor-resistance-rerun.md`. The owner set the targets for a full
Daedric suit and asked that lower-tier armor matter much more at low area levels.

## Formula

- **A** = Daggerfall's live armor points: 100 minus each part's live value, as a body-part weighted average out of
  20. A full suit gives Leather 15, Chain 30, Iron 35, Steel 45, Elven 55, Dwarven 65, Mithril 75, Ebony 85,
  Orcish 95, Daedric 105.
- **L** = area level.

> **Armor DR = D(L) x (A / 105)^p(L)**

- **D(L)** is the full Daedric value. It is linear between the owner's targets: 80% at L1, 78% at L5, 76.5% at L15,
  75% at L25, 72% at L30. That is -0.5 per level from L1 to L5, -0.15 per level from L5 to L25, and -0.6 per level
  from L25 to L30.
- **p(L) = 0.35 + 0.055 x L** controls how fast lower tiers fall behind. It is 0.4 at L1, so cheap armor is strong,
  and 2.0 at L30, so cheap armor is close to useless.

Total damage taken = (1 - armor DR) x (1 - physical resistance, cap 25%) x Willpower factor (x1.2 at 0 to x0.8 at
100). All three multiply. Armor and physical resistance apply only to physical damage. Willpower applies to all.

## Armor DR by set and area level

| Suit (A) | L1 | L5 | L10 | L15 | L20 | L25 | L30 |
|---|---|---|---|---|---|---|---|
| Leather (15) | 36% | 23% | 13% | 8% | 5% | 3% | 1% |
| Chain (30) | 48% | 36% | 25% | 18% | 12% | 9% | 6% |
| Iron (35) | 51% | 39% | 29% | 21% | 15% | 11% | 8% |
| Steel (45) | 57% | 46% | 36% | 28% | 22% | 17% | 13% |
| Elven (55) | 62% | 52% | 43% | 36% | 30% | 25% | 20% |
| Dwarven (65) | 66% | 58% | 50% | 44% | 38% | 33% | 28% |
| Mithril (75) | 70% | 63% | 57% | 52% | 47% | 42% | 37% |
| Ebony (85) | 73% | 68% | 64% | 60% | 56% | 52% | 47% |
| Orcish (95) | 77% | 73% | 71% | 68% | 66% | 63% | 59% |
| Daedric (105) | 80% | 78% | 77% | 76% | 76% | 75% | 72% |

A mixed or partial suit uses its weighted A. For example, full Daedric without a helmet has A 94.5, which lands
close to the Orcish row.

## Combined examples (physical hits)

| Case | Armor | Physical resistance | Willpower | Physical damage taken | Effective DR |
|---|---|---|---|---|---|
| Best case, L25: Daedric, WP 100, 25% physical | 75% | 25% | x0.8 | 0.25 x 0.75 x 0.8 = **15.0%** | **85%** |
| Best case, L30: same kit | 72% | 25% | x0.8 | 0.28 x 0.75 x 0.8 = **16.8%** | **83%** |
| Nord in Steel, L5, WP 40 | 46% | 6% (Nord) | x1.04 | 0.54 x 0.94 x 1.04 = **52.9%** | **47%** |
| Same Nord, WP 50 | 46% | 6% | x1.00 | **50.8%** | **49%** |

Notes:

- The owner already accepted that the best case can somewhat break the game: about 85% at L25, and a little less at
  L30.
- Below L5, any metal suit cuts physical damage by more than half. By L25, only Ebony and better is above 50%.
- Wear (1/30 of Daggerfall's rate, and broken pieces stop counting) and the physical-only rule are unchanged from the
  rerun note.
