# Energy splash: 20% for single-hit guns, 10% per hit for multi-hit guns (2026-11-27)

Research only. This checks the owner's proposed splash rule.

Assumptions:
- Skill 100, so damage x1.5. Projectiles land 80% of the time, hitscan always.
- Splash radius 64. It hits about 3 neighbours in a dense pack and never the target that was hit.
- Splash never hurts the player. It neither causes nor converts burn, so the numbers count no burn.
- Exploding hits (the BFG ball) do not splash.
- BFG rays that land: 15 on a lone big target, about 25 of 40 in a dense pack. Rays that hit a wall do nothing,
  because DRLA only makes ray effects on monsters.
- Overkill and overlapping splash are ignored.

## Splash damage at skill 100: today (20% per hit) against the new rule

| Gun | Hits landed per shot | (a) One neighbour of a lone big target, per second | (b) Whole dense pack, per second | Splash events per shot |
|---|---|---|---|---|
| Plasma Rifle (34 a bolt) | 1 | 63, unchanged | 189, unchanged | 1 |
| Laser Rifle (30 a shot) | 1 | 42, unchanged | 126, unchanged | 1 |
| Railgun (300), 1 target | 1 | 91, unchanged | 274, unchanged | 1 |
| Railgun, pierces 3 | 3 | 91 → 46 if pierce counts as multi-hit | 821 → 410 | 3 |
| Plasma Shotgun Mk II (11 of 14 pellets land, 27 each) | about 11 | 106 → **53** | 317 → **159** | up to 11 |
| BFG9000 rays (101 each) | 15 / 25 | 176 → **88** | 885 → **443** (1,518 → 759 per shot) | 15-25 |

## The owner's point: what splash adds to the BFG in a pack

| Damage per shot in a dense pack | Today (20%) | New (10%) |
|---|---|---|
| Direct damage: 25 rays + ball | 3,070 | 3,070 |
| Splash damage | 1,518 (+49%) | 759 (**+25%**) |
| Monsters touched per shot | about 25 hit, plus up to about 75 splashed | same |
| For comparison, a single-hit gun such as the Plasma Rifle | +60% (20% x 3 neighbours) | +60% |

- Splash comes only from rays that land.
- BFG ray hits are scattered, so their splashes reach monsters the rays skipped. At 10% the BFG still touches about
  4x more monsters per shot than its rays alone.
- Per point of damage dealt, the BFG gets half the splash a plasma bolt gets. It gets far more spread.

## Performance

- Today, splash events per shot equal the hits landed: up to about 40 for a BFG shot and 11 for a Mk II blast. Each
  event is one radius search.
- **Merging all of a shot's hits on the same enemy into one splash** gives the same damage. Splash is linear: summing
  the hit damage and splashing once from that enemy's centre gives the same total to each neighbour. The only
  difference is a few units of offset in where it is centred.
- With merging, events per shot drop to the number of distinct monsters hit: 1-3 for a shotgun blast on a target, and
  at most 25 for a BFG shot.

## Verdict

- **The rule balances well.** Single-hit guns get +60% pack damage. Multi-hit guns get +30% but spread it over many
  more monsters, which fits trash. Without the halving, a BFG shot would splash about 1,500 damage on top of its rays.
- **Tweak 1:** decide "multi-hit" by the gun (it fires more than one pellet or ray per shot), not by how many hits
  landed. Otherwise a shotgun that lands one pellet gets 20%.
- **Tweak 2:** merge each shot's hits on the same enemy into one splash. Same damage, and at most 25 events per BFG
  shot instead of 40.
- **Open fork:** does a piercing Railgun or Particle Beam count as single-hit (20% on every monster it passes
  through) or multi-hit (10%)? Lean single-hit, because it is one beam.
