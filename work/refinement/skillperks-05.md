> **Sent back (2026-11-27):** Pistols part stopped on open owner questions: pistol fire-rate multipliers (which shot gaps are fast/slow, do mods count), whether they multiply the skill-100 bonus pool, and shrapnel V/range and what spends the pool. Q&A sheet items 82-84 (`work/notes/20261127-owner-qa.md`). Work so far: branch `agent/skillperks-20261127-115755`, notes from run 20261127-115755 (`work/notes/20261127-115755.md` if present).

# Pistols perks

Add the perks of the Pistols skill. Do this after `skillcore` 01 (new skills and the perk framework), `skillcore` 03
(the Pistols skill itself), and the earlier cards in this lane. The perks apply only while a pistol is held: stock
Doom's pistol and DRLA's pistol-type guns. No rifle is ever a pistol (owner, 2026-11-26: "pistols and rifles becomes
just pistols", "no rifle is counted"). Every effect must work with stock Doom weapons, not only DRLA.

Each perk unlocks when the Pistols skill reaches that level, and stays once reached. General skill rules:
`work/backlog/skills-in-doom.md`.

**Skill 25**
- Damage multiplier by fire rate: a reversed, weaker Deadeye. Fast-firing pistols deal about 2.5x damage, scaling down
  to 1.5x for slow-firing ones. This multiplies damage only. The gun does not fire faster.
- Reloads 20% faster.

**Skill 50**
- Overkill carry-through: when a shot kills, its leftover damage carries on through the corpse to the next enemy, with
  no limit while damage remains.
- Bonus damage pool: 100 bonus damage that is always recharging and refills every 0.5 s. Shots spend it, with no cap
  per shot. It is flat and added to the shot's damage: a deliberate mid-game power spike.
- Reloads another 20% faster (40% in all).

**Skill 75**
- Deadeye: a damage multiplier by fire rate, the other way round. Fast-firing pistols get 1.5x, scaling up to 3x for
  slow-firing ones. It multiplies with the skill 25 multiplier.
- Reloads another 20% faster (60% in all).

**Skill 100: shrapnel (owner, 2026-11-26).** Pistol hits no longer just carry their leftover damage on; they also
burst into shrapnel.
- Every pistol hit makes 3 bullet fragments. They fork away behind the enemy in a V pattern, as if the bullet exploded
  into shrapnel.
- Each fragment deals 33% of that hit's damage. Fragments never damage the monster they split from.
- The carry-through from skill 50 still happens. Carry-through hits make their own fragments, at 33% of the damage
  left when the carry-through hit landed.
- Fragments make no fragments and no carry-through of their own.
- Fragments are not smart, with one exception: if an enemy is within 5 degrees of a fragment's path behind the first
  enemy, the fragment turns to hit it.

**Not decided, so leave out and ask in your report:** which fire rates count as fast and slow, and
how the multipliers scale between them; whether Deadeye also multiplies the bonus pool. Owner note: faster raise and
lower may not look good.

For scale, the rifles research (`work/notes/20261126-003658.md`, "DPS under the Rifles and Pistols perks") estimates
pistols at about 330-410 damage per second with all of the above.

Done when: tests show each perk with the stock pistol and DRLA's Pistol, Handcannon and Marksman Pistol, and a paired
run shows the carry-through and the shrapnel.

Also part of this card: when the feature is in its final form, add what a player needs to know about it to
`manual.md` (the player manual), in plain player-facing language.
