# Monster damage types (feeds `work/refinement/armordr-01.md`)

Method: grep of `DamageType` in UZDoom `wadsrc/static/zscript/actors/doom/` and a per-actor scan of `damagetype` in the DRLA Monsters 7.3 and Colourful Hell 1.04 DECORATE (`GameMods/ExtractedData/`). Counts are numbers of actors or states that name the type, not damage dealt. I did not measure damage shares per type. Shares below are rough guesses.

## Stock Doom (UZDoom)

Monster attacks name no damage type. Imp, Demon, Zombieman, Shotgunguy, Chaingunner, Cacodemon, Baron, Hell Knight, Lost Soul, Mancubus, Arachnotron, Revenant, Spider Mastermind, Cyberdemon and Pain Elemental all deal Normal. The Cyberdemon rocket explosion is Normal too.

The only exception is the Archvile. `A_VileAttack` defaults `damagetype = "Fire"` (`archvile.zs:149`). The blast on the player is Fire, and the direct 20 damage is untyped unless the VAF flag is set. The other named types in the stock zscript are player weapons only (Grenade, BFGSplash).

Army share: about 98% Normal and about 2% Fire (Archvile only).

## DRLA Monsters 7.3

| Type | Count | Used by (examples) | Share (guess) | Proposed class |
|---|---|---|---|---|
| none (Normal) | most attacks | basic projectiles, hitscan, direct melee not routed through a puff | about 50-60% | physical |
| Plasma | 48 | Deathweaver, Lord of the Abyss, DeVile stun shot, Cacobyss explosion, Technophobia drops | about 10-15% | shock (energy) |
| Fire | 44 | Magmabus fireballs and flamethrower, Nightmare boss fireball, Technophobia missiles, Deathweaver suicide | about 15% | fire |
| Melee | 16 | blunt and weapon puffs, Cyberdemon, Lost Soul, Wildcard boss | about 10% | physical |
| Bullet | 2 | enemy bullet puff | about 5-10% | physical |
| Piercing | 4 | Mastermind bullet puff, Abominant gravity pulse | about 3% | physical |
| Radiant | 4 | Abominant pulses, Watcher blast | about 2% | magic |
| Mindrape | 6 | DeVile copy attack, Nightmare Mastermind dark aura, Spider Overmind mind attack | about 2% | magic |
| Mysterious | 2 | anti-telefrag, TechVile vortex | under 1% | environment (telefrag) or magic |
| Nulldamage | 8 | LOS checkers, beam terminators | 0 (no damage) | ignore |

Test actors named `RLTestGC*` (Acid, Tiberium, Ice, Lightning, Breath, Manuel, Supershoelaces and so on) are debug and do not appear in play. Ice, Lightning and Acid come from there, so they are not real monster damage.

## Colourful Hell 1.04 (counts are actors or states naming the type)

| Type | Count | Used by (examples) | Share (guess) | Proposed class |
|---|---|---|---|---|
| Plasma | about 191 | Baron and Abyss Baron lightning and bolts, vile bolts, power bombs | about 30% | shock |
| Fire | about 174 | fire viles, Fire shotgun guys, comets, breath attacks, flares | about 30% | fire |
| Melee | about 73 | Vile ground spikes, rock drops, Baron rock, soul charge | about 10% | physical |
| Ice | about 44 | Ice viles, Ice seeker Baron, Cyan Baron bombs | about 8% | frost |
| Poison | about 20 | Greenies, puddles, needles, slime ball, gas | about 5% | poison |
| Lightning | 4 | Storm strike and storm bolts | about 1% | shock |
| Psychic custom types | about 11 | `GetOutOfMyHeadCharles` (6: Abyss mind spikes, psychic tangle), `Dimp` (5: Void field, mind bone) | about 2% | magic |
| Hornet | 2 | Black Lost Soul | under 1% | poison (sting) or physical |
| Typos and odd | 3 | `meelee`, `abysspe`, `normal` | under 1% | treat `meelee` as physical, `normal` as physical, `abysspe` as magic |
| none | the rest | plain projectiles and hitscan | about 10% | physical |

## Proposed classes (summary)

- **Physical (armor applies):** Normal, Melee, Bullet, Piercing, Hornet, plus all explosion and projectile damage with no type.
- **Fire:** Fire.
- **Frost:** Ice.
- **Shock:** Plasma, Lightning. Plasma is a judgment call: it is an energy weapon with no direct Daggerfall equivalent, so it could be magic or physical instead. The owner decides.
- **Poison:** Poison, Hornet if kept separate.
- **Magic:** Radiant, Mindrape, `GetOutOfMyHeadCharles`, `Dimp`, `Abysspe`.
- **Environment:** Mysterious (telefrag), plus any slime or lava floor damage, which is not a monster attack.

Open points:

- Types are free-form names, so mods can add new ones. Map unknown names to physical by default.
- Plasma is the largest typed share in both mods. Whether it counts as shock decides how much DRLA and Colourful Hell damage armor ignores.
- Not checked: DRLAX and Schism, and the untyped share was estimated rather than counted.

## Daggerfall's damage types and defenses (from code)

- **Elements** (`DFCareer.Elements`, `API/DFCareer.cs:505`): Fire, Frost, DiseaseOrPoison, Shock, Magic, plus None. Spell-side `ElementTypes` (`MagicAndEffectsEnums.cs:36`) has the same five (Fire, Cold, Poison, Shock, Magic). `DFCareer.EffectFlags` adds Paralysis and Disease as resist-able effects.
- **Physical** is not an element. Weapon hits are reduced by armor (armor value) and the target's material/silver rules (`FormulaHelper.cs`: `MinMetalToHit`, silver weapons vs. undead and similar). Special weapon-side damage also exists: `SunDamage` and `HolyDamage` ability flags on some monsters.
- **Defenses against an element**, all in `FormulaHelper.SavingThrow` (line 1446):
  1. Magic-effect resistance for that element: a flat chance roll that negates the hit.
  2. Career tolerance per type (Paralysis, Magic, Poison, Fire, Frost, Shock, Disease): Resistant +25, Immune +50, Low tolerance -25, Critical weakness -50 to a base 50% saving throw. Race adds +30 resist, 100 immune, -25 low, -50 weakness. Biography modifiers apply to Magic, Poison and Disease.
  3. Willpower adds `MagicResist` (willpower / 10). Result is clamped 5-95 (100 or more is full immunity). A successful save halves damage or duration, prorated near the roll.
- So there is no per-element damage-multiplier table: a resistance is a saving-throw chance that reduces the hit, not a fixed percentage cut.

## Proposed mapping of Doom monster attacks to Daggerfall types

Rule: unknown or missing damage names default to **physical** (armor applies). A split attack ("half X, half Y") deals each half as its own type. Owner's fixed examples are marked (fixed).

| Doom attack / name | Daggerfall type | Reason |
|---|---|---|
| Imp fireball (fixed) | Fire | Owner decision; it is a burning ball. |
| Cacodemon ball (fixed) | 50% Fire, 50% Shock | Owner decision: half fire. The other half is my guess: lightning-green energy ball, so Shock. Owner to confirm. |
| Baron / Hell Knight projectile (fixed) | 50% Shock, 50% Frost | Owner decision for Baron. Hell Knight shares the same green ball, so I'd copy it. |
| Archvile fire blast (stock `Fire`) | Fire | Already typed Fire in stock Doom. |
| Archvile direct hit | Physical | Untyped in stock Doom. |
| Mancubus fireballs | Fire | Flame cannon visuals. |
| Revenant homing missile | Physical | Rocket explosion; no elemental theme. |
| Lost Soul charge, Demon/Spectre bite, melee claws | Physical | Bodily impact; armor should stop it. |
| Zombieman, Shotgunner, Chaingunner, Spider bullets | Physical | Bullets. |
| Cyberdemon and Pain Elemental explosions | Physical | Rocket blast. |
| Arachnotron plasma | Shock | Plasma maps to Shock (see Plasma below). |
| DRLA Fire | Fire | Direct name match. |
| DRLA Plasma | Shock | Energy has no Daggerfall equivalent; Shock is closest. Owner to confirm. |
| DRLA Melee, Bullet, Piercing, none | Physical | Armor. |
| DRLA Radiant | Magic | Holy light, not a bodily hit. |
| DRLA Mindrape | Magic | Mental attack. |
| DRLA Mysterious (telefrag) | Environment, ignore resistances | Not a monster attack. |
| DRLA Nulldamage | none | Zero-damage helpers. |
| Colourful Hell Fire / Ice / Poison / Lightning | Fire / Frost / Poison / Shock | Direct name matches. |
| Colourful Hell Plasma | Shock | Same as DRLA Plasma. |
| Colourful Hell Melee, Hornet | Physical | Hornet could be Poison (sting); I'd leave it physical. |
| Colourful Hell `GetOutOfMyHeadCharles`, `Dimp`, `Abysspe` | Magic | Psychic and abyss attacks. |
| Colourful Hell `meelee`, `normal` | Physical | Typos and default. |
| Any other name | Physical | Default rule. |

Implementation note: since Daggerfall has no fixed percent cut, the owner's "Daggerfall's resistances play a part" means either a saving-throw roll per hit (Daggerfall's own way, noisy for a fast shooter) or a flat percentage derived from the same tolerance numbers (smooth, but a new rule).
