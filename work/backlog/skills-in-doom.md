# Daggerfall skills in Doom

**Waiting on:** owner design (in discussion, 2026-11-25).

Proposal (undecided where this file does not say otherwise): `work/notes/20261125-skills-armor-proposal.md`.
This file holds the owner's decisions so far and is the source of truth over the proposal.

## General (owner, 2026-11-25)

- No Doom class. The Doom player is a normal character with no class effects; Daggerfall skills apply all perks and
  modifiers. DRLA classes are inspiration only.
- Each skill grants a perk at 25, 50, 75 and 100, besides its continuous scaling.
- New gun skills are **new skills**, added beside Daggerfall's. They do not replace or rename existing skills.
  Short Blade, Long Blade, Axe, Blunt Weapon, Archery and Destruction stay and will be supported later
  ([original weapon skills](original-weapon-skills.md)). Critical Strike is out (bad for balance).
- **Skill count:** the new skills take the total past Daggerfall's 35 (the earlier "35 for now" no longer fits). Hard
  cap 64 until the skill-raised bitfield is widened; each new skill needs skill tables, character sheet and class maker
  entries, guild training, bridge sheet slots and save compatibility.

## New skills

Melee, Rifles and Pistols, Shotguns, Automatics, Explosives, Energy Weapons. Marksmanship is planned but in the backlog
([marksmanship](marksmanship.md)).

### Melee
Raises close combat and greatly raises damage reduction while a melee weapon is held, to make melee viable. Numbers
and perks open. Hand-to-Hand stays separate: it governs martial arts attacks such as vanilla Doom's fist.

### Rifles and Pistols
All semi-automatic ballistic rifles and pistols.
- **25:** reversed, weaker Deadeye: fast-firing guns get the larger multiplier (about 2.5x), slow ones down to 1.5x.
  Reload 20% faster.
- **50:** a shot that kills carries its remaining (overkill) damage on through the corpse to the next enemy, with no
  limit while damage remains. Reload another 20% faster. A recharging pool of 100 bonus damage is spent on shots
  (reading: it refills over 0.5 s and is always recharging).
- **75:** Deadeye, the complement of 25: 1.5x for fast-firing guns up to 3x for slow ones, multiplying with 25. Reload
  another 20% faster.
- **100:** open; something game-changing. Owner ideas: +25% maximum fire rate on all pistols.
- Note: faster raise and lower may not look good.

### Automatics
Damage +0% to +60% at 100.
- **25:** Burst fire: +30% damage on the first 3 shots of a burst; the bonus resets 0.3 s after the burst ends.
  Daggerfall sends Doom the modifier as "+x% on the first n shots of a burst".
- **50:** Marine effect at about half strength, as a whole-shot rule (DRLA Marine: rapid-fire uses 1 ammo per 4
  shots), for example every 2nd shot free.
- **75:** open (stagger or suppression; Doom monsters already have pain chance).
- **100:** Marine effect at full strength (1 ammo per 4 shots).

### Shotguns
Damage +0% to +75% at 100.
- **25:** reload about 35% faster.
- **50 and 100:** Renegade effect, milder (DRLA Renegade: +50% pellets). At 100, reload faster still.
- **75:** heavy knockback scaled by enemy size, stagger, and bonus damage when the knockback slams the enemy into a
  wall.

### Explosives
Damage +0% to +60% at 100. The proposal's primary perks stand, except rocket jump (does not fit Doom):
- **25:** own splash hurts 50% less. **50:** bonus damage to the primary (directly hit) target instead of rocket jump.
  **75:** immune to own splash.
- **100: Inpulsa's Broken Heart:** enemies killed by explosives explode for about 25% of their maximum health around
  them, and those deaths chain, each generation at half effect (25%, 12.5%, 6.25% and so on).

### Energy Weapons
Theme: escalating damage for even more escalating cost and ammo use, the rich guy's guns. **25:** energy weapon ammo
consumption increases (with more damage). Rest open; proposals wanted.

## Jumping (owner, 2026-11-25)

- Jump height linear to +100% at 100, plus a +25% spike from 25 on (+125% at 100). Double jump at 50, fall damage
  immunity at 75, triple jump at 100. Jumping reduces fall damage below 75; curve open.
- The fall damage curve must keep jumping in place (including double and triple jumps) from causing fall damage.
- **Prerequisite:** fall damage must exist. Doom has none by default, and with Daggerfall's rendering off it is not
  clear the hidden Daggerfall pawn takes any either. Make sure fall damage is in the game first.
- Skill effects in Doom are milder than Daggerfall's die rolls (continuous scaling stays modest).
