# Skills, perks, classes and armor in Doomerfall: a proposal

**Status: PROPOSAL, UNDECIDED.** Game design belongs to the owner. Everything here is options plus a lean, except
where marked "owner, date". Nothing in this note changes code, todo, backlog, or questions. Owner decisions are
also listed in `work/backlog/skills-in-doom.md`.

Sources read: `DFCareer.cs:448` (skill enum), `FormulaHelper.cs` (to-hit, armor, language pacification),
`DaggerfallEntity.UpdateEquippedArmorValues`, `DaggerfallUnityItem.GetMaterialArmorValue`, `EnemyEntity.cs:323`
(enemy skill), `DoomerfallHp.cs` (Doom hits applied with no armor yet), `DoomerfallSheet.cs` and
`bridge/doomerfall_bridge.h` (skills, armor, fatigue and magicka already published to Doom), DRLA
`language.classes`, `actors/classes/*.txt`, `actors/base/ArsenalTokens.txt`, `ArsenalDamageTypes.txt`,
`NormalArmors.txt`, DRLAX `language.pda.txt`, `mapinfo.txt` of both.

## 0. Principles

Decided (owner, 2026-11-25):
- **No Doom class.** The Doom player is a normal character. Daggerfall skills apply all perks and modifiers. DRLA
  classes are inspiration only.
- **Perks at 25, 50, 75 and 100.** Each skill grants a discrete perk at each threshold, besides any continuous
  scaling. Perks are where the memorable, playstyle-changing effects live; Jumping is the model (section 3).
- **Milder than Daggerfall's die rolls.** Continuous effects stay modest.
- **Stay within Daggerfall's 35 skills.**
- **Hand-to-Hand governs Doom melee damage** (fists and other melee), for now.
- **Archery stays a skill;** its Doom role is undecided.

Proposed (undecided):
- **Skills shape feel, not success.** No die roll decides whether a shot lands. Continuous scaling is secondary:
  damage %, spread, reload and swap speed, movement, capped around +15 to +20% at skill 100.
- **Damage bonuses multiply** with material and ammo bonuses (owner, 2026-11-24, `gamedesign/damage.md`).
- **Deterministic where possible.** "Free ammo" is an accumulator (every Nth shot free), not a chance.
- **Use-based progression stays.** Doom streams telemetry (hits and kills by weapon category, damage taken, jumps,
  climbs, sprint time) and Daggerfall turns it into skill uses (`architecture.md`, Progression row).
- **Works without DRLA.** Every perk is defined on a Doomerfall weapon *category* or on the player, and stock Doom
  weapons belong to categories too. DRLA type tokens only feed the category table.

## 1. All 35 Daggerfall skills

Legend: **Keep** = Daggerfall rule unchanged. **Doom** = new Doom-side effect. **Repurpose** = the skill gets a new
meaning. **Hide** = no effect for now. Perks for every kept skill are in section 3.

| # | Skill | What it does in Daggerfall Unity | Proposal |
|---|---|---|---|
| 1 | Medical | Faster health recovery while resting | Keep resting. Doom perks: healing, second chance |
| 2 | Etiquette | Dialogue reactions; pacifies most human classes, vampires, liches | Keep dialogue. Doom perks: hostile humans (nobles, knights, guards) parley and yield |
| 3 | Streetwise | Dialogue with commoners; pacifies thief-type classes | Keep dialogue. Doom perks: hostile rogues yield; fencing and black market |
| 4 | Jumping | Jump height | **Owner, 2026-11-25:** see "Jumping perks" in section 3 |
| 5-12 | Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian, Impish | Each pacifies its monster group on first sight | Those monsters no longer exist. Section 6 |
| 13 | Lockpicking | Opens locks | Keep (locks are Daggerfall's). Doom perks: breaching, magic locks |
| 14 | Mercantile | Buy and sell prices | Keep. Perks: appraisal, supply, ordering guns |
| 15 | Pickpocket | Steal from NPCs | Keep. Doom perks: disarming hostile humans |
| 16 | Stealth | Sneaking past enemies | Keep. Doom: slows the detection bar (planned); perks change its rules |
| 17 | Swimming | Swim speed | Keep, applied to Doom swim speed |
| 18 | Climbing | Wall climbing | Keep (implemented, `DoomerfallClimb`) |
| 19 | Backstabbing | Hit chance plus 3x damage from behind | Doom: bonus against monsters that have not detected you |
| 20 | Dodging | Enemy to-hit minus Dodging/4 | Doom: Dodging/4 extra armor points (section 8) plus dash perks |
| 21 | Running | Run speed | Doom: run speed, slide, adrenaline perks |
| 22 | Destruction | Destruction spell cost and success | Keep for spells. **Repurpose also** as Energy weapons (lean) |
| 23-27 | Restoration, Illusion, Alteration, Thaumaturgy, Mysticism | Spell schools | Keep for spells. Doom perks that work before spells exist (powerups, healing, items, resurrection) |
| 28 | Short Blade | Daggers, tanto, shortswords, wakazashi | **Repurpose (lean):** Pistols |
| 29 | Long Blade | Broadsword, saber, longsword, katana, claymore, dai-katana | **Repurpose (lean):** Rapid-fire |
| 30 | Hand-to-Hand | Unarmed damage and hit chance | **Owner, 2026-11-25:** governs Doom melee damage (fists and other melee) |
| 31 | Axe | Battle axe, war axe | **Repurpose (lean):** Shotguns |
| 32 | Blunt Weapon | Staff, mace, flail, warhammer | **Repurpose (lean):** Explosives |
| 33 | Archery | Short and long bow | **Owner, 2026-11-25:** stays a skill, role undecided. Options in section 3 |
| 34 | Critical Strike | Extra to-hit when a skill roll succeeds | Doom: deterministic weak-spot hits |

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

### Proposed categories and skill mapping (within the 35 skills)

| Category | Stock Doom | DRLA | Skill |
|---|---|---|---|
| Melee | Fist, Chainsaw | Melee token, combat knife | Hand-to-Hand (owner, 2026-11-25) |
| Pistols | Pistol | Pistol token (non-cell) | Short Blade (lean) |
| Shotguns | Shotgun, Super Shotgun | Shotgun token | Axe (lean) |
| Rapid-fire | Chaingun | Rapidfire token | Long Blade (lean) |
| Explosives | Rocket Launcher | rocket/grenade/missile ammo | Blunt Weapon (lean) |
| Energy | Plasma Rifle, BFG9000 | cell ammo or Plasma damage type, BFGs | Destruction (lean) |
| Precision | (none in stock) | SingleShotRifle token | Archery is one option (role undecided); else fold into Pistols or Rapid-fire |

Category precedence for overlapping tokens (lean): Melee > Explosives > Energy (uses cells) > Shotguns > Precision >
Rapid-fire > Pistols. So a Plasma Pistol is Energy and a Storm Pistol is a Shotgun. Alternative: form wins over
ammo (Plasma Pistol = Pistol). Doomerfall would keep one weapon-to-category table, generated from the tokens plus
the stock list, so it works without DRLA.

Why repurpose the blade and blunt skills: Daggerfall weapons convert into Doom guns (`gamedesign.md`, the design
goal's ebony mace), so those skills lose their items, and their class data, guild trainers, sheet, saves and
advancement keep working unchanged. Display names can change in Doomerfall's text (for example "Axe" shown as
"Shotguns") without touching save data. Pairing logic (arguable): Short Blade = light and quick; Long Blade =
sustained flurry; Axe = heavy close-range cleave; Blunt = smash and area; Destruction = energy. Destruction then
covers energy guns *and* destruction spells when spells arrive, which makes battlemage builds natural but couples
the two. Alternative for Energy: Thaumaturgy.

## 3. Perks at 25, 50, 75 and 100

### How Doom would apply them (engineering, proposed)

- Doom already receives every skill's base and live value (`DFB_SHEET_SKILLS_BASE/LIVE`). The perk tier is
  floor(skill / 25), from one shared table, so Daggerfall's numbers decide and Doom only reads them.
- Without Daggerfall (plain UZDoom) the sheet is invalid, so the player has no perks: a normal Doom marine.
- Most weapon perks hook in one place: a Doomerfall inventory item on the player that adjusts damage, ammo use and
  weapon states by category (`ModifyDamage`, `AbsorbDamage`, `DepleteAmmo` overrides, weapon state speed), so
  stock and DRLA weapons get the same perk without editing either.
- Not built yet, and needed by some perks: **fall damage** (Jumping), **the detection bar** (Stealth,
  Backstabbing), **Doom-side spells** (magic schools), **spending magicka or fatigue from Doom** (the bridge only
  publishes them today), **hostile human surrender** (Etiquette, Streetwise), **monster factions** (languages).
- Live or base skill? Live lets Fortify and Drain effects switch perks on and off (fun with potions), base is
  steadier. Lean: live.

Each table: **bold = lean**, then alternatives. "Needs" lists unbuilt systems. The scaling line is secondary.

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
- Constraint on the fall damage curve (owner, 2026-11-25): at every skill level, jumping in place and landing
  (including double and triple jumps) must not cause fall damage. Falls onto lower ground can still hurt. Lean: raise
  the no-damage fall distance by at least the skill's extra jump height, and apply the percentage reduction above it.
- Fall damage shrinks with Jumping until immunity at 75. **Lean:** linear from 0% reduction at skill 0 to 50% just
  below 75, then immune. The owner gave no curve.
- Implementation notes: Doom jump height grows with the square of jump speed, so +100% height is about 1.41x jump
  speed (+125% is 1.5x). UZDoom has no falling damage unless the `fallingdamage` dmflag is on, and Daggerfall-side
  fall damage is not built (`CHANGELOG.md`, Climbing), so "reduced fall damage" needs falling damage to exist first.
  Extra jumps are midair jumps; the skill uses for Jumping keep coming from Doom's jump telemetry.

### Weapon skills

**Short Blade: Pistols** (Scout, Trespasser). Scaling: damage +0..+15%, spread -0..-30%.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Quickdraw:** pistols raise and lower instantly | Pistol swap also reloads | Skip Select/Deselect states for the Pistols category |
| 50 | **Steady hand:** first shot after 0.4 s without firing has zero spread | Fan the hammer: hold fire for +50% rate, double spread | Spread override in the fire hook |
| 75 | **Overpenetration:** pistol bullets pass through the first monster into one more (Trespasser) | Upper-body hits +50% (needs hit height vs monster height) | Continue the hitscan trace past the first hit |
| 100 | **Deadeye:** slow-firing pistols deal 2x, scaled down for fast ones (Scout's 3x-8x, milder) | Akimbo: wield two pistols (overlay sprite, costly on DRLA guns); Last round in a magazine deals 3x (stock pistol has no magazine) | Damage factor by the weapon's refire time |

**Long Blade: Rapid-fire** (Marine, Bunker). Scaling: damage +0..+15%, spin-up and swap faster.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Controlled burst:** first 3 rounds of each trigger pull have zero spread | Chaingun/minigun spin-up halved | Spread override by shots since trigger press |
| 50 | **Ammo chain:** every 4th round is free (Marine, milder) | Every 3rd round | `DepleteAmmo` accumulator |
| 75 | **Suppression:** a monster taking 6+ of your hits in 1 s is staggered (forced pain) and slowed for 1 s | Walking fire: no spread growth while moving | Per-target hit counter; pain state and speed change |
| 100 | **Overdrive:** after 2 s of continuous fire, fire rate +25% | Siege stance: while firing and not moving, 25% less damage from the front (Bunker) | Weapon tic scaling while held |

**Axe: Shotguns** (Renegade). Scaling: damage +0..+15%, pump and reload faster.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Free shell:** picking up shells makes your next shotgun shot cost nothing (one stored) (Renegade) | Shotgun swap time halved | Token set on shell pickup, consumed in `DepleteAmmo` |
| 50 | **Buckshot:** +25% pellets, carry-over for fractions (Renegade's +50%, milder) | Tighter spread -30% | Extra pellets in the fire hook |
| 75 | **Knockdown:** point-blank shotgun hits knock monsters back and stagger them | Instant swap to and from any weapon (Renegade) | Thrust on damage within a short range |
| 100 | **Slug load:** a toggle key fires one accurate slug carrying all pellet damage | Overkill pellets: pellets that kill keep going; Super Shotgun double-tap then instant reload once per 3 s | Toggle replaces the pellet spray with one trace. Uses its own key, because DRLA uses altfire |

**Blunt Weapon: Explosives** (Demolitionist, Sarge, Bunker). Scaling: damage +0..+15%, splash radius +0..+10%.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Blast discipline:** your own splash hurts you 50% less | Rockets reload faster | Self-damage factor on splash |
| 50 | **Rocket jump:** your own splash pushes you 50% harder and deals no damage while you are airborne | Shrapnel: explosions throw 4 bullet fragments | Thrust scaling; pairs with Jumping |
| 75 | **Fireangel:** immune to your own splash (Demolitionist) | Bouncing grenade mode (Bunker) | Self-splash factor 0 |
| 100 | **Chain reaction:** monsters killed by your explosions burst for a small blast | Cluster rockets split into 3 bomblets; Second launcher (Sarge) | Spawn a weak explosion on death by explosive. Cap bursts per tic for slaughter packs |

**Destruction: Energy weapons** (Demolitionist, Bunker), also spells later. Scaling: damage +0..+15%, BFG charge
-0..-15%.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Efficient cells:** every 4th energy shot is free | Destruction spells cost 20% less (needs spells) | `DepleteAmmo` accumulator |
| 50 | **Ionize:** energy hits leave the target taking +15% from all sources for 2 s | Overcharge: hold fire for one charged bolt | Timed debuff item on the monster |
| 75 | **Arc:** energy projectiles jump to one nearby monster for 50% damage | BFG tracer count +50% | Spawn a short arc on impact |
| 100 | **Mana battery:** with no cells, energy weapons draw Daggerfall magicka instead | Kills refund 1 cell; Plasma spray never hurts you | Needs a new bridge event to spend magicka (Daggerfall owns it) |

**Hand-to-Hand: Melee** (Commando, Nano Maniac, Saboteur). Governs melee damage (owner, 2026-11-25). Scaling:
melee damage, the main continuous effect here (lean up to +60%, Commando's +100% milder).

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Haymaker:** punches knock small monsters back and stagger them | Melee swap is instant | Thrust plus forced pain on fist hits |
| 50 | **Bloodlust:** a melee gib grants 5 s of berserk (melee x2, red tint) (Commando) | Vengeance: 3 hits taken in 2 s grants berserk | Short custom damage powerup |
| 75 | **Siphon:** melee kills give a little ammo for your last gun (Nano Maniac) | Melee kills drop a smoke bomb that blinds nearby monsters (Trespasser) | Give ammo on melee kill |
| 100 | **Finisher:** melee on a staggered monster under 20% health kills it and heals you 5% of max HP | Melee strips resistance for 3 s (Saboteur) | Heal goes over the existing heal event; bosses excluded |

**Archery** (role undecided, owner 2026-11-25). Three candidate roles, each with perks. Lean: **A**, because DRLA
has a precision family and Daggerfall bows are aimed ranged weapons.

| Tier | A. Precision rifles (Sniper) | B. Aiming, all guns | C. Bows and crossbows (if added as Doom weapons) |
|---|---|---|---|
| 25 | Zoom on precision rifles | **Zoom key for any gun** (2x field of view) | Arrows are recovered from bodies |
| 50 | Hold breath: zoomed and still, zero spread and +25% damage | Crouched or still: spread -50% | Draw-charge: hold fire for up to 2x |
| 75 | Rifle rounds pierce every monster in line | Look at a monster to see its health | Special arrows (fire, poison) via Daggerfall items |
| 100 | Longshot: hold fire to charge to 2x, take +25% damage meanwhile (Sniper's 4x, milder) | Mark: an aimed target takes +20% from all your attacks for 3 s | Volley: fire 3 arrows in a fan |
| Needs | Stock Doom has no precision gun, so without DRLA the perks do nothing | Works on stock guns | New weapons |

**Critical Strike.** Scaling: none (lean), so the perks carry it.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Weak spot:** every 6th hit on the same monster deals +50% | Random Critical Strike / 5 % chance (a roll, damage only) | Per-target hit counter |
| 50 | **Telling blow:** weak-spot hits always stagger | Every 5th hit | Forced pain state |
| 75 | **Exploit:** after a weak-spot hit the target takes +15% from all sources for 3 s | Every 4th hit | Timed debuff |
| 100 | **Execution:** a weak-spot hit on a non-boss monster under 25% health kills it | Weak-spot hits gib | Bosses excluded |

### Movement and survival skills

**Running** (Scout). Scaling: run speed +0..+10%, slower fatigue drain.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Long legs:** sprinting costs no fatigue while lightly loaded | Faster acceleration | Needs fatigue spent from Doom (published only today) |
| 50 | **Slide:** crouch while running to slide, with a lower hitbox and kept momentum | Vault low obstacles | Crouch height plus kept velocity |
| 75 | **Shoulder charge:** running into a small monster knocks it back | Momentum: +10% speed after 1 s of running | Bump check on the player |
| 100 | **Adrenaline:** under 25% of max HP, +25% speed and no fatigue cost (Daggerfall's Adrenaline Rush) | Run and gun: full speed while firing heavy weapons | Speed factor from published HP |

**Dodging.** Scaling: Dodging/4 armor points (section 8).

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Sidestep:** double-tap strafe for a short dash (2 s cooldown) | Dash key | Velocity impulse, cooldown token |
| 50 | **Graze:** hits within 0.3 s after a dash deal half damage | Dash cooldown 1 s | Timed damage factor |
| 75 | **Second wind:** a kill resets the dash cooldown | Splash damage -30% | Event on kill |
| 100 | **Untouchable:** a dash makes you invulnerable for 0.25 s | Blur: monsters' hitscan aim wobbles while dashing (Doom's shadow flag) | Brief invulnerability flag |

**Swimming.** Scaling: swim speed.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Deep lungs:** air lasts 50% longer | Less underwater fog | Air supply factor |
| 50 | **Swift stroke:** swim speed equals run speed | Fire any weapon underwater at full rate | Water move factor |
| 75 | **Diver:** no damage landing in water from any height | Dash underwater | Needs fall damage |
| 100 | **Amphibious:** breathe underwater indefinitely | Water hides you from monsters (bar does not fill submerged) | Air never runs out; the alternative needs the detection bar |

**Climbing** (implemented). Scaling: climb speed and success, as today.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Mantle:** pull yourself onto ledges within reach while jumping | Climb speed +25% | Ledge check on jump |
| 50 | **Hang:** holding still on a wall skips skill rolls | Climb down with Back | Matches the open question in `work/questions.md` |
| 75 | **Wall jump:** jump off the wall you are climbing | Ceiling crawl in low spaces | Impulse away from the wall normal |
| 100 | **Sure grip:** climbing never fails, and pistols and melee work while climbing | Climb at run speed | Skip the roll; allow one-handed categories |

**Medical** (Medic). Scaling: resting heal rate (Daggerfall's), pickups heal +0..+20%.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Field dressing:** 10 minutes of loitering heals like an hour | Pickups +25% | Daggerfall-side rest rule |
| 50 | **Medic's bag:** health pickups taken at full health go into a pool (cap 50 HP) used with a key (Medic) | Overheal to 110% that decays | Pool kept by Daggerfall as a counter |
| 75 | **Antidote:** poison and disease damage halved | Bleeding stops faster (no bleeding exists) | Daggerfall-side |
| 100 | **Second chance:** once per game day, a lethal hit leaves you at 1 HP and heals 25% over 5 s | Pickups heal 2x | Daggerfall owns death, so Daggerfall applies it |

### Stealth skills

**Stealth.** Scaling: detection bar fill rate (planned). All perks need the detection bar.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Soft steps:** your footsteps and landings never fill the bar | Crouch walking at full speed | Mute movement noise |
| 50 | **Shadow:** in dark sectors the bar fills half as fast | Crouching halves fill | Sector light level |
| 75 | **Lose them:** breaking line of sight for 5 s returns alerted monsters to searching | Melee and silenced shots do not alert | Monster state reset |
| 100 | **Ghost:** firing a gun no longer wakes everything; it fills the bar by weapon noise and distance | Standing still makes you invisible to monsters that have not seen you | Changes the "firing wakes all" rule |

**Backstabbing.** Scaling: +0..+50% damage on monsters that have not detected you. Needs the detection bar.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Silent kill:** killing an unaware monster does not fill the bar | Unaware kills drop no alert sound | Bar hook |
| 50 | **Assassinate:** melee on an unaware monster deals 3x (Daggerfall's backstab) | Applies to hits from behind too | Damage factor |
| 75 | **Vanish:** an unaware kill freezes the bar for 3 s | Smoke on unaware kill (Trespasser) | Bar hook |
| 100 | **Opening shot:** your first hit on an unaware monster with any weapon deals 3x | Unaware kills chain: each within 3 s adds +25% to the next | Damage factor by awareness |

### Social and trade skills

**Etiquette.** Scaling: Daggerfall's dialogue rules. Doom perks need hostile human surrender (not built).

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Parley:** hail a hostile guard or knight; it holds fire for 3 s to let you surrender | Better temple and noble prices | Use key on a hostile human bot |
| 50 | **Yield:** hostile nobles, knights and guards under 25% health surrender instead of fighting on | Guards accept surrender while you are armed | Bot leaves combat; Daggerfall decides the crime outcome |
| 75 | **Court access:** no trespass crime inside castles and palaces | Halved fines | Daggerfall-side |
| 100 | **Stand down:** a hailed group of hostile non-quest humans can be talked out of the fight | Hire a human ally bot | Daggerfall roll on Etiquette, as its own pacification |

**Streetwise.** Same pattern for thieves, rogues and commoners.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Fence:** pawn shops buy Doom guns and stolen goods | Better prices in poor towns | Ties to the open Doom item pricing question |
| 50 | **Yield:** hostile thieves and rogues under 25% health surrender | Rogues sometimes pay you off | Needs surrender |
| 75 | **Word on the street:** rumors name the loot identity of nearby dungeons | Rumors warn of the biggest pack | Daggerfall rumor text |
| 100 | **Black market:** a contact sells rare Doom guns and ammo tiers | Thieves Guild discount | Shop stock rule |

**Mercantile.** Scaling: prices (Daggerfall's).

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Appraise:** see an item's value under the crosshair | Sell ammo in bulk | Look label (built) shows value |
| 50 | **Supplier:** shops always stock some ammo for your drawn gun's type | Ammo 20% cheaper | Shop stock rule |
| 75 | **Repair deal:** armor repair costs halved | Sell at full value to your guild | Daggerfall-side |
| 100 | **Special order:** order a Doom gun family from a smith, delivered in days | Shops buy at full value | Daggerfall-side; stock guns orderable without DRLA |

**Lockpicking.** Scaling: Daggerfall's lock chance.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Quiet picks:** picking makes no noise | Faster picking | Needs the detection bar |
| 50 | **Breacher:** shotgun and explosive hits bash locked doors open | Spot traps | Damage event on a door to Daggerfall's bash rule |
| 75 | **Second try:** a failed pick can be retried at once | Picking never breaks | Daggerfall-side |
| 100 | **Master key:** magically locked doors can be picked | Unlock from a distance | Daggerfall-side |

**Pickpocket.** Scaling: Daggerfall's steal chance.

| Tier | Perk | Alternatives | How in Doom / needs |
|---|---|---|---|
| 25 | **Light fingers:** stealing from sleeping NPCs never wakes them | Steal from shop counters | Daggerfall-side |
| 50 | **Quick hands:** taking from piles and bodies is instant | Looting does not fill the bar | Doom Use path |
| 75 | **Disarm:** melee on a hostile human bot can knock its weapon to the ground | Stun on melee hit | Bot drops its weapon pickup |
| 100 | **Grand theft:** melee hits on hostile humans steal some of their ammo | Steal a gun outright | Give ammo on hit |

### Magic schools (spells come later; these perks work before spells)

| Skill | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| Restoration | **Out of combat, regenerate to 25% of max HP** | Healing spells cost 20% less (needs spells) | **Purify: nukage and slime damage halved** | **Overflow: healing past max HP becomes 25 temporary armor points** |
| Alteration | **Powerups last 25% longer** (Marine) | **Armor wears half as fast** | **Radiation suit also blocks splash from hazards** | **Supercharged: during a powerup, fire rate +15%** (Marine) |
| Illusion | **Invisibility powerups last 50% longer** | **Blur while sprinting (Doom's shadow flag: monster aim wobbles)** | Decoy: alerted monsters lose you 2 s sooner (needs bar) | **Doppelganger: once a minute a heavy hit spawns a decoy monsters target for 3 s** |
| Thaumaturgy | **Sense: monsters within 20 m show as marks on Daggerfall's automap** | **Item glow: Doom items glow by tier** (Technician beams) | Soul harvest: kills fill soul gems (needs spells) | **Transmute: break unwanted Doom guns into ammo** (Technician scavenger) |
| Mysticism | **Consecrate: monsters you kill cannot be resurrected** (Sarge's stomp) | Recall costs less (needs spells) | **Banish: summoned monsters die with their summoner** | **Null field: monster projectiles slow near you for 1 s every 10 s** |

Alternatives for the magic schools are kept minimal on purpose: once Doom spells exist, most 50 and 75 perks
should become spell rules (cost, range, duration), and the owner may prefer that from the start.

### Languages (only if they come back; current lean is hidden)

One template for all eight, assuming option L2 (faction lore, section 6):

| Tier | Perk (lean) | Alternatives |
|---|---|---|
| 25 | See that faction's health bars | +5% damage against it |
| 50 | Its monsters fill the detection bar 25% slower | Its packs show on the automap when near |
| 75 | When its pack leader dies, stragglers flee | Its monsters infight more easily |
| 100 | Lone monsters or small groups of it ignore you unless attacked | Turn one weak monster into a temporary ally |

## 4. DRLA classes into skills

**Owner decision (2026-11-25):** the Doom player is a normal character with no class effects; DRLA classes are
inspiration only. The table says where each class idea landed in section 3.

Active classes in DRLA 1.1.5 `mapinfo.txt`: Marine, Scout, Technician, Renegade, Demolitionist, Commando. Commented
out and "unfinished": Sniper, Saboteur, Cyborg, Medic, Scientist, Executive. DRLAX 1.2b adds Mechanoid, Nomad,
Nano Maniac, Phase Sisters, Sarge, Trespasser, Bunker.

| Class | DRLA effect | Where it went |
|---|---|---|
| Marine | Rapid-fire uses 1 ammo per 4 shots; powerups last 50% longer and raise rapid-fire rate | Long Blade 50 Ammo chain; Alteration 25 and 100 |
| Scout | Pistols 3x-8x, half spread; +10% speed and jump; map; double jump | Short Blade 50 and 100; Running; Jumping 50 (owner). Map dropped (Daggerfall automap only) |
| Technician | Scrap weapons into modpacks; 8 modpacks; rarity beams; assemblies +10/25/50% | Thaumaturgy 50 and 100. Modpack and assembly perks dropped for now (DRLA only) |
| Renegade | +50% pellets; instant swap; armor +50%; free shot on shell pickup | Axe 25, 50, 75 alternative. Armor bonus dropped (Daggerfall armor, section 8) |
| Demolitionist | Immune to own splash; half ammo on multi-ammo weapons; explodes when armor breaks | Blunt 25 and 75; Destruction 25. Armor-break bombs dropped |
| Commando | Melee +100%; berserk; 10% resist all | Hand-to-Hand scaling and 50. Resist is armor's job |
| Sniper* | Scope charge to 4x; single-shot rifles +100% and perfect | Archery option A |
| Saboteur* | Melee strips resistance; stronger explosions | Hand-to-Hand 100 alternative |
| Cyborg* | 200 base HP, no armor | Dropped (HP is Daggerfall's) |
| Medic* | Double healing; overflow pool | Medical 50 |
| Scientist* | Chemical beakers; poison melee | Dropped |
| Executive* | Bodyguards; datadisks | Etiquette 100 alternative (ally) |
| Mechanoid | Damage per installed modpack | Dropped (DRLA only) |
| Nomad | Luck per level; inventory wiped | Dropped (object permanence) |
| Nano Maniac | Melee regenerates ammo; weapons rerolled | Hand-to-Hand 75 |
| Phase Sisters | Two characters | Dropped |
| Sarge | Shoulder rocket weapon; stomp prevents resurrection | Blunt 100 alternative; Mysticism 25 |
| Trespasser | Pistol rounds pierce in a cone; smoke on melee kill | Short Blade 75; Hand-to-Hand 75 alternative |
| Bunker | Chaingun shield; bouncing rockets | Long Blade 100 alternative; Blunt 75 alternative |

\* unfinished, disabled in DRLA's own class list.

## 5. Melee skills

Daggerfall melee skills and their weapons:

| Skill | Weapons |
|---|---|
| Short Blade | Dagger, Tanto, Shortsword, Wakazashi |
| Long Blade | Broadsword, Saber, Longsword, Katana, Claymore, Dai-Katana |
| Axe | Battle Axe, War Axe |
| Blunt Weapon | Staff, Mace, Flail, Warhammer |
| Hand-to-Hand | Unarmed |
| (Archery) | Short Bow, Long Bow |

Decided: Hand-to-Hand governs Doom melee damage, for now (owner, 2026-11-25). Doom has few melee weapons: stock Fist
and Chainsaw; DRLA adds 4 chainsaw variants.

Still open: what the other four do.

| Option | What | For | Against |
|---|---|---|---|
| **M1 (lean)** | The four blade and blunt skills become gun categories (section 2) | Uses five skills that lost their items; no new skills | Familiar names, new meanings (display names help) |
| M2 | Keep them as melee, if Daggerfall melee weapons become real Doom melee weapons | Faithful | Needs new Doom weapons, and guns then need homes elsewhere in the 35 |
| M3 | Hand-to-Hand for fists, one blade skill for chainsaws and future melee, the rest guns | Some melee variety | One skill spent on a thin weapon pool |

Open dependency: how Daggerfall weapon items convert to Doom guns is not documented in `gamedesign.md` beyond
"drops translate into DRLX weapons". If a sword converts to a specific gun family, the skill mapping should follow
the same lines.

## 6. Language skills (not Streetwise or Etiquette)

Current design: "probably on the way out for now" (owner, 2026-11-24; `work/backlog/revisit-languages.md`). In
Daggerfall each pacifies a monster group on first sight (`FormulaHelper.GetEnemyEntityLanguageSkill`). With Doom
packs replacing those monsters the skills have no targets, and pacifying a slaughter pack would undercut the game.

| Option | Idea | Notes |
|---|---|---|
| **L1 (current lean)** | Hide them; no effect | Cheapest; matches the owner's note. But the perk rule then leaves 8 skills with no perks |
| L2 Faction lore | Each language is knowledge of one Doom monster family, with perks per the template in section 3 | Example: Impish = imps and small demons; Daedric = hell nobles and barons; Giantish = mancubi, cyberdemons; Dragonish = cacodemons and flyers; Harpy = lost souls, pain elementals; Orcish = former humans; Centaurian = arachnotrons, spider masterminds; Spriggan and Nymph = DRLA or Colourful Hell variants |
| L3 Intimidation only | High skill makes a pack's stragglers flee when its leader dies | Fits boss-and-escort encounters |
| L4 Merge | Fold all languages into one "Demonology" skill and hide the rest | One useful skill instead of eight weak ones |

## 7. New Game: no DRLA class

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
- Daggerfall's class (preset or custom) is the only class: its skill levels flow to Doom through the existing sheet,
  and so its perks follow from its skills.
- Risk to check: DRLA ACS may assume a known class token. Needs one probe run before relying on it.

Still for the owner (not decided): the starting kit. Lean: the gun of the character's highest weapon skill, plus
fists and a pistol. Daggerfall class specials (Adrenaline Rush, Athleticism, Regenerate Health, weapon Expertise)
need Doom meanings later; Expertise could count as +10 skill for perk thresholds in that category.

## 8. Armor: Daggerfall's mitigation as damage reduction

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

## 9. Questions for the owner (each with a lean)

Skills and perks:
1. Do the perk leans in section 3 fit, skill by skill? Lean: yes as a first pass; the owner picks per skill.
2. Short Blade, Long Blade, Axe and Blunt become Pistols, Rapid-fire, Shotguns and Explosives (M1)? Lean yes, with
   Doomerfall display names.
3. Archery's role: precision rifles (A), aiming for all guns (B), or bows (C)? Lean A. Note that A does nothing
   without DRLA, so B is the stock-friendly choice.
4. Should Destruction cover energy weapons as well as destruction spells? Lean yes.
5. Do cell weapons go to Energy even when shaped like pistols or rifles? Lean yes (ammo wins).
6. Perks follow the live skill (Fortify and Drain can switch them) rather than the base skill? Lean live.
7. Continuous scaling capped around +15% per weapon skill, with Hand-to-Hand's melee damage up to +60%? Lean yes.
8. Fall damage below Jumping 75: linear to 50% reduction, with the safe height raised by the extra jump height? Lean
   yes.
9. Languages: hidden (L1, no perks) or faction lore (L2, perks per the template)? Lean L1 now, L2 when revisited.
10. Social perks: should hostile humans parley and yield (Etiquette, Streetwise)? Lean yes, built later.
11. Magic school perks before spells exist, as in section 3, or wait for spells? Lean: use them now, revisit with
    spells.
12. Starting kit after New Game: the highest weapon skill's gun plus fists and pistol? Lean yes.

Armor:
13. Armor curve: hyperbolic K=80 (H), H100, or depth-aware (D)? Lean H, revisit with the HP formula.
14. One weighted average, not per hit location? Lean yes.
15. Full vs physical, half vs fire, plasma and splash, none vs environment and poison? Lean yes.
16. Total armor cap 75%? Lean yes.
17. Dodging adds Dodging/4 armor points? Lean yes.

## Suspected oversights

- `DoomerfallHp.cs` applies Doom hits with "no armor or scaling yet", while Doom's own stock armor is used up on
  pickup. Until section 8 lands, Daggerfall armor has no effect at all in bridged play. Expected, but worth keeping
  in mind when judging difficulty in play tests. Confidence high.
