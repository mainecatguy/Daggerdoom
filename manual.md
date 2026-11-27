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

- **Strength:** your melee hits do more damage: +1% per point, so +50% at 50 and double damage at 100. Melee means
  your fists and kicks and weapons that use the Melee skill, such as the chainsaw, the Ripper and the Energysaw.
  Shots fired from a gun never get it, even if they land after you switch to your fists. Strength above 100 counts
  as 100.
- **Agility:** you reload and switch weapons faster: up to 40% faster at 100 (20% at 50). You also get a chance to
  dodge damage completely: 15% at 100 (7.5% at 50). Agility above 100 counts as 100.
- **Speed:** how fast you walk and run in Doom. 50 is normal speed; 0 is 25% slower and 100 is 25% faster. It does
  not change how fast you climb or how high you jump. Speed above 100 counts as 100.
- **Endurance:** raises your maximum HP (see Health).
- **Willpower:** changes the damage you take in combat and from the environment (monsters, your own explosions,
  harmful floors, crushers, falls): 20% less at 100, normal at 50, 20% more at 0. It is applied last, after armor and
  resistances. Willpower above 100 counts as 100. It also affects your ability to cast spells.
- **Luck:** monsters drop ammo more often: each ammo drop has a Luck-in-100 chance to come with a second one, so about
  twice as many ammo drops at 100 (half again as many at 50). It never changes what else a place's monsters drop. Luck above 100
  counts as 100. Luck keeps all its usual Daggerfall effects too.
- **Intelligence** and **Personality:** work as in Daggerfall (Intelligence sets your spell points; Personality helps
  when talking, trading and dealing with people).

## Weapon skills

Doomerfall adds seven weapon skills to your character sheet: the gun skills **Shotguns**, **Automatics**,
**Explosives**, **Pistols** and **Rifles**, plus **Energy Weapons** and **Melee**. The monster languages (Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian,
Impish) are gone: you can no longer calm monsters by speaking to them.

- Most weapons belong to one of these skills; a few belong to two (see "Weapons that belong to two skills"). Shotguns covers shotguns, Automatics covers chainguns, miniguns and
  other rapid-fire guns, including the Assault Rifle Chaingun, Assault Rifle Minigun and Autocannon, Explosives covers rocket, missile and grenade launchers, and Pistols covers every pistol,
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
- Automatics changes how its guns behave (see "Automatics" below). The other gun skills do not yet.

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
like). You start with fists and a gun chosen by your best gun skill (below). Perks come from your skills.

### Your starting gun

When guns are in the game, a new character starts with the most basic gun of their highest gun skill, instead of the
pistol. The pistol's usual starting bullets (60 with the Doom Roguelike Arsenal, 50 without) set the ammo:

| Highest skill | Starting gun | Starting ammo |
|---|---|---|
| Pistols | Pistol | 60 bullets (50) |
| Rifles | Light Carbine | 60 bullets (50) |
| Automatics | Chaingun | 60 bullets (50) |
| Shotguns | Shotgun | 20 shells (16) |
| Explosives | Rocket launcher | 12 rockets (10) |
| Melee | Chainsaw | none |

- With the Doom Roguelike Arsenal you get its version of the gun; without it, stock Doom's. The Light Carbine is the
  same either way.
- Only these six skills count. Hand-to-Hand, Energy Weapons and Daggerfall's old weapon skills don't. Energy weapons
  as starting guns come later.
- Your skill values decide, whether or not the skill is one of your class skills. A class with none of the six as a
  class skill gets the gun of whichever of them rolled highest.
- **A tie gives you every tied gun.** Ammo of one kind is not doubled: Pistols and Rifles tied at 30 give a pistol, a
  Light Carbine and 60 bullets. The first gun in the table's order is in your hands; the others are on their number
  keys.
- Each starting gun goes on its usual number key (pistol 2, shotgun 3, chaingun and Light Carbine 4, rocket launcher
  5, chainsaw on 1 after your fists).

## Perks

A skill earns a **perk** when it reaches 25, 50, 75 and 100.

- When you earn a perk, the game pauses and a window tells you what the perk does. Click to close it, and play
  carries on.
- If the skill rises while a menu is open, for example while training or travelling, the window appears once
  you are back in the game. Several perks at once share one window.
- Loading a save does not show perks you already have.
- So far, Jumping and the gun skills (Shotguns, Automatics and Explosives) have perks. The window says when a perk
  does not work yet.

### Automatics

Automatics covers chainguns, miniguns and other rapid-fire guns, such as the stock chaingun and the Battle Rifle. The
Uzi is a Pistol, not an Automatic.

- **Damage:** automatic guns do more damage as the skill rises, up to 60% more at 100.
- **25, burst fire:** the first 3 shots of each burst do 30% more damage. Let go of the trigger for a moment (0.3
  seconds) and the next burst gets the bonus again, so short bursts hit harder than holding the trigger down.
- **50:** every second shot uses no ammo.
- **75:** each hit makes the enemy take 1% more damage from everything, yours and anyone else's, up to 15%. It never
  wears off for that enemy.
- **100:** automatic guns use only 1 ammo for every 4 shots.
- The bonuses add up: a burst shot at 100 does 1.6 x 1.3, about twice the damage.
- Only hits from the automatic gun itself get these bonuses. A rocket, grenade or exploding barrel that goes off while
  you hold an automatic gets nothing. A shot from an automatic gun keeps its bonus even if you switch weapons before
  it lands.
- These only work in the Daggerfall world. Your current skill counts, so an effect that lowers or raises the skill
  changes them too.

## Falling and jumping

In Daggerfall's world, falls hurt, by Daggerfall's own rule:

- A fall is measured from where you left the ground to where you land. The first **5 metres** are free; every metre
  past that costs **5 HP**. A 9 metre drop costs 20 HP, a 15 metre drop 50 HP. Armor does not help.
- A jump that lands where it started never hurts, however high it goes, double and triple jumps included.
- Grabbing a wall while climbing starts the fall over from there.
- Landing outdoors on a sea or lake tile never hurts, as in Daggerfall.
- While a **Slowfall** spell is active, falls do not hurt. If it runs out in mid-air, only the part of the fall after
  it ran out counts. Slowfall does not make you fall more slowly yet; you fall at the normal speed.

Your **Jumping** skill (the permanent value on your character sheet) changes how you jump:

- Every point of Jumping makes your jumps 1% higher, up to twice as high at 100.
- **25:** a sudden boost of 25% more height on top of that (so at 100 your jumps are 2.25 times as high).
- **50:** double jump. Press Jump again in mid-air to jump once more, as strong as a jump from the ground. You can
  also use it after walking off an edge.
- **75:** falling no longer hurts you.
- **100:** triple jump. You can jump twice in mid-air.

Below 75, Jumping does not lower falling damage yet. Jumping does not train by jumping in Doom yet; train it at a
guild.

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
gun's name and its types, for example "Plasma Rifle. Type: Energy" or "Laser Shotgun. Types: Energy, Shotgun". A gun
with two types uses whichever of those skills is higher (above). Doom Roguelike Arsenal guns also show a short
description from the arsenal's own notes, and every gun shows its material and weight.

- The types are Pistol, Shotgun, Automatic, Explosive, Rifle, Energy, Melee and Hand-to-Hand, one for each weapon
  skill.
- "Types: none" means the gun belongs to no weapon skill yet.
- A gun's types appear once its picture has loaded in the inventory. Until then the description shows only its name.

## Light Carbine

The Light Carbine is a semi-automatic rifle: one shot per trigger pull, with a little more damage per shot than the
Battle Rifle (+20%). Otherwise it handles like the Battle Rifle: same accuracy, 20-round magazine, bullets and reload.
It is always in the game. Former Humans, Former Commandos, Elite Former Humans and Former Cyborgs that carry a battle
rifle drop a Light Carbine about half the time instead of a Battle Rifle.

## Ammo pickups

Ammo comes in material tiers, from Regular through Steel, Silver and on up to Daedric. Higher tiers hit harder and
are rarer, but a pickup of any tier holds the same amount as a Regular one: a clip is 10 bullets, a box of bullets 50,
4 shells, a box of shells 20, 1 rocket, a box of rockets 5, a cell 20 and a cell pack 100. Ammo a monster drops holds
half (at least 1).

**Shops are where you buy ammo.** General stores, weapon smiths and armorers always have Regular bullets, shells,
rockets and energy cells, and restock them whenever Daggerfall restocks the shop. A typical general store holds about
300 bullets, 120 shells, 30 rockets and 300 cells, and an armorer about half that. Each shop has its own habits, which
stay the same in every game. Some carry far more of one kind, an occasional one deals almost only in a single kind, a
few are big depots and some are nearly empty. Better shops stock more. Regular ammo costs 1 gold a bullet, 3 a shell,
10 a rocket and 10 a cell, before the shop's own prices. Weapon smiths also sometimes stock higher tiers, in packs of
80 bullets, 20 shells, 8 rockets or 100 cells.

Regular ammo has no material, so it goes by its plain name: Bullets, Shells, Rockets, Energy Cells. Every other tier
puts its material first, such as Silver Bullets.

Health, ammo and other pickups lying in a place are always the same ones each time you come. A pickup you take is
gone for good: it does not come back when you leave and return, or when you load a save.

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
- People keep living while you rest or loiter. When the window closes, everyone is already where the new hour puts
  them, so nobody jumps to a new place after you look up.

You cannot rest:

- with **hostile monsters nearby**: any monster that is after you and can see you, or any monster within about 12 metres, even one
  that has not noticed you. Daggerfall tells you enemies are nearby. Kill them or get away first.
- while **falling, climbing or swimming**.
- **outdoors inside a town's walls** (camping in town is a crime, and the guards come), or **inside a building**
  unless you rented a room there, own it, or belong to a guild that lets members rest in its hall.

## Character sheet and spellbook

Press **P** for Daggerfall's character sheet and **Backspace** for your spellbook (rebind them in Options, Customize
Controls, Doomerfall Controls as **Open Character Sheet** and **Open Spellbook**). Like the other keys, they are set for
you only on a fresh install. Doom stays frozen while either is open.

- The character sheet works as in Daggerfall. Its **Spellbook**, **Inventory** and **Logbook** buttons open those windows
  on top of it, and closing them takes you back to the sheet.
- The spellbook works as in Daggerfall: browse your spells and their effects, sort, rename and delete them. Backspace,
  Escape or **Exit** closes it.
- You need a spellbook in your inventory. Without one, you are told "You have no spellbook!"
- **You cannot cast spells yet.** Choosing a spell in the spellbook, however you opened it (Backspace, the character
  sheet, the spellbook in your inventory, or the level-up sheet), says so and does nothing else.

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
- The first time you open a dungeon's door, or start or load a game inside a dungeon you have not visited, the game
  builds that dungeon first. This can take from a few seconds to over a minute on a busy PC. The game shows
  **Loading...** and pauses until it is done: nothing in the place moves or attacks you, Use does nothing, and you
  cannot save. Daggerfall's clock stops too, so poison, disease and other timed effects do not run during the wait.
  The menu and console still work, so you can quit. A very large dungeon army can also show **Loading...** for a second or two as you enter.

## Damage numbers

Turn on **Show damage numbers** in Options, HUD Options to see how much damage each of your hits does: a small gold
number rises over the monster you hit and fades in about a second. Hits that land together, such as shotgun pellets,
show as one number. It is off by default.
