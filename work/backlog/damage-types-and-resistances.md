# Doom damage types mapped to Daggerfall resistances (card ready)

Waiting on: the owner moving it to todo. Proposal approved (owner, 2026-11-27: "Very good let's run with this proposal
for damage").

Doom sends each hit's damage type to Daggerfall, which applies its resistances as damage reduction.
- Types: Physical (armor and physical resistance), Thermal (was Fire; Fire Resistance is renamed Thermal Resistance),
  Shock, Poison, Magic. Nothing deals Frost to the player.
- Monster mapping (`work/notes/20261126-monster-damage-types.md`, mapping section): Imp projectile Thermal;
  Cacodemon half Thermal; Baron and Hell Knight projectiles Magic; Plasma to Shock; unknown or untyped damage
  Physical.
- Resistance as per-hit DR, relative to a normal character (`work/notes/20261126-armor-resistance-rerun.md`, section
  2): Resistant 41%, race resist 50%, immune 100%, low tolerance takes x1.41, critical weakness x1.64 (that note's
  table); resist potions and spells as in the note.
- Willpower multiplies all damage last.

Done when: hits of each type in a test are reduced by the matching resistance; untyped damage counts as physical. (The
Fire to Thermal label change is its own card, `thermal-relabel`.) Manual: a short section on damage types, which monsters deal what, and
which resistance stops it (owner, 2026-11-26).
