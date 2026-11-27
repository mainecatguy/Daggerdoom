# Doomerfall player manual

What players need to know to play Doomerfall. Started 2026-11-25 with one fact; more will be added.

## Health

Your maximum HP comes from your Endurance and your level:

- You start with **50 + your Endurance** HP.
- Each level after the first adds **your Endurance / 15** HP.
- It always uses your current Endurance. Raising Endurance later counts for all your past levels too.
- When your maximum HP goes up (a level, more Endurance), your current HP goes up by the same amount. When it goes
  down, your current HP is lowered only if it is now above the new maximum.
- Spells and effects that fortify or drain Endurance count while they last: Fortify Endurance raises your maximum HP
  until it wears off, and Drain Endurance lowers it until it is healed.

Your class gives an **Endurance (and max Endurance) bonus**: it raises your starting Endurance and how high your
Endurance can go (past 100 for tough classes). A Barbarian gets +17, a Warrior +12, a Mage -2.

| Endurance | Level 1 | Level 10 | Level 20 |
|---|---|---|---|
| 30 | 80 | 98 | 118 |
| 50 | 100 | 130 | 163 |
| 75 | 125 | 170 | 220 |
| 100 | 150 | 210 | 277 |

## Levelling up

Your level comes from your skills, as in Daggerfall. Not every skill can be trained by use yet:

- **Fighting in Doom does not train any skill yet.** Weapon skills, Hand-to-Hand, Critical Strike, Dodging and the
  magic schools do not improve from combat or spells cast in Doom.
- What does count today: **Climbing** (each climb), and what you do in Daggerfall's own windows, such as
  **Etiquette** and **Streetwise** when talking to people, and **Mercantile** when buying and selling.

Skills only go up, and a new level is only granted, when time passes: when you **rest** (see Resting) or **fast
travel**. Daggerfall checks your skills at most once every 6 game hours.

When you have earned a level, Doom's HUD says **"You have reached level N"**, and Daggerfall's character sheet opens
by itself inside Doom (after you wake up, or when you arrive):

- Your level and maximum HP have already gone up.
- You get a few **bonus points** (usually 4 to 6) to add to your attributes. Click an attribute, then click the
  small **up arrow** to its right to add a point to it (the down arrow takes one back). The number between the
  arrows is how many points are left.
- Click **Exit** when all the points are spent. If you try to leave earlier, Daggerfall reminds you to spend them.

You are back in Doom with the new attributes in effect.

## Weapon skills

Doomerfall adds seven weapon skills to your character sheet: the gun skills **Shotguns**, **Automatics**,
**Explosives**, **Pistols** and **Rifles**, plus **Energy Weapons** and **Melee**. The monster languages (Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian,
Impish) are gone: you can no longer calm monsters by speaking to them.

- Most weapons belong to one of these skills; a few belong to two (see "Weapons that belong to two skills"). Shotguns covers shotguns, Automatics covers chainguns, miniguns and
  other rapid-fire guns, Explosives covers rocket, missile and grenade launchers, and Pistols covers every pistol,
  revolver and Uzi, including plasma pistols and pistols that fire shotgun shells. Rifles covers ballistic
  semi-automatic and single-shot rifles that are not explosives, energy weapons, shotguns or pistols.
- No rifle counts as a pistol.
- **Energy Weapons** covers guns that use cells (plasma rifles, lasers, railguns, BFGs) and energy guns that recharge
  instead of using cells (the nuclear plasma guns and BFGs), even when they fire like an automatic. Energy pistols and
  energy shotguns belong to two skills (below).
- **Melee** covers the chainsaw and other melee weapons, such as powered saws, the Ripper and the Dragonslayer sword. Your bare fists are not
  Melee: they use Hand-to-Hand, as in Daggerfall.
- Energy Weapons and Melee are placeholders for now: they show on the sheet, can be trained and are saved, but have
  no perks yet.
- The Fighters Guild trains all seven weapon skills.
- Magic items that enhance a monster language, including the Enhances Daedric power that Fire and Frost Daedra
  souls add when bound into an item, still exist but do nothing. Their description says "(no effect)". The item
  maker cannot make Enhances Skill items for the weapon skills.
- A character imported from a classic Daggerfall save starts the weapon skills untrained; their old language values
  and practice are not carried over.
- The gun skills do not change how guns behave yet.

### Class skills

Every class lists Doom weapon skills in place of Daggerfall's weapon skills. Each class has its own hand-made list,
with at least one gun skill and usually two or more chosen to fit it. A Warrior's primary skills are Shotguns,
Automatics and Melee, an Archer's primary skill is Rifles, and a Mage carries Pistols and Energy Weapons as minor skills.
Destruction, Hand-to-Hand and Dodging stay where they were. Critical Strike and the monster languages are gone from
every class, replaced by other skills, for example Running for the Assassin and the Monk.

- The custom class maker offers the seven Doom weapon skills instead of Short Blade, Long Blade, Axe, Blunt Weapon and
  Archery, and no longer offers Critical Strike.
- A custom class from an older save converts by a default rule: Short Blade becomes Pistols, Long Blade Automatics,
  Axe Shotguns, Blunt Weapon Melee and Archery Rifles. If the class already has that skill, it takes the first one it
  lacks of Pistols, Shotguns, Automatics, Rifles, Explosives, Energy Weapons and Melee. A language becomes Etiquette,
  Streetwise, Mercantile or Medical, and Critical Strike becomes a weapon skill or Running.
- An older save loads at the same level, with the same progress towards the next level. The class lists change to the
  new ones, but your skill values are kept as they were.

## Perks

A skill earns a **perk** when it reaches 25, 50, 75 and 100.

- When you earn a perk, the game pauses and a window tells you what the perk does. Click to close it, and play
  carries on.
- If the skill rises while a menu is open, for example while training or travelling, the window appears once
  you are back in the game. Several perks at once share one window.
- Loading a save does not show perks you already have.
- So far, Jumping and the gun skills (Shotguns, Automatics and Explosives) have perks. The window says when a perk
  does not work yet.

## Weapons that belong to two skills

Some guns fit two weapon skills, for example a laser shotgun is both a Shotgun and an Energy Weapon. Such a gun uses
whichever of its skills is higher, never both at once.

- **Pistols and Energy Weapons:** energy pistols, both the cell-fed ones (plasma pistols, the Plasma Uzi, the Baron
  Blaster, the Neural Stunner) and the self-charging ones (blasters, nuclear plasma pistols and the nuclear plasma
  revolver).
- **Shotguns and Energy Weapons:** energy shotguns, such as the laser shotgun, plasma shotguns and the nuclear plasma
  shotgun.
- No other pair counts: a pistol that fires shotgun shells is only a Pistol, and an automatic shotgun is only a
  Shotgun.
- If both skills are equal, the gun uses its main skill: Pistols for an energy pistol, Energy Weapons for an energy
  shotgun.

## Resting

Press **Z** (rebind it in Options, Customize Controls, Doomerfall Controls as **Rest**) to open Daggerfall's rest
window. Z is set for you only on a fresh install; if you played before resting existed, bind **Rest** there once.
It works as in Daggerfall:

- **Rest for a while**: rest for the number of hours you type.
- **Rest until healed**: rest until your health, fatigue and magicka are full.
- **Loiter**: pass the hours you type without recovering anything.
- Click **Stop**, or press the rest key again, to wake up early. Doom stays frozen while you rest; time passes in the world.
- **Resting restores HP three times as fast as in Daggerfall.** Fatigue and magicka come back at Daggerfall's rates.
  Resting also trains Medical.
- When you wake up, Daggerfall checks your skills, and you may level up (see Levelling up).

You cannot rest:

- with **hostile monsters nearby**: any monster that is after you and can see you, or any monster within about 12 metres, even one
  that has not noticed you. Daggerfall tells you enemies are nearby. Kill them or get away first.
- while **falling, climbing or swimming**.
- **outdoors inside a town's walls** (camping in town is a crime, and the guards come), or **inside a building**
  unless you rented a room there, own it, or belong to a guild that lets members rest in its hall.
