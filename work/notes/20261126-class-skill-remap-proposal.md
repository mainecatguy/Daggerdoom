# Preset class skills: no-guns cards and guns cards (proposal)

Proposal only. No code changed. Owner approval needed. Replaces the rejected
`work/notes/20261126-class-slot-proposal.md` (gun skills straight into language slots) and reuses its class data and
facts.

**Owner's approach (2026-11-26):** the game will have two modes, no guns and guns. No-guns mode replaces removed skills
with Daggerfall skills, deterministically. Guns mode uses hand-made altered class cards: every class gets at least one
firearm skill, usually two, and every Daggerfall weapon skill is replaced by some Doom skill, chosen to fit the class.
"Destro stays": Destruction is never replaced. Hand-to-Hand stays (martial arts, `work/backlog/skills-in-doom.md`).

**Level rule** (`PlayerEntity.SetCurrentLevelUpSkillSum`): all 3 primaries + best 2 of 3 majors + best 1 of 6 minors.
A primary or major that never rises slows the class. Minor choices barely affect pace.

**Class data:** read from `CLASS00.CFG`-`CLASS17.CFG` (skill bytes 16-27). `CLASS18` is never offered.

## No-guns mode: removed skill to Daggerfall skill

A fixed table, so the result is the same in every game. Two rules, then per-class judgment:

- **A language** becomes a communication skill the class lacks (Etiquette, Streetwise, Mercantile), else a fitting
  non-combat skill.
- **Critical Strike in a minor slot** becomes a Daggerfall weapon skill the class lacks, to keep the combat flavor.
  **Critical Strike in a primary or major slot** goes to a skill that rises steadily in Doom play (Running,
  Backstabbing, Stealth), because those four classes already hold all five weapon skills.

No gun skills. Every pick was checked against the class's full list: no duplicates.

| Class | Tier | Old | New | Reason |
|---|---|---|---|---|
| Mage | Minor | Dragonish | Etiquette | Language to the kept court language; scholar's manners. |
| Mage | Minor | Daedric | Mercantile | Buying reagents, scrolls and spells. |
| Sorcerer | Minor | Dragonish | Etiquette | Same list as Mage. |
| Sorcerer | Minor | Daedric | Mercantile | Same list as Mage. |
| Nightblade | Minor | Critical Strike | Archery | The ranged assassin. |
| Burglar | Minor | Critical Strike | Hand-to-Hand | A quiet scuffle; adds no weapon to a non-fighter. |
| Rogue | Minor | Critical Strike | Short Blade | The dirk beside the sword. |
| Acrobat | Minor | Critical Strike | Long Blade | The fencer. |
| Thief | Minor | Critical Strike | Blunt Weapon | The cosh. |
| Assassin | **Primary** | Critical Strike | Running | Rises all the time in Doom play, so pace holds; escape. |
| Monk | **Primary** | Critical Strike | Running | Speed for an unarmed fighter; rises steadily. |
| Archer | **Major** | Critical Strike | Backstabbing | Shooting unaware targets; it levels 10x faster from that in Doom (todo `skillbasics` 03). |
| Ranger | **Major** | Critical Strike | Stealth | The woodland hunter's concealment. |
| Ranger | Minor | Spriggan | Medical | A nature language to field lore and wound care. |
| Barbarian | Minor | Critical Strike | Hand-to-Hand | The brawler. |
| Barbarian | Minor | Giantish | Streetwise | A language to rough-company talk. |

Spellsword, Battlemage, Healer, Bard, Warrior and Knight have no removed skills.

Pace: all four dead primary and major slots (Assassin, Monk, Archer, Ranger) hold live skills again, so those classes
return to vanilla pace. Assassin and Monk start with Running 28-31 and get its 25 perk.

## Guns mode: altered class cards

Each guns card is the no-guns card with every weapon slot (Short Blade, Long Blade, Axe, Blunt Weapon, Archery,
including the ones the no-guns table added) given a Doom skill by hand. Every other slot, Destruction and Hand-to-Hand
included, is unchanged, so tiers and slot counts stay the same and pace stays close to vanilla. Firearms are Pistols,
Shotguns, Automatics, Rifles, Explosives and Energy Weapons; Melee is not a firearm.

Each cell reads `Daggerfall skill > Doom skill`. Slots not shown are unchanged from the no-guns card.

| # | Class | Primary | Major | Minor | Theme |
|---|---|---|---|---|---|
| 00 | Mage | | | Short Blade > Pistols, Blunt Weapon > Energy Weapons | The scholar's costly arcane-tech gun, and a sidearm for when magicka runs out. |
| 01 | Spellsword | Axe > Shotguns, Long Blade > Melee, Blunt Weapon > Automatics | | Short Blade > Energy Weapons, Archery > Rifles | The blade stays a blade (Melee); spell and steel become magic-tech guns at the side. |
| 02 | Battlemage | Long Blade > Explosives, Axe > Energy Weapons | | Archery > Rifles, Short Blade > Melee, Blunt Weapon > Shotguns | The war wizard is artillery: Energy Weapons and Explosives beside a Destruction primary. |
| 03 | Sorcerer | | | Short Blade > Explosives, Blunt Weapon > Energy Weapons | Cannot regain magicka, so carries stored power: cells and charges. |
| 04 | Healer | | | Short Blade > Pistols, Blunt Weapon > Shotguns | The country doctor's sidearm and coach gun. |
| 05 | Nightblade | | Short Blade > Pistols | Archery > Rifles | The silenced pistol and the sniper rifle. |
| 06 | Bard | | Short Blade > Pistols | Archery > Automatics | The duelist's pistol, and the tommy gun in the instrument case. |
| 07 | Burglar | | Short Blade > Pistols | | A non-fighter with one weapon slot: a light pistol. |
| 08 | Rogue | Long Blade > Shotguns | | Short Blade > Pistols, Blunt Weapon > Melee | The close-range brawler with a backup pistol and a cosh. |
| 09 | Acrobat | | | Long Blade > Automatics, Short Blade > Pistols, Archery > Melee | Run and gun while tumbling; a knife for the landing. |
| 10 | Thief | Short Blade > Pistols | | Blunt Weapon > Explosives | The concealable pistol, and charges for safes. |
| 11 | Assassin | | Short Blade > Pistols, Long Blade > Rifles, Blunt Weapon > Melee | Axe > Explosives, Archery > Automatics | The hitman's three tools: silenced pistol, sniper rifle, knife; a bomb as the backup plan. |
| 12 | Monk | | Blunt Weapon > Melee | Axe > Shotguns, Long Blade > Energy Weapons, Archery > Rifles, Short Blade > Pistols | Martial weapons beside Hand-to-Hand; guns only as minors, with ki focused into energy and the patience of the rifle. |
| 13 | Archer | Archery > Rifles | Axe > Explosives, Blunt Weapon > Melee | Long Blade > Automatics, Short Blade > Shotguns | The marksman; the grenade launcher keeps the bow's arcing shot. |
| 14 | Ranger | Long Blade > Rifles, Axe > Shotguns | Archery > Melee | Blunt Weapon > Explosives, Short Blade > Automatics | The hunter's rifle and scattergun, a machete, and traps as mines. |
| 15 | Barbarian | Blunt Weapon > Melee, Long Blade > Automatics, Axe > Shotguns | | Archery > Explosives | Chainsaw, minigun and shotgun up front; a thrown charge for range. |
| 16 | Warrior | Axe > Shotguns, Long Blade > Automatics, Blunt Weapon > Melee | Archery > Rifles, Short Blade > Explosives | | The soldier: rifleman, grenadier and close-quarters fighter. |
| 17 | Knight | Long Blade > Melee, Blunt Weapon > Energy Weapons | Axe > Shotguns, Archery > Rifles, Short Blade > Automatics | | The noble keeps the sword and can afford the rich man's guns. |

**Checks:**

- Every class has at least one firearm. Burglar has one (its only weapon slot); Mage, Sorcerer, Healer, Nightblade,
  Bard and Thief have two; Rogue and Acrobat two plus Melee; the rest three or more, because they hold four or five
  weapon slots and each needs a different skill.
- No class has a skill twice: within each class every Doom skill is different, and none of the seven Doom skills is in
  any no-guns card.
- Destruction and Hand-to-Hand are unchanged everywhere.

**Spread across the 18 classes:**

| Doom skill | Classes | Of which primary |
|---|---|---|
| Pistols | 10: Mage, Healer, Nightblade, Bard, Burglar, Rogue, Acrobat, Thief, Assassin, Monk | Thief |
| Shotguns | 10: Spellsword, Battlemage, Healer, Rogue, Monk, Archer, Ranger, Barbarian, Warrior, Knight | Spellsword, Rogue, Ranger, Barbarian, Warrior |
| Automatics | 9: Spellsword, Bard, Acrobat, Assassin, Archer, Ranger, Barbarian, Warrior, Knight | Spellsword, Barbarian, Warrior |
| Rifles | 9: Spellsword, Battlemage, Nightblade, Assassin, Monk, Archer, Ranger, Warrior, Knight | Archer, Ranger |
| Explosives | 8: Battlemage, Sorcerer, Thief, Assassin, Archer, Ranger, Barbarian, Warrior | Battlemage |
| Energy Weapons | 6: Mage, Spellsword, Battlemage, Sorcerer, Monk, Knight | Battlemage, Knight |
| Melee | 11: Spellsword, Battlemage, Rogue, Acrobat, Assassin, Monk, Archer, Ranger, Barbarian, Warrior, Knight | Spellsword, Barbarian, Warrior, Knight |

Energy Weapons is the rarest on purpose (the rich man's guns). Melee is the most common because Short Blade and Blunt
Weapon are so widespread and the fighter classes keep a close-combat skill.

**Starting gun** (`20261126-light-carbine-starting-gun.md`, highest Doom weapon skill) follows the primaries: Warrior,
Spellsword and Barbarian roll among shotgun, chaingun and chainsaw; Ranger rifle or shotgun; Archer the Light Carbine;
Rogue shotgun; Thief pistol; Battlemage rocket launcher or energy gun; Knight chainsaw or energy gun. The energy gun
part of that rule is "later", so Battlemage and Knight need it, or a stand-in, when guns cards ship.

**Pace:** each slot keeps its tier. A class whose primaries are three gun families (Spellsword, Barbarian, Warrior)
keeps vanilla pace only if the player uses or buys all three, as vanilla needed three weapon types.

## Custom classes in guns mode (suggestion)

- In guns mode the class maker offers the Doom skills instead of the five Daggerfall weapon skills.
- A custom class made in no-guns mode converts by a default map: Short Blade to Pistols, Long Blade to Automatics, Axe
  to Shotguns, Blunt Weapon to Melee, Archery to Rifles. If that would repeat a skill, the lower slot takes the first
  Doom skill the class lacks from Pistols, Shotguns, Automatics, Rifles, Explosives, Energy Weapons, Melee.
- A custom class with no weapon skills gets no firearm; buying one with Skill XP is always possible.

## Procedural alternative

Owner's idea (2026-11-26), for comparison with the hand-made cards: Dodging is also out. That leaves seven Daggerfall
slots (Short Blade, Long Blade, Axe, Blunt Weapon, Archery, Critical Strike, Dodging) for seven Doom skills. Guns mode
is one fixed one-to-one rule applied to each class's vanilla card. Hand-to-Hand and Destruction stay. Languages take
their no-guns replacements in both modes.

### The rule

| Daggerfall slot | Doom skill | Why |
|---|---|---|
| Short Blade | Melee | A short blade is a knife; DRLA's combat knife is a Melee weapon. |
| Long Blade | Automatics | The main fighter skill to the main Doom weapon family. |
| Axe | Shotguns | Heavy close-range cleave. |
| Blunt Weapon | Explosives | Smash and area damage. |
| Archery | Rifles | Precise long-range shots. |
| Critical Strike | Energy Weapons | Escalating damage, like a critical hit; lands on the precision and killer classes. |
| Dodging | Pistols | The light, quick gun for evasive characters (Healer, Nightblade, Rogue, Acrobat primaries). |

**How it was chosen:** I scored all 5,040 assignments by script. No assignment leaves a class without a firearm,
because every class holds at least two of the seven slots. How often each Doom skill appears is fixed by its source:
Short Blade is in 16 classes, Dodging 15, Blunt Weapon 13, Archery 11, Long Blade and Critical Strike 10 each, Axe 9.
So the choice comes down to theme and one-firearm classes. Three assignments were compared:

- **A:** Short Blade to Pistols, Dodging to Melee. No class has only one firearm, but Healer and Archer get a Melee
  primary and the six Dodging-primary classes lose a firearm primary.
- **B (chosen):** Short Blade to Melee, Dodging to Pistols. Firearm primaries go to the evasive classes, and Short
  Blade becomes the knife. Cost: Bard has only one firearm.
- **B with Blunt Weapon and Critical Strike swapped** (Blunt Weapon to Energy Weapons, Critical Strike to
  Explosives): mages get Energy Weapons, but Monk gets an Explosives primary, Barbarian and Warrior an Energy Weapons
  primary, and Energy Weapons lands in 13 classes, too common for the rich man's guns.

### What each class gets in guns mode

Doom skills in bold. The last column counts firearms (Melee excluded).

| # | Class | Primary | Major | Minor | Firearms |
|---|---|---|---|---|---|
| 00 | Mage | Mysticism, Alteration, Thaumaturgy | Illusion, Destruction, Restoration | Medical, **Melee**, **Explosives**, Etiquette, Mercantile, **Pistols** | 2 |
| 01 | Spellsword | **Shotguns**, **Automatics**, **Explosives** | Destruction, Illusion, Alteration | Restoration, Thaumaturgy, Mysticism, **Melee**, Hand-to-Hand, **Rifles** | 4 |
| 02 | Battlemage | Destruction, **Automatics**, **Shotguns** | Thaumaturgy, Alteration, Hand-to-Hand | Illusion, Mysticism, Restoration, **Rifles**, **Melee**, **Explosives** | 4 |
| 03 | Sorcerer | Mysticism, Alteration, Thaumaturgy | Destruction, Restoration, Illusion | Medical, **Melee**, **Explosives**, Etiquette, Mercantile, **Pistols** | 2 |
| 04 | Healer | Restoration, Medical, **Pistols** | Thaumaturgy, Mysticism, Alteration | Illusion, Streetwise, Etiquette, **Melee**, Hand-to-Hand, **Explosives** | 2 |
| 05 | Nightblade | Illusion, Stealth, **Pistols** | Thaumaturgy, **Melee**, Lockpicking | Alteration, **Energy Weapons**, Mercantile, Destruction, Restoration, Backstabbing | 2 |
| 06 | Bard | Streetwise, Etiquette, Pickpocket | Stealth, **Melee**, Hand-to-Hand | Lockpicking, Alteration, Illusion, Destruction, **Rifles**, Restoration | **1** |
| 07 | Burglar | Lockpicking, Stealth, Climbing | Mercantile, **Pistols**, **Melee** | Jumping, Running, **Energy Weapons**, Pickpocket, Streetwise, Backstabbing | 2 |
| 08 | Rogue | **Automatics**, Stealth, **Pistols** | Pickpocket, Backstabbing, Streetwise | **Energy Weapons**, **Explosives**, Lockpicking, Hand-to-Hand, Running, Swimming | 4 |
| 09 | Acrobat | Jumping, **Pistols**, Running | Climbing, Hand-to-Hand, Stealth | Pickpocket, **Energy Weapons**, Backstabbing, **Melee**, **Rifles**, Swimming | 3 |
| 10 | Thief | Pickpocket, Stealth, **Melee** | Backstabbing, Climbing, Lockpicking | **Energy Weapons**, Jumping, Running, **Pistols**, Streetwise, Mercantile | 2 |
| 11 | Assassin | **Energy Weapons**, Backstabbing, Stealth | **Melee**, **Automatics**, **Explosives** | **Shotguns**, **Rifles**, Lockpicking, Pickpocket, Climbing, **Pistols** | 6 |
| 12 | Monk | Hand-to-Hand, **Energy Weapons**, **Pistols** | Swimming, Medical, **Explosives** | **Shotguns**, **Automatics**, **Rifles**, **Melee**, Jumping, Climbing | 6 |
| 13 | Archer | **Rifles**, Hand-to-Hand, **Pistols** | **Shotguns**, **Explosives**, **Energy Weapons** | **Automatics**, **Melee**, Climbing, Jumping, Running, Swimming | 6 |
| 14 | Ranger | **Automatics**, **Shotguns**, Climbing | Swimming, **Rifles**, **Energy Weapons** | **Explosives**, Hand-to-Hand, **Melee**, Running, **Pistols**, Medical | 6 |
| 15 | Barbarian | **Explosives**, **Automatics**, **Shotguns** | Jumping, Running, Swimming | Medical, Climbing, **Pistols**, **Energy Weapons**, **Rifles**, Streetwise | 6 |
| 16 | Warrior | **Shotguns**, **Automatics**, **Explosives** | Hand-to-Hand, **Rifles**, **Melee** | Climbing, Jumping, **Pistols**, Running, Swimming, Medical | 5 |
| 17 | Knight | **Automatics**, Etiquette, **Explosives** | **Shotguns**, **Rifles**, **Melee** | Medical, **Pistols**, Hand-to-Hand, Jumping, Swimming, Climbing | 5 |

Spread: Melee 16 classes (primary 1), Pistols 15 (6), Explosives 13 (4), Rifles 11 (1), Automatics 10 (7), Energy
Weapons 10 (2), Shotguns 9 (5). No class has a skill twice, because the rule is one to one.

**Flags:**

- **One firearm:** Bard (Rifles only; Short Blade became Melee). No class has none.
- **Odd results:**
  - Melee is a primary only for Thief. Knight, Warrior, Barbarian and Spellsword lose their close-combat primary.
  - Monk gets Pistols and Energy Weapons as primaries (from Dodging and Critical Strike), and an Explosives major.
  - Assassin's primary is Energy Weapons, not a quiet gun.
  - Mage and Sorcerer get no Energy Weapons. Thieves (Nightblade, Burglar, Rogue, Acrobat, Thief) do.
  - Healer has an Explosives minor.
  - Pistols and Melee are in 15-16 classes each: nearly everyone holds both.
  - Five classes have six firearms (Assassin, Monk, Archer, Ranger, Barbarian), so firearm counts swing from 1 to 6.

### What no-guns mode needs

The step 1 table stays. Dodging's 15 slots also need a Daggerfall skill, chosen like step 1 (the evasion idea becomes
movement where the slot is free; primaries go to skills that rise steadily). Checked against each class's no-guns
card: no duplicates.

| Class | Tier | Dodging becomes |
|---|---|---|
| Mage, Sorcerer | Minor | Running |
| Healer | **Primary** | Running |
| Nightblade | **Primary** | Running |
| Burglar | Major | Swimming (canals and sewers) |
| Rogue | **Primary** | Jumping |
| Acrobat | **Primary** | Blunt Weapon (the acrobat's staff; Jumping, Running and Climbing are already taken) |
| Thief | Minor | Swimming |
| Assassin | Minor | Medical (poisons and anatomy) |
| Monk | **Primary** | Stealth |
| Archer | **Primary** | Stealth (the hidden marksman) |
| Ranger | Minor | Backstabbing (ambush) |
| Barbarian | Minor | Stealth |
| Warrior | Minor | Streetwise (the mercenary's contacts) |
| Knight | Minor | Running |

### Compared with the hand-made cards

The procedural rule is one table of seven rows. It is deterministic, easy to explain, and works the same for custom
classes, so no class maker or conversion rule is needed. It also frees Dodging's slots for guns, giving the evasive
classes firearm primaries. What it loses is control over each class. Firearm counts swing from one (Bard) to six.
Melee leaves the fighters' primaries. A few classes get odd skills: Monk's pistols, Assassin's energy gun, Healer's
explosives, and no Energy Weapons for mages. Pistols and Melee end up on nearly every card, so classes look more
alike. It also removes Dodging, a planned skill, in both modes. The hand-made cards keep Dodging and keep every
class to one to four firearms chosen for its theme, but they cost 18 tables to maintain and need a separate rule for
custom classes.

## Implementation notes (for the later card)

- Two fixed tables keyed by class index: the no-guns replacements, and the guns cards (the slot-by-slot table above).
  The guns card applies only when guns are on. Both run on every class load (CFG and save).
- Replace today's placeholder (`DFCareer.RemapRemovedSkills` on `agent/skillcore-20261126-114057`), which puts gun
  skills into language slots (the rejected approach) and leaves Critical Strike in place. The new skills may still use
  the freed enum numbers; only class lists change.
- No-guns fallback for custom classes: a language becomes the first free of Etiquette, Streetwise, Mercantile,
  Medical; Critical Strike the first free of Short Blade, Long Blade, Axe, Blunt Weapon, Archery, Running.
- Saves store the career, so a remap at load changes the level sum: rebase `startingLevelUpSkillSum` by the
  difference so no one jumps or stalls a level.

## Questions for the owner

1. **Rifles is not built yet** (backlog), but nine guns cards use it, as a primary for Archer and Ranger. Should the
   guns cards wait for Rifles, or should Rifles slots hold Archery until it exists?
2. **Burglar has only one firearm** (Pistols), because it has only one weapon slot. OK, or should its guns card also
   swap a non-weapon minor (for example its Hand-to-Hand) for Shotguns?
3. **Skill values across modes (can wait for the guns-off option):** are a Daggerfall weapon skill and the Doom skill
   that replaces it separate values (recommended: new skills are new skills), or does a character's value carry over
   when switching modes?
4. **Hand-made cards or the procedural alternative?** The procedural rule also removes Dodging in both modes.
