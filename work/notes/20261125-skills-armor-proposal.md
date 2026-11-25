# Skills, classes and armor in Doomerfall: a proposal

**Status: PROPOSAL, UNDECIDED.** Game design belongs to the owner. Everything here is options plus a lean, except
where marked "owner, date". Nothing in this note changes code, todo, backlog, or questions.

Sources read: `DFCareer.cs:448` (skill enum), `FormulaHelper.cs` (to-hit, armor, language pacification),
`DaggerfallEntity.UpdateEquippedArmorValues`, `DaggerfallUnityItem.GetMaterialArmorValue`, `EnemyEntity.cs:323`
(enemy skill), `DoomerfallHp.cs` (Doom hits applied with no armor yet), `DoomerfallSheet.cs` (armor and skills
already published to Doom), DRLA `language.classes`, `actors/classes/*.txt`, `actors/base/ArsenalTokens.txt`,
`ArsenalDamageTypes.txt`, `NormalArmors.txt`, DRLAX `language.pda.txt`, `mapinfo.txt` of both.

## 0. General principles proposed

- **Skills shape feel, not success.** No die roll decides whether a shot lands. Skills scale continuous values:
  damage %, spread, reload and refire speed, swap speed, recoil, ammo efficiency, movement.
- **Modest.** A skill at 100 should feel like a strong specialist, not a different game. Proposed scale: effects
  grow linearly from skill 0 to 100, with a typical cap of +15 to +25% on any one value. DRLA class perks (often
  +50% to 8x) become the far end of a skill, at roughly a third to a half of DRLA's strength.
- **Damage bonuses multiply** with material and ammo bonuses (owner, 2026-11-24, `gamedesign/damage.md`).
- **Deterministic where possible.** "Ammo saving" is an accumulator (every Nth shot free) rather than a random
  chance, so it never feels like a roll.
- **Use-based progression stays.** Doom streams telemetry (hits and kills by weapon category, damage taken, jumps,
  climbs, sprint time) and Daggerfall turns it into skill uses with its own advancement rules
  (`architecture.md`, Progression row).
- **Perks at 25, 50, 75 and 100 (owner, 2026-11-25).** Besides any continuous scaling, each skill grants a
  discrete perk at skill 25, 50, 75 and 100. Perks for skills other than Jumping are not designed yet.
- **Works without DRLA.** Every effect is defined on a Doomerfall weapon *category*, and stock Doom weapons belong to
  categories too. DRLA type tokens only feed the category table.

## 1. All 35 Daggerfall skills

Legend: **Keep** = Daggerfall rule unchanged. **Doom** = new Doom-side effect. **Repurpose** = the skill gets a new
meaning. **Limit/Drop** = reduced or hidden.

| # | Skill | What it does in Daggerfall Unity | Proposal |
|---|---|---|---|
| 1 | Medical | Faster health recovery while resting | Keep resting. Doom: health pickups heal +0..+25% more (Medic-like) |
| 2 | Etiquette | Dialogue reactions; pacifies most human classes, vampires, liches | Keep dialogue. Option: hostile NPC bots more likely to accept surrender / yield (section 5) |
| 3 | Streetwise | Dialogue with commoners; pacifies thief-type classes | Keep, same as Etiquette |
| 4 | Jumping | Jump height | **Owner, 2026-11-25:** jump height up to +100%, a +25% spike at 25, double jump at 50, fall damage immunity at 75, triple jump at 100; Jumping also reduces fall damage. See "Jumping perks" below. |
| 5-12 | Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian, Impish | Each pacifies its monster group on first sight (Orcs, Harpies, Giants and Gargoyles, Dragonlings, Nymphs and Lamias, Daedra, Spriggans, Centaurs, Imps and Dreugh) | Those monsters no longer exist. See section 5 |
| 13 | Lockpicking | Opens locks | Keep (locks are Daggerfall's, `gamedesign.md`) |
| 14 | Mercantile | Buy and sell prices | Keep |
| 15 | Pickpocket | Steal from NPCs | Keep |
| 16 | Stealth | Sneaking past enemies | Keep. Doom: slows the detection bar (already planned) |
| 17 | Swimming | Swim speed | Keep, applied to Doom swim speed |
| 18 | Climbing | Wall climbing | Keep (implemented, `DoomerfallClimb`) |
| 19 | Backstabbing | Hit chance plus 3x damage from behind | Doom: +0..+50% damage to monsters that have not detected you or are hit from behind. Ties into Stealth |
| 20 | Dodging | Enemy to-hit minus Dodging/4 | Doom: counts as Dodging/4 extra armor points (section 7), option: faster strafe or a short dodge dash |
| 21 | Running | Run speed | Doom: run speed +0..+10%, slower fatigue drain while sprinting |
| 22 | Destruction | Destruction spell cost and success | Keep for spells. **Repurpose also** as Energy weapons (section 2) |
| 23 | Restoration | Healing spells | Keep for spells |
| 24 | Illusion | Invisibility, chameleon, etc. | Keep for spells |
| 25 | Alteration | Shield, levitation, etc. | Keep for spells |
| 26 | Thaumaturgy | Detect, soul trap, etc. | Keep for spells |
| 27 | Mysticism | Dispel, recall, etc. | Keep for spells |
| 28 | Short Blade | Daggers, tanto, shortswords, wakazashi | **Repurpose:** Pistols |
| 29 | Long Blade | Broadsword, saber, longsword, katana, claymore, dai-katana | **Repurpose:** Rapid-fire |
| 30 | Hand-to-Hand | Unarmed damage and hit chance | **Repurpose/extend:** all Melee |
| 31 | Axe | Battle axe, war axe | **Repurpose:** Shotguns |
| 32 | Blunt Weapon | Staff, mace, flail, warhammer | **Repurpose:** Explosives |
| 33 | Archery | Short and long bow | **Repurpose:** Precision rifles |
| 34 | Critical Strike | Extra to-hit when a skill roll succeeds | Doom: weak-spot bonus, see below |

**Critical Strike** options: (a) every hit has Critical Strike / 5 % chance for +50% damage (a roll, but only on
damage, never on hitting); (b) deterministic: every Nth hit on the same target deals +50%, N falling from 8 to 4
with skill. Lean (b).

### Jumping perks (owner, 2026-11-25)

| Skill | Jump height | Fall damage | Perk |
|---|---|---|---|
| 0 | +0% | full | none |
| 25 | +25% linear, +25% spike = +50% | reduced (see below) | +25% jump height spike |
| 50 | +50% + 25% = +75% | reduced | double jump |
| 75 | +75% + 25% = +100% | none | fall damage immunity |
| 100 | +100% + 25% = +125% | none | triple jump |

- Jump height grows linearly to +100% at skill 100, and the 25 spike adds +25% on top from skill 25 onward.
  The spike stacks on top, so the total is +125% at skill 100 (owner, 2026-11-25).
- Fall damage shrinks with Jumping until immunity at 75. **Lean:** linear from 0% reduction at skill 0 to 50% just
  below 75, then immune. The owner gave no curve.
- Implementation notes: Doom jump height grows with the square of jump speed, so +100% height is about 1.41x jump
  speed (+125% is 1.5x). UZDoom has no falling damage unless the `fallingdamage` dmflag is on, and Daggerfall-side
  fall damage is not built (`CHANGELOG.md`, Climbing), so "reduced fall damage" needs falling damage to exist first.
  Extra jumps are midair jumps; the skill uses for Jumping keep coming from Doom's jump telemetry.

## 2. Weapon-type skills

### Categories, confirmed from the data

DRLA marks its weapons with type tokens (`ArsenalTokens.txt:49-57`), used by the class perks:

| DRLA token | Count of weapon files | Used by |
|---|---|---|
| `RLMeleeTypeWeapon` | 6 (Fist, Chainsaw, Double/Piercing Chainsaw, Energysaw, Ripper) | Commando |
| `RLPistolTypeWeapon` | 62 (pistols, revolvers, handcannons, blasters, Uzis) | Scout |
| `RLShotgunTypeWeapon` | 54 (non-fixed multi-pellet; includes Storm pistols) | Renegade |
| `RLRapidfireTypeWeapon` | 56 (chainguns, miniguns, rifles, Uzis, flamethrower) | Marine |
| `RLSingleShotRifleTypeWeapon` | 12 (railgun, gauss, marksman, anti-materiel, Elephant Gun) | Sniper (unfinished class) |
| `RLEfficientAmmoTypeWeapon` | 54 (uses more than one non-shell ammo per shot: plasma, BFGs) | Demolitionist |
| Basic/Advanced/Master assembly | assemblies | Technician |

There is no explosive token. Rockets, grenades and missiles are found by ammo (rockets) or splash damage. DRLA damage
types are Melee, Bullet, Fire (explosions and fire), Plasma, plus Holy, Unholy, Piercing, Slime and specials
(`ArsenalDamageTypes.txt`). Tokens overlap: a Plasma Uzi is Pistol + Rapidfire + EfficientAmmo.

### Proposed Doomerfall categories and skill mapping (lean: repurpose, no new skills)

| Category | Stock Doom | DRLA | Skill (lean) |
|---|---|---|---|
| Melee | Fist, Chainsaw | Melee token, combat knife | Hand-to-Hand |
| Pistols | Pistol | Pistol token (non-cell) | Short Blade |
| Shotguns | Shotgun, Super Shotgun | Shotgun token | Axe |
| Rapid-fire | Chaingun | Rapidfire token | Long Blade |
| Explosives | Rocket Launcher | rocket/grenade/missile ammo | Blunt Weapon |
| Precision | (none in stock) | SingleShotRifle token | Archery |
| Energy | Plasma Rifle, BFG9000 | cell ammo or Plasma damage type, BFGs | Destruction |

Category precedence for overlapping tokens (lean): Melee > Explosives > Energy (uses cells) > Shotguns > Precision >
Rapid-fire > Pistols. So a Plasma Pistol is Energy and a Storm Pistol is a Shotgun. Alternative: form wins over
ammo (Plasma Pistol = Pistol). Doomerfall would keep one weapon-to-category table, generated from the tokens plus
the stock list, so it works without DRLA.

Why repurpose:
- Daggerfall weapons convert into Doom guns (`gamedesign.md`, the design goal's ebony mace), so the blade, axe, blunt
  and bow skills lose their items. Their existing class data, guild trainers, character sheet, saves and
  advancement all keep working with no new code in those systems.
- Adding skills is expensive: `DFCareer.Skills` is a fixed 35-entry enum indexed in arrays sized by
  `DaggerfallSkills.Count`, read from classic `CLASS*.CFG` careers, saved in save files, shown on fixed sheet pages,
  used by guild training lists and quest checks, and named by `TextProvider`. New skills would touch all of them.
- Display names can change in Doomerfall's text (for example "Axe" shown as "Shotguns") without touching save data.

Pairing logic (all arguable): Short Blade = light and quick (pistols); Long Blade = sustained flurry (rapid-fire);
Axe = heavy close-range cleave (shotguns); Blunt = smash and area (explosives); Archery = aimed ranged (precision);
Destruction = energy. Destruction then covers energy guns *and* destruction spells when spells arrive. That makes
"battlemage" builds natural but couples the two. Alternative: energy on Thaumaturgy, or BFG-class alone on
Mysticism.

Options instead of the lean:
- **B. New skills** for the seven categories, leaving Daggerfall's melee skills as melee. Cleanest meaning,
  highest cost (see above), and the old melee skills would then govern almost nothing.
- **C. Hybrid:** repurpose four melee skills, keep Archery as bows if bows ever become Doom weapons, and fold
  Precision into Pistols.

### Per-category effects (skill 0 to 100, linear)

Common to every category: damage +0..+20%, swap speed (raise/lower) +0..+30%, reload speed +0..+15% where the
weapon reloads. Each category adds one signature effect, a reduced version of the matching DRLA perk:

| Category | Signature effect at 100 | DRLA origin |
|---|---|---|
| Melee | +60% melee damage (instead of +20%); berserk for 5 s after a melee gib at 75+ | Commando: +100% melee, berserk |
| Pistols | spread -40%; slow-firing pistols up to +50% damage (scaled by fire rate) | Scout: 3x-8x, half spread |
| Shotguns | +25% pellets, rounded down per shot with carry-over | Renegade: +50% pellets |
| Rapid-fire | every 4th round free (25% ammo saved) | Marine: 75% saved |
| Explosives | own splash damage -60% | Demolitionist: immune |
| Precision | spread to zero on first shot, +30% damage | Sniper: +100%, perfect accuracy |
| Energy | every 4th cell charge free; BFG-class charge time -15% | Demolitionist: half ammo |

## 3. DRLA classes into skills

**Owner decision (2026-11-25): by default the Doom player is a normal character with no class effects. Unless
overridden by Daggerfall skills it has nothing; Daggerfall does the work of applying skills and modifiers.** So no
DRLA perk is ever granted by class. The table below says which Daggerfall skill reproduces each perk, graded, on
stock and DRLA weapons alike.

Active classes in DRLA 1.1.5 `mapinfo.txt`: Marine, Scout, Technician, Renegade, Demolitionist, Commando. Commented
out and "unfinished": Sniper, Saboteur, Cyborg, Medic, Scientist, Executive. DRLAX 1.2b adds Mechanoid, Nomad,
Nano Maniac, Phase Sisters, Sarge, Trespasser, Bunker.

| Class | DRLA effect | Doomerfall home (lean) |
|---|---|---|
| Marine | Rapid-fire uses 1 ammo per 4 shots; powerups last 50% longer and raise rapid-fire rate | Long Blade (Rapid-fire) ammo saving. Powerup duration: Alteration or Thaumaturgy +0..+25% (option), or drop |
| Scout | Pistols 3x-8x damage, half spread; +10% speed, +10% jump; always has map; double jump | Short Blade (Pistols); Running; Jumping (double jump at 50, owner). Map: drop (Daggerfall automap only) |
| Technician | Scrap exotic+ weapons into modpacks; 8 modpacks; rarity beams; assemblies +10/25/50% damage | No combat skill fits. Option: Mercantile or Lockpicking as "tinkering" (modpack cap, assembly damage +0..+20%). Lean: drop for now, revisit with DRLA mods |
| Renegade | +50% pellets; instant weapon swap; armor +50% protection to 80%; free shot on shell pickup | Axe (Shotguns) pellets; swap speed from each category skill. Armor bonus: drop (Daggerfall armor rules, section 7) |
| Demolitionist | Immune to own splash; half ammo on multi-ammo weapons; explodes when armor breaks | Blunt (Explosives) splash reduction; Destruction (Energy) cell saving. Drop the armor-break bombs |
| Commando | Melee +100%; berserk when hit 3x in 2 s or on melee gib; 10% resist all | Hand-to-Hand (Melee). The 10% resist is Daggerfall armor and resistances' job |
| Sniper* | Scope charge to 4x, takes +50% damage meanwhile; single-shot rifles +100% and perfect | Archery (Precision) |
| Saboteur* | Melee debuffs enemy resistance; stronger explosions | Option: Backstabbing or Hand-to-Hand at 75+ adds a short "exposed" debuff. Lean drop |
| Cyborg* | 200 base HP, no armor, heals from armor repair | Drop (HP is Daggerfall's) |
| Medic* | Double healing; overflow health pool | Medical (pickup healing) |
| Scientist* | Thrown chemical beakers; poison melee | Drop; spells and poison are Daggerfall's |
| Executive* | Bodyguards; datadisks | Drop |
| Mechanoid | Damage per installed modpack | Drop (DRLA-only) |
| Nomad | Luck rises per level; inventory wiped per level | Drop (conflicts with object permanence) |
| Nano Maniac | Melee regenerates ammo; weapons rerolled per level | Option: Hand-to-Hand 75+ melee kills give a little ammo of the drawn gun. Reroll: drop |
| Phase Sisters | Two characters, Marine plus Renegade | Drop |
| Sarge | Shoulder rocket weapon; stomp corpses | Drop (option: Blunt 100 reloads rockets faster) |
| Trespasser | Pistol rounds pierce in a cone; melee kills drop smoke bombs | Option: Short Blade 100 gives pierce to one extra target. Smoke: drop |
| Bunker | Chaingun shield powered by cells; bouncing rockets | Drop |

\* unfinished, disabled in DRLA's own class list.

## 4. Melee skills: consolidate or keep

Daggerfall melee skills and their weapons:

| Skill | Weapons |
|---|---|
| Short Blade | Dagger, Tanto, Shortsword, Wakazashi |
| Long Blade | Broadsword, Saber, Longsword, Katana, Claymore, Dai-Katana |
| Axe | Battle Axe, War Axe |
| Blunt Weapon | Staff, Mace, Flail, Warhammer |
| Hand-to-Hand | Unarmed |
| (Archery) | Short Bow, Long Bow |

Doom has few melee weapons: stock Fist and Chainsaw; DRLA adds 4 chainsaw variants (6 with the Melee token).

| Option | What | For | Against |
|---|---|---|---|
| **M1 (lean)** | One Melee skill = Hand-to-Hand; the four blade/blunt skills plus Archery become gun categories | Matches how few Doom melee weapons exist; frees five skills at no cost | Daggerfall veterans see familiar names with new meanings (fixable with display names) |
| M2 | Keep all four as melee, if Daggerfall melee weapons become real Doom melee weapons | Faithful | Needs new Doom weapons, and gun categories then need new skills (option B) |
| M3 | Two melee skills: Hand-to-Hand (fists, knives) and Blade/Blunt (chainsaws and any future melee) | Some melee variety | Spends one more skill on a thin weapon pool |

Open dependency: how Daggerfall weapon items convert to Doom guns is not documented in `gamedesign.md` beyond
"drops translate into DRLX weapons". If a sword converts to a specific gun family, the skill mapping should follow
the same lines (for example Axe items become shotguns).

## 5. Language skills (not Streetwise or Etiquette)

Current design: "probably on the way out for now" (owner, 2026-11-24; `work/backlog/revisit-languages.md`). In
Daggerfall each pacifies a monster group on first sight (`FormulaHelper.GetEnemyEntityLanguageSkill`). With Doom
packs replacing those monsters the skills have no targets. Pacifying a slaughter-sized pack would also undercut the
core fantasy.

| Option | Idea | Notes |
|---|---|---|
| **L1 (current lean)** | Hide them; no effect | Cheapest; matches the owner's current note |
| L2 Faction lore | Each language becomes knowledge of one Doom monster family: +0..+10% damage against it and its detection bar fills up to 25% slower | Keeps 8 skills useful, rewards specialization, no pacifying. Example: Impish = imps and small demons; Daedric = hell nobles and barons; Giantish = mancubi, cyberdemons; Dragonish = cacodemons and flyers; Harpy = lost souls, pain elementals; Orcish = former humans; Centaurian = arachnotrons, spider masterminds; Spriggan and Nymph = DRLA or Colourful Hell variants |
| L3 Intimidation | High skill in a pack's faction makes stragglers flee when the pack leader dies | Fits "kill the leader" encounters (`gamedesign.md` boss escorts); Doom flee AI exists |
| L4 Pacify only small or lone groups | Faithful pacification limited to packs under N points | Keeps Daggerfall flavor; must never touch slaughter packs or quest foes |
| L5 Merge | Fold all languages into one "Demonology" skill (lore + intimidation) and hide the rest | One useful skill instead of eight weak ones |
| Etiquette / Streetwise extra | Hostile human NPC bots (guards, classes) may surrender or yield at low health, scaled by the matching skill | Fits Daggerfall's surrender to guards |

Lean if languages come back: L2, possibly with L3 at high skill.

## 6. New Game: no DRLA class

**Decided (owner, 2026-11-25):** the Doom player is a normal character with no class effects. Daggerfall applies
all skills and modifiers. Today `dd_bridge.cpp:2147` logs "Doom starts with its default class" (DRLA's first class,
Marine, with its Ammochain perk).

Proposed shape (engineering, within the decision):
- A Doomerfall player class, for example `DoomerfallPlayer`. With DRLA loaded it derives from `DoomRLPlayer` and
  keeps DRLA's infrastructure start items (HUD changers, `RLArmorSpecial`, `RLArmorRemover`, `RLBootsRemover`,
  `RLWipeAssemblies`, stamina, fists) but none of the perk items (`RLAmmoChainPerk`, `RLBerserkerPerk`,
  `RLFireangelPerk`, ...), no class `DamageFactor`s (Commando's 0.9, Demolitionist's `RadiusDamageFactor 0`, Holy
  factors) and no class starting weapon. Without DRLA it derives from the stock `DoomPlayer`.
- DRLA's class menu is skipped in bridged games. Standalone UZDoom with DRLA keeps DRLA's classes (Doom still runs
  without Daggerfall).
- Daggerfall's class (preset or custom) is the only class: its skill levels, primary/major/minor skills and
  weapon expertise flow to Doom through the existing sheet.
- Risk to check: DRLA ACS may assume a known class token. Needs one probe run before relying on it.

Still for the owner (not decided): the starting kit. Lean: the starting gun follows the character's highest
weapon-category skill (like Daggerfall giving class weapons), plus fists and a pistol. Also Daggerfall class
specials (Adrenaline Rush, Athleticism, Regenerate Health, weapon Expertise) need Doom meanings later; Expertise
could add +10% to the matching category.

## 7. Armor: Daggerfall's mitigation as damage reduction

### Daggerfall's math (verified in code)

- Each body part starts at armor value 100. Each equipped piece subtracts 5 x material value
  (`DaggerfallEntity.cs:610`). Material values (`DaggerfallUnityItem.cs:1029`): Leather 3, Chain 6, Iron 7,
  Steel/Silver 9, Elven 11, Dwarven 13, Mithril/Adamantium 15, Ebony 17, Orcish 19, Daedric 21. Artifacts halve.
  Shields add 5 x (Buckler 1, Round 2, Kite 3, Tower 4) to the parts they cover.
- Seven parts, hit with weights out of 20 (`CalculateStruckBodyPart`): Head 2, Right arm 3, Left arm 3, Chest 4,
  Hands 4, Legs 3, Feet 1.
- Chance to hit the player = attacker skill + armor value of struck part + adrenaline + enchantments +
  (luck and agility differences)/10 - Dodging/4 - biography mod - 50, clamped 3 to 97 (`FormulaHelper.cs:796`,
  `1202`, `1224`). Monsters also pass a separate reflexes gate first, unrelated to armor.
- Enemy skill = 30 + 5 x level, max 100 (`EnemyEntity.cs:323`).

Write armor points A = 5 x material per part (0 to 105). With equal stats and no Dodging:
**P(hit) = clamp(S + 50 - A, 3, 97)**. Expected-damage reduction from armor = 1 - P(A)/P(0).

### Equivalent damage reduction, full suit of one material

| Armor (A) | vs S 35 (enemy lvl 1) | vs S 55 (lvl 5) | vs S 80 (lvl 10) | vs S 100 (lvl 14+) |
|---|---|---|---|---|
| None (0) | 0% (85% hit) | 0% (97%) | 0% (97%) | 0% (97%) |
| Leather (15) | 18% | 7% | 0% | 0% |
| Chain (30) | 35% | 23% | 0% | 0% |
| Iron (35) | 41% | 28% | 2% | 0% |
| Steel (45) | 53% | 38% | 12% | 0% |
| Elven (55) | 65% | 48% | 23% | 2% |
| Dwarven (65) | 76% | 59% | 33% | 12% |
| Mithril (75) | 88% | 69% | 43% | 23% |
| Ebony (85) | 96% | 79% | 54% | 33% |
| Orcish (95) | 96% | 90% | 64% | 43% |
| Daedric (105) | 96% | 97% | 74% | 54% |

Findings:
- Daggerfall's armor is very contextual: 0% to 96% for the same suit, because to-hit is additive and clamped.
  Against weak enemies good armor is near immunity; against strong ones cheap armor does nothing.
- Along the "matched" diagonal (gear typical for the depth), Daggerfall delivers roughly 20-35% early,
  30-45% mid, and about 55% with daedric against the strongest enemies.
- Each armor point is worth 5 points of hit chance; in the unclamped zone the reduction is linear in A.

### Converting to Doom

Doom has no misses against the player: a hit lands or the player dodged it by moving. Turning Daggerfall's average
miss rate into a per-hit reduction gives the **same expected damage with less variance**, which suits action play.
Nothing about dodging changes: player skill still decides which hits land.

Inputs already reach Doom: `DFB_SHEET_ARMOR_LIVE` holds each part's live value including spell modifiers, so
A_part = 100 - live value. Weighted average: A = sum(weight_part x A_part) / 20.

Curve options:

| Option | Formula | Leather / Chain / Steel / Dwarven / Ebony / Daedric | Notes |
|---|---|---|---|
| F. Faithful | 1 - clamp(S+50-A)/clamp(S+50), S from area level | see table above | Near immunity in low areas, nothing in deep ones. Area level (not player level) keeps the world pillar, but numbers swing too much for Doom |
| **H. Hyperbolic, K=80 (lean)** | DR = A / (A + 80) | 16 / 27 / 36 / 45 / 52 / 57% | Smooth, never reaches 100%, fits the matched diagonal. Tower shield on daedric: 59% |
| H100 | DR = A / (A + 100) | 13 / 23 / 31 / 39 / 46 / 51% | Pick if HP grows a lot with level |
| L. Linear with cap | DR = 0.55% x A, cap 60% | 8 / 17 / 25 / 36 / 47 / 58% | Simple; cheap armor feels weak |
| D. Depth-aware | DR = A / (A + 60 + 3 x area level) | area 1: 19/33/42/51/58/63%; area 20: 12/21/29/37/44/49% | Keeps Daggerfall's "deep places punch through armor" in a soft form, world-indexed |

For reference: Doom green armor absorbs 33%, blue 50%, DRLA armors 10-60% (`Armor.SavePercent`). Daedric under H
is about a permanent blue armor.

### Smoothing and design consequences

| Topic | Options | Lean |
|---|---|---|
| Per hit vs per part | (a) weighted average of parts; (b) random part per hit (faithful, adds variance, missing helmet becomes a gamble); (c) part from hit height (projectile/puff Z; splash has none) | (a). Same expected value as Daggerfall; a missing helmet costs 10% of the armor, as in Daggerfall on average |
| Damage types | (a) armor reduces everything, like Doom armor; (b) full vs Melee, Bullet, Piercing and projectile impact; half vs Fire and Plasma and explosive splash; none vs slime/nukage, falling, crushing, drowning, telefrag, poison and disease | (b). Daggerfall armor never stopped spells; Daggerfall's resistances (already in the sheet) handle elements |
| Hitscan packs | Slaughter-scale zombie packs deal many small hits; percent DR scales them evenly, unlike Doom's flat armor pool | Fine with percent DR; no change |
| Cap | Hyperbola stays below 100%; spells (Shield) can push A past 105 | Hard cap 75% total from all armor sources |
| Dodging | Adds Dodging/4 to A (Dodging 60 = +15, a leather suit) | Lean yes, faithful and modest |
| Weight | Daggerfall plate is heavy; encumbrance slows Doom movement (planned). In Doom, speed is defense | Keep; plate's speed cost will matter more than in Daggerfall, a real trade-off. Watch in play tests |
| Condition | Daggerfall damages armor on hits (`DamageEquipment`) | Keep: each Doom hit wears a piece (random by part weight); broken pieces stop counting |
| Stock Doom armor | Currently used up on pickup (stopgap) | Keep as is until DRLA armor's role is decided |
| DRLA armor | (a) refused, as now; (b) stacks multiplicatively under the 75% cap; (c) only its type resistances (`DamageFactor`) and specials apply, not save percent | Owner question, already open in `work/backlog/drla-armor-role.md`. Lean (c) if allowed at all: daedric 57% plus DRLA 60% would be 83% |
| Order | Damage arrives from Doom, Daggerfall applies armor DR, then resistances, then HP (Daggerfall owns HP; `DoomerfallHp` applies hits unchanged today) | As stated |
| HP rescale | DR multiplies, so it works with any HP scale. But effective HP = HP / (1 - DR): 300 HP in daedric is about 700 effective HP | Tune the HP curve and K together; if high-level HP is several hundred, prefer H100 or D |

## 8. Questions for the owner (each with a lean)

1. Repurpose Short Blade, Long Blade, Axe, Blunt and Archery as gun categories (M1), or add new skills? Lean:
   repurpose, with Doomerfall display names.
2. Which skill pairs with which category? Lean: table in section 2.
3. Should Destruction cover energy weapons as well as destruction spells? Lean yes.
4. Do cell weapons go to Energy even when shaped like pistols or rifles? Lean yes (ammo wins).
5. Effect size: about +20% per value at skill 100, signature perks at a third to a half of DRLA's strength? Lean yes.
6. Languages: keep hidden (L1), or faction lore (L2)? Lean L1 now, L2 when revisited.
7. Should hostile human NPCs yield based on Etiquette or Streetwise? Lean yes, later.
8. Starting kit after New Game with no class: highest weapon skill's gun plus fists and pistol? Lean yes.
9. Armor curve: hyperbolic K=80 (H), H100, or depth-aware (D)? Lean H, revisit with the HP formula.
10. Armor applied as one weighted average, not per hit location? Lean yes.
11. Armor full vs physical, half vs fire/plasma/splash, none vs environment and poison? Lean yes.
12. Total armor cap 75%? Lean yes.
13. Dodging adds Dodging/4 armor points? Lean yes.
14. Critical Strike as deterministic every-Nth-hit bonus? Lean yes.
15. Technician-style perks (modpacks, assemblies): drop for now? Lean yes.

## Suspected oversights

- `DoomerfallHp.cs` applies Doom hits with "no armor or scaling yet", while Doom's own stock armor is used up on
  pickup. Until section 7 lands, Daggerfall armor has no effect at all in bridged play. Expected, but worth keeping
  in mind when judging difficulty in play tests. Confidence high.
