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

## Attributes

What your attributes do now. They use your current value, so spells and effects that fortify or drain an attribute
count while they last.

- **Agility:** you reload and switch weapons faster: up to 40% faster at 100 (20% at 50). You also get a chance to
  dodge damage completely: 15% at 100 (7.5% at 50). Agility above 100 counts as 100.
- **Willpower:** changes the damage you take in combat and from the environment (monsters, your own explosions,
  harmful floors, crushers, falls): 20% less at 100, normal at 50, 20% more at 0. It is applied last, after armor and
  resistances. Willpower above 100 counts as 100. It also affects your ability to cast spells.

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

### No Doom class

Your Daggerfall class is your only class. New Game goes straight from Doom's menu to Daggerfall's character creation,
with no Doom Roguelike Arsenal class menu, and your Doom character has no DRLA class perk (no Marine Ammochain and the
like). You start with fists and a pistol. Perks come from your skills.

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

## Your fists

- You always have your fists. Press **1** to raise them, and they use your Hand-to-Hand skill.
- Fists are not an item, so they never show in your inventory and can't be dropped, sold or lost.
- Fists always take the first square of hotkey 1. You can't remove or replace them there. Key 1's other squares
  take items as usual, and pressing 1 again moves on to them.
- Raising your fists only lowers your gun. Press the gun's key to raise it again, with its magazine as you left it.

### Seeing a gun's skills

Select **Info** on a gun in your inventory to see which weapon skills it counts as. The description starts with the
gun's name and its types, for example "Plasma Rifle. Types: Energy" or "Laser Shotgun. Types: Energy, Shotgun". A gun
with two types uses whichever of those skills is higher (above). Doom Roguelike Arsenal guns also show a short
description from the arsenal's own notes, and every gun shows its material and weight.

- The types are Pistol, Shotgun, Automatic, Explosive, Rifle, Energy, Melee and Hand-to-Hand, one for each weapon
  skill.
- "Types: none" means the gun belongs to no weapon skill yet.
- A gun's types appear once its picture has loaded in the inventory. Until then the description shows only its name.

## Ammo pickups

Ammo comes in material tiers, from Regular through Steel, Silver and on up to Daedric. Higher tiers hit harder and
are rarer, but a pickup of any tier holds the same amount as a Regular one: a clip is 10 bullets, a box of bullets 50,
4 shells, a box of shells 20, 1 rocket, a box of rockets 5, a cell 20 and a cell pack 100. Ammo a monster drops holds
half (at least 1). A shop pack of any tier holds 80 bullets, 20 shells, 8 rockets or 100 cells.

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

## Locked doors

Some dungeon doors are locked. Look at one: it reads **Locked.**, or "This is a magically held lock..." for a magic one.
A door you have picked open reads **Door**.

- Press **Use (E)** on a locked door while you carry **lockpicks** (shown in your inventory, 25 gold each at general
  stores and pawn shops, and sometimes in treasure or on human enemies; every new character starts with a few) to start
  lockpicking. Press **Fire** when the gold chevron is over the white arc. Your Lockpicking skill and your level make
  the arc wider and the chevron slower, as Daggerfall's lockpicking chance would.
- A **hit** opens the door and keeps your pick. A **miss** breaks one pick. Each attempt trains Lockpicking, and you may
  try again as often as you have picks.
- Getting hit, walking away or pressing Use again cancels the attempt for free.
- Without lockpicks, Use only tells you the door is locked. A **magically held** door cannot be picked.
- A door you picked open **stays unlocked**: after saving and loading, and after you leave the dungeon and come back.
- Levers and other switches in a dungeon can still lock, unlock, open and close doors, as in Daggerfall.

## Entering a place

- When you go through a door into or out of a dungeon or building, or walk out of a town, the game pauses until the
  new place is ready (and autosaved, if autosaves are on). A long wait shows **Loading...**. Nothing in the new place moves or
  attacks you until play resumes.

## Damage numbers

Turn on **Show damage numbers** in Options, HUD Options to see how much damage each of your hits does: a small gold
number rises over the monster you hit and fades in about a second. Hits that land together, such as shotgun pellets,
show as one number. It is off by default.
