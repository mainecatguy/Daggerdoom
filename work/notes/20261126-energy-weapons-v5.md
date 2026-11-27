# Energy Weapons v5: numbers for the owner's new perk design (2026-11-26)

This checks the owner's v5 perk design against Shotguns. The card draft is `work/refinement/skillperks-06-energy.md`.

What the numbers assume:
- Damage scales from +0% to +50% (assumed). Burn uses the card values.
- Burn converted to direct damage: 20% of the pending burn at 50, 40% at 75 and 100. The 100 explosion does not change
  single-target times.
- Projectiles land 60% of the time at skill 0, 70% at 50 (+30% speed) and 80% at 100 (+60% speed). Hitscan always
  lands.
- BFG ray hits: 0 on an imp, 5 on a Baron, 15 on a Cyberdemon or titan. Rays also burn.
- Shotguns use their card perks, with DRLA reload times. Wall slams are not counted.
- Energy magazine reloads are not counted, which flatters energy by about 15-30% in long fights.
- Times come from a tic-by-tic simulation.

## Time to kill, in seconds (skill 0 / 50 / 100)

| Weapon | Imp 60 | Baron 1,000 | Cyberdemon 4,000 | Titan 15,000 |
|---|---|---|---|---|
| Plasma Rifle | 0.9 / 0.6 / 0.5 | 6.9 / 2.8 / 1.7 | 26 / 9.3 / 5.5 | 96 / 33 / 20 |
| Plasma Uzi | 0.5 / 0.3 / 0.3 | 3.5 / 1.5 / 0.9 | 13 / 4.7 / 2.8 | 48 / 17 / 9.8 |
| Laser Rifle (hitscan) | 0.3 / 0.3 / 0.1 | 7.0 / 3.0 / 2.0 | 28 / 12 / 7.7 | 107 / 43 / 29 |
| Railgun (hitscan) | 0 / 0 / 0 | 2.6 / 1.3 / 1.2 | 13 / 5.3 / 3.8 | 49 / 20 / 13 |
| BFG9000 | 0.6 / 0.5 / 0.4 | 2.3 / 1.1 / 0.4 | 5.7 / 2.2 / 2.1 | 20 / 7.9 / 5.5 |
| DRLA Shotgun (baseline) | 1.3 / 0 / 0 | 22 / 7.7 / 4.8 | 75 / 26 / 15 | 281 / 98 / 58 |
| DRLA Double Shotgun (baseline) | 0 / 0 / 0 | 14 / 5.1 / 2.5 | 50 / 17 / 10 | 193 / 65 / 38 |

## Multiplier on base damage at 100

- Energy: 1.5 x 2.5 = **3.75**. With the better projectile hit rate (80% against 60%), about **5.0** for projectile
  guns.
- Shotguns: about **4.5** (1.75 x 2 pellets x faster reloads).

## Gold per 1,000 damage (skill 0 / 100, cells at 10 gold)

| Weapon | Gold per 1,000 damage |
|---|---|
| Plasma Rifle (lower tier: half the cells from 25) | 740 / 74 |
| Plasma Uzi | 740 / 150 |
| Laser Rifle (lower tier) | 500 / 67 |
| Railgun | 200 / 53 |
| BFG9000 on a boss (lower tier) | 310 / 39 |
| Shotgun (3 gold a shell) | 54 / 15 |

## Proposed lower-tier list

DRLA's **Standard and Exotic** guns, plus the **Basic assemblies**: Plasma Rifle, BFG9000, Laser Rifle, Plasma Shotgun,
Tristar Blaster, the High Power versions, Heavy Plasma Shotgun, and Overcharged (Plasmatic Shrapnel) Plasma Shotgun.

Reason: these are DRLA's own lowest tiers, the guns found early. Advanced and Master assemblies, Superior, Unique,
Legendary and Demonic guns pay full price.

Open fork: the BFG9000 is "Standard" in DRLA. At half price it becomes the cheapest boss killer (39 gold per 1,000
damage). Leave it out of the list?

## Verdict

- **In line with Shotguns.** Both skills give about 4-5x. Energy at 100 is level with the Double Shotgun on Barons
  (1.7 s against 2.5 s).
- **Bosses:** energy kills about 2x faster (titan 20 s against 38 s). That comes from the higher gun tier, and it
  costs 4-10x the gold per damage.
- **The half-price cells at 25 are the big change.** They cut lower-tier gold costs by about 10x between skill 0 and
  100, so the "expensive" theme lasts mostly at low skill and on high-tier guns.
- **BFG** stays the allowed outlier. Excluding it from the half-price list keeps it costly.
- **Swarms:** burn and conversion still mostly go to waste. Splash and the 100 explosion are what energy has against
  packs.
