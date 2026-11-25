# Player HP on Doom's scale

**Waiting on:** the owner rethinking the HP formula. A stopgap normalization toward 100 is being chosen first
(owner, 2026-11-24).

Problem: Doom's damage and health values assume a player with about 100 HP. Daggerfall's starting max HP is
25 + the class's HP per level, about 31 to 40 at level 1 (`FormulaHelper.RollMaxHealth`), so Doom hits are about 3x
too strong.

Owner direction (2026-11-24):
- Change Daggerfall's own HP numbers (Daggerfall owns HP), not a display or bridge conversion.
- Everything that comes from Daggerfall scales with it: max HP, level-up gains, heal and damage spells and potions,
  rest and regeneration, poison and disease drain, and any later Daggerfall-side damage. Percent effects (temple full
  heal, restore to max) need nothing.
- Doom damage stays Doom's. Almost all weapons are Doom weapons.

Open questions:
- A flat 3x gives about 93 to 120 at level 1 but about 830 for a level 20 warrior. The level curve has to be checked
  against encounter point growth. The owner expects to rethink the formula.
- Doom health pickups (stimpack 10, medikit 25) and armor stay flat, so they shrink as max HP grows. Keep them flat,
  or heal a share of max HP?
- Existing saves store max HP: apply only to new games, or recompute on load?

Discussion so far (owner, 2026-11-24, undecided; owner is sleeping on it):
- Class must stop dictating HP: too strong in this mod. Stock HP per level ranges from Mage 6 to Barbarian 25 (read
  from `CLASS*.CFG`). At 50 Endurance, level 20 is about 117 for a Mage and 406 for a Barbarian. In Daggerfall the
  counterweight was magicka and spells, which Doom combat does not have yet. HP-heavy classes also have the lowest
  advancement multipliers (Barbarian 0.64, Mage 1.04), so they also level faster.
- Endurance order matters in stock: each level-up adds floor(END/10) - 5 at the END of that moment, never
  recalculated.
- Forms considered: power roots 100 x (h/35)^p (p = 1/1.4, 1/2, 1/3, 1/4); square root at high levels with a low-level
  nerf, 17 x sqrt(h - 15) leading; and a fresh formula, 3 x level + 2 x END (scale fits; Endurance outweighs level).

Implementation hint: Daggerfall Unity formulas have an override hook (`FormulaHelper.TryGetOverride`, for example
`RollMaxHealth`, `CalculateHitPointsPerLevelUp`, rest recovery), so most of it can live in Doomerfall code. Damage
from Doom over the bridge skips the scale. Related: [Megasphere gives max HP plus 100](megasphere-max-plus-100.md).
