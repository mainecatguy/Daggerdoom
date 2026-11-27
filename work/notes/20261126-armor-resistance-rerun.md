# Armor and resistance rerun under the 2026-11-26 scheme

Research only. Inputs: `gamedesign/decisions/20261126-thermal-and-physical-resistance-owner.md`,
`20261126-monster-damage-classes-owner.md`, `work/notes/20261126-monster-damage-types.md`, and my
`20261126-armor-report.md`. Numbers come from a small script that follows the formulas below.

## 1. Armor DR (physical only, no shields)

**A** = Daggerfall's live armor points (100 minus each part's live value), as a body-part weighted average (out of 20).
**L** = area level.

> **DR = 68% x (A / 105)^p**, with **p = 0.75 + 0.05 x L**, clamped to 0.8-2.0.

- The ceiling is 68%. The earlier curve averaged 67%. I add about 3 points because shields are gone (a Round Shield
  was worth about +5 A) and take about 2 off to make room for physical resistance.
- Daedric always gives 68%. Lower tiers lose protection as area level rises: cheap armor is decent in low areas and
  poor in deep ones. The swing is much milder than Daggerfall's, where Steel went from 51% to 0%.

| Suit (A) | L1 | L5 (low) | L15 (mid) | L25 (high) |
|---|---|---|---|---|
| Leather (15) | 14% | 10% | 4% | 1% |
| Chain (30) | 25% | 19% | 10% | 6% |
| Iron (35) | 28% | 23% | 13% | 8% |
| Steel (45) | 35% | 29% | 19% | 12% |
| Elven (55) | 41% | 36% | 26% | 19% |
| Dwarven (65) | 46% | 42% | 33% | 26% |
| Mithril (75) | 52% | 49% | 41% | 35% |
| Ebony (85) | 57% | 55% | 50% | 45% |
| Orcish (95) | 63% | 62% | 59% | 56% |
| Daedric (105) | 68% | 68% | 68% | 68% |

Wear at 1/30 of Daggerfall's rate is about (damage / 300) condition per physical hit. Keep the fraction between hits,
or most hits wear nothing.

## 2. Resistances

**Physical** (Frost sources at 1/5, added up, cap 25%, multiplied with armor):

| Source | Gives |
|---|---|
| None | 0% |
| Class Resistant to Frost (+25) | 5% |
| Nord race (+30) | 6% |
| Class Immune to Frost (+50) | 10% |
| Resist Frost potion (chance 100, `ElementalResistance.cs:98`) | 20% |
| Spell or enchantment at chance X | X / 5 |

**Thermal, Shock, Poison, Magic.** Daggerfall gives a saving throw, not a percentage. T = 50, plus race (+30 resist,
-25 low, -50 weak, 100 immune), plus class (+25 resist, +50 immune, -25 low, -50 weak), plus biography (Magic, Poison,
Disease), clamped 5-95. At 100 or more the hit is fully negated. A roll at or under T cancels the hit, but within 20
of T the cut is only partial (`FormulaHelper.cs:1446-1560`). The expected fraction of damage taken is
F(T) = (110.5 - T) / 100 for T from 20 to 95.

**Proposal: an expected-value multiplier relative to a normal character**, m = F(T) / F(50). There is no free
baseline. An ordinary character takes full damage, just as an unarmored one does. Willpower's `MagicResist` is left
out because Willpower is already the final multiplier.

| Tolerance | T | DR per hit |
|---|---|---|
| None | 50 | 0% |
| Class Resistant | 75 | 41% |
| Race resist (only Breton Magic in stock races, `RaceTemplate.cs:191`) | 80 | 50% |
| Low tolerance | 25 | -41% (takes x1.41) |
| Critical weakness | 0 | -64% |
| Immune, or race + class resist | 100+ | 100% |
| Resist potion: Fire and Shock are chance 100; Poison is 5 + 19 per level | - | 100% while active (Poison: that chance) |

A spell or enchantment at chance c multiplies damage taken by (1 - c), on top of the above.

**Share of incoming damage by type.** These are guesses from actor counts in the damage-types note, after the
owner's reclassification, not measured damage.

| Army | Physical | Thermal | Shock (Plasma, proposed) | Magic | Poison |
|---|---|---|---|---|---|
| Stock Doom | ~65% | ~20% (Imp, Mancubus, half Caco, Archvile) | ~5% (Arachnotron) | ~10% (Baron, Hell Knight) | 0 |
| DRLA Monsters | ~65% | ~15% | ~12% | ~5% | ~3% |
| Colourful Hell (Ice counts as Thermal) | ~20% | ~38% | ~30% | ~7% | ~5% |

Physical resistance and armor matter most against stock Doom and DRLA. Thermal and Shock matter most against
Colourful Hell. Poison barely matters anywhere.

## 3. Combined examples (DRLA mix; Willpower x = 1.2 - 0.4 x WP / 100)

| Character | Physical | Other types | Willpower | Physical hit taken | Damage taken overall |
|---|---|---|---|---|---|
| Nord in Steel, L5, WP 40 | 29% armor, x 6% resist = 33% | none | x1.04 | 70% | **82%** (18% reduction) |
| Breton mage in Leather, L15, WP 70 | 4% | Magic 50% | x0.92 | 88% | **87%** (13% reduction) |
| Daedric tank, L25, WP 50, Nord + Resist Frost potion | 68% armor, x 25% cap = 76% | none | x1.00 | 24% | **51%** (49% reduction) |

The Daedric tank keeps only 15% overall reduction against Colourful Hell, because most of that army's damage is
not physical.

## 4. Forks for the owner

1. **Armor DR cap.** Daedric alone is 68%, and physical resistance takes it to 76%. Cap physical at 75% (lean, about
   the same as today) or 66%? At 66%, Daedric's armor ceiling drops to about 60% so it still sits under the cap.
2. **Elemental baseline.** Relative, as proposed: a normal character takes full damage. Or Daggerfall's absolute
   value: everyone avoids about 40% of all Thermal, Shock and Magic damage, and race resist reaches 70%. Lean
   relative.
3. **Area-level swing.** p = 0.75 + 0.05 x L as above (Steel 29% at L5, 12% at L25)? Or gentler, 0.05 changed to
   0.03 (Steel 29% to 17%)? Lean as above.
