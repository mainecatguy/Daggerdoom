# Area loot variety: design proposal

**Status: proposal for the owner. Nothing here is approved or implemented.** It is a design note. No code was written and no simulation was run. Item names come from the extracted mod files in `GameMods/ExtractedData/`. Statements about Daggerfall's loot code come from reading `LootTables.cs`.

## Owner feedback (2026-11-23)

These decisions override anything below that conflicts with them.

- **No per-save reshuffle.** Loot genomes, encounter theming, and loot drops come from fixed seeds. The same dungeon is the same kind of place in every game and for every player. This answers decision 7. See "Fixed seeds, not per-save randomness" in `gamedesign.md`.
- Loot and encounter theming use **separate seed definitions.** Section 7's "follow the encounter decision" therefore means: both genomes are fixed, each from its own seed.
- Optional random-per-save checkboxes are in the backlog as "Random or deterministic options."
- The overworld uses fixed seeds based on region. That makes the regional layer in decision 4 the natural home for wilderness loot.
- Daggerfall's random loot rolls get a fixed loot seed now. That work is in `work/todo.md` as "Fixed loot seeds for Daggerfall's random loot."

## 1. Recommendation

**Yes, give each area a fixed loot identity. Make it lighter and simpler than the encounter genome, and loosely tie it to the army.**

1. **Each dungeon gets a small loot genome of 6 genes.** It is built the same way as the encounter genome, from the dungeon's identity, but with its own salt so the two genomes are independent. It needs no saved data.
2. **The genome only changes *which kind* of item drops. It never changes *how good* it is or *how much* drops.** The order of rolls makes this automatic:
   - Daggerfall's loot table decides how many items drop and in which category.
   - The approved material tier roll decides the tier.
   - The genome then reweights the choice among the items allowed for that category and tier.

   The tier is decided before the genome has any say, so the tier odds come out exactly as approved.
3. **Drops vary moderately between places.** In a typical area, about 6 drops in 10 follow its identity, and the rest come from the normal pool. Every kind of item stays possible everywhere, and each ammo type has a minimum share, so a player's main gun is never starved.
4. **Loot loosely echoes the army that guarded it.** A pack of shotgun Sergeants leans its loot toward shells. Demons carry no guns, so a demon army adds no echo, and loot follows the area's own genome.

**Why.**

- **It creates knowledge worth having.** "The crypt near Sentinel is shotgun country" is a fact the player can learn, plan around, and travel for. It makes picking a dungeon a real choice.
- **It produces Bayesian surprise cheaply.** The player learns the pattern, and the occasional exception cache breaks it. A plasma rifle in a shotgun dungeon is memorable because the player expected shotguns.
- **It cannot touch the approved tier rules,** because of the roll order above.
- **Loot needs fewer genes than encounters.** A player sees hundreds of monsters in a dungeon, but perhaps only 10 to 40 drops. With so few drops, a player can learn only one or two strong patterns per place. Thirteen subtle genes would be invisible.

## 2. Where the genome sits in the loot roll

Today, `LootTables.GenerateLoot` gives each dungeon type a loot table key. For example, Crypts use `K`, which is heavy on religious items. Giant Strongholds use `F`, which is 50% weapons and 50% armor. `GenerateRandomLoot` then rolls categories (`WP`, `AM`, `MI`, and the rest), halving the chance after each success.

The proposed order of rolls is:

| Step | Owner | Genome's role |
|---|---|---|
| 1. How many items, which categories, how much gold | Daggerfall's loot table, by dungeon type and enemy | **None** |
| 2. Material tier (Tin through Daedric) | Approved tier roll, by area level | **None** |
| 3. Which concrete item in that category and tier | Inventory translation (owner design, deferred) | **Reweights this choice only** |

Two layers of identity result:

- **Dungeon type (already exists):** shared by all Crypts, coarse, and predictable.
- **Loot genome (new):** unique to each dungeon, and decides the details.

**One caveat on "kind" versus "power".** Inside one tier, items can still differ in strength. An `RLPistol` is weaker than an `RLRocketLauncher`. The genome must therefore shift weight only among items the translation rule treats as equal in value. If the translation rule puts the pistol and the BFG in the same bucket, that is a translation question, not a genome question. The genome never moves an item from one bucket to another.

**Things the genome does not touch:** drop counts, gold amounts, tier odds, Daedric's own check, Daggerfall's category chances, or the size of an ammo stack.

## 3. The loot genes

Each gene uses a short circular list of levels, like the encounter genes. The lists below are starters for the owner to edit. If the encounter genome's recipe is reused unchanged, each gene needs exactly 13 levels. Repeating "Balanced" to fill them is fine for loot.

### L1 Arsenal: which weapon family is common

DRLA's weapons fall into families by ammo type and role. The table below uses the Standard, Exotic, and Superior groups:

| Family | Real DRLA items | Reserve ammo |
|---|---|---|
| Pistols | `RLPistol`, `RLCombatPistol`, `RLMarksmanPistol`, `RLHandcannon`, `RLHuntingRevolver`, `RLPP7` | Clip |
| Shotguns | `RLShotgun`, `RLCombatShotgun`, `RLDoubleShotgun`, `RLAssaultShotgun`, `RLSuperShotgun`, `RLHuntingShotgun` | Shell |
| Rapid fire | `RLBattleRifle`, `RLChaingun`, `RLUzi`, `RLMinigun`, `RLThompson`, `RLRCP90`, `RLVanguardRifle` | Clip |
| Precision | `RLMarksmanPistol`, `RLMarksmanRifle`, `RLHuntingRevolver` | Clip |
| Explosives | `RLRocketLauncher`, `RLMissileLauncher`, `RLNapalmLauncher` | RocketAmmo |
| Energy | `RLPlasmaRifle`, `RLLaserRifle`, `RLTristarBlaster`, `RLPlasmaShotgun`, `RLCombatTranslocator`, `RLBlaster` | Cell, except `RLBlaster`, which lists no reserve ammo |
| Doomsday | `RLBFG9000`, `RLNuclearBFG9000` | Cell or BFG charge |
| Melee | `RLChainsaw` | none |

**Starter levels:** Balanced · Pistol Armory · Shotgun Armory · Rapid Fire · Precision · Explosives · Energy · "Old World" (the Superior guns: `RLThompson`, `RLPP7`, and the hunting weapons) · Close Quarters (shotguns and melee) · Long Range (precision and explosives) · Ballistic (every Clip and Shell family) · Heavy (explosives and energy) · Balanced.

**What it changes:** in a Shotgun Armory, about 6 weapon drops in 10 come from the shotgun family. The other 4 come from the normal pool for that tier.

Unique, Legendary, and Demonic DRLA weapons should be left out of family weighting at first. They are rare enough that they should feel like events wherever they appear.

### L2 Ammo stance: how ammo relates to the Arsenal

DRLA has exactly four reserve ammo classes, `Clip`, `Shell`, `RocketAmmo`, and `Cell` (`actors/misc/Ammo.txt`), which are the same four as plain Doom.

**Starter levels:**

- **Matches the Arsenal** (most levels): you find ammo for the guns that drop here.
- **Matches the army:** ammo follows what the guards were shooting.
- **Even spread:** no lean.
- **Off-hand:** ammo favors one family other than the Arsenal's, so the player keeps rotating guns.
- **Lean:** the Arsenal's ammo appears at its minimum share. The place is full of guns and short on their ammo. Use rarely.

**Hard floor:** every ammo class keeps at least 10% of ammo drops in every area. Ammo tiers (Tin through Daedric) are rolled as approved and are never touched.

### L3 Focus: how strongly the area sticks to its identity

This gene uses the accepted **U-shaped distribution**. Most areas are either lightly flavored, with about 30% of drops on-theme, or strongly specialized, with about 85%. Few areas sit in the lukewarm middle. Both ends teach the player something: "anything goes here" or "this place is all rockets."

**What it changes:** the on-theme share for L1, L2, L4, and L5.

### L4 Mod packs

DRLA's mod pack items include `RLPowerModItem`, `RLBulkModItem`, `RLAgilityModItem`, `RLTechnicalModItem`, `RLSniperModItem`, `RLFirestormModItem`, `RLNanoModItem`, `RLOnyxModItem`, and `RLArtiModItem`.

- The **basic** mods are Power, Bulk, Agility, and Technical. The genome reweights only among these.
- The **exotic** mods are Sniper, Firestorm, and Nano. They have their own bucket and are reweighted only among themselves.
- Onyx and Arti stay outside the genome.

**Starter levels:** Balanced · Power · Bulk · Agility · Technical · Power plus Bulk · Agility plus Technical · Sniper lean · Firestorm lean · Nano lean · and so on.

**What it changes:** a Bulk dungeon lets the player bulk up one favorite gun over a few visits. That is a reason to return to a place.

### L5 Kit: which consumables are common

The Daggerfall category that produces Doom consumables is part of the deferred translation design. Whatever it is, this gene reweights within it:

| Level | Real items it favors |
|---|---|
| Medic | `RLStimpack`, `RLMedikit` |
| Escape | `RLPhaseDevice`, `RLHomingPhaseDevice`, `RLRecallPhaseDevice`, `DRLAX_SmokeBomb` |
| Scout | `RLInfrared`, `DRLAX_RadarDevice`, computer maps |
| Brawler | `RLBerserk` |
| Hazard | `RLRadSuit` |
| Hunter | `DRLAX_SoulTrap`, `DRLAX_NanoTape` |
| Balanced | no lean |

Spheres such as `RLSoulsphere`, `RLMegasphere`, and `RLInvulnerabilitySphere` should stay outside the genome, like the unique weapons.

### L6 Exception: how the area breaks its own pattern

This gene is the main source of surprise. It decides how a dungeon breaks its theme, using the same Keep, Twist, Invert, and Break idea as the encounter proposal. Odds are lower than for encounters, because there are fewer drops.

**Starter levels:**

- **None.**
- **One odd cache:** a single pile in the whole dungeon uses a far-away family.
- **Deep break:** the deepest section uses the opposite family.
- **Inverted wing:** one section flips the theme.
- **Last pile breaks theme.**
- **Mirror:** the Arsenal and Ammo leans swap for one section.

**Example:** in a Shotgun Armory with "One odd cache," exactly one pile holds an `RLPlasmaRifle` and cells.

### A seventh gene to keep for later: armor style

What DRLA armor does is still undecided ("What DRLA armor does" in the backlog). If DRLA armor gets a role, a gene can reweight among its families. Until then, Daggerfall armor drops are untouched:

- Ballistic: `RLBallisticVestArmor`, `RLBulletProofVestArmor`, `RLBallisticShieldArmor`
- Energy: `RLEnergyShieldArmor`, `RLEnergyShieldedVestArmor`, `RLPlasmaShieldArmor`
- Medical: `RLMedicalArmor`, `RLSurvivalMediArmor`
- Mobility: `RLDuelistArmor`, `RLPhaseshiftArmor`
- Heavy: `RLCyberwarriorArmor`, `RLGothicArmor`

## 4. Reuse inside a dungeon: cache recipes

Daggerfall's treasure piles have fixed places in each dungeon block. Each pile can pick a **cache recipe**, a small fixed combination, using the accepted **Pitman-Yor style reuse**. For example:

- "Shells and a stimpack"
- "Rockets only"
- "A weapon and its ammo"

A new pile usually reuses a recipe already seen in this dungeon, more often the more common it is. Now and then it invents a new one. The player soon recognizes "the usual crate" here, and new kinds keep trickling in. The recipe only chooses the kinds. Each item's tier is still rolled as approved.

## 5. How loot relates to the army

| Option | Result | Verdict |
|---|---|---|
| Independent | Most variety, but no link the player can learn between enemies and loot | Rejected |
| Army decides loot | Very coherent, but loot becomes a copy of the encounter genome. A demon or Lost Soul army has nothing sensible to drop. | Rejected |
| **Loose echo per pack** | **The pack whose death produced the loot adds a small lean toward what it carried** | **Recommended** |

When an encounter's corpse is looted, its loot roll gets a small extra lean from that pack's own mooks. The pack is deterministic, so the echo is too. It reads the planned pack, not which mooks the player killed or how. The echo map comes straight from the DRLA monster names:

| Mook | Echo |
|---|---|
| `RLFormerHumanPistol`, `RLEliteHumanCombatPistol` | Pistols and Clip |
| `RLFormerSergeantShotgun`, `RLEliteSergeantDoubleShotgun` | Shotguns and Shell |
| `RLFormerCommandoChaingun`, `RLEliteCommandoMinigun` | Rapid fire and Clip |
| `RLFormerCaptainPlasmaRifle`, `RLEliteCaptainTristarBlaster` | Energy and Cell |
| Mancubi, `RLRevenant`, `RLCyberneticRevenant` | RocketAmmo |
| Technophobia column (Cybernetic monsters) | Cell |
| Demons, Imps, Lost Souls, Barons, and other monsters without guns | No echo |

**Suggested strength:** about 2 drops in 10 from the echo, taken from the normal pool's share. The area's own identity is unchanged. The result reads naturally: a Grunt Army dungeon drops guns, like Former Humans always have, and a Hell Nobility dungeon drops whatever the place itself favors.

## 6. Plain Doom

Without DRLA, the genome collapses gracefully:

- **L1 Arsenal:** the stock weapons form 5 families. These are bullets (`Pistol`, `Chaingun`), shells (`Shotgun`, `SuperShotgun`), rockets (`RocketLauncher`), cells (`PlasmaRifle`, `BFG9000`), and melee (`Chainsaw`). Each DRLA level falls back to its nearest stock family.
- **L2 Ammo:** works unchanged, because the four ammo classes are the same.
- **L3 Focus and L6 Exception:** unchanged.
- **L5 Kit:** uses the stock items `Stimpack`, `Medikit`, `Berserk`, `Blursphere`, `RadSuit`, `Infrared`, and `Allmap`.
- **L4 Mods** and armor style are dormant.

Everything stays deterministic.

## 7. Rules check

- **Tier rules:** the tier is rolled before the genome speaks, and the genome cannot read or change it. All three approved rules therefore hold exactly: monotonic improvement with level, lower tiers more common, and Daedric only by its own check. A cheap offline test can confirm it: roll many drops with and without the genome and compare the tier counts.
- **No player scaling:** the inputs are only the area's identity, its area level, the planned encounter, and a fixed salt. The genome never looks at what the player carries, their class, or what they have found before.
  - **Existing problem:** `GenerateRandomLoot` uses `playerEntity.Level` for gold and for the weapon and armor rolls. That belongs to the existing backlog item "Area level replaces player level."
  - Armor still fits the player's gender and race. That is fit, not scaling, so this proposal leaves it alone.
- **Determinism:**
  - The seed is the area's identity, a "loot" salt, and the pile or encounter index.
  - **Existing problem:** `GenerateRandomLoot` reseeds with `Random.InitState(items.GetHashCode())`. That is the hash code of a fresh list object, which is not a fixed seed.
  - Once Daggerfall rolls and saves loot, it stays as rolled. The genome matters only at roll time.
  - A per-save reshuffle should follow whatever the owner decides for encounters (encounter decision 2).

## 8. Worked examples

Each tier below comes from the approved roll and is shown only to make the example concrete. Which items are in a tier's pool is placeholder until inventory translation is designed.

**A. Level 8 Human Stronghold.** Arsenal: Shotgun Armory. Focus: strong. Ammo: Matches. Mods: Bulk. Exception: Deep break. Army: Grunt Army.

- A weapon drop rolls Steel. Most of the time it is `RLShotgun`, `RLCombatShotgun`, or `RLDoubleShotgun`. Sometimes it is something else from the Steel pool, such as an `RLBattleRifle`.
- Ammo is mostly Shell, but every class still appears at least 10% of the time.
- A Sergeant pack's corpse leans further toward shells. A Commando pack leans toward Clip.
- In the deepest block, the theme inverts. The caches there hold an `RLPlasmaRifle` and cells.
- Mod packs are mostly `RLBulkModItem`.

**B. Level 22 Laboratory.** Arsenal: Energy. Focus: strong. Ammo: Matches. Kit: Escape. Mods: Nano lean. Army: Machine Legion.

- Weapons skew to `RLLaserRifle`, `RLTristarBlaster`, and `RLPlasmaShotgun` within whatever bucket the tier roll allows.
- The Cybernetic army's echo also points to Cell, so this is a strongly cell-rich place.
- Consumables favor `RLPhaseDevice` and `DRLAX_SmokeBomb`.

**C. "Oops All Imp" dungeon, level 12.** Arsenal: Explosives. Focus: light. Army: all `RLImp`.

- Imps add no echo.
- Loot leans gently toward `RLRocketLauncher`, `RLMissileLauncher`, and RocketAmmo, with lots of variety. This shows that loot has its own identity even when the army is strange.

**D. The same stronghold as A, without DRLA.** Mostly `Shotgun` and `SuperShotgun`, mostly `Shell`, and a `PlasmaRifle` cache in the deepest block.

## 9. Rejected

- **Genomes that change tier odds,** such as a "rich dungeon" multiplier. This breaks the approved rules.
- **Genomes that change drop counts or gold.** Quantity is Daggerfall's economy. A later gene that clumps loot into fewer, bigger piles while keeping the total the same is possible, but not first.
- **Smart loot,** which biases drops toward the player's guns or class. This is scaling to the player.
- **"Pity timers" that guarantee ammo after a dry spell.** They depend on the player's history. Fixed floors do the same job without it.
- **DRLA's own spawners,** such as `RLStandardWeaponSpawner` and `RLClipSpawner`. They are `RandomSpawner`s and not deterministic, as the encounter proposal also found.
- **Hard bans,** where an area can never drop X. These risk starving a gun. Use leans and floors instead.
- **Thirteen full genes and a per-room cascade.** There are too few drops per dungeon for the player to notice.
- **Loot fully controlled by the army,** and **fully independent loot.** See section 5.

## 10. Smallest first version

This can only be built after inventory translation has a rule for at least one weapon and the ammo system exists. Both are in the backlog.

1. A loot genome function that reuses the encounter genome's recipe with a "loot" salt. It computes all genes but uses only **L1 Arsenal** and **L2 Ammo**, with a single fixed Focus of 60% and 10% ammo floors.
2. A hook in the translation step, after the tier roll, seeded from the area, the salt, and the pile or corpse index.
3. The plain-Doom fallback with 5 families and 4 ammo classes.
4. An offline check script that rolls 10,000 drops for 20 dungeons. It prints family shares, which should show clear identities, and tier shares, which must match the approved table with and without the genome.

The echo, exceptions, cache recipes, Kit, and Mods can be added one at a time after that.

## 11. Decisions for the owner

1. **Should areas have loot identities at all?** Claude recommends yes, in this lighter form.
2. **How strong should identities be?** Claude recommends the U-shaped Focus, from about 30% to 85% on-theme, with 10% ammo floors.
3. **Should loot echo the army?** Claude recommends a light echo of about 20% from the pack that died, with no echo for monsters without guns.
4. **Which areas get genomes?** Claude recommends dungeons first. Options for later are a weak regional lean ("Sentinel is rocket country") for wilderness encounters, and towns and shops.
5. **Should dungeon type lean the genome,** for example Laboratories toward Energy? Claude recommends no for the first version, because Daggerfall's loot table keys already give each type an identity.
6. **Should DRLA monsters' own drops exist on Daggerfall maps?** About 21 DRLA Monsters states call `A_DropItem("Clip")`. Those drops are rolled by Doom, are outside Daggerfall's saves, and use random spawners. Options are to suppress them, keep them as unsaved ammo scraps, or replace them with the echo.
7. **Should each new game reshuffle loot genomes?** Claude recommends following the encounter decision, so both genomes reshuffle together or neither does.
