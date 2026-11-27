# Energy Weapons: real damage numbers and a check of the owner's perks (2026-11-26)

Goal: give the owner real energy-weapon numbers so he can judge the proposed Energy Weapons perks (owner design,
2026-11-26). This note is analysis only. Nothing here is decided.

Sources: DRLA 1.1.5 DECORATE in `GameMods/ExtractedData/DoomRL_Arsenal_1.1.5/actors/weapons/**`. Each gun's unmodded
`Fire` path was parsed by a throwaway script, then checked by hand on the plasma rifle, BFG, railgun and Lucifer
Cannon. Stock values come from `UZDoom/wadsrc/static/zscript/actors/doom/weaponplasma.zs` and `weaponbfg.zs`
(PlasmaBall Damage 5, BFGBall Damage 100). The DRLA PDA (`language.weapons`) agrees for plasma rifle and BFG.

Conventions: Doom `Damage N` means N x 1d8, averaging 4.5N. `Damage (expr)` is used as written. A_FireBullets with
FBF_NORANDOM uses its formula as written. Explosions count at full damage on the target they hit. Fire rate is the
held-trigger cycle in tics (35 tics = 1 s). Reloads, DRLA mods and the Fireangel perk are ignored. Cells: reloads move
1 cell into 1 magazine round, except plasma pistols (2 cells per round). Cells per shot = the `useammo` cost plus
both `A_TakeInventory` lines (DRLA takes them one after another, and the Fireangel perk skips the second one). Cell =
5 gold. Treat every figure as roughly right, to about 10-20%.

## 1. Energy weapons

P = projectile, H = hitscan or rail, X = explodes (excluded from the 25 splash as written). "Dmg/shot" is against one
target, average roll.

| Weapon | Dmg/shot | Shots/s | Cells/shot | DPS | Dmg/cell | Gold/s | Type |
|---|---|---|---|---|---|---|---|
| **Rifles** | | | | | | | |
| Plasma Rifle (stock and DRLA) | 22.5 | 11.7 | 1 | 262 | 22 | 58 | P |
| Hyperblaster | 22.5 | 11.7 | 1 | 262 | 22 | 58 | P (speed 45) |
| HP Plasma Rifle | 32.5 | 7.0 | 1 | 228 | 32 | 35 | P |
| Plasma Rifle Mk II | 74 | 3.9 | 3 | 286 | 24 | 58 | P (6-damage puff explosion) |
| Assault Plasma Rifle | 67.5 | 2.1 | 1 | 139 | 68 | 10 | P |
| Burst Plasma Rifle (4-shot burst) | 180/burst | 2.2 bursts | 4 | 394 | 45 | 44 | P |
| Suss Gun | 42 | 11.7 | 1 | 490 | 42 | 58 | P (wide spread) |
| Laser Rifle | 20 | 7.0 | 1 | 140 | 20 | 35 | H |
| HP Laser Rifle | 27.5 | 11.7 | 1 | 321 | 28 | 58 | H |
| Assault Laser Rifle | 60 | 1.9 | 1 | 117 | 60 | 10 | H |
| Burst Laser Rifle (4-shot burst) | 160/burst | 2.2 bursts | 4 | 350 | 40 | 44 | H |
| Laser Minigun (after 1.3 s spin-up) | 20 | 35 | 1 | 700 | 20 | 175 | H |
| **Pistols (2 cells per round)** | | | | | | | |
| Plasma Pistol | 63 | 1.8 | 2 | 116 | 32 | 18 | P |
| Plasma Combat Pistol | 72 | 2.7 | 2 | 194 | 36 | 27 | P |
| Plasma Marksman Pistol | 72 | 3.2 | 2 | 229 | 36 | 32 | P (FastProjectile) |
| Plasma Handcannon | 125 | 2.1 | 2 | 257 | 62 | 21 | P (8-damage puff explosion) |
| Plasma Uzi | 45 | 11.7 | 2 | 525 | 22 | 117 | P |
| **Shotguns (all pellets on one target)** | | | | | | | |
| Laser Shotgun (7) | 140 | 2.3 | 3 | 327 | 47 | 35 | H |
| Plasma Shotgun (7) / Overcharged (7) | 105 | 1.4 | 3 | 147 | 35 | 21 | P |
| Heavy Plasma Shotgun (7) | 158 | 1.4 | 3 | 220 | 52 | 21 | P |
| Plasma Shotgun Mk II (14) | 252 | 1.75 | 6 | 441 | 42 | 52 | P |
| Hell's Reign (6) | 480 | 1.2 | 5 | 560 | 96 | 29 | P (1-damage puff explosion) |
| Voltgun (40 bolts) | 400 | 0.8 | 15 | 318 | 27 | 60 | P (FastProjectile) |
| **Heavy, slow, piercing** | | | | | | | |
| Railgun | 200 | 1.5 | 4 | 304 | 50 | 30 | H, pierces |
| Particle Beam Cannon | 900 | 0.85 | 30 | 768 | 30 | 128 | H, pierces |
| Plasma Redirection Cannon | 120 | 2.9 | 4 | 350 | 30 | 58 | P (speed 22) |
| Neural Stunner | 314 | 0.95 | 6 | 297 | 52 | 28 | P, "NeuralStun" damage type |
| Unmaker (demonic) | 389 | 1.75 | 20 | 680 | 19 | 175 | P, "Unholy" damage type |
| **Exploding** | | | | | | | |
| Tristar Blaster (1 of 3 balls hits) | 182 | 1.0 | 15 | 177 | 12 | 73 | X (r96; up to 3x on a big target) |
| HP Tristar Blaster (1 of 3) | 238 | 1.0 | 15 | 231 | 16 | 73 | X |
| Plasma Cannon | 346 | 0.76 | 10 | 263 | 35 | 38 | X (256 at r128) |
| Quantum Tantrum Cannon | 264 | 0.95 | 10 | 250 | 26 | 47 | X (256 at r128, speed 15) |
| Zeus Cannon | 361 | 0.67 | 50 | 243 | 7 | 168 | X (256 at r256, speed 12) |
| BFG10K (after 0.9 s charge) | 296 | 5.8 | 5 | 1727 | 59 | 146 | X (hitscan + 256 explosion) |
| BFG9000, ball only (stock and DRLA) | 450 | 0.58 | 40 | 262 | 11 | 117 | X |
| BFG9000, ball + all 40 rays (big target) | 3150 | 0.58 | 40 | 1838 | 79 | 117 | X |
| HP BFG9000, ball + 40 rays | 3600 | 0.58 | 40 | 2100 | 90 | 117 | X |
| VBFG9000, ball + 60 rays | 6885 | 0.26 | 60 | 1798 | 115 | 78 | X |
| Biggest Fucking Gun, ripper + 100 exploding rays | up to ~24,000 | 0.19 | 100 | up to ~4,600 | ~240 | 96 | X (very rough) |

Not computed (special mechanics): Lucifer Cannon (charge weapon, 5 cells for a basic shot), Baron Blaster (ripper,
speed 1, 50 damage per contact), Plasma Refractor (refracted bolts), Null Pointer ("NullDamage" field), Reality
Distortion Array (morphs targets), Chameleon Rifle (bullets, 16 per shot at 4 tics), and the Nuclear/Nanomachic
variants (same damage as the base guns, with self-recharging ammo).

Reference (DRLA PDA and stock): DRLA Chaingun 12 per 4 tics = 105 DPS at 12 damage per gold. DRLA Shotgun 70 per
10 tics = 245 DPS while firing, 23 per gold. DRLA Rocket Launcher about 218 per 23 tics (55-tic reload after each
rocket), 22 per gold. Plasma Rifle 262 DPS at **4.5 damage per gold**. Cells already cost 2-5x more gold per damage than
the other ammo.

## 2. The owner's design on representative weapons (one target, steady state)

Let D be the weapon DPS at skill s, so D = base DPS x (1 + 0.6 s/100). Burn b is the burn percentage. With unlimited
stacking, each hit adds b x hit over 3 s. Once it has run 3 s, the burn stacks saturate and **burn DPS = b x D**, so
total = (1 + b) x D. The 75 "pull 40% of the remaining burn" moves burn damage earlier and adds none. At steady state
each hit pulls almost exactly b x its own damage, and about 1.5 hits' worth of burn stays pending. Strip
multiplies everything by (1 + X) for X stripped. Under the owner's cap of 30% per 3 s, X reaches 30% at 3 s of fire
and 100% at 10 s.

Total single-target multiplier on base DPS:

| Skill | Damage | Burn | Strip | Multiplier |
|---|---|---|---|---|
| 0 | 1.00 | none | none | **1.0** |
| 25 | 1.15 | 50% | none | **1.73** |
| 50 | 1.30 | 100% | none | **2.6** |
| 75 | 1.45 | 100% | 30% / 100% | **3.8 / 5.8** |
| 100 | 1.60 | 150% (read as replacing 100%) | 30% / 100% | **5.2 / 8.0** |

(At 75 and 100, the first figure is 3 s into the fight and the second is 10 s in.)

| Weapon (base DPS) | 0 | 25 | 50 | 75 (3 s / 10 s) | 100 (3 s / 10 s) |
|---|---|---|---|---|---|
| Plasma Rifle (262) | 262 | 453 | 682 | 990 / 1520 | 1365 / 2100 |
| BFG9000 ball + 40 rays, big target (1838) | 1838 | 3170 | 4780 | 6930 / 10660 | 9560 / 14700 |
| Plasma Uzi (525), rapid | 525 | 906 | 1365 | 1980 / 3045 | 2730 / 4200 |
| Laser Minigun (700), rapid hitscan | 700 | 1208 | 1820 | 2640 / 4060 | 3640 / 5600 |
| Plasma Cannon (263), slow, exploding | 263 | 454 | 684 | 992 / 1525 | 1368 / 2104 |
| Railgun (304), piercing | 304 | 524 | 790 | 1146 / 1763 | 1581 / 2432 |
| Laser Shotgun (327) | 327 | 564 | 850 | 1236 / 1897 | 1700 / 2616 |
| Plasma Pistol (116) | 116 | 200 | 302 | 437 / 673 | 603 / 928 |

Burn ramp-up. A simulation of the stacks, run at 35 tics a second, shows how much of the (1 + b) total actually lands
in the first second. This matters in slaughter packs, where most targets die within a second:
- Plasma rifle, b = 100%: 1.18x the hit damage without the 75 pull, and 1.82x with it. The pull makes burn almost
  instant on rapid guns.
- BFG ball: 1.33x in the first second either way, since only one shot lands. Burn on slow guns stays a delayed DoT.
- Railgun: 1.22x without the pull and 1.38x with it.

Which weapons the rules favour or neglect:
- **Burn** grows with damage, so it treats all guns alike on paper. In practice it is wasted on overkill: pellets and
  BFG damage on small enemies, and any target that dies before its burn runs out. It is strong on bosses and weak
  on fodder.
- **The 75 pull** favours rapid fire (above). It does nothing extra for slow guns.
- **The 25 splash** leaves out the exploding guns (Tristars, Plasma Cannon, Tantrum, Zeus, every BFG and the BFG10K).
  Read literally, it also leaves out guns with token puff explosions: Mk II (6 damage), Handcannon (8), Hell's Reign
  (1) and Neural Stunner (1). Suggested fix: splash = 30% of the hit minus the gun's own explosion damage, never below 0.
- **The 50 speed bonus** does nothing for every laser, the Railgun, Particle Beam, Laser Minigun and BFG10K, and almost
  nothing for FastProjectile guns (Marksman, Voltgun). The slow balls gain the most: Zeus (speed 12), Tantrum (15),
  Redirection (22), BFG and plasma rifle (25), Tristar, Unmaker, Hell's Reign and Suss (30).
- **Multi-hit and piercing guns** (Railgun, Particle Beam, shotguns, Hell's Reign, Voltgun's 40 bolts) get the most
  from splash and the 100 explosion, because each target they touch is a separate trigger.
- **BFG rays:** if the 40-100 rays count as hits, burn adds about 4,000 damage to a single BFG9000 shot at 100 skill.
  One HP BFG shot at 100 with full strip is 3600 x 8 = about 29,000, which kills a 15,000 HP titan outright.
  Suggested: rays deal burn but no splash, pull or explosion. Or rays deal no burn at all.

## 3. Compared with the other gun skills (one target, multiplier on base DPS)

| Skill level | Automatics | Shotguns | Explosives | Energy (owner design) |
|---|---|---|---|---|
| 25 | 1.15 (+30% on the first 3 shots of a burst only) | 1.19 (+ reloads ~35% faster) | 1.15 (+ self-splash cut) | 1.73 |
| 50 | 1.30, half the ammo | 1.38 x 1.5 pellets = 2.06 | 1.30 + open direct-hit bonus | 2.6 |
| 75 | 1.45 x 1.15 = 1.67 | 1.56 x 1.5 = 2.34 + wall slams | 1.45 | 3.8 / 5.8 |
| 100 | 1.60 x 1.15 = 1.84, quarter ammo | 1.75 x 2.0 = 3.5 + slams up to 400 | 1.60 + pack chains | 5.2 / 8.0 |

Gold per 1,000 damage at 100: Chaingun about 11, Shotgun about 12, Rocket about 29, Plasma Rifle about 43 (31 with full
strip). At skill 0 the Plasma Rifle costs about 222.

Findings:
- From 50 up, Energy's single-target multiplier is about 1.3-2.3x the Shotgun skill and 3-4x Automatics. That is on
  top of energy guns having the highest base DPS.
- The cost theme fades with skill. Burn makes every cell deal 2.5x more, so a maxed energy user pays only about 1.5x
  rocket prices per damage. Cells stop being "logistically expensive" at the top. If the owner wants the cost to
  stay felt, the easiest knob is to lower burn (for example 25%/50%/75% at 25/50/100) or to keep the continuous
  damage at +30%.
- The AoE (25 splash and the 100 explosion) goes on top of this, so Energy also beats Explosives at clearing packs
  near the target.

## 4. Strip Resistances: a big enemy against a swarm

DRLA resistances are per-damage-type `DamageFactor` values in the monster DECORATE. Plasma factors in DRLA Monsters
are mostly 0.75-0.8, a few 1.2-2.0, and two monsters are immune (0). Daggerfall already sits on top of these
(`gamedesign.md`, "Damage and resistances").

How it plays under the owner's limits (30% gained per 3 s, 100% total):
- **Swarm:** the strip does almost nothing. An imp dies to 3 plasma bolts after about 2.5% strip. The strip only ever
  matters on targets that live several seconds.
- **Big enemy:** the 10%-a-second rate cap already limits the damage. With the plasma rifle at 100 (1365 DPS before
  strip):
  - Cyberdemon (4,000 HP): 2.9 s without strip, about 2.6 s with it.
  - Titan (15,000 HP): 11.0 s and 128 cells without strip; about 7.9 s and 92 cells with a 100% cap; about 8.8 s and
    103 cells with a 30% cap.
  - So the strip saves 20-30% of the cells on a titan. That is meaningful but not a delete button. The real boss
    risk is burn on BFG rays (section 2).

Proposed rule ("Exposed"):
1. Each direct energy hit adds Exposed = 30% x (the gun's shot interval / 3 s). Every gun at full fire then reaches
   the cap at the same speed, whatever its fire rate. The plasma rifle adds 0.86% a hit and the BFG 17% a hit.
   Splash, explosions and burn ticks add none.
2. Gain is capped at 10 points per second per target, which is the owner's 30% per 3 s, applied evenly. Total
   Exposed is capped at 100%.
3. Exposed works as "+X% damage taken from all sources" (multiplicative), so immune targets stay immune. Doing it
   additively on the factor (0.75 + X) would make immune monsters killable. The Automatics 75 perk already uses
   "+% damage taken" (+15%, permanent), so this matches it and keeps one code path.
4. Decay (not in the owner's text): after 2 s with no energy hit, Exposed falls 10 points a second. It is spent by
   firing, which suits the cost theme.
5. Optional boss brake, if the owner wants one: total cap = 100% x sqrt(1000 / max HP), with a floor of 30% (Cyberdemon
   50%, 10,000 HP and above 30%). Without the BFG-ray problem this is probably not needed.

## 5. Pitch for the 100 explosion

- **Trigger:** every direct hit at 75+ already pulls 40% of the target's burn. At 100, pulled damage builds up on the
  target, and the target explodes **at most once per 0.25 s** with the total pulled since its last explosion. No
  damage is lost, and a fast gun no longer means more explosions.
- **Explosion:** radius 128 (the rocket's). Every *other* enemy in range takes **25% of the pulled total** with no
  falloff, plus burn at **50% of that** over 3 s. It never hurts the player, adds no Exposed, and **cannot cause
  pulls or explosions (no chaining)**.
- **Size check:**
  - Plasma rifle at 100: about 54 pulled per hit, about 160 per 0.25 s. Each neighbour takes 40 per explosion, which
    is about 160 DPS plus 80 burn DPS, so about 240 area DPS. That is about the area damage of a stock rocket launcher
    (about 128 splash per 20 tics, about 220 DPS).
  - BFG ball: one explosion of about 150 every 1.7 s, small next to the rays.
  - Railgun: each target it pierces explodes on its own.
- **Chain risk:**
  - With chaining allowed, burning packs are the danger. The 25 splash sets the whole pack burning, and every
    burning monster holds a pool. One hit would then set off every pool in range within a single tic, a cascade
    across the whole pack. Explosions per tic are bounded only by the pack size (hundreds), and each one runs a
    radius search. A hitch is likely. The damage itself does not run away: per generation, 25% x 40% of a pool is
    small. The *number* of explosions is the problem.
  - With no chaining, explosions per tic are at most the distinct targets hit directly that tic: 14 for a Mk II
    shotgun blast, 40 for the Voltgun, and 40-100 if BFG rays count. Add a **global queue of at most 16 explosions
    per tic** (the rest wait for later tics), and leave rays out of explosions.
  - If the owner wants chains (like Explosives 100): halve the effect each generation, allow at most 3 generations,
    and use the same per-tic queue.
- **Burn implementation (performance):** keep one burn pool per monster instead of a list of stacks. It drains at
  pool / 3 s (exponential), ticks every 5 tics, and is pulled 40% per hit. Total damage is unchanged, and it costs one
  inventory item or thinker per burning monster. Persistence across saves is not needed.

## 6. Questions for the owner (ambiguities)

1. Does the 25 splash also hit the directly hit target (+30% on one target), or only the enemies around it? This
   note assumes only the others. Radius pitch: 64.
2. Does burn stack without limit already at 25, or only from 50? The text says "no limit" only at 50.
3. At 100, does "+150%" replace the 100% (150% total), or add to it (250%)? This note assumes it replaces it.
4. Is burn taken from the damage after resistances and armour, and then dealt with no second resistance roll?
   Recommended: yes. Otherwise the resistance is applied twice.
5. Are burn ticks, splash and explosions "hits" that can splash, strip, pull or explode again? Recommended: only
   direct weapon hits are.
6. Do BFG rays count as hits for burn, splash, pull and explosion? This decides whether BFGs one-shot titans.
7. Strip: is 30% the most gained per 3 s (so 100% is reached after 10 s), as read here? Does it decay? Is it "+X%
   damage taken from all sources" (helping other weapons and allies), or only for energy damage?
8. Is the 75 pull damage moved from the burn (total unchanged, as read here), or extra damage?
9. Can 100 explosions chain?
10. Which guns count also changes the splash rule (plasma pistols and shotguns, Railgun, Unmaker; the proposal's
   question 1). Should guns with token puff explosions (Mk II, Handcannon, Hell's Reign, Neural Stunner) still get the
   splash?
11. Balance: at 100, Energy is 5.2-8x base DPS, against 3.5x for Shotguns and 1.8x for Automatics, and its gold cost
   per damage falls to about 1.5x rockets. Is that the intended power curve, or should burn or the continuous bonus
   come down?

## Revision 2: tuned numbers (owner's perk design kept)

| Level | Owner draft | Proposed |
|---|---|---|
| Continuous | +0 to +60% damage | **+0 to +50%** |
| 25 | burn 50% over 3 s, splash 30% | **burn 40%**, splash 20% (r64, not the hit target) |
| 50 | burn 100%, unlimited stacks, projectiles +30% speed | **burn 70%**, rest unchanged |
| 75 | strip up to 100% (30% per 3 s), pull 40% | **strip cap 30% total** (reached in 3 s, decays when not hit), pull 40% |
| 100 | burn 150%, explosion | **burn 100%**; explosion 25% of pulled burn (r128), at most 1 per target per 0.25 s, no chaining |

At 100 the total single-target multiplier is 1.5 x 2.0 x 1.3 = **3.9x** (draft: 8x). Plasma Rifle about 1,020 DPS,
Plasma Uzi 2,050, Laser Minigun 2,730. BFGs stay outliers (BFG9000 with all rays about 7,200).

TTK in seconds, from a tic simulation: target 512 units away, projectile travel and burn ramp included, Minigun 0.8 s
spin-up included, stock DRLA HP (Imp 60, Baron 1,000, Cyberdemon 4,000, titan 15,000). Automatics uses its own perks
(+60%, +15% damage taken).

| Weapon, skill 0 / 50 / 100 | Imp | Baron | Cyberdemon | Titan |
|---|---|---|---|---|
| Plasma Rifle | 0.8 / 0.6 / 0.5 | 4.4 / 2.8 / 1.7 | 16 / 8.2 / 4.7 | 58 / 28 / 15 |
| Plasma Uzi | 0.4 / 0.3 / 0.3 | 2.2 / 1.5 / 0.9 | 7.9 / 4.4 / 2.5 | 29 / 14 / 7.9 |
| Railgun (hitscan) | 0 / 0 / 0 | 2.6 / 2.0 / 1.3 | 12 / 6.6 / 3.9 | 49 / 24 / 13 |
| DRLA Chaingun | 0.5 / 0.3 / 0.3 | 9.5 / 7.3 / 5.3 | 38 / 29 / 21 | >120 / 110 / 78 |
| DRLA Minigun | 1.0 / 0.9 / 0.9 | 4.3 / 3.5 / 2.7 | 15 / 12 / 8.5 | 54 / 42 / 30 |

Reading: Automatics still win on imps, because their damage lands at once and an imp dies before burn matters. From
50 up, energy kills Barons and bosses about 1.6-2x faster than the Minigun, and cells cost about 4x as much per damage.
Burn makes up about half of energy damage at 100.

Earlier questions settled by these numbers: 3 (+150%), 7 (strip cap and decay), 9 (chaining), 11 (power curve).
Still open:
1. Does burn stack without limit already at 25, or only from 50?
2. Is the 75 pull moved burn (total unchanged, as assumed here), or extra damage?
3. Do BFG rays apply burn? (If yes, BFGs delete titans.)
4. Is strip "+30% damage taken from all sources", or only from energy damage?
5. Do guns with token puff explosions (Mk II, Handcannon, Hell's Reign, Neural Stunner) still get the 25 splash?

## Revision 3: owner answers and verdict (2026-11-26)

Owner answers (2026-11-26):
- Explosions do not chain. The burn an explosion spreads stays on nearby enemies, and they explode only when a later
  direct hit pulls their burn.
- Strip is halved on hitscan guns, so 15% instead of 30%.
- Non-exploding automatic energy guns will also count as Automatics, using whichever skill is higher.
- Cells should cost more.

Verdict: **not too strong with the Revision 2 numbers. No damage change is proposed.**
- On swarms, most burn is wasted on monsters that die anyway. At 100, a Plasma Rifle needs 2 hits on an imp, and only
  about 1.2x its hit damage actually lands. That gives about 470 useful DPS against 515 for the Minigun, so they are
  even, and energy also pays projectile travel and slower visible kills.
- The 1.6-2x edge shows up only on Barons and bosses, which is the role the skill is meant for. Most of the gap comes
  from the guns themselves: DRLA's energy guns are a higher tier than its bullet guns.
- If play-testing shows bosses melting, make the smallest change first: lower the burn at 100 from 100% to 80%.
  That gives 3.5x instead of 3.9x.

Proposed cell price: **8 gold** (was 5). Gold per 1,000 damage:

| Weapon | Skill 0 | Skill 100 |
|---|---|---|
| Chaingun (1 gold a bullet; a quarter of the ammo used at 100) | 83 | 11 |
| Shotgun (3 gold a shell) | 43 | 12 |
| Rocket Launcher (10 gold a rocket) | 46 | 29 |
| Plasma Rifle at 8 gold a cell (boss / swarm) | 356 | 91 / about 200 |

At 8 gold, a 15 s titan fight with the Plasma Rifle costs about 1,400 gold, and one BFG shot costs 320.

## Revision 4: no Exposed, owner's burn levels, compared with Shotguns (2026-11-26)

Scenario:
- Energy: +0-50% damage. Burn 50% at 25, 100% at 50, 150% at 100. 40% pull at 75. No strip. Cells cost 10 gold.
- Hit rates: projectiles 60% (owner: travel time is "like a 40% damage nerf"), 70% from 50 (faster projectiles).
  Hitscan 100%. BFG: realistic ray hits of 0 / 5 / 15 / 15, which apply burn.
- Shotguns, from card 04: +0-75% damage, reload 35% faster from 25, 1.5x pellets at 50 and 2x at 100. Wall slams are
  left out. Pellet hits are 80% on small targets and 100% on bosses. DRLA PDA cycles: Shotgun 10 + 36 tics reload per
  shell, Double Shotgun 10 + 53.
- Energy magazine reloads are left out, which flatters energy by about 15-30% in long fights.

TTK in seconds at skill 0 / 50 / 100:

| Weapon | Imp 60 | Baron 1,000 | Cyberdemon 4,000 | Titan 15,000 |
|---|---|---|---|---|
| Plasma Rifle | 0.9 / 0.6 / 0.5 | 6.9 / 3.3 / 2.0 | 26 / 9.9 / 6.3 | 96 / 34 / 22 |
| Plasma Uzi | 0.5 / 0.3 / 0.3 | 3.5 / 1.9 / 1.0 | 13 / 5.3 / 3.3 | 48 / 17 / 11 |
| Laser Rifle (hitscan) | 0.3 / 0.3 / 0.1 | 7.0 / 3.6 / 2.0 | 28 / 12 / 7.7 | 107 / 44 / 29 |
| Railgun (hitscan) | 0 / 0 / 0 | 2.6 / 1.6 / 1.2 | 13 / 5.8 / 3.8 | 49 / 20 / 13 |
| BFG9000 | 0.6 / 0.5 / 0.5 | 2.3 / 1.1 / 0.5 | 5.7 / 2.2 / 2.2 | 20 / 8.0 / 5.6 |
| DRLA Shotgun | 1.3 / 0 / 0 | 22 / 7.7 / 4.8 | 75 / 26 / 15 | 281 / 98 / 58 |
| DRLA Double Shotgun | 0 / 0 / 0 | 14 / 5.1 / 2.5 | 50 / 17 / 10 | 193 / 65 / 38 |

Multiplier on base DPS at 100:
- Energy: 1.5 x 2.5 = 3.75. Counting the better projectile hit rate, about 4.4 against skill 0.
- Shotguns: 1.75 x 2 pellets x about 1.3 from faster reloads, about 4.5.

Gold per 1,000 damage (skill 0 / 100), hit rates included:
- Plasma Rifle about 740 / 170.
- Shotgun about 54 / 15.

Verdict: **in line with Shotguns.**
- The skills give the same multiplier, about 4.4x.
- On Barons, energy at 100 is level with the Double Shotgun (2.0 against 2.5 s).
- On bosses, energy kills about 1.6x faster (titan 22 against 38 s). That comes from the higher gun tier, not the
  perks, and it costs about 11x the gold per damage. Wall slams would narrow the gap.
- The BFG with burn is the outlier (titan in 5.6 s at 40 cells, 400 gold, a shot), as allowed.
- Nothing here looks too strong or too weak. Play-testing on bosses is the remaining check.
