# Damage magic rework

**Waiting on:** owner design. The owner set this apart from non-damage magic on 2026-11-25.

Daggerfall's damage spells (Destruction: Damage Health/Fatigue/Spell Points, Continuous Damage, Disintegrate, Drain and Transfer attributes, Vampiric) were balanced against Daggerfall melee. DRLA weapons such as a ~1600 RPM minigun out-damage any stock spell by orders of magnitude, so stock damage magic would never be worth casting. The owner expects to rework it completely.

Facts to start from:

- Stock effects live in `daggerfall-unity-master/Assets/Scripts/Game/MagicAndEffects/Effects/Destruction/`. Damage is rolled per effect from the spellmaker's base + per-level dice, with elements (fire, frost, shock, poison, magic) and delivery (caster, touch, target at range, area at range, area around caster).
- Daggerfall's resistances and tolerances are already in the Doom sheet (`DFB_SHEET_RESIST_*`, `DFB_SHEET_TOLERANCE`), so element rules can apply on the Doom side.
- The skills proposal (`work/notes/20261125-skills-armor-proposal.md`) leans toward Destruction also covering energy weapons, which couples spell and energy-gun balance.

Open questions for the owner:

1. What is damage magic for when guns exist: burst, crowd control, ammo-free sustain, anti-monster-class (e.g. undead, daedra), or something else?
2. Do damage spells scale with area level, skill, or both, to stay relevant against slaughter-map packs?
3. Which stock effects are cut, kept, or converted (Drain/Transfer attributes, Disintegrate, Damage Fatigue, Damage Spell Points)?

Owner decisions (2026-11-25):

- Damage spells and new effects may cost under one magicka point per target; see "Fractional magicka".
- Dispel Undead and Dispel Daedra left this plan for `work/future-ideas.md`.
- Drain and Transfer "could still work". Facts: Drain lowers one of the target's attributes until healed; Transfer does the same and raises the caster's same attribute by the amount taken (Transfer Health instead damages the target and heals the caster each magic round). Both target others only. Doom monsters have no attributes, so on monsters each attribute needs a Doom meaning (for example Strength to monster damage, Speed to monster speed) for the drain half; the caster's half already works in Daggerfall.
