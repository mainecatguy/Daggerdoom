# Weapon mods: sold by merchants, found in dungeons and loot

Read `gamedesign.md`'s randomness principles first ("Randomness" and "Adding things to random pools").
Lane: `weaponmods` (new). Model: Opus. After `shoplevels` 05-07. Only when guns are enabled (always today; backlog
`guns-off-option`).

Owner (2026-11-27): "We also need merchants to sell weapon mods. Mods should have a base price of 600. They are
relatively rare in terms of how frequently they drop. Mods have different rarities. There are rare and non-rare mods.
Finding a rare should be a bit more difficult. Mods should also be able to appear in dungeons or drop in random loot".

- DRLA's weapon mod packs become Daggerfall items with a base price of 600, split into non-rare and rare (for example
  DRLA's basic packs vs its exotic ones; list the split in the notes).
- **How rare (owner, 2026-11-27):** "they get put in the loot pool with weapons but they should be approximately 10x as
  rare as a weapon"; then: "we want that system to play its part but we want the total drop rate to be about 1/10th the
  chance of the gun". Target: overall, mods appear about 1/25 as often as guns, only where guns can appear (owner, 2026-11-27: "let's
  adjust to 1/25 as often as guns"). Within mods,
  a rare mod is about 1/3 as likely as a non-rare one (the product owner's number for "a bit more difficult").
- **Worked into the existing systems:** the vendor system (shop identity, lots, Pitman-Yor reuse, exceptions) and the
  loot "genetics" decide where and when mods turn up, with the 1/25 target as the overall rate. Mods are added to the
  pool and never replace or crowd out other items. The worker has latitude in how (`gamedesign.md`, "Adding things to
  random pools").
- **Item:** 600 base price for non-rare mods, 1,800 for rare (product owner's numbers); 0.5 kg; no material tier; bought
  by the shops that buy guns.

Done when: shops, dungeons and loot surveys show mods at about 1/25 the rate of guns where guns appear, never elsewhere,
rare ones at about 1/3 the rate of non-rare ones, all seeded; buying one at 600
base and applying it to a gun works in a paired run.
