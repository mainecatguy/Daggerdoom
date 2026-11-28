# Gun damage enchantments: balance pass (2026-11-27)

Checks the pool design in `work/refinement/gunenchantments-01.md`.

## The two enchantments (Daggerfall Unity's real data)

Cast When Strikes is a fixed list of 12 classic spells (`Effects/Enchanting/CastWhenStrikes.cs`). There are no custom
magnitudes. Damage comes from `SPELLS.STD`: base roll + (per-level roll x caster level), where caster level is the
player's level (`EntityEffect.GetMagnitude`, `FormulaHelper.CalculateCasterLevel`). Each strike costs a Daggerfall
weapon 10 condition.

| Enchantment | Cost (points) | Damage | Avg at level 10 | Avg at level 25 |
|---|---:|---|---:|---:|
| **Normal: Wizard's Fire** (fire) | 480 | 1-15 + 1-4/level | **33** | 70 |
| Fire Storm (fire) | 840 | 1-20 + 1-5/level | 40 | 85 |
| **Powerful: Ice Bolt** (frost) | 990 | 1-35 + 1-5/level | 48 | **93** |

Cases used below: **Normal = Wizard's Fire at level 10 (B = 33) on a mid-skill gun**, **Powerful = Ice Bolt at
level 25 (B = 93) on a max-skill gun**. Pool 120B = 3,960 / 11,160. Each hit spends 4B = 132 / 372. Refill 8B/s =
264 / 744 bonus DPS.

What the gun numbers assume: the Pistol and Minigun come from `20261126-003658.md` (Pistol 30 base, 265 at 50, 330 at
75+; Minigun 280 unperked, with about 2x and 4x assumed for Automatics). The Plasma Rifle, BFG and Shotgun DPS come
from v5 Cyberdemon/titan times. The rocket's own DPS is assumed to be 350 / 700. Hits per second: Pistol 2.5,
Minigun 35 x 70% = 24.5, Shotgun 7 pellets x 0.95 = 6.6, Plasma 8.2, rocket impact 1.6, BFG ball + 15 rays per 1.7 s =
9.4 on a big target (only the ball on an imp). While firing, the pool still refills, so it empties after 30 / (hits/s
- 2) seconds. Script: a 0.01 s simulation in the session scratchpad.

## Table 1: burst, sustained, and how far one pool goes

| Gun | Seconds to empty | Burst bonus total (N / P) | Bonus DPS while full (N / P) | Bonus DPS when empty (N / P) | Own DPS (mid / max) | Barons / Cybers per burst, with gun damage (N / P) |
|---|---:|---:|---:|---:|---:|---|
| Pistol | 60 (never, in practice) | n/a | 330 / 930 | 264 / 744 | 265 / 330 | never runs out |
| Minigun | 1.3 | 4,300 / 12,200 | 3,230 / 9,110 | 264 / 744 | 560 / 1,120 | 5.1, 1.3 / 13.6, 3.4 |
| Shotgun | 6.5 | 5,700 / 16,000 | 870 / 2,460 | 264 / 744 | 154 / 267 | 6.7, 1.7 / 17.8, 4.4 |
| Plasma Rifle | 4.8 | 5,200 / 14,800 | 1,080 / 3,050 | 264 / 744 | 430 / 727 | 7.3, 1.8 / 18.3, 4.6 |
| Rocket (impact) | never | n/a | 211 / 595 | 211 / 595 | 350 / 700 | never runs out |
| BFG (16 hits/shot) | 4.1 (2 shots) | 5,000 / 14,200 | 1,240 / 3,500 | 264 / 744 | 1,900 / 2,700 | 12.7, 3.2 / 25.1, 6.3 |

Imps: every hit kills one and still spends a full 1/30, so one pool is about **30 imps** for single-hit guns, but only
about 4 for the Shotgun (7 pellets each spend). A titan (15,000) takes 4 normal pools or 1.3 powerful pools. Bonus alone
per pool: Normal is about 4 Barons or 1 Cyberdemon. Powerful is 10 Barons or 2.8 Cyberdemons.

## Table 2: time to kill, gun alone -> gun + enchantment (seconds)

| Gun | Cyberdemon, N | Titan, N | Cyberdemon, P | Titan, P |
|---|---|---|---|---|
| Pistol | 15.1 -> 6.7 | 57 -> 25 | 12.1 -> 3.2 | 45 -> 12 |
| Minigun | 7.1 -> 1.1 | 27 -> 13 | 3.6 -> 0.4 | 13 -> 2.1 |
| Shotgun | 26 -> 3.9 | 97 -> 26 | 15 -> 1.5 | 56 -> 5.5 |
| Plasma Rifle | 9.3 -> 2.6 | 35 -> 16 | 5.5 -> 1.1 | 21 -> 4.0 |
| Rocket (impact) | 11.4 -> 7.1 | 43 -> 27 | 5.7 -> 3.1 | 21 -> 12 |
| BFG | 2.1 -> 1.3 | 7.9 -> 5.1 | 1.5 -> 0.7 | 5.6 -> 2.4 |

## Wear

- **As written** (each bonus point costs cost/200 condition), one pool costs 0.6 x B x cost: **9,500** (Normal) or
  **55,000** (Powerful). Daggerfall weapon condition is template HP x material/4 (`ItemBuilder`): a longsword is
  800 iron, 4,800 ebony; a warhammer is 1,600 iron, 12,800 daedric. So **one pool breaks almost any gun**. Per point,
  that is 8x Daggerfall's own rate (10 per strike for about 33 damage is 0.3 a point; this is 2.4).
- Guns have no condition yet (`DoomerfallDoomItems.cs`: "no condition or enchantments yet").

## Verdict: too strong, by about 3-10x

- **Low-rate guns never run out.** The Pistol and rocket impact fire 2.5 hits/s or fewer, so they get the full 4B per
  hit forever. Normal more than doubles a mid Pistol, and Powerful is 2.8x a max Pistol. A 12-damage bullet carries
  +132 or +372.
- **The sustained 8B/s alone is a whole gun.** Normal adds 264 DPS, equal to a mid-skill Pistol. Powerful adds 744, a
  max-skill Plasma Rifle. This comes from one 480-990 point enchantment. Daggerfall gives the same spell about 1B/s (one
  strike a second).
- **Burst deletes a boss.** One pool is a Cyberdemon (Normal) or three (Powerful). The Shotgun and Minigun become boss
  killers 4-10x faster. Several enchantments on one gun multiply all of this.
- **Imps are fine** (overkill wastes it), except the Shotgun, which drains 7/30 per shot.

Smallest changes:
1. **Pool 120x -> 30x, refill 15 s -> 30 s.** This keeps the owner's 4x per hit and its display, with 7-8 big hits per
   pool, and sustains 1B/s like Daggerfall. Result: Cyberdemon 1.4-4x faster, titan 1.2-1.6x faster (Normal Pistol
   57 -> 47 s, Plasma 35 -> 30 s; Powerful Plasma 21 -> 15 s, Pistol 45 -> 29 s). A strong opening burst and a small
   tail. (Alternative: keep 120x/15 s but spend 1x per hit, i.e. 30x pool with 1/30 spends. Sustained is 2B/s, which
   loses the 4x feel.)
2. **Wear per full spend, not per point:** each 1/30 spend costs cost/200 condition, and partial spends cost in
   proportion. One pool costs 0.15 x cost = **72** (Wizard's Fire) or **149** (Ice Bolt), about 1.5-3% of an ebony
   longsword-class gun.

Open for the owner: what condition guns get (none exists yet), and whether the level-scaled spell damage (33 at
level 10 to 93 at level 25) should drive the pool at all.

## Rerun 2: pool 15x, 15 s refill, wear 1/20,000 (owner, 2026-11-27)

The owner was right: under the old wear rule a gun broke after about one pool, so as a whole the first design was weak
(broken guns), not strong. This rerun judges damage and wear together. Same guns, enchantments and script. The pool is
15B and refills at B/s (33 Normal, 93 Powerful).

Two readings of the per-hit spend:
- **A (literal):** 1/30 of the pool = 0.5B per hit (16 / 47). The pool drains only above 2 hits/s.
- **B (keeps the 4x):** 4B per hit (132 / 372). The pool is 3.75 hits, then 4B arrives every 4 s.

Both deliver the same sustained B/s and nearly the same burst total (about 16-21B). B front-loads the burst into one
volley, and it keeps the item maker's "4x" display true (under A it would read 0.5x). The table shows A, with B where it
differs.

| Gun | Seconds to empty, A (B) | Burst total, N / P | Sustained bonus DPS, N / P | Own DPS, mid / max | Titan TTK, N | Titan TTK, P |
|---|---|---|---|---|---|---|
| Pistol | 60 (1.7) | slow drain (550 / 1,550) | 33 / 93 | 265 / 330 | 57 -> 49 | 45 -> 34 |
| Minigun | 1.3 (0.15) | 540 / 1,520 | 33 / 93 | 560 / 1,120 | 27 -> 24 | 13 -> 11 |
| Shotgun | 6.5 (0.6) | 710 / 2,000 | 33 / 93 | 154 / 267 | 97 -> 78 | 56 -> 38 |
| Plasma Rifle | 4.8 (0.5) | 655 / 1,845 | 33 / 93 | 430 / 727 | 35 -> 31 | 21 -> 17 |
| Rocket (impact) | never (2.8) | n/a (590 / 1,650) | 26 / 74 (33 / 93) | 350 / 700 | 43 -> 40 | 21 -> 19 |
| BFG | 4.1 (0.4) | 630 / 1,770 | 33 / 93 | 1,900 / 2,700 | 8 -> 8 | 6 -> 5 |

Enemies per pool:
- Normal: about 0.5-0.7 Baron, 0.15 Cyberdemon, 0.04 titan. Imps: about 10 imps' worth of HP under A; about 4 imps
  under B (each 4B hit overkills).
- Powerful: about 1.5-2 Barons, 0.4-0.5 Cyberdemon, 0.1 titan.
- Under B, the volley matters on Barons. A Powerful Plasma Rifle kills a Baron in 1.38 -> 0.27 s (A: 0.91 s).

Against own DPS, the sustained bonus is:
- Normal on mid guns: Pistol +12%, Plasma +8%, Shotgun +21%, BFG about 2%.
- Powerful on max guns: Pistol +28%, Plasma +13%, Shotgun +35%, BFG 3%.

**Wear.** Condition per 1,000 bonus damage is cost/20: **24** (Wizard's Fire) and **50** (Ice Bolt), whatever the
level. Assumed slaughter pace: about 12 minutes of combat per dungeon, with bonus spent at the refill rate. That is
about 24,000 bonus (N) or 67,000 (P) per dungeon. Gun condition follows a longsword-class weapon (800 x material/4):
steel/elven 1,200-1,600 for a level-10 player, ebony/daedric 4,800-6,400 at level 25.

| Wear rate | Normal, steel gun (1,200) | Powerful, ebony gun (4,800) | Powerful, daedric gun (6,400) |
|---|---|---|---|
| 1/20,000 (owner) | 570 a dungeon: **2 dungeons**, 25 min of combat | 3,300 a dungeon: **1.5 dungeons**, 17 min | 2 dungeons, 23 min |
| **1/100,000 (proposed)** | 115 a dungeon: **10 dungeons**, 2.1 h | 660 a dungeon: **7 dungeons**, 1.5 h | 10 dungeons, 1.9 h |

Wear scales with B x cost, so a powerful enchantment on a cheap material wears fastest, as in Daggerfall.

**Combined verdict: fine. It is a modest perk, not a second gun.**
- Damage adds about 10-35% sustained, plus an opening burst worth half a Baron (N) or two Barons (P). Bosses die 5-30%
  faster. It is weakest on high-DPS guns (BFG, Minigun) and strongest on the Shotgun and Pistol.
- At 1/20,000, a gun still needs repair every 1.5-2 dungeons. That misses the owner's "very little wear".
- Smallest tweaks:
  1. **Wear 1/20,000 -> 1/100,000**, which gives 7-10 dungeons between repairs.
  2. Prefer **reading B** (4B per hit, 15B pool): same totals, keeps the 4x display, and a felt volley instead of
     +16 per bullet.

If Normal feels too faint in play, a 30x pool (still 15 s) doubles burst and sustained (Normal +16-42%) and stays well
below the first design.
