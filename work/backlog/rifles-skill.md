# Rifles skill

**Waiting on:** owner design. Backlog for now.

A new skill named Rifles (owner, 2026-11-26: "Instead of Marksmanship we'll call it rifles"). It replaces the
Marksmanship backlog item. Archery stays a separate Daggerfall skill (backlog, [original weapon
skills](original-weapon-skills.md)).

**What a rifle is (owner, 2026-11-26):** "all ballistic semi-automatic weapons that are not explosives, energy weapons,
shotguns or pistols." Heavy single-shot rifles are rifles too. The Assault Chaingun, Assault Minigun and Autocannon are
Automatics, not rifles. The Elephant Gun is a rifle. The Steel Beast is a shotgun, because it fires pellets. No rifle
counts as a pistol. Doomerfall's rifle tag is `rifletag` 01. The rifles research has the list and numbers (`work/notes/20261126-003658.md`). Stock Doom has no rifles.

**Baseline (owner, 2026-11-26):** rifle damage +0% to +60%, rising with the Rifles skill from 0 to 100. This replaces
the Marksmanship draft's +0% to +100%.

**Perks (owner, 2026-11-26).** Each unlocks when the Rifles skill reaches that level, and applies to all rifles.

- **Skill 25:** reloads 20% faster. Rifles deal +30 flat bonus damage, added before other modifiers. Hits cripple
  enemies: each hit adds cripple equal to its damage divided by the enemy's max HP when the hit lands (a hit for 10% of
  its max HP adds 10%). Hits add up, to at most 75%. A crippled enemy's movement and attack speed drop by its cripple %.
  The cripple lasts until the enemy dies. Cripple pool: +10% cripple that refills every 2 seconds and is added to the
  next hit, even one that dealt little damage. Doom tracks cripple entirely; Daggerfall does not mediate it (owner:
  too complicated, bad engineering).
- **Skill 50:** +1 penetration. A bonus damage pool of 150 that refills over 1 second (kept, owner 2026-11-26).
  Reloads another 20% faster. Estimate (rifles research numbers, skill 100): the pool adds about 40-80% to light and
  medium rifles' damage per second and 15-25% to the heavies.
- **Skill 75:** crippled enemies take +2% damage for every 1% cripple, so +150% at the cap. It applies to damage from
  any source, not only rifles (owner, 2026-11-26: "people don't switch weapons all that much but if they want to they
  can, that's play"). Replaces steady shot. This makes rifles the guns for hunting large monsters (HP up to about
  20,000). Estimate (rifles research numbers, skill 100, one target): against a 20,000 HP monster, rifle damage per
  second roughly doubles (+100% to +123%), and against 500-1,000 HP monsters it adds 0-60%.
- **Skill 100:** true overpenetration. The shot passes through every enemy in its path, killing or not, with no limit.
  The first penetration (from skill 50) loses no damage. Each penetration after that deals 3/4 of the one before.
  Example, 4 pinkies in a row: 1st takes 100%, 2nd 100%, 3rd 75%, 4th 75% of 75%.

The Marksmanship draft's kill carry-through at 25 (2026-11-25) is replaced by these perks.

Notes: the heavies (Anti-Materiel, Gauss Rifle, Sniper) hit far harder per shot than pistols, so the perks need their
own balance. Within the 35-skill limit the skill also needs a free slot.
