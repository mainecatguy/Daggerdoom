# Damage

Game design rules for how damage is calculated. Owner decisions are dated. Proposals that are not decided are marked.

## Who owns damage bonuses

- Daggerfall tabulates and manages damage bonuses (owner, 2026-11-24). See also "Damage and resistances" in
  `gamedesign.md`: Daggerfall controls damage, and DRLA keeps its resistance system.

## Ammo material bonuses

- Each ammo material tier has a damage bonus (owner, 2026-11-24). The values are still being decided.
- **Material bonuses multiply with other bonuses,** such as future skill-based bonuses, rather than adding to them
  (owner, 2026-11-24). For example, a +100% material and a +20% skill bonus give 2.0 x 1.2 = 2.4 times base damage.

## Ammo tags

- Ammo can carry tags such as `reduced_noise`. While that ammo is loaded, Daggerfall shows its tags as a kind of
  player state, and clears them when the weapon changes (owner, 2026-11-24).
- An ammo's in-game description states what it does, including its bonus (owner, 2026-11-24).
