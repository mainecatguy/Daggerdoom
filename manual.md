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

## Perks

A skill earns a **perk** when it reaches 25, 50, 75 and 100.

- When you earn a perk, the game pauses and a window tells you what the perk does. Click to close it, and play
  carries on.
- If the skill rises while a menu is open, for example while training or travelling, the window appears once
  you are back in the game. Several perks at once share one window.
- Loading a save does not show perks you already have.
- So far, Jumping and the gun skills (Shotguns, Automatics and Explosives) have perks. The window says when a perk
  does not work yet.

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
