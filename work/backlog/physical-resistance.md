# Physical resistance from Frost resistance (card ready)

Waiting on: the owner moving it to todo; with or after `armor-damage-reduction`.

Owner decisions (2026-11-26, `gamedesign/decisions/20261126-thermal-and-physical-resistance-owner.md`): nothing deals
Frost to the player, so every Frost resistance source converts to physical resistance at 1/5: race (Nord +30 gives 6%;
no Frost bonus, no physical resistance), class traits (Resistant 5%, Immune 10%), Resist Frost potions and spells
(a chance-100 potion gives 20%), spellmaker Frost resistance. All sources add up; the total caps at 25%. It multiplies
with armor DR on physical hits. Table: `work/notes/20261126-armor-resistance-rerun.md`, section 2.

Done when: the character's physical resistance is computed from these sources, sent to Doom, capped at 25%, and shown
reducing physical damage multiplicatively in a test. Manual: one line under Armor.
