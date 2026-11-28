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

- **Fighting trains the skill of the weapon you use.** Every 250 damage you deal with a weapon counts as one use of
  its skill (Shotguns, Automatics, Explosives, Pistols, Energy Weapons, Melee, or Hand-to-Hand for your fists).
  Dodging and the magic schools do not improve from fighting yet.
- **Climbing** counts each climb, and so do **Running** and **Backstabbing** (see below). What you do in Daggerfall's own windows counts
  as in Daggerfall, such as **Etiquette** and **Streetwise** when talking to people, **Mercantile** when buying and
  selling, **Pickpocket**, **Medical** when resting, and **Lockpicking** (see Talking, trading and stealing).
- You can also **buy** skill points with **Skill XP** (see "Skill XP and the Skills menu"). Bought points count
  towards your level just like trained ones, and a level earned that way is granted straight away.

**Running** improves the more time you spend running, as in Daggerfall but one and a half times as fast: about
5 practice uses per second of running. Running means holding **Run** (or having **Always Run** on) while you actually
move. Walking, standing still, holding Run without moving, or running straight into a wall does not count (sliding
along a wall does, because you are still moving). Time with the game paused never counts, and neither does time spent
with **Horse** or **Cart** chosen in the transport menu. Running does not make you faster in Doom yet.

**Backstabbing** makes your hits on enemies that have not noticed you hit harder: normal damage at skill 0, rising
evenly to **five times** the damage at skill 100 (three times at 50). It works with every weapon, guns included, and
stacks with your other damage bonuses (ammo and weapon material). An enemy has noticed you once it is after you, is
fighting anything else, or has heard you: any noise you made before this attack (an earlier shot, for example) puts it on
alert, even if it has not found you yet. Only the noise you make in the first second after you start the attack
does not count, and that second includes any spin-up: a weapon that spins up for most of a second gets only the rest
of that second of firing. Noise after that first second does count, even in the same held burst. A reload in the
middle of a burst is not a fresh start, and a new shot after your weapon is ready again is a new attack, so an enemy
that heard the earlier shot is alert. This way a loud gun can still land a sneak shot on an enemy that had not heard
you before. Your first hit wakes it up, so the bonus is for the opening hit: every pellet of one shotgun blast that lands together counts, the next
shot does not. Each such sneak hit also practises Backstabbing, ten times as much as a hit practises a weapon skill in Daggerfall.

Skills only go up, and a new level is only granted, when time passes: when you **rest** (see Resting) or **fast
travel**. Daggerfall checks your skills at most once every 6 game hours.

When a skill goes up by a point, you hear Daggerfall's fanfare and the top of the screen says **"Your <skill> skill
has improved."** If several skills go up at once, the fanfare plays once and each skill gets its own message. This
happens when you close the message at the end of a rest, or once you have arrived from fast travel.

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
  Strength also changes the damage of shotguns, explosives and automatic weapons: 20% less at 0, normal at 50, 20%
  more at 100. Other guns don't get it. What counts is the weapon that made the attack, so a rocket you fired
  still counts as an explosive if it lands after you switch to your fists. Strength above 100 counts as 100.
- **Agility:** changes the damage of every gun: 10% less at 0, normal at 50, 10% more at 100. Rifles and pistols get
  that much again, so they range from 20% less to 20% more. Fists and melee weapons don't get it. You also reload and
  switch weapons faster: up to 40% faster at 100 (20% at 50). Agility does not let you dodge. Agility above 100
  counts as 100.
- **Speed:** how fast you walk and run in Doom. 50 is normal speed; 0 is 25% slower and 100 is 25% faster. It does
  not change how fast you climb or how high you jump. Speed above 100 counts as 100.
- **Endurance:** raises your maximum HP (see Health).
- **Willpower:** changes the damage you take in combat and from the environment (monsters, your own explosions,
  harmful floors, crushers, falls): 20% less at 100, normal at 50, 20% more at 0. It is applied last, after armor and
  resistances. Willpower above 100 counts as 100. It also affects your ability to cast spells.
- **Luck:** every monster that dies, whoever killed it, has a chance to drop ammo: half your Luck, in percent (25% at
  50, 50% at 100; no chance at 0). The ammo is one small dropped pickup of a random type (bullets, shells, rockets or
  cells), of the usual materials for the area. Summoned and revived monsters never drop anything, and town guards are
  not monsters, so they never roll. Luck never changes what else monsters drop.
  Above 50, Luck also gives you a chance for a super critical hit that does 5 times the damage: 0.1% per point
  above 50, so 5% at 100 and none at 50 or below. Each bullet, pellet, punch or projectile hit rolls once. An
  explosion rolls once, and a lucky explosion is critical on everything it hits. Burning and other damage over time
  is never critical. Luck above 100 counts as 100. Luck keeps all its usual Daggerfall effects too.
- **Intelligence** and **Personality:** work as in Daggerfall (Intelligence sets your spell points; Personality helps
  when talking, trading and dealing with people).

On the character sheet (P), left-click an attribute to read Daggerfall's description followed by what it does in
Doomerfall: the rule, its formula, and what your current value gives you.

## Weapon skills

Doomerfall adds seven weapon skills to your character sheet: the gun skills **Shotguns**, **Automatics**,
**Explosives**, **Pistols** and **Rifles**, plus **Energy Weapons** and **Melee**. The monster languages (Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian,
Impish) are gone: you can no longer calm monsters by speaking to them.

- Most weapons belong to one of these skills; a few belong to two (see "Weapons that belong to two skills"). Shotguns covers shotguns, Automatics covers chainguns, miniguns and
  other rapid-fire guns, including the Uzi and its variants (except the Plasma Uzi, which is still a Pistol and an Energy Weapon), the Assault Rifle Chaingun, Assault Rifle Minigun and Autocannon, Explosives covers rocket, missile and grenade launchers, and Pistols covers every pistol
  and revolver, including plasma pistols and pistols that fire shotgun shells. Rifles covers ballistic
  semi-automatic and single-shot rifles that are not explosives, energy weapons, shotguns or pistols.
- No rifle counts as a pistol.
- **Energy Weapons** covers guns that use cells (plasma rifles, lasers, railguns, BFGs) and energy guns that recharge
  instead of using cells (the nuclear plasma guns and BFGs), even when they fire like an automatic. Energy pistols and
  energy shotguns belong to two skills (below).
- **Melee** covers the chainsaw and other melee weapons, such as powered saws, the Ripper and the Dragonslayer sword. Your bare fists are not
  Melee: they use Hand-to-Hand, as in Daggerfall.
- Melee is a placeholder for now: it shows on the sheet, can be trained and is saved, but has no perks yet.
- The Fighters Guild trains all seven weapon skills.
- The item maker's Enhances Skill power can raise any of the seven weapon skills, like any other skill.
- Old powers that enhanced a monster language now enhance another skill instead, the same one every time: Orcish
  Medical, Harpy Jumping, Giantish Pistols, Dragonish Melee, Nymph Stealth, Daedric Backstabbing, Spriggan
  Restoration, Centaurian Thaumaturgy, Impish Hand-to-Hand. So a Fire or Frost Daedra soul bound into an item adds
  Enhances Backstabbing, and "of Venom Spitting" items enhance Melee.
- A character imported from a classic Daggerfall save starts the weapon skills untrained; their old language values
  and practice are not carried over.
- Automatics, Explosives, Shotguns and Pistols change how their guns behave (see "Automatics", "Explosives",
  "Shotguns" and "Pistols" below). The other gun skills do not yet.

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

## Skill XP and the Skills menu

You earn **Skill XP** by hurting things in Doom: **1 Skill XP for every 100 damage** you deal, added up across
everything you hit. Monsters, guards and townspeople all count. Damage beyond what kills a target does not count, so
a rocket into a small monster is worth only that monster's health. Each target is worth its full health at most once,
even if it heals or is brought back to life. Your own allies are worth nothing.

Spend Skill XP in the **Skills menu**. Open it with **U** in Doom, or click **SKILLS** at the bottom of the
character sheet (P). Rebind the key in Options, Customize Controls, Doomerfall Controls, "Open Skills".

- The left side lists every skill you can raise, with its current value. Click one (or use the arrow keys).
- The right side shows that skill's **price for its next point**, the **BUY POINT** button, and all four of its
  **perks** (at 25, 50, 75 and 100). Perks you already have are marked with a star and shown in gold.
- Points get expensive. The price grows with the skill's value and your level, and depends on your class: classes
  that learn quickly in Daggerfall pay less. Every skill costs the same at the same value, whichever it is.
- Most of your growth still comes from using your skills. Skill XP adds about a quarter on top.
- A skill at 100 cannot be raised, and once any of your primary skills reaches 100, the others stop at 95, as in
  Daggerfall.
- If the points you buy earn a new level, you get it when you close the menu: the character sheet opens (or you
  return to it, if you opened the menu from there) and you assign your attribute points as usual.
- While a level-up is waiting for you to assign its attribute points, you cannot buy skill points. The SKILLS
  button on the sheet does not open the menu then. If you open the menu with its key, BUY POINT is greyed out until
  you assign the points on the character sheet.
- Your Skill XP is kept in your save.

## Perks

A skill earns a **perk** when it reaches 25, 50, 75 and 100. You can read every skill's perks in the Skills menu.

- When you earn a perk, the game pauses and a window tells you what the perk does. Click to close it, and play
  carries on.
- If the skill rises while a menu is open, for example while training or travelling, the window appears once
  you are back in the game. Several perks at once share one window.
- Loading a save does not show perks you already have.
- So far, Jumping and the gun skills (Shotguns, Automatics, Explosives and Pistols) have perks. The window says when a perk
  does not work yet.

### Automatics

Automatics covers chainguns, miniguns and other rapid-fire guns, such as the stock chaingun and the Battle Rifle. The
Uzi and its variants are Automatics too.

- **Damage:** automatic guns do more damage as the skill rises, up to 60% more at 100.
- **25, burst fire:** the first 3 shots of each burst do 30% more damage. Let go of the trigger for a moment (0.3
  seconds) and the next burst gets the bonus again, so short bursts hit harder than holding the trigger down.
- **25, ammo:** every third shot uses no ammo. The count starts again when you put the gun away.
- **50:** every second shot uses no ammo (this replaces the 25 saving).
- **50, fire-rate bonus:** every automatic gun has a speed of its own, set by the time between its shots, and gets
  a bonus to match ("tics" are Doom's 1/35-second steps; the gun's own speed, without mods):
  - **Slow guns** (4 or more tics between shots, such as the Battle Rifle and the stock chaingun): each bullet does
    25 more damage and passes through one more enemy, hitting the next one behind with full damage.
  - **Medium guns** (3 tics, such as the Uzi): each bullet does 7 more damage and passes through one more enemy.
  - **Fast guns** (1-2 tics, such as the minigun and the Thompson): each shot has a 10% chance to fire one extra
    bullet for free, a copy of the shot's own bullet with the same damage and spread.
  - The extra damage counts as part of the bullet's own damage, so every percentage bonus increases it too.
  - A gun with firing modes counts at the speed of the mode you use: the Grammaton Cleric Beretta is a slow gun in
    single and full-auto fire and a fast gun in burst fire. An alternate fire that shoots has its own speed. A gun
    that spins up counts at full speed.
- **75:** each hit makes the enemy take 1% more damage from everything, yours and anyone else's, up to 15%. It never
  wears off for that enemy.
- **75, suppression:** each hit slows the enemy's movement by 5% more, up to 40%. Its attacks are not slowed. The
  slow fades away over 5 seconds after your last hit, and a new hit adds to what is left.
- **100:** automatic guns use only 1 ammo for every 4 shots. Each hit now makes the enemy take 2% more damage from
  everything, up to 30% in total.
- The bonuses add up: a burst shot at 100 does 1.6 x 1.3, about twice the damage.
- Only hits from the automatic gun itself get these bonuses. A rocket, grenade or exploding barrel that goes off while
  you hold an automatic gets nothing. A shot from an automatic gun keeps its bonus even if you switch weapons, or
  save and load, before it lands, and so does anything the shot sets off (its explosion or fragments).
- These only work in the Daggerfall world. Your current skill counts, so an effect that lowers or raises the skill
  changes them too.

### Explosives

Explosives covers rocket, missile and grenade launchers, such as the stock rocket launcher and DRLA's Rocket Launcher.

- **Damage:** explosive weapons do more damage as the skill rises, up to 60% more at 100, both to the enemy a rocket
  hits and to everything its blast reaches.
- **25:** your own blasts hurt you 95% less.
- **50:** explosives do extra damage to the enemy they hit directly. This perk does not work yet.
- **75:** your own blasts hurt you 99% less.
- **100, Inpulsa's Broken Heart:** an enemy your explosives kill explodes for a quarter of its maximum health, hurting
  everything nearby (about a rocket blast's reach). Enemies killed by that blast explode too, each time at half the
  strength of the blast before. These blasts never hurt you, but they do hurt anyone else nearby, townspeople included.
  Big monsters make big blasts, so killing a large demon in a crowd can clear the crowd.
- In a big pack the blasts go off in quick succession over a few moments, not all at once.
- Only your explosive weapon's own shots count, including anything they break into, such as a cluster rocket's
  pieces. An exploding barrel or another gun's shot gets nothing. A rocket keeps its bonuses if you switch weapons
  before it lands.
- These only work in the Daggerfall world. Your current skill counts.

### Shotguns

Shotguns covers shotguns, such as the stock shotgun, the Double Shotgun, the Assault Shotgun and the Autoshotgun.

- **Damage:** every pellet does more damage as the skill rises, up to 75% more at 100.
- **25:** shotguns reload about 35% faster. For a shotgun that pumps or reloads after every shot, such as the stock
  shotgun, that is the pump after each shot, so it fires about a quarter faster.
- **50:** shotguns fire 50% more pellets.
- **75, knockback:** a shotgun blast shoves the enemy away from you and staggers it. The more pellets hit, the harder
  the shove, so it is strongest up close and with a big shotgun such as the Double Shotgun. Big, heavy enemies move
  less, and a light shove does not stagger. An enemy knocked into a wall takes up to 200 extra damage, more the faster
  it hits. This happens once per shot, not once per pellet.
- **100:** shotguns fire twice as many pellets, and the knockback and wall damage are twice as strong (up to 400).
- Only pellets from the shotgun itself count. These only work in the Daggerfall world, and your current skill counts.
- Shotguns that fire energy balls instead of pellets, such as the Plasma Shotgun, use Shotguns only when it is higher
  than your Energy Weapons skill. Then their balls get the damage bonus and the knockback, but you do not yet get more
  balls per shot at 50 and 100. A ball still counts if you switch guns before it lands.

### Energy Weapons

Energy Weapons covers plasma, laser and BFG guns, such as the stock Plasma Rifle and BFG9000.

- **Damage:** every hit does more damage as the skill rises, up to 50% more at 100.
- **25, plasma burn:** an enemy you hit directly burns for half the hit's damage over 3 seconds. Burn stacks without
  limit. Hits that do not explode also splash 20% of their damage onto enemies right beside the one you hit.
- **50:** burn rises to the hit's full damage, and each direct hit first turns 20% of the enemy's burn into instant
  damage.
- **75:** burn rises to 125%, and each direct hit turns 40% of the burn into instant damage.
- **100:** burn rises to 150%. The burn a hit turns into damage also bursts out, setting nearby enemies burning. The
  burst never hurts you, and it does not set off more bursts: hit those enemies to burst them in turn.
- Energy projectiles fly 15% faster at each of 25, 50, 75 and 100.

### Pistols

Pistols covers pistols, such as the stock pistol, the Pistol, the Handcannon and the Marksman Pistol. Rifles never count.

- **25:** pistols deal more damage the faster they fire: x2.5 for the fastest pistols, down to x1.5 for the slowest.
  Pistols reload 20% faster.
- **50:** pistols reload 40% faster. **Overkill:** when a pistol shot kills an enemy, the damage left over goes on through
  the body into the next enemy behind it, and on again if that one dies too, until the damage runs out. **Bonus
  damage:** every pistol shot uses up a 100-damage bonus, added to its damage if it hits; a miss wastes it. The bonus
  refills in half a second, so a pistol that fires a little slower than that gets it on every shot.
- **75: Deadeye.** Pistols deal more damage the slower they fire: x1.5 for the fastest pistols, up to x3 for the
  slowest. This multiplies with the skill 25 bonus, but not with the 100-damage bonus, which is always just 100.
  Pistols reload 60% faster.
- **100: Shrapnel.** Every pistol hit, and every overkill hit, bursts into 3 fragments that fan out behind the enemy in a
  30-degree V, each doing a third of that hit's damage, however far they fly. A fragment never hurts the enemy it came
  out of, and fragments do not burst again or carry overkill. A fragment locks on to an enemy that is almost exactly in
  its path. Fragment hits make a smaller splash than a bullet, because they are weaker.
- **Fast and slow pistols** are the same as for the Doom Roguelike Arsenal's Scout class. The slowest are the stock
  pistol, the Pistol, the Handcannon, revolvers and most plasma and laser pistols; the Combat Pistol and Storm pistols
  are a little faster; the Shredder Pistol is in the middle; the Plasma Uzi is nearly the fastest; the Marksman Pistol
  counts as the fastest. The Grammaton Cleric Beretta depends on its fire mode: single shots count as slow, burst as a
  little faster than the Shredder Pistol, and full-auto as fast. With both multipliers, a slow pistol does x4.5 damage
  and the fastest do x3.75.
- Overkill and fragments fly level from where the shot hit, and stop at walls like bullets.
- The stock Doom pistol has no reload, so the faster reloads do nothing for it; everything else works with it.
- These only work in the Daggerfall world, and your current skill counts.

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

## Swimming outdoors

The sea and lakes outdoors work as in Daggerfall. Walk onto a water tile and you swim. The water's edge is
Daggerfall's own, in the wilderness and in towns.

- Your view drops to the water line, and you move at **25% of your speed, plus 1% for every 2 points of Swimming**
  (75% at Swimming 100).
- You cannot jump or rest while swimming. The transport menu works as on land.
- Every game minute of swimming practises Swimming. On a failed Swimming roll that minute costs four times the usual
  fatigue (never for Argonians), so swimming with a low Swimming skill tires you quickly.
- A class with **Regeneration: In Water** heals 1 health every 4 game minutes while swimming.
- You cannot dive outdoors, so you never run out of breath there, as in Daggerfall.
- With **Water Walking** you walk on the water at full speed. Shallow water and docks are walked on, not swum.

## Weapons that belong to two skills

Some guns fit two weapon skills, for example a laser shotgun is both a Shotgun and an Energy Weapon. Such a gun uses
whichever of its skills is higher, never both at once.

- **Pistols and Energy Weapons:** energy pistols, both the cell-fed ones (plasma pistols, the Plasma Uzi, the Baron
  Blaster, the Neural Stunner) and the self-charging ones (blasters, nuclear plasma pistols and the nuclear plasma
  revolver).
- **Shotguns and Energy Weapons:** energy shotguns, such as the laser shotgun, plasma shotguns and the nuclear plasma
  shotgun.
- **Pistols and Automatics:** the Grammaton Cleric Beretta, dual pistols with single, burst and full-auto modes.
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

## No shields (for now)

Shields are out of the game until they work in Doom's combat. Shops don't sell them, enemies and treasure don't
drop them, and no new character starts with one. A shield in an older save stays in your inventory, where you can
carry, drop or sell it, but you can't equip it ("Shields cannot be used."). If it was in your hand, loading the save
takes it off. A shield on a hotkey only shows the same message.

Two quest rewards are still shields for now, so their quests keep working: Auriel's Shield and Spell Breaker. You can
get and carry them, but not equip them.

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

**Every shop has its own rhythm, the same in every game.** Some get a small delivery every few days; others get one
big delivery on a fixed day each week, fortnight or month, and their shelves thin out in between, so it pays to learn
when your favourite smith restocks. Shops other than pawn shops also have their own tastes in their regular goods:
specialists carry noticeably more of a few kinds (but never only those), generalists a bit of everything, and most of
those goods come from the shop's two or three regular suppliers, with a new one now and then. Pawn shops buy from
whoever comes through the door (estates, salvage, townsfolk), so they differ only in rhythm. Ammo is restocked every
day whatever the shop's delivery days. Goods nobody buys
stay on the shelf: cheap things sell to other customers within days, expensive pieces such as Daedric weapons can stay
for months.

Regular ammo has no material, so it goes by its plain name: Bullets, Shells, Rockets, Energy Cells. Every other tier
puts its material first, such as Silver Bullets.

**Changing ammo.** The **Change Ammo** control (Options, Customize Controls, Doomerfall Controls) loads the next tier
you carry for the gun in your hands. The gun reloads with it, and a notice such as "Loading Silver Bullets." shows at
the top of the screen. The loaded ammo's icon, in its tier's colour, takes the place of the word AMMO in the status
bar's ammo box (on the fullscreen HUD it is the icon beside your reserve count), so you can always see which ammo is in
the gun.

Health, ammo and powerups lie around only in dungeons, about one or two per room. Houses, shops and other buildings
have none: rest to heal. Across all dungeons about 3 in 10 pickups are health, 3 in 10 bullets, a quarter shells, 1 in
10 rockets and a few energy cells, but each dungeon has its own leaning: some are full of shells or health and others short on health, a few are rocket or
cell caches. About 1 pickup in 50 is a powerup: Berserk, Partial Invisibility or a Light Amplification Visor, more
rarely a Soulsphere, and very rarely a Megasphere or Invulnerability. A dungeon's leaning is the same in every game.

Pickups lying in a place are always the same ones each time you come. A pickup you take is gone for good: it does not
come back when you leave and return, or when you load a save.

## Selling Doom weapons

Every Doom weapon (DRLA, Doom, Heretic, Hexen and Schism) has a gold value and a weight. **Value** starts from the
Daggerfall weapon closest in role (a pistol is priced like a dagger, a shotgun like a broadsword, a rocket launcher
like a claymore, a BFG like a dai-katana), then goes up with the gun's material exactly as Daggerfall weapons do, and
with its rarity. A common gun is worth a fifth of that Daggerfall weapon in the same material, uncommon two fifths,
rare three fifths, very rare 1.2 times, and legendary twice: a Daedric legendary BFG is worth twice a Daedric
dai-katana. **Weight** depends on what the weapon is and how big it is: an Iron pistol about 1 kg, a shotgun 3 to 4
kg, a chaingun about 10 kg, a BFG 15 to 20 kg. Material changes it as it does Daggerfall weapons: Steel and Daedric
guns are a quarter heavier, Dwarven a quarter lighter, Ebony half the weight. Info on a gun shows its weight.

Weapon smiths, armorers, pawn shops and general stores buy Doom weapons, as they buy Daggerfall weapons. The gun you
are holding is not offered for sale; switch to another gun first if you want to sell it.

## Light and darkness

- Dungeons are dark, as in Daggerfall: a dim glow everywhere, the dungeon's own torches and braziers, and a light you
  carry that reaches about 6 m around you. Monsters past your light and away from the dungeon's lights are hard to
  see. Muzzle flashes, explosions and the Light Amplification Visor still light things up.
- In dungeons, doors and other moving parts are as dark as the walls around them.
- Outdoors, trees, plants and monsters take the same daylight as the ground: they do not get darker with distance.
  At night and in snow everything outdoors is as dim as the ground.

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

**Tab** freezes the game under a four-way menu: Character (up), Magic (left), Inventory (right), Map (down); point and click, or press a direction twice (arrows or WASD), and Tab or Escape closes it or the window it opened.

Press **P** for Daggerfall's character sheet and **Backspace** for your spellbook (rebind them in Options, Customize
Controls, Doomerfall Controls as **Open Character Sheet** and **Open Spellbook**). Like the other keys, they are set for
you only on a fresh install. Doom stays frozen while either is open.

- The character sheet works as in Daggerfall. Its **Spellbook**, **Inventory** and **Logbook** buttons open those windows
  on top of it, and closing them takes you back to the sheet.
- Clicking a quest's place in the logbook (from the sheet, from **J**, or from the sheet that opens when you level up)
  and answering Yes closes the menu and opens fast travel on that place, as if you had pressed the fast travel key.
  As with that key, you cannot travel from indoors. On a level-up sheet, spend your bonus points first.
- The spellbook works as in Daggerfall: browse your spells and their effects, sort, rename and delete them. Backspace,
  Escape or **Exit** closes it.
- You need a spellbook in your inventory. Without one, you are told "You have no spellbook!"
- **You cannot cast spells yet.** Choosing a spell in the spellbook, however you opened it (Backspace, the character
  sheet, the spellbook in your inventory, or the level-up sheet), says so and does nothing else.

## Status: where you are, the time and your health

Press **Y** for Daggerfall's status message, indoors or outdoors: where you are and the date and time, then, on the
next press, your health ("You are healthy.", or the diseases and poisons you suffer). Press Y or Enter, or click, to go
from the first message to the second and to close it; Escape closes it. Doom stays frozen while it is open.

Y is set for you only on a fresh install. On an existing install, bind it yourself in Options, Customize Controls,
Doomerfall Controls, **Status (location, time, health)**.

## Transport: foot, horse, cart, ship

Press **T** for Daggerfall's transport menu (rebind it in Options, Customize Controls, Doomerfall Controls as **Open
Transport**). It is set for you only on a fresh install. Doom stays frozen while the menu is open. T, Escape or **Exit**
closes it.

- It lists what you own as in Daggerfall: Horse, Cart and Ship are greyed out until you buy one.
- Choosing **Foot**, **Horse** or **Cart** works as in Daggerfall, and Daggerfall keeps the choice, in saves too.
  **Riding does not change how you move in Doom yet**, and Doom shows no horse or cart.
- **Ship** works as in Daggerfall: it takes you to your ship, and choosing it again on board takes you back to where
  you boarded.
- You can only open it outdoors, standing on the ground. Indoors you are told you cannot change transportation.

## Locked doors

Some dungeon doors are locked. Look at one: it reads **Locked.**, or "This is a magically held lock..." for a magic one.
A door you have picked open reads **Door**.

- Press **Use (E)** on a locked door while you carry **lockpicks** (shown in your inventory, 25 gold each at general
  stores and pawn shops on most days, now and then at weapon smiths and armorers, and sometimes in treasure or on
  enemies that carry gold, such as bandits, orcs and undead; every new character starts with a few) to start
  lockpicking. Press **Fire** when the gold chevron is over the white arc. Your Lockpicking skill and your level make
  the arc wider and the chevron slower, as Daggerfall's lockpicking chance would.
- A **hit** opens the door and keeps your pick. A **miss** breaks one pick. Each attempt trains Lockpicking, and you may
  try again as often as you have picks.
- Getting hit, walking away or pressing Use again cancels the attempt for free.
- Without lockpicks, Use only tells you the door is locked. A **magically held** door cannot be picked.
- A door you picked open **stays unlocked**: after saving and loading, and after you leave the dungeon and come back.
- Levers and other switches in a dungeon can still lock, unlock, open and close doors, as in Daggerfall.

## Talking, trading and stealing

These skills work as in Daggerfall and improve as you use them:

- **Etiquette and Streetwise:** press **Use (E)** on a person to talk. Asking in the **polite** tone uses Etiquette and
  asking in the **blunt** tone uses Streetwise. A higher skill makes people more willing to answer in that tone.
- **Mercantile:** press Use on a shopkeeper to buy and sell. Your Mercantile skill (against the merchant's) sets the
  prices, and every completed trade trains it.
- **Pickpocket:** crouch (the screen shows **Sneaking**) and press Use on a person walking about town to try to pick
  their pocket. You get one try per person (the game may forget who you tried after you load a save or meet a great
  many people). If it works you may find a few gold pieces. If it fails, the game records it as a crime, but no
  guards come after you in the streets yet. Stealing from shop shelves and from containers in homes also uses Pickpocket.
- **Medical:** every hour you rest heals you more with a higher Medical skill, and trains it (see Resting).
- **Lockpicking:** see Locked doors. Doors of town buildings are never locked in Doomerfall yet.

Like every skill, these only go up when Daggerfall checks your skills, after a rest or fast travel (see Levelling up).

### People your quests send you to

When a quest tells you to meet someone in a building or a dungeon, that person stands where the quest put them, as in
Daggerfall. Press **Use (E)** on them to talk, hand over quest items, or collect your reward. When the quest is done with
them, or sends them somewhere else, they disappear from that spot. Items a quest leaves lying in a building do not show
up yet.

## Entering a place

- When you go through a door into or out of a dungeon or building, or walk out of a town, the game pauses until the
  new place is ready (and autosaved, if autosaves are on). A long wait shows **Loading...**. Nothing in the new place moves or
  attacks you until play resumes.
- The first time you open a dungeon's door, or start or load a game inside a dungeon you have not visited, the game
  builds that dungeon first. This can take from a few seconds to over a minute on a busy PC. The game shows
  **Loading...** and pauses until it is done: nothing in the place moves or attacks you, Use does nothing, and you
  cannot save. Daggerfall's clock stops too, so poison, disease and other timed effects do not run during the wait.
  The menu and console still work, so you can quit. A very large dungeon army can also show **Loading...** for a second or two as you enter.

## Town notice boards

Every walled town has a notice board beside each side of its gates, as in Daggerfall. Press Use (or Info) on one to
read the town's name and its news or rumors. You must be within about 6 m.

## Damage numbers

Turn on **Show damage numbers** in Options, HUD Options to see how much damage each of your hits does: a small gold
number rises over the monster you hit and fades in about a second. Hits that land together, such as shotgun pellets,
show as one number. It is off by default.

## Menu text and font mods

Daggerfall's menus mix two kinds of words: text (item names, the talk window, numbers, and labels such as Sell) and
words painted into the menu pictures (such as the character sheet's headings and the red EXIT buttons).

- The small popups for shopkeepers (Talk / Sell), guild halls (Join Guild / Talk / service), smiths (Repair Item /
  Talk / Sell) and witches (Talk / Daedra Summoning / Quest) draw all their row words as text, so a popup no longer
  mixes painted and text words in its rows. Their EXIT button stays a picture.
- A Daggerfall Unity font replacement changes text drawn in the font it replaces. A font named `FONT0003-SDF.ttf`
  (or `.otf`) in Daggerfall Unity's `StreamingAssets\Fonts` folder, or in a font mod, replaces the default font. Most
  menu text uses it, including the four popups. Daggerfall's other fonts are replaced separately by files named
  `FONT0000-SDF` (large font: quest journal, spell maker), `FONT0001-SDF` (titles), `FONT0002-SDF` (small font) and
  `FONT0004-SDF` (item stack counts). Painted words, including EXIT and the character sheet's headings, stay as
  they are.
- A Daggerfall Unity texture pack that replaces a menu picture shows as the pack made it. If it replaces one of the
  four popups' pictures, that popup keeps the pack's own painted row words instead of drawing them as text.

## Developer tools (dev mode)

- Find NPC (dev mode only, `dd_dev 1`): press N (Doomerfall Controls, "Find NPC by name") or type `dd_findnpc [name]`
  in the console. The box opens listing the NPCs your active quests name: pick one with the arrows and Enter (or click). Or type any part of a name (any word of it; small typos are fine) to filter the list, closest
  matches first, then everyone Daggerfall knows. A gold chevron points at the door of the
  building they are in when you are outside, or at the NPC when you share their building or dungeon, with the name and
  distance (at the screen edge when off screen). Someone in another place is named in text with the place and
  building. It clears when you change area or search again.

## The dead stay dead

A townsperson you kill in town dies with Daggerfall's blood splash and, as in Daggerfall, leaves no body. They stay dead when you leave and come back and after you save and load, and killing one is still murder. (A town watchman is different: as in Daggerfall, attacking one turns them into the city watch, and outdoors that watch does not come after you in Doom yet, so the watchman just vanishes.) City guards who come into a building after you leave a body when killed, as in Daggerfall, and the body stays there when you leave and come back and after you save and load.
