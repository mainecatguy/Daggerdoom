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
