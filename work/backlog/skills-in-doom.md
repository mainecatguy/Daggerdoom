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
- New skills and the perk framework: in todo, `work/queue/skillcore/01.opus.new-skills-and-perk-framework.md`.
- Stay within Daggerfall's 35 skills. **Owner (2026-11-26): remove the nine monster languages for now; their slots make room for the new skills.** (Earlier: "Open: the new skills need more than 35.") (Facts: hard cap 64 until the
  skill-raised bitfield is widened; each new skill needs skill tables, character sheet and class maker entries, guild
  training, bridge sheet slots and save compatibility.)
- Skill effects in Doom are milder than Daggerfall's die rolls.

**Open owner answers the cards wait on:** perks follow live or base skill value
(`skillcore` 01 uses base until answered); rifles in Rifles and Pistols or not (`skillperks` 05).

## New skills

Melee, Rifles and Pistols, Shotguns, Automatics, Explosives, Energy Weapons. Marksmanship is planned but in the backlog
([marksmanship](marksmanship.md)).

### Melee
Raises close combat and greatly raises damage reduction while a melee weapon is held, to make melee viable. Numbers
and perks open. Hand-to-Hand stays separate: it governs martial arts attacks such as vanilla Doom's fist.

### Rifles and Pistols
In todo: `work/queue/skillperks/05.opus.rifles-and-pistols.md` (gated on the rifles research,
`skillresearch` 01).

### Automatics
In todo: `work/queue/skillperks/02.opus.automatics.md`.

### Shotguns
In todo: `work/queue/skillperks/04.opus.shotguns.md`.

### Explosives
In todo: `work/queue/skillperks/03.opus.explosives.md`.

### Energy Weapons
Theme: escalating damage for even more escalating cost and ammo use, the rich guy's guns. **25:** energy weapon ammo
consumption increases (with more damage). Rest open; proposals wanted.

## Jumping
In todo: `work/queue/skillperks/01.opus.jumping.md` (adds fall damage first).

## Other skills (placeholders, owner is detailing)

Not designed yet unless noted. Brainstormed perks for many of these are in section 3 of the proposal note.

- **Hand-to-Hand:** governs martial arts attacks, such as vanilla Doom's fist (owner).
- **Short Blade, Long Blade, Axe, Blunt Weapon, Archery:** stay; supported later ([original weapon
  skills](original-weapon-skills.md)).
- **Destruction:** stays; supported later.
- **Restoration, Illusion, Alteration, Thaumaturgy, Mysticism:** placeholders.
- **Medical:** In todo (works and levels as in Daggerfall): `work/queue/skillbasics/01.opus.daggerfall-interaction-skills.md`. Perks TBD.
- **Running:** In todo (levels from time spent running, 1.5x Daggerfall's rate; owner calls it Athletics): `work/queue/skillbasics/02.opus.running-levels.md`. Perks and the movement speed formula TBD, to be defined here.
- **Dodging:** placeholder.
- **Swimming:** placeholder.
- **Climbing:** placeholder. (Already wired: Doom runs climbs with Daggerfall's Climbing chances and reports skill
  uses.)
- **Stealth:** placeholder. (Planned to slow the detection bar, `gamedesign.md`.)
- **Backstabbing:** In todo (up to 5x damage to unaware enemies; levels 10x faster from shooting unaware enemies): `work/queue/skillbasics/03.opus.backstabbing.md`. Perks TBD as a separate task.
- **Lockpicking:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Pickpocket:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Mercantile:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Etiquette:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Streetwise:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Languages (Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian, Impish):** removed for now
  (owner, 2026-11-26); their slots hold the new skills (`gamedesign.md`; [revisit languages](revisit-languages.md)).
- **Critical Strike:** out (owner).
- **Marksmanship (new):** backlog ([marksmanship](marksmanship.md)).

## Perk popups
In todo: `work/queue/skillcore/02.opus.perk-popup.md`.

## Skill XP and buying skills
In todo: research `work/queue/skillresearch/02.opus.skill-xp-system.md`, then the purchase menu with visible perks
(`skillmenu` 01) and the skill point sound and message (`skillmenu` 02). Daggerfall's level-up flow in Doom:
`levelup` 01.

## Tutorial (owner, 2026-11-25: backlog item, after the game is complete)

Update Daggerfall's tutorial into a Doomerfall tutorial that covers how all this works, including buying skills with
Skill XP.
