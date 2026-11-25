# Daggerfall skills in Doom

**Waiting on:** owner design. Research needs a specialist.

Proposal (undecided): `work/notes/20261125-skills-armor-proposal.md`: all 35 skills, weapon category skills, DRLA class
effects as skills, melee consolidation, language skills, and armor as damage reduction.

Owner decisions so far (2026-11-25):
- No Doom class. On New Game the Doom player is a normal character with no class effects; unless a Daggerfall skill
  says otherwise it has nothing, and Daggerfall applies skills and modifiers. DRLA classes are inspiration for skill
  effects only.
- Hand-to-Hand governs Doom melee damage (fists and other melee), for now.
- Archery stays a skill; its Doom role is not decided.
- Skill effects in Doom are milder than Daggerfall's die rolls.
- Stay within Daggerfall's 35 skills for now. (More would need a wider skill-raised bitfield past 64, new bridge sheet
  slots, skill tables, character sheet and class maker, guild training and save compatibility.)
- Each skill grants a perk at 25, 50, 75 and 100, besides any continuous scaling.
- Jumping: jump height up to +100% with a +25% spike at 25; double jump at 50; fall damage immunity at 75; triple jump
  at 100; Jumping reduces fall damage below 75. The spike stacks on top: +125% at 100. Open: the fall damage curve
  below 75.
