# Rifles skill

**Waiting on:** owner design. Backlog for now.

A new skill named Rifles (owner, 2026-11-26: "Instead of Marksmanship we'll call it rifles"). It replaces the
Marksmanship backlog item. Archery stays a separate Daggerfall skill (backlog, [original weapon
skills](original-weapon-skills.md)).

**What a rifle is (owner, 2026-11-26):** "all ballistic semi-automatic weapons that are not explosives, energy weapons,
shotguns or pistols." Heavy single-shot rifles are rifles too. The Assault Chaingun, Assault Minigun and Autocannon are
Automatics, not rifles. No rifle counts as a pistol. Doomerfall's rifle tag is `rifletag` 01. The rifles research has
the list and numbers (`work/notes/20261126-003658.md`). Stock Doom has no rifles.

**Baseline (owner, 2026-11-26):** rifle damage +0% to +60%, rising with the Rifles skill from 0 to 100. This replaces
the Marksmanship draft's +0% to +100%.

**Perks (owner, 2026-11-26).** Each unlocks when the Rifles skill reaches that level, and applies to all rifles.

- **Skill 25:** reloads 20% faster. Rifles deal +30 flat bonus damage, added before other modifiers. Hits cripple
  enemies based on their remaining life: the enemy's movement and attack speed drop by the hit's damage divided by its
  remaining health (a hit for half its remaining life slows it 50%). The cripple lasts until the enemy dies. Open: the
  cap, and whether later hits add to it.
- **Skill 50:** +1 penetration. A bonus damage pool of 150 that refills over 1 second. Reloads another 20% faster.
- **Skill 75:** steady shot. Damage rises with the time since your last shot, up to +100% after 1.5 s, so slow rifles
  gain the most.
- **Skill 100:** true overpenetration. The shot passes through every enemy in its path, killing or not, with no limit.
  The first penetration (from skill 50) loses no damage. Each penetration after that deals 3/4 of the one before.
  Example, 4 pinkies in a row: 1st takes 100%, 2nd 100%, 3rd 75%, 4th 75% of 75%.

The Marksmanship draft's kill carry-through at 25 (2026-11-25) is replaced by these perks.

Notes: the heavies (Anti-Materiel, Gauss Rifle, Sniper) hit far harder per shot than pistols, so the perks need their
own balance. Within the 35-skill limit the skill also needs a free slot.
