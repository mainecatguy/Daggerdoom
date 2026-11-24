# Proposal: material tier odds by area level

**Status:** proposal for the owner. Nothing is implemented. The numbers were computed with a throwaway script, and the feel of the drops has not been play-tested.

## Owner's requirements (2026-11-23)

- Use area level instead of player level.
- A Daedric result becomes a random result among all categories, biased against rarer tiers.
- Daedric stays the best category, and that reroll is the only way to get it.
- Every category gets monotonically better with level.
- **Lower tier items are always more common.** At best, a lower tier can be only slightly less common than the tier above it.
- Ammo has a Tin tier below Iron, at about -35% damage.

## What "monotonically better" means here

Every tier's own share cannot rise forever, because the shares must add up to 100%. So the rule is: **at every level, the chance of getting "this tier or better" never falls, for every tier.**

## Proposed roll

1. **Set the level's falloff.** `falloff = 0.50 + 0.40 × (level - 1) / 29`, with level limited to 1 through 30. It runs from 0.50 at level 1 to 0.90 at level 30.
2. **Roll a tier.** Each tier is `falloff` times as likely as the tier below it.
3. **Resolve Daedric.** If the roll lands on Daedric, roll once more with the same odds and keep that result. Daedric therefore requires two Daedric rolls in a row.

Ammo uses the same roll with Tin added as the lowest of 11 tiers.

This replaces Daggerfall's material table. That table cannot meet the commonness rule, because Steel is about twice as common as Iron and Elven is about twice as common as Silver.

## Weapon and armor material odds

| Level | Iron | Steel | Silver | Elven | Dwarven | Mithril | Adamantium | Ebony | Orcish | Daedric |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 50.10% | 25.05% | 12.52% | 6.26% | 3.13% | 1.57% | 0.78% | 0.39% | 0.20% | 1 in 1,046,529 |
| 5 | 44.71% | 24.82% | 13.78% | 7.65% | 4.25% | 2.36% | 1.31% | 0.73% | 0.40% | 1 in 200,214 |
| 10 | 38.13% | 23.80% | 14.85% | 9.27% | 5.79% | 3.61% | 2.25% | 1.41% | 0.88% | 1 in 33,656 |
| 15 | 31.86% | 22.08% | 15.31% | 10.61% | 7.35% | 5.10% | 3.53% | 2.45% | 1.70% | 1 in 7,398 |
| 20 | 26.04% | 19.84% | 15.12% | 11.52% | 8.78% | 6.69% | 5.10% | 3.89% | 2.96% | 1 in 2,050 |
| 25 | 20.81% | 17.29% | 14.37% | 11.94% | 9.92% | 8.25% | 6.85% | 5.70% | 4.73% | 1 in 696 |
| 30 | 16.27% | 14.64% | 13.18% | 11.86% | 10.67% | 9.61% | 8.64% | 7.78% | 7.00% | 1 in 283 |

## Ammo odds

| Level | Tin | Iron | Steel | Silver | Elven | Dwarven | Mithril | Adamantium | Ebony | Orcish | Daedric |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 50.05% | 25.02% | 12.51% | 6.26% | 3.13% | 1.56% | 0.78% | 0.39% | 0.20% | 0.10% | 1 in 4,190,209 |
| 10 | 37.93% | 23.67% | 14.77% | 9.22% | 5.76% | 3.59% | 2.24% | 1.40% | 0.87% | 0.55% | 1 in 86,987 |
| 20 | 25.47% | 19.41% | 14.79% | 11.27% | 8.59% | 6.55% | 4.99% | 3.80% | 2.90% | 2.21% | 1 in 3,650 |
| 30 | 15.31% | 13.78% | 12.40% | 11.16% | 10.05% | 9.04% | 8.14% | 7.32% | 6.59% | 5.93% | 1 in 387 |

## Checks

Exact calculation for levels 1 through 60, with levels above 30 counted as 30, for both the 10-tier and 11-tier tables:

- "This tier or better" never falls for any tier.
- Every lower tier is at least 11% more common than the tier above it.
- Daedric is the rarest tier at every level.
- A 2,000,000-roll simulation of the two-step Daedric roll at level 30 gave 0.349%, against 0.354% calculated.

## Tuning knobs

- **Starting falloff (0.50):** higher makes early areas less Iron-heavy.
- **Final falloff (0.90):** closer to 1.0 makes the endgame flatter and Daedric more common. It must stay below 1.0 for lower tiers to remain more common.
- **Level cap (30):** should follow the owner's level range research.

## Effects to judge

- Rare tiers have no hard level gates, but early odds are small. Ebony is 0.39% at level 1.
- Daedric is effectively unavailable before about level 15.
- The jump from Orcish to Daedric is large, at 7.00% against 0.35% at level 30.
