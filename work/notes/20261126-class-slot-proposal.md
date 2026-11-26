# Preset class slots for removed languages and Critical Strike: proposal

Research and proposal only. No code changed. Owner decision needed.

## Facts

- **Source data:** `GameResources/DAGGER/ARENA2/CLASS00.CFG` to `CLASS18.CFG`, read by `ClassFile.cs` (skill bytes
  16-27: 3 primary, 3 major, 6 minor; name at byte 28). `CreateCharClassSelect.cs` lists every file except the last,
  so the preset classes are `CLASS00`-`CLASS17`. `CLASS18` is a second unused "Knight" with an invalid skill byte (35);
  it is never offered and is ignored here.
- **Level rule** (`PlayerEntity.SetCurrentLevelUpSkillSum`): level sum = all 3 primaries + the best 2 of 3 majors + the
  best 1 of 6 minors. So:
  - a dead **primary** slot is a large drag (one sixth of the sum never rises);
  - a dead **major** slot is dropped as the lowest major, so the class loses its spare major;
  - a dead **minor** slot barely matters for pace. Minors matter for starting values and identity.
- **Starting values** (`SkillsRollout.cs`): primary 28 + 0-3, major and minor lower. A skill put in a primary slot
  starts above 25, so the character begins with that skill's 25 perk.
- **Today's placeholder** (branch `agent/skillcore-20261126-114057`, `DFCareer.RemapRemovedSkills`, run on CFG load and
  on save load in `SerializablePlayer.cs`): slots 4-6 (Orcish, Harpy, Giantish) already read as Shotguns, Automatics,
  Explosives. Languages 7-12 become gun skill `(L - 4) % 3` or the next free one. **Critical Strike is not remapped**:
  it stays in class lists as a skill that never rises and cannot be bought, which today slows Assassin and Monk
  (primary) and Archer and Ranger (major).

## 1. Affected classes (16 slots in 12 classes)

Affected slots in **bold**. The other 6 preset classes (Spellsword, Battlemage, Healer, Bard, Warrior, Knight) have none.

| # | Class | Primary | Major | Minor |
|---|---|---|---|---|
| 00 | Mage | Mysticism, Alteration, Thaumaturgy | Illusion, Destruction, Restoration | Medical, Short Blade, Blunt Weapon, **Dragonish**, **Daedric**, Dodging |
| 03 | Sorcerer | Mysticism, Alteration, Thaumaturgy | Destruction, Restoration, Illusion | Medical, Short Blade, Blunt Weapon, **Dragonish**, **Daedric**, Dodging |
| 05 | Nightblade | Illusion, Stealth, Dodging | Thaumaturgy, Short Blade, Lockpicking | Alteration, **Critical Strike**, Mercantile, Destruction, Restoration, Backstabbing |
| 07 | Burglar | Lockpicking, Stealth, Climbing | Mercantile, Dodging, Short Blade | Jumping, Running, **Critical Strike**, Pickpocket, Streetwise, Backstabbing |
| 08 | Rogue | Long Blade, Stealth, Dodging | Pickpocket, Backstabbing, Streetwise | **Critical Strike**, Blunt Weapon, Lockpicking, Hand-to-Hand, Running, Swimming |
| 09 | Acrobat | Jumping, Dodging, Running | Climbing, Hand-to-Hand, Stealth | Pickpocket, **Critical Strike**, Backstabbing, Short Blade, Archery, Swimming |
| 10 | Thief | Pickpocket, Stealth, Short Blade | Backstabbing, Climbing, Lockpicking | **Critical Strike**, Jumping, Running, Dodging, Streetwise, Mercantile |
| 11 | Assassin | **Critical Strike**, Backstabbing, Stealth | Short Blade, Long Blade, Blunt Weapon | Axe, Archery, Lockpicking, Pickpocket, Climbing, Dodging |
| 12 | Monk | Hand-to-Hand, **Critical Strike**, Dodging | Swimming, Medical, Blunt Weapon | Axe, Long Blade, Archery, Short Blade, Jumping, Climbing |
| 13 | Archer | Archery, Hand-to-Hand, Dodging | Axe, Blunt Weapon, **Critical Strike** | Long Blade, Short Blade, Climbing, Jumping, Running, Swimming |
| 14 | Ranger | Long Blade, Axe, Climbing | Swimming, Archery, **Critical Strike** | Blunt Weapon, Hand-to-Hand, Short Blade, Running, Dodging, **Spriggan** |
| 15 | Barbarian | Blunt Weapon, Long Blade, Axe | Jumping, Running, Swimming | Medical, Climbing, Dodging, **Critical Strike**, Archery, **Giantish** |

By tier: 2 primary (Assassin, Monk), 2 major (Archer, Ranger), 12 minor. By kind: 10 Critical Strike, 6 languages
(Barbarian's Giantish already reads as Explosives).

## 2-3. Recommended table

Uses only skills that exist or are in todo (Pistols: `skillcore` 03). Implement after Pistols lands. No class gets a
skill twice (checked against each class's full list above).

| Class | Tier | Old | New | Reason |
|---|---|---|---|---|
| Mage | Minor | Dragonish | Pistols | A caster's sidearm for when spell points run out. |
| Mage | Minor | Daedric | Explosives | The gun-world fireball; matches Destruction. |
| Sorcerer | Minor | Dragonish | Automatics | Sorcerers cannot regenerate spell points, so they lean on sustained fire. |
| Sorcerer | Minor | Daedric | Explosives | Same reason as Mage. |
| Nightblade | Minor | Critical Strike | Pistols | Quiet precision sidearm for a spellblade assassin. |
| Burglar | Minor | Critical Strike | Pistols | Light gun for a non-fighter; does not change the class's sneak focus. |
| Rogue | Minor | Critical Strike | Shotguns | Close-range brawler (Long Blade, Hand-to-Hand). |
| Acrobat | Minor | Critical Strike | Automatics | Run-and-gun spray fits Jumping, Dodging, Running primaries. |
| Thief | Minor | Critical Strike | Pistols | Light concealable gun. |
| Assassin | **Primary** | Critical Strike | Pistols | The hitman skill: Deadeye and overkill carry-through; Backstabbing already works with guns. Starts above 25. |
| Monk | **Primary** | Critical Strike | Running | Monks fight unarmed (Hand-to-Hand); speed suits that, and a gun primary would not. Running rises steadily, like Critical Strike did from every blow. |
| Archer | **Major** | Critical Strike | Pistols | The precision ranged skill until Rifles exists (then consider Rifles here). |
| Ranger | **Major** | Critical Strike | Shotguns | The hunter's long gun. |
| Ranger | Minor | Spriggan | Stealth | Woodland tracking, replacing a nature language. |
| Barbarian | Minor | Critical Strike | Automatics | The barbarian with a minigun. |
| Barbarian | Minor | Giantish | Explosives | Unchanged: slot 6 already reads as Explosives. |

**Pace:** every replacement is a live skill, so all four primary and major slots rise again, restoring vanilla pace for
Assassin, Monk, Archer and Ranger (today they level slower than vanilla because Critical Strike never rises). How fast
the gun skills rise depends on the open Skill XP and use-gain answers (`work/notes/20261126-010200.md`); if gun skills
rise mainly by buying, Assassin and Archer level mostly through purchases. Minor changes do not affect pace noticeably.

**Side effect to accept:** Assassin starts with Pistols 28-31 and Monk with Running 28-31, so both start with the 25
perk. That suits their identity, but it is a balance point.

**Implementation notes (for the later card):** replace the placeholder with a table keyed by class index
(`CLASS00`-`CLASS17`) that also covers Critical Strike; keep a blanket fallback for custom classes. Old saves store the
career, so the save-load remap changes a character's level sum; rebase `startingLevelUpSkillSum` by the difference so
nobody jumps or stalls a level on load.

**Alternative (simpler blanket rule):** replace each removed language or Critical Strike with the first of Pistols,
Shotguns, Automatics, Explosives that the class does not already have (worse only for Monk, who gets a gun primary,
and for variety: nearly every thief-type class gets Pistols).

## Melee and gun skills in class lists (open owner question)

This proposal **partly answers** it: 11 of 18 preset classes get at least one gun skill in their lists (Assassin and
Archer at primary/major, the rest at minor), so buying or raising that skill counts toward their level as in vanilla.

It **leaves open**:
- The 7 classes with no freed slot get no gun skill: Spellsword, Battlemage, Healer, Bard, Monk, **Warrior**, **Knight**.
  The most martial classes have none, which is odd in a gun-heavy game. Fixing that means swapping out a skill they
  already have, a bigger design change than filling dead slots.
- **Melee** (not built yet) is in no class. Its natural homes are Warrior, Knight, Barbarian, Spellsword, Battlemage,
  but again only by replacing an existing skill.
- **Energy Weapons** (not built yet) would fit Mage and Sorcerer better than Explosives or Automatics; revisit when it
  exists. **Rifles** (backlog) would fit Archer's major better than Pistols.
- Any general rule (for example "a class's melee weapon skills also count for Melee") remains the owner's call.
