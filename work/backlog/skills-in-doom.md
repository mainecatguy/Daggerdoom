# Daggerfall skills in Doom

**Waiting on:** owner design. Research needs a specialist.

Proposal (undecided): `work/notes/20261125-skills-armor-proposal.md`: all 35 skills, weapon category skills, DRLA class
effects as skills, melee consolidation, language skills, and armor as damage reduction.

Owner decisions so far (2026-11-25):
- No Doom class. On New Game the Doom player is a normal character with no class effects; unless a Daggerfall skill
  says otherwise it has nothing, and Daggerfall applies skills and modifiers. DRLA classes are inspiration for skill
  effects only.
- Hand-to-Hand governs Doom martial arts attacks, such as vanilla Doom's fist. Not other melee weapons (corrected by
  the owner, 2026-11-25).
- New weapon skills (Pistols and the other Doom categories) are added, not made by renaming old skills. Short Blade,
  Long Blade, Axe, Blunt Weapon and Archery (the owner said "Marksmanship") stay in the game; how they work in Doom is
  a separate backlog item ([original weapon skills](original-weapon-skills.md)).
- Pistols: the proposed perks are fine to the extent they can be done safely. Overpenetration reaches at most one more
  enemy (reading of "overpenetration hits only one enemy").
- Skill effects in Doom are milder than Daggerfall's die rolls.
- Stay within Daggerfall's 35 skills for now. **Conflict:** adding new weapon skills needs more than 35; open. (More would need a wider skill-raised bitfield past 64, new bridge sheet
  slots, skill tables, character sheet and class maker, guild training and save compatibility.)
- Each skill grants a perk at 25, 50, 75 and 100, besides any continuous scaling.
- Jumping: jump height up to +100% with a +25% spike at 25; double jump at 50; fall damage immunity at 75; triple jump
  at 100; Jumping reduces fall damage below 75. The spike stacks on top: +125% at 100. Open: the fall damage curve
  below 75.
- The fall damage curve must at least ensure that jumping in place (including double and triple jumps) never causes
  fall damage at any skill level. Falls onto lower ground can still hurt.
