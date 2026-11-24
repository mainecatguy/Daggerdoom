# Material tier odds by area level

**Status:** design approved by the owner on 2026-11-23. Nothing is implemented. The numbers were computed with a throwaway script, and the feel of the drops has not been play-tested.

## Owner's requirements

- Use area level, never player level.
- Daedric is the best category, and its own check is the only way to get it.
- Every category gets monotonically better with level.
- Lower tier items are always more common. At best, a lower tier can be only slightly less common than the tier above it.
- Daedric is about 1 in 20 at level 30 and half of that at level 20.

"Monotonically better" means that at every level, the chance of getting "this tier or better" never falls, for every tier. Each tier's own share cannot rise forever, because the shares must add up to 100%.

## The roll

Levels below 1 count as 1, and levels above 30 count as 30.

1. **Roll for Daedric first.**
   - Levels 1 to 20: `chance = 0.025 × ((level - 1) / 19)^3`
   - Levels 20 to 30: `chance = 0.025 + 0.025 × (level - 20) / 10`
2. **If that misses, roll the lower tiers.** Each tier is `falloff` times as likely as the tier below it.
   - Levels 1 to 20: `falloff = 0.50 + 0.30 × (level - 1) / 19`
   - Levels 20 to 30: `falloff = 0.80 + 0.10 × (level - 20) / 10`
3. **Ammo** uses the same tiers and odds as weapons and armor. (owner, 2026-11-24)

## Material odds for weapons, armor, and ammo

| Level | Iron | Steel | Silver | Elven | Dwarven | Mithril | Adamantium | Ebony | Orcish | Daedric |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 50.10% | 25.05% | 12.52% | 6.26% | 3.13% | 1.57% | 0.78% | 0.39% | 0.20% | none |
| 5 | 43.92% | 24.74% | 13.93% | 7.85% | 4.42% | 2.49% | 1.40% | 0.79% | 0.44% | 1 in 4,287 |
| 10 | 36.37% | 23.35% | 14.99% | 9.63% | 6.18% | 3.97% | 2.55% | 1.64% | 1.05% | 1 in 376 |
| 15 | 29.15% | 21.02% | 15.16% | 10.93% | 7.88% | 5.68% | 4.10% | 2.95% | 2.13% | 1 in 100 |
| 20 | 22.52% | 18.02% | 14.41% | 11.53% | 9.23% | 7.38% | 5.90% | 4.72% | 3.78% | 1 in 40 |
| 25 | 18.79% | 15.97% | 13.58% | 11.54% | 9.81% | 8.34% | 7.09% | 6.02% | 5.12% | 1 in 27 |
| 30 | 15.51% | 13.96% | 12.56% | 11.31% | 10.17% | 9.16% | 8.24% | 7.42% | 6.68% | 1 in 20 |

## Checks

Exact calculation for levels 1 through 60, with levels above 30 counted as 30, for the table:

- "This tier or better" never falls for any tier.
- Every lower tier is about 11% or more common than the tier above it.
- Daedric is the rarest tier at every level.
