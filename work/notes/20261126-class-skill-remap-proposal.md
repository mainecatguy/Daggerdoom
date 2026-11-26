# Preset class skills: two-step remap proposal

Proposal only. No code changed. Owner approval needed. Replaces the rejected
`work/notes/20261126-class-slot-proposal.md` (gun skills straight into language slots) and reuses its class data and
facts.

**Rules followed:** the two-step remap (`gamedesign/decisions/20261126-two-step-skill-remap.md`): step 1 replaces removed
skills with Daggerfall skills, step 2 reroutes Daggerfall weapon skills to Doom skills when guns are on. Hand-to-Hand
stays separate for martial arts (`work/backlog/skills-in-doom.md`). Destruction stays a spell skill
(`work/backlog/original-weapon-skills.md`). Rifles is planned (`work/backlog/rifles-skill.md`).

**Level rule** (`PlayerEntity.SetCurrentLevelUpSkillSum`): all 3 primaries + best 2 of 3 majors + best 1 of 6 minors.
A primary or major that never rises slows the class. Minor choices barely affect pace.

**Class data:** read from `CLASS00.CFG`-`CLASS17.CFG` (skill bytes 16-27). `CLASS18` is never offered.

## Step 1: medieval mode (removed skill to Daggerfall skill)

Two rules, then per-class judgment:

- **A language** becomes a communication skill the class lacks (Etiquette, Streetwise, Mercantile), else a fitting
  non-combat skill.
- **Critical Strike in a minor slot** becomes a Daggerfall weapon skill the class lacks, so the class keeps the combat
  flavor and, in gun mode, step 2 turns it into a Doom skill. **Critical Strike in a primary or major slot** goes to a
  skill that rises steadily in Doom play (Running, Backstabbing, Stealth), because those four classes already hold all
  five weapon skills.

No gun skills. Every pick was checked against the class's full list: no duplicates.

| Class | Tier | Old | New | Reason |
|---|---|---|---|---|
| Mage | Minor | Dragonish | Etiquette | Language to the kept court language; scholar's manners. |
| Mage | Minor | Daedric | Mercantile | Buying reagents, scrolls and spells. |
| Sorcerer | Minor | Dragonish | Etiquette | Same list as Mage. |
| Sorcerer | Minor | Daedric | Mercantile | Same list as Mage. |
| Nightblade | Minor | Critical Strike | Archery | Ranged assassin; becomes Rifles (a sniper) in gun mode. |
| Burglar | Minor | Critical Strike | Hand-to-Hand | A quiet scuffle; adds no gun to a non-fighter. |
| Rogue | Minor | Critical Strike | Short Blade | The dirk beside the sword; Pistols in gun mode. |
| Acrobat | Minor | Critical Strike | Long Blade | Fencer; Automatics (run-and-gun) in gun mode. |
| Thief | Minor | Critical Strike | Blunt Weapon | The cosh; Melee in gun mode. |
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

Alternative for Assassin (not recommended, it reorders slots): move Archery from minor to primary (Rifles in gun mode,
the hitman with a rifle) and put Streetwise in the freed minor.

## Step 2: guns on (Daggerfall weapon skill to Doom skill)

Applied to the step 1 result. One to one:

| Daggerfall skill | Doom skill | Why |
|---|---|---|
| Short Blade | Pistols | Light, quick, concealable sidearm. Thief and Bard classes. |
| Long Blade | Automatics | The main fighter skill to the main Doom weapon family (sustained flurry). |
| Axe | Shotguns | Heavy close-range cleave. |
| Blunt Weapon | Melee | Maces, hammers and flails stay the brute close-combat skill (Monk, Thief's cosh, fighters). |
| Archery | Rifles | Precise long-range shots. **Until Rifles exists: Explosives** (temporary; see question 2). |
| Hand-to-Hand | unchanged | Governs martial arts, such as Doom's fist (owner). |
| Destruction | unchanged | A spell school, supported later. See question 3. |

**Duplicates.** The mapping is one to one, and step 1 never repeats a Daggerfall skill, so step 2 can never give a
preset class the same skill twice. Six preset classes hold all five weapon skills and end with five different Doom
skills. Guard for custom classes or later data (for example a custom class that already lists Pistols and Short
Blade): the higher slot keeps its mapping (primary over major over minor, then list order); the other slot takes the
first Doom skill the class lacks from Explosives, Energy Weapons (once built), Pistols, Shotguns, Automatics, Melee,
Rifles; if none is free, it keeps its Daggerfall skill.

**Effect:** six source skills (with Destruction unmapped, five) cannot cover seven Doom skills. Once Rifles exists,
Explosives and Energy Weapons are in no preset class. They stay buyable with Skill XP and can be in custom classes.

## Result per class (both steps, guns on, Rifles built)

Step 1 replacements in **bold**. Before Rifles exists, read every Rifles as Explosives.

| # | Class | Primary | Major | Minor |
|---|---|---|---|---|
| 00 | Mage | Mysticism, Alteration, Thaumaturgy | Illusion, Destruction, Restoration | Medical, Pistols, Melee, **Etiquette**, **Mercantile**, Dodging |
| 01 | Spellsword | Shotguns, Automatics, Melee | Destruction, Illusion, Alteration | Restoration, Thaumaturgy, Mysticism, Pistols, Hand-to-Hand, Rifles |
| 02 | Battlemage | Destruction, Automatics, Shotguns | Thaumaturgy, Alteration, Hand-to-Hand | Illusion, Mysticism, Restoration, Rifles, Pistols, Melee |
| 03 | Sorcerer | Mysticism, Alteration, Thaumaturgy | Destruction, Restoration, Illusion | Medical, Pistols, Melee, **Etiquette**, **Mercantile**, Dodging |
| 04 | Healer | Restoration, Medical, Dodging | Thaumaturgy, Mysticism, Alteration | Illusion, Streetwise, Etiquette, Pistols, Hand-to-Hand, Melee |
| 05 | Nightblade | Illusion, Stealth, Dodging | Thaumaturgy, Pistols, Lockpicking | Alteration, **Rifles**, Mercantile, Destruction, Restoration, Backstabbing |
| 06 | Bard | Streetwise, Etiquette, Pickpocket | Stealth, Pistols, Hand-to-Hand | Lockpicking, Alteration, Illusion, Destruction, Rifles, Restoration |
| 07 | Burglar | Lockpicking, Stealth, Climbing | Mercantile, Dodging, Pistols | Jumping, Running, **Hand-to-Hand**, Pickpocket, Streetwise, Backstabbing |
| 08 | Rogue | Automatics, Stealth, Dodging | Pickpocket, Backstabbing, Streetwise | **Pistols**, Melee, Lockpicking, Hand-to-Hand, Running, Swimming |
| 09 | Acrobat | Jumping, Dodging, Running | Climbing, Hand-to-Hand, Stealth | Pickpocket, **Automatics**, Backstabbing, Pistols, Rifles, Swimming |
| 10 | Thief | Pickpocket, Stealth, Pistols | Backstabbing, Climbing, Lockpicking | **Melee**, Jumping, Running, Dodging, Streetwise, Mercantile |
| 11 | Assassin | **Running**, Backstabbing, Stealth | Pistols, Automatics, Melee | Shotguns, Rifles, Lockpicking, Pickpocket, Climbing, Dodging |
| 12 | Monk | Hand-to-Hand, **Running**, Dodging | Swimming, Medical, Melee | Shotguns, Automatics, Rifles, Pistols, Jumping, Climbing |
| 13 | Archer | Rifles, Hand-to-Hand, Dodging | Shotguns, Melee, **Backstabbing** | Automatics, Pistols, Climbing, Jumping, Running, Swimming |
| 14 | Ranger | Automatics, Shotguns, Climbing | Swimming, Rifles, **Stealth** | Melee, Hand-to-Hand, Pistols, Running, Dodging, **Medical** |
| 15 | Barbarian | Melee, Automatics, Shotguns | Jumping, Running, Swimming | Medical, Climbing, Dodging, **Hand-to-Hand**, Rifles, **Streetwise** |
| 16 | Warrior | Shotguns, Automatics, Melee | Hand-to-Hand, Rifles, Pistols | Climbing, Jumping, Dodging, Running, Swimming, Medical |
| 17 | Knight | Automatics, Etiquette, Melee | Shotguns, Rifles, Pistols | Medical, Dodging, Hand-to-Hand, Jumping, Swimming, Climbing |

Medieval mode is the same table with step 2 undone (Pistols = Short Blade, Automatics = Long Blade, Shotguns = Axe,
Melee = Blunt Weapon, Rifles = Archery).

Starting gun (`20261126-light-carbine-starting-gun.md`, highest Doom weapon skill) then follows the primaries: Warrior,
Spellsword and Barbarian roll among shotgun, chaingun and chainsaw; Knight chaingun or chainsaw; Battlemage and Ranger
chaingun or shotgun; Rogue chaingun; Thief pistol; Archer the Light Carbine (the rocket launcher until Rifles exists).

Pace note for gun mode: a class whose three primaries map to three gun families (Warrior, Spellsword, Barbarian)
keeps vanilla pace only if the player uses all three families or buys them, as vanilla needed three weapon types.

## Implementation notes (for the later card)

- Order: step 1 on every class load (CFG and save); step 2 only when guns are on, on the step 1 result.
- Replace today's placeholder (`DFCareer.RemapRemovedSkills` on `agent/skillcore-20261126-114057`), which puts gun
  skills into language slots (the rejected approach) and leaves Critical Strike in place. The new skills may still use
  the freed enum numbers; only class lists change.
- Step 1 is a table keyed by class index, with a blanket fallback for custom classes (language: first free of
  Etiquette, Streetwise, Mercantile, Medical; Critical Strike: first free of Short Blade, Long Blade, Axe, Blunt
  Weapon, Archery, Running).
- Saves store the career, so a remap at load changes the level sum: rebase `startingLevelUpSkillSum` by the
  difference so no one jumps or stalls a level.

## Questions for the owner

1. **Melee or Explosives in classes?** Five Daggerfall weapon skills cannot cover every Doom skill. Recommended:
   Blunt Weapon to Melee, so Explosives is in no preset class (buy only). Alternative: Blunt Weapon to Explosives, so
   Melee is in no preset class.
2. **Archery before Rifles exists:** map it to Explosives for now, then to Rifles when the skill is built (one more
   save remap)? Or bring Rifles forward so Archery maps straight to it?
3. **Destruction:** keep it a spell skill only, so Energy Weapons is in no preset class (recommended)? Or reroute it
   to Energy Weapons in gun mode (an earlier lean), which takes the Destruction spell skill out of gun-mode classes?
4. **Skill values across modes (can wait for the guns-off option):** are the Daggerfall weapon skill and its Doom
   skill separate values (recommended: new skills are new skills), or does a character's Long Blade value carry to
   Automatics when switching modes?
