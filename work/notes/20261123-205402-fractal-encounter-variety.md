# Encounter variety: armies, genomes, and points

**Status: design approved by the owner on 2026-11-24. Nothing is implemented. Implementation is "Mook packs" in `work/todo.md`, with cards in `work/queue/encounters`.**

This version replaces the first draft. It is written in plain language. The math lives in the appendix, and nobody needs it to use the system.

**Evidence levels:**

- **Read:** taken from real UZDoom, DRLA, or Colourful Hell files, with a reference, but not run.
- **Proposed:** a design suggestion. Play will decide whether it is fun.

At the owner's direction, no simulations or engine tests back this report.

---

## 1. The idea in one paragraph

Every dungeon gets a fixed **genome**: a short list of settings computed from the dungeon's identity, so it is always the same and needs no saving. The genome generates the dungeon's **army**, which is mostly coherent but never a fixed "type." It also decides how big the army's monsters are, who fights whom, and how the army spreads through the rooms. Rooms reuse a few recurring **squads**, so the player learns what this place is like. Then a few rooms deliberately break that pattern. That learn-then-break rhythm is the goal: **maximum surprise, which comes from breaking expectations, not from pure randomness.**

---

## 2. Owner decisions so far

- Maximizing surprise, measured as broken expectations, is the goal. The genome approach is accepted.
- The genome generates **armies and their size**, which stay mostly coherent but vary.
- **Civil War** sides are mostly random: two independently generated armies.
- **No mine-dominated armies.** Annoying classes get a cap.
- Every part of the design must be a **concrete thing we can apply to Doom monsters.**
- **Moment-scale live events,** such as mid-fight betrayals or reinforcement waves, are a possible future item, not current scope.
- **All DRLA monsters are used, including Arch-viles.** Monsters may push the player because Doom owns movement. Arch-vile revives are invisible to Daggerfall for now, and better handling is in the backlog.
- It must **work with plain Doom**, and work best with DRLA.
- **Colourful Hell is added** alongside DRLA. A compatibility patch is being built.
- **The math stays under the hood.** Pitman-Yor squads and the U-shaped size distribution are accepted.
- The system must **stay simple and stay out of the way of the rest of the code.** It is one self-contained module, and other code relies only on its interface contract (section 9).
- **The budget is an average per encounter,** meaning each enemy Daggerfall places. The dungeon pools the averages and shares them out very unevenly. Level 30 averages 90 points (section 6).
- **Every placement holds at least one monster, no matter what.** Taking points away can never leave a placement unable to afford its cheapest monster, so every Daggerfall enemy has a kill trigger.
- **Dungeons have bosses, decided procedurally per dungeon,** with the deepest guarding treasure where possible. Bosses are strong army monsters, not Black and White titans.
- **Black and White titans are rare,** found only in some dungeons of level 20 and higher. A dungeon that has one pays for it with points from its other encounters. Dragon's Dens at area level 25 or higher always have one.
- **The leader is what counts to Daggerfall.** Each Daggerfall enemy becomes one encounter whose leader stands on Daggerfall's spawn point. Daggerfall's drops and quest completion follow the leader's death only.
- **Spawns are the same for everyone.** Two players in separate games who enter the same dungeon get the same spawns.
- **Themes and regions are leanings.** Each guarantees at least something from its leaning, and the rest varies.
- **Points that do not fit are never lost.** Monsters spread wider, get promoted, or the points move elsewhere.
- **The leader always stands on the placement's origin point,** so quest triggers never break.
- **Doom owns spawning,** deterministically. Daggerfall sends facts about the place (section 9).
- **Only Hell Mines are capped** for now. The rest of the annoying list is deferred.
- **Every dungeon is the same in every playthrough.** Per-save randomness is only the optional checkbox in "Random or deterministic options" in the backlog.
- **Civil War appears in about 35% of dungeons.**
- **Drops are out of scope.** What drops from what is a separate task.

---

## 3. How a dungeon gets its monsters

1. **Read the genome.** The dungeon's identity gives 10 settings, called genes (section 4).
2. **Build the army.** Pick an anchor monster, then add monsters that resemble it, as tightly as the coherence gene says (section 5).
3. **Set the budget.** Area level sets the average points per placement. The dungeon pools them, keeps each placement's cheapest monster safe, pays for a few bosses and sometimes a titan, then shares out the rest unevenly, by a different amount in each dungeon (section 6).
4. **Fill each placement.** Daggerfall's enemy placements become squads drawn from the army. Common squads recur and new ones keep trickling in (section 7).
5. **Name each mook.** Every mook's ID is its placement plus its number in the squad, so the same dungeon always produces the same mooks, for every player. Only deaths are saved. The leader is the one Daggerfall counts.

The player's character level is never an input anywhere.

---

## 4. The genes

Each gene has 13 settings, ordered in a ring so that neighboring settings are similar. Every gene changes something concrete about Doom monsters.

| Gene | What it changes in Doom | Range of settings |
|---|---|---|
| **Anchor** | Which monster kind the army is built around | The 17 stock Doom monster kinds, weighted |
| **Coherence** | How closely the army's other monsters must resemble the anchor | "Oops All One" ↔ wild mixed horde |
| **Tier lean** | Where the army sits on the tier ladder | Mostly standard ↔ mostly elite |
| **Size** | Many weak monsters versus few strong ones | Huge swarm ↔ lone titan, U-shaped |
| **Factions** | Who fights whom | United, Civil War with several player stances |
| **Placement** | Where squads stand | Scattered, garrisoned, chokepoints, central mass, deep end, near entrance |
| **Awareness** | Whether monsters start asleep, alert, or flagged as ambushers | All asleep ↔ all alert, with mixes |
| **Encounter swing** | How much each placement's points vary around the level's curve | Steady ↔ spiky, with rare heavy encounters |
| **Squad novelty** | How often rooms invent new squads instead of reusing old ones | Disciplined ↔ constantly new |
| **Exceptions** | How often and how hard a room breaks the army's pattern | Never ↔ often |

**Guarantee from the appendix:** any two of Daggerfall's 4,232 dungeons differ in at least 7 of these 10 genes. Every combination of any 3 settings, such as "Civil War + lone titan + all asleep," appears somewhere in the world.

**Dropped from the first draft** because they were not concrete enough: signposting, fake clues, "theme shown only at depth," and generic mutators. Colourful Hell's elite colours already cover the "titan" idea with real monsters.

---

### 4.1 Daggerfall's dungeon theme steers the genes (owner, 2026-11-23)

Every Daggerfall dungeon has a type, such as Vampire Haunt or Dragon's Den (`DFRegion.DungeonTypes`, 19 types). The type is a **leaning**: it steers genes toward its vibe without deciding them outright, and exceptions are allowed.

**Something from the leaning is guaranteed (owner, 2026-11-24).** Every dungeon includes at least one thing from its theme, such as one fitting squad or the boss, even when its genes roll an exception. The rest varies freely. The same holds for the regional leaning (section 9.2): nearby dungeons share at least one regional trait, such as a favourite monster kind, and otherwise differ.

**How it works:** the genome still produces each gene's raw setting, 0 to 12, exactly as before. The dungeon type decides what each setting **means**. For each type, about 9 of the 13 settings point to fitting choices and about 4 point anywhere. So roughly 70% of a type's dungeons follow its theme on a given gene, and the rest are deliberate exceptions. Because only the meanings change, the guarantees that dungeons differ and that combinations are covered still hold for the raw settings.

The theme mainly steers **Anchor** and the **traits** favoured when picking core monsters. It can also nudge **Placement** and **Awareness**. Suggested starting table:

| Dungeon type | Favoured monsters and traits | Other nudges |
|---|---|---|
| Crypt, Cemetery | Revenants, Arch-viles, Lost Souls | Sleepers, dead ends loaded |
| Vampire Haunt | Stealth: Spectres, Nightmare Imps, `RLStealth*` | Sleepers, darkness-friendly |
| Coven | Summoners and casters: Arch-viles, Pain Elementals | Central mass |
| Desecrated Temple | Hell nobility: Hell Knights, Barons | Garrisoned rooms |
| Dragon's Den | One huge titan: Cyberdemon, EX titans, Mancubi | Lone titan size, central mass |
| Volcanic Caves | Fire: Imps, Mancubi, Magmabus, Nightmare Arch-vile | |
| Spider Nest, Scorpion Nest | Arachnotrons, Masterminds, Deathweavers | Swarm size |
| Harpy Nest | Flyers: Cacodemons, Lost Souls, Pain Elementals, Volacubus | Vertical placement |
| Orc, Human, Barbarian, Giant Strongholds | Former Human armies, with big brutes for Giants | Chokepoints, sentries |
| Prison | Former Humans, Demons | Garrisoned, all asleep |
| Laboratory | Machines: the Technophobia family | Technophobia tier lean |
| Mine, Natural Cave | Melee rush: Demons, Spectres | Scattered |
| Ruined Castle | Mixed nobility and soldiers | |

**The table stays hand-written, in the data file (owner left it to engineering, 2026-11-24).** Building it from Daggerfall's encounter tables would still need a hand-written creature-to-Doom mapping, and those tables mix in filler creatures such as rats and bats that blur each type's vibe. Nineteen rows are easier to read and tune.

## 5. Building the army

### 5.1 The monster pool

Every spawnable monster from all loaded mods goes into one pool. Each gets a few tags read from its definition:

- **Kind:** which of the 17 stock Doom monsters it descends from, such as Imp or Baron.
- **Tier:** its place on the shared tier ladder (section 8).
- **Traits:** hitscan, projectile, melee, flies, summons, invisible or stealthy, homing, explosive.
- **Points:** its cost (section 8).
- **Annoying:** whether it is capped (section 5.3).

With only stock Doom loaded, the pool holds the 17 stock monsters, and everything still works with less variety.

### 5.2 Choosing monsters

1. **Anchor:** pick a monster of the anchor kind, near the tier lean.
2. **Core, about 75% of the army's points:** add 1 to 3 more monsters. Each pick is weighted by how much it resembles the anchor: same kind, shared traits, close tier. The coherence gene decides how strict this is.
3. **Support, about 20%:** add 1 to 3 monsters that only loosely resemble the core. They often cover something the core lacks, such as flyers in a melee army.
4. **Wildcard, about 5%:** sometimes one monster from anywhere in the pool.

At the strictest coherence, the core has one monster and there is no support or wildcard. That is **Oops All One**, and it emerges from the dial instead of being a special case. At the loosest setting, you get a strange mixed horde.

### 5.3 Caps

Some monsters are fun alone and miserable in bulk. A capped class gets a maximum share of an army's points and can never be its anchor or core. The owner owns this list, and for now it holds only the Hell Mines (owner, 2026-11-23):

- `RLCyberneticLostSoul`
- `RLTechnophobiaHellmine`

Other candidates, such as The Hungry or Pain Elementals, are deferred until play shows a problem.

### 5.4 One colour per monster kind (owner, 2026-11-23)

Avoid "colour vomit," a rainbow of Colourful Hell rarities mixed together in one army.

- When an army includes a monster kind, it picks **one colour for that kind and sticks to it**. If the army's Cacodemons are Blue, every Cacodemon in it is Blue, not a mix of Common, Green, and Blue.
- Different kinds may have different colours. An army can have Blue Cacodemons with Red Imps.
- The only other colours of that kind come from the existing variation rules, such as exception rooms, wildcards, or a Civil War side. They are a deliberate surprise, not background noise.
- **Black and White EX titans, and legendary monsters if a mod adds them, are exempt.** They appear by their normal rare rules on top of the locked colour, because they are rare and dangerous enough not to spoil the look.
- **DRLA families are not locked (owner, 2026-11-23).** DRLA's Standard, Nightmare, Technophobia, and Armageddon variants have distinct art, not recolours, so mixing them is variety rather than vomit. Each army instead rolls a **variant spread** for each kind: how many DRLA families of that kind it uses, from one up to all four. The roll is U-shaped, so armies often use one family of a kind and sometimes use all four. One map might have all four kinds of imps, and another only Nightmare Imps mixed with other monsters. The coherence gene nudges the roll: tight armies lean toward one family, and loose armies lean toward several.

### 5.5 Civil War

About **35% of dungeons** have a Civil War (owner, 2026-11-23): the factions gene maps about 5 of its 13 settings to Civil War stances and the rest to a united army. When it does, a **second army** is built from the next seed, with its own anchor. The two must differ visibly, by kind or by at least two tiers, so the fight reads as a war rather than chaos. Each placement belongs to one side, alternating by the genome, so both sides are present and the per-encounter budget is unchanged. Each side's attitude to the player comes from the factions gene: hunt everyone, ignore you until shot, or ignore you entirely. When one side is wiped out, the survivors turn on the player.

**Problem monsters are left out of Civil War armies (owner, 2026-11-24).** In a Civil War dungeon, neither army may include Arch-viles or any other monster whose abilities would break factions: summoners such as Pain Elementals, monsters that revive others or change their own TID (`MonsterBoss.txt:21`, `ArmageddonRevenant.txt:631`), and monsters that use unfiltered `A_RadiusGive`. The pool marks these, and the planner skips them when building either army. United dungeons still use them.

Rigging factions needs no engine change (appendix B).

---

## 6. The budget

Points are set **per encounter**, meaning each enemy Daggerfall places, but only as an **average** (owner, 2026-11-24). The dungeon pools every placement's average and then shares the pool out very unevenly, so the player can never guess a room's size from the last one.

### 6.1 Average points by area level

The owner's examples, priced with the points in section 8.3, with the top at 90 (owner, 2026-11-24, after the points were lowered):

| Area level | Owner's example | Average points per encounter |
|---:|---|---:|
| 0 | | 2.5 |
| 1 | 3 pistol guys, 2 shotgunners, 2 imps, or 1 pinky | 3.5 |
| 5 | 9 pistols, 5 shotgunners, 4 imps, or 3 pinkies | 9 |
| 10 | About 20 pistols | 20 |
| 20 | About 2.1 × level 10 | 42 |
| 30 | About 2.1 × level 20 | 90 |

Between anchors, points grow by the same factor each level, so level 15 gets about 29. Above level 10, each 10 levels multiply points by about 2.1. With the revised points, the owner's level 1 example now prices at 2.6 to 3.8, so 3.5 buys about 3 pistol guys or between 2 and 3 Imps. The table is data, so tuning it never touches code.

**What level 30's average buys,** all equally dangerous in an open fight: about 90 Former Humans, about 10 Barons, or about 2 Cyberdemons. Black and White titans are out of reach of one average encounter. They come from the pool (section 6.3).

### 6.2 Sharing out the pool

**Pool** = the level's average × the number of placements. It is shared out in this order, all from the dungeon's own seed:

1. **Every placement keeps one monster.** Before anything is shared out, each placement sets aside the cost of its cheapest monster: the cheapest army monster that fits there, or failing that the cheapest monster in the pool, usually a pistol Former Human. Nothing later can take that amount away, so every Daggerfall enemy has something to kill and its kill trigger always works.
2. **The bosses** get their share (section 6.4).
3. **A titan**, if this dungeon rolled one, takes its points (section 6.3).
4. **The rest is split unevenly, by a different amount in each dungeon.** Each dungeon has its own idea of a "normal" pack: some dungeons are many small packs, others a few huge ones. Most placements land near that dungeon's normal. A few get nothing beyond their one monster, and a few get 5 to 10 times the normal. The encounter swing gene sets how wild the split is, from nearly even to extreme, and the exceptions gene adds the rare extreme packs.

This is the learn-then-break rule applied to pack sizes. The player learns what a pack looks like here, and then a pack breaks it, in both directions: a lone pistol guy where a horde was expected, or a horde where a lone guard stood. Because each dungeon's "normal" differs too, the previous dungeon's lessons do not carry over.

### 6.3 Black and White titans

Colourful Hell's Black and White EX titans are among the worst enemies in the game, and they stay **rare** (owner, 2026-11-24):

- **Below area level 20, no dungeon has one.**
- **From level 20 up, only some dungeons have one:** about 1 in 5 at level 25 and about 1 in 3 at level 30. Most high-level dungeons never have one. The genome decides, so a given dungeon always has one or never does.
- **Dragon's Dens at level 25 or higher always have one,** as the dragon, at the deepest boss placement.
- **A dungeon has at most one.**

**How a dungeon pays for one.** A titan costs about 140 to 250 points, more than several ordinary encounters put together. So it takes points away from the dungeon's other encounters, which then get smaller. To keep that from emptying the rest of the dungeon, a titan may use at most 40% of the dungeon's total points. A small dungeon that cannot pay for one within that limit gets none, even if it rolled one.

Outside Dragon's Dens, the titan stands at a random placement that is not a boss placement, so it is its own surprise. Legendary monsters, if a mod adds them, follow the same rules.

### 6.4 Bosses

Dungeons have bosses, decided **procedurally for each dungeon** with no fixed ratio (owner, 2026-11-24). They are **not** Black and White titans.

- **How many and how strong:** each dungeon decides from its genome. One might have a single strong boss, another several minibosses, another a strong boss with minibosses along the way. Bigger dungeons tend to have more, but nothing forces a count.
- **Where:** the deepest boss stands at the placement farthest from the entrance by walking distance. If Daggerfall's dungeon has treasure, it is the far placement closest to a treasure pile, so the end of the dungeon has a boss guarding treasure. Minibosses go at other far-flung placements, preferring ones near other treasure piles, and spaced apart.
- **What:** a boss encounter takes extra points from the pool. A strong boss takes about 4 to 8 times the average and a miniboss about 2 to 4 times. Its leader is the strongest army monster that fits there, one tier up from the army's usual, with an escort from the army.
- **The treasure itself is not this module's job.** The plan names the boss placements, so the loot work can put treasure there.
- If walking distance cannot be measured, for example because the map has no entrance marker, bosses go at random spread-out placements.

### 6.5 Choosing monsters for the points

The size gene picks where on the "many weak versus few strong" scale this army sits. A U-shaped curve makes the extremes common and the middle rarer. Big encounters from the pool buy bigger monsters, so a heavy encounter in a swarm army is a bigger swarm, and in a titan army it is a bigger titan.

### 6.6 Points that do not fit

**Points are never lost (owner, 2026-11-24).** When monsters do not fit around a placement:

1. **Spread wider.** Keep searching farther out for valid spots (section 9.3).
2. **Promote.** Swap several small monsters for fewer, stronger army monsters that fit, such as a higher tier of the same kind.
3. **Move.** Give the leftover points to the nearest placement that has room.

Points are dropped only if the whole dungeon is full, which a test should report.

---

## 7. Rooms: recurring squads

A **squad** is a small recipe drawn from the army, such as "6 imps and a Baron." For each placement, the dungeon either reuses an existing squad or invents a new one. Squads used often are more likely to be reused, and the more squads exist, the more willing it is to invent another. This is the **Pitman-Yor** rule.

In a 100-room dungeon, this gives roughly 23 squad types. A handful recur constantly, a few appear several times, and many appear once. The regulars teach the player what this place is like, and the newcomers are the surprise. The squad novelty gene sets how inventive each dungeon is.

### 7.1 Surprise rooms without live events

These are all generated up front, so they are save-safe and in scope now:

- **Wrong tier:** an elite room in a standard dungeon, or the reverse.
- **Wrong army:** a squad from a different anchor entirely.
- **Lone titan:** one Colourful Hell EX titan or DRLA boss where a swarm was expected.
- **Sleeping horde:** a packed room that is entirely asleep.
- **Local war:** two squads that hate each other, in a united dungeon.
- **Empty wing:** a whole section with nothing in it.

The exceptions gene decides how often these happen and how extreme they are. Each is the **opposite** of the dungeon's pattern, which is why it lands.

---

## 8. Points and tiers

### 8.1 What Colourful Hell's data shows

Colourful Hell replaces each stock monster with colour variants. The table compares each colour's health with the stock monster's, as a median across all 17 monster kinds. **Read from `GameMods/ExtractedData/ColourfulHell_1_04/decorate/`.**

| Colour | Health vs. stock | Share of its kind's spawns |
|---|---:|---:|
| Common | 1.0× | about 30–38% |
| Green | 1.2× | about 22% |
| Blue | 1.4× | about 12% |
| Purple | 1.7× | about 5% |
| Cyan | 1.7× | about 7% |
| Brown | 2.0× | about 5% |
| Fire-Blue | 2.0× | about 3% |
| Yellow | 2.1× | about 3% |
| Gray | 2.2× | about 3% |
| Red | 2.7× | about 2% |
| Abyss | 3.8× | about 3% |
| Black and White **EX** | 22× to 418× | about 0.1% |

The EX monsters are titans, for example `BlackImpEX` at 8,600 health and `BlackFatsoEX` at 18,000. Where a monster kind has no EX version, Black and White fall back to Red.

DRLA's families raise health less steeply. Nightmare is roughly 1.3×, Technophobia about 2×, and Armageddon varies widely. DRLA's danger comes much more from abilities than from health, so its families are placed by danger, not health alone.

### 8.2 The shared tier ladder

**Higher tiers are not rarer (owner, 2026-11-24).** A tier only changes a monster's cost. Whether an army gets one depends on its points and on what its genes rolled, such as the tier lean.

| Tier | Colourful Hell | Colour multiplier | DRLA | Family multiplier |
|---:|---|---:|---|---:|
| 1 | Common | ×1 | Standard | ×1 |
| 2 | Green | ×1.25 | | |
| 3 | Blue | ×1.5 | | |
| 4 | Purple, Cyan | ×2 | Nightmare | ×1.75 |
| 5 | Brown, Fire-Blue, Yellow, Gray | ×3 | | |
| 6 | Red | ×4 | Technophobia | ×2.75 |
| 7 | Abyss | ×10 | Armageddon | ×4 |
| 8 | EX titans | own value | Bosses and wildcards | own value |

**Colour multipliers were raised (owner, 2026-11-24).** The first draft used health ratios alone, which undercounted what the elite colours add: faster projectiles, extra attacks, and more speed. Green and Blue stay, Purple and Cyan go to ×2, Red goes to ×4 at the owner's direction, and Brown, Fire-Blue, Yellow, and Gray sit between at ×3. Abyss is ×10 (owner, 2026-11-24). Abyss monsters are the step just below the EX titans, with about 3.8 times stock health and the strongest attacks of the ordinary colours. The DRLA family multipliers are unchanged until play shows otherwise. All of these live in the data file.

### 8.3 The points rule: Lanchester's square law

**Why simple sums fail.** While the player kills a group, every monster still alive keeps dealing damage. The number of attackers and the fight's length both grow with group size, so the damage the player takes grows with the **square** of the group's size. This is Lanchester's square law for ranged combat. Adding up health would make 8 Barons look as dangerous as 300 Former Humans, when the swarm is far deadlier.

**The rule (owner-approved approach, 2026-11-23):**

> **Monster points = √(health × damage it lands per second)**, normalized so a Former Human is 1. Squad points then add up normally.

With this scoring, two squads with equal points are about equally dangerous in an open fight, whatever their sizes. The damage a player takes from a squad is roughly **(squad points)² ÷ (2 × the player's damage per second)**.

**Damage landed per second** = damage per attack × the share of attacks that hit ÷ the time between attacks. The first draft overestimated it. The revised assumptions for a decent player (owner, 2026-11-24):

- **Ordinary projectiles hit 15% of the time,** so 85% are dodged. This covers fireballs, plasma, and rockets.
- **Revenant homing missiles** still hit 50% of the time (owner, 2026-11-23).
- **Monsters spend most of their time chasing, not attacking.** An Imp lands about 0.5 damage per second (owner). The time between attacks was set so the Imp matches that, and the same pacing applies to every monster.
- **Melee** monsters, including Lost Souls, Demons, and Spectres, land fewer hits than first assumed, about 60% of the first draft's rate relative to hitscan.
- **Hitscan** is unchanged relative to the Former Human.
- **Arch-viles are set to 20 points** by the owner. They are a nightmare.

**Results for the 17 stock Doom monsters.** These are estimates and have not been measured in play:

| Monster | Health | First draft | Revised points |
|---|---:|---:|---:|
| Former Human | 20 | 1.0 | **1.0** |
| Imp | 60 | 1.6 | **1.3** |
| Lost Soul | 100 | 2.3 | **1.8** |
| Sergeant | 30 | 1.9 | **1.9** |
| Demon | 150 | 3.8 | **2.9** |
| Spectre | 150 | 4.1 | **3.2** |
| Commando | 70 | 4.5 | **4.5** |
| Cacodemon | 400 | 5.5 | **4.8** |
| Pain Elemental | 400 | 6.2 | **4.8** |
| Hell Knight | 500 | 7.2 | **6.2** |
| Mancubus | 600 | 9.7 | **8.4** |
| Baron | 1,000 | 10.2 | **8.8** |
| Revenant | 300 | 9.3 | **9.0** |
| Arachnotron | 500 | 12.2 | **10.6** |
| Arch-vile | 700 | 17.4 | **20** (owner) |
| Cyberdemon | 4,000 | 50 | **43** |
| Mastermind | 3,000 | 46 | **46** |

**Check against the owner's example:** 300 Former Humans score 300. 8 Barons score about 70. By the square law, the swarm is about (300 ÷ 70)² ≈ **18 times** as dangerous. About 34 Barons would match it.

**Tiers.** A colour or family multiplier applies to points, using the ladder in 8.2. The DRLA families are guesses until measured.

**EX titans: a special case.** Colourful Hell's Black and White EX monsters have 8,600 to 18,000 health. The owner reports they are extremely dangerous, which fits their speed (19 to 31, against stock 8 to 12) and their heavy beam and explosion attacks. A placeholder of 80 to 150 damage landed per second gives **about 140 to 250 points each**, or 3 to 5 Cyberdemons. The square law also predicts what makes them terrifying. A lone monster deals damage for its whole life, so a decent player at about 50 damage per second would take about 16,000 damage killing one in the open. Fighting one needs cover, or very strong weapons.

### 8.4 Limits of the square law

- **The absolute numbers are too high.** The formula assumes every monster can shoot the player the whole time. In real Doom, corridors, doors, cover, and monsters blocking each other limit how many attack at once, which pushes danger toward a simple sum. Use the formula to **rank and price** monsters, not to predict exact damage.
- **Splash weapons** kill crowds faster than single targets, which also weakens swarms.
- **Budgets must allow for this.** Because danger grows with the square of points, doubling a room's points makes it about four times as dangerous. The area-level budget formula should grow more slowly than the difficulty it aims for.
- **Measure later.** An automated arena test that pits each monster against a scripted test player could replace every estimate in this section with a measurement.

### 8.5 Colourful Hell notes

- **Spawn the real classes directly.** Each colour has a stub, such as `BrownImp`, that consults Colourful Hell's settings and spawns the real monster, `BrownImp2`, or rerolls through the colour spawner. The genome must spawn the real class, such as `BrownImp2`, or it would lose determinism.
- **Colourful Hell monsters drop items,** including health, armor, ammo, and weapons such as `CH_Chainsaw`. That competes with Daggerfall's loot rules. The mod has settings to turn drops off (`CH_HealthDrops`, `CH_AmmoDrops`, `CH_ExtraDrops`, `CH_BackPackDrops`). Drops are out of this module's scope. Native drops stay for now, and "Review native Doom monster drops" in the backlog covers them.

---

## 9. Staying simple and out of the way

The encounter generator is **one self-contained module that runs in Doom** (owner direction, 2026-11-24). Daggerfall sends facts about the place. Doom works out the whole army and places the mooks, deterministically. Code that uses the module needs only this contract. Genes, armies, and points are private.

### 9.1 Why Doom can own it

Doom already knows what the module needs most: which monster classes are loaded, the map's geometry, how big each monster is, and walking distances. Daggerfall knows the place, the level, and what is dead. Splitting it this way keeps every input where it already lives. Daggerfall still owns permanent state: which mooks died, and quests.

What makes it work:

- **Determinism:** the module uses its own integer hash for randomness, never Doom's shared random generator or floating-point decisions. It runs once at map load, before the first tic, and handles placements in `placementId` order.
- **The genome:** Doom computes the genes itself from the dungeon index Daggerfall sends. Daggerfall never needs to know them.
- **Mook IDs** depend only on the plan, not on where monsters ended up, so Daggerfall's list of dead mooks stays valid.

The owner confirmed this split on 2026-11-24, and `architecture.md`'s encounters row now says so. One cost: ZScript is harder to unit test than C#. A command-line test hook can dump the plan to a log file for comparison.

### 9.2 Interface contract

**Daggerfall → Doom, once per area load:**

| Field | Meaning |
|---|---|
| `dungeonIndex` | Fixed index of this dungeon among Daggerfall's dungeons. It seeds the genome. |
| `locationId`, `locationName` | Daggerfall's location identity. |
| `regionIndex`, `regionName` | The region of the world. |
| `worldX`, `worldY` | Floating-point world map position, so nearby dungeons share a regional leaning: at least one shared trait, and otherwise varied. |
| `dungeonType` | Daggerfall's dungeon type, such as Vampire Haunt. It is the theme (section 4.1). |
| `areaLevel` | 0 to 30. |
| `placements` | One per Daggerfall enemy: `placementId` (fixed, such as block and record index), its position in Doom coordinates, the Daggerfall enemy type it replaces, and whether a quest uses it. |
| `deadMookIds` | Mooks Daggerfall recorded as dead. They are planned as usual but not spawned. |
| `seedOffset` | 0, the default, means fixed dungeons. Non-zero only if the optional per-save random checkbox is built. |

**Doom → Daggerfall:**

| Event | Meaning |
|---|---|
| `mookKilled` | `mookId` and `placementId`. Daggerfall records every death so dead mooks stay dead. Only the leader's death counts as the Daggerfall enemy dying, for Daggerfall's drops and quest completion. |

**Inside Doom, two parts:**

- **`EncounterPlanner.Plan(request) → plan`.** A pure function with no spawning. The plan lists factions with their stance toward the player, the boss placements, and for each placement its faction, whether it starts awake, and its monsters, each with `className` and `mookId`. The placer picks the leader (section 9.3).
- **`MookPlacer.Place(plan)`.** Spawns the plan on the map, following section 9.3. When something does not fit, it asks the planner to promote or move the points (section 6.6).

**Promises:**

- The same request with the same mods and map always gives the same plan and the same placement.
- Every placement holds at least one mook.
- Every `className` is a loaded class. With only stock Doom, the plan uses stock monsters.
- Mook IDs are unique in the area and stable.
- The total points match the pool, apart from anything reported as not fitting.

**Not the module's job:** drops and treasure, deciding when a Daggerfall enemy counts as killed for quests, and saving deaths.

**Data:** one data file holds the monster pool's tags, the points table, tier multipliers, the area level curve, the titan chances, the theme table, and the caps.

### 9.3 Placement rules for the spawning work

- **Hard requirement: the leader stands exactly on the placement's origin point,** where Daggerfall would have spawned its monster. The leader is what Daggerfall counts for its drops and quest completion, so this keeps quests and drops working and guarantees nothing important ends up out of bounds.
- **The leader is the highest-point monster in the encounter that fits at the origin** (owner, 2026-11-24). If none fits, the cheapest monster in the pool becomes the leader and stands there.
- **The rest spread out a lot.** Search outward from the origin in rings, in a fixed order, and keep going farther until every monster has a valid spot. A spot is valid when the monster fits there by Doom's own position check and it can walk from the origin without passing through walls. Spots never come from outside the walkable map.
- **The search order is fixed,** such as by ring and then by angle, so the same map always gives the same spots.
- Monsters keep a few body widths apart, so packs fill rooms and halls instead of stacking.
- Spawning happens at map load, before doors or lifts move.

This is recorded in "Mook packs" in `work/todo.md` and in card 5 of `work/queue/encounters`.

---

## 10. Surprising combinations the genome guarantees

Each is a combination of three settings, so the guarantee says it exists somewhere:

- **Oops All Imp + lone titan size:** a whole dungeon built up for one imp.
- **Civil War + ignore you until shot + all asleep:** a cold war you walk through unnoticed, until your first shot.
- **Stealthy anchor + swarm size:** hundreds of feet you can hear and cannot see.
- **Strict coherence + Abyss tier lean + chokepoints:** every doorway held by one terrifying kind of monster.
- **Melee anchor + all asleep + near entrance:** one gunshot wakes a ring of teeth.
- **Wild horde + even budget + high novelty:** no two rooms alike.
- **Standard tier lean + frequent exceptions:** an easy dungeon with one Red Cyberdemon behind a door.
- **Civil War + survivors turn on you + spiky budget:** a quiet dungeon with one enormous battle you can let finish or join.

---

## 11. Smallest first version worth building

1. The genome function, computing all 10 genes but using only Anchor, Coherence, Tier lean, Size, and Factions.
2. The monster pool with tags and points for stock Doom, DRLA, and Colourful Hell real classes.
3. Army building with core, support, wildcard, and caps.
4. Budget: the pooled average, each placement's protected cheapest monster, bosses, the uneven split, and the U-shaped size curve. Titans can come second.
5. Pitman-Yor squads.
6. Civil War as two armies, in one stance only at first.
7. Tests: the same dungeon always yields the same mooks, Civil War with 100 against 100, a save and reload mid-war, and a performance check at slaughter scale.

---

## 12. Decisions for the owner

None remain. The owner approved the design on 2026-11-24 and set the Abyss multiplier to ×10.

Quest placements getting bigger packs and high-point leaders is the backlog item "Quest packs steal points."

Answered on 2026-11-23 and 2026-11-24: per-encounter average budget with pooling, level 30 at 90, revised monster points and colour multipliers, higher tiers costing more rather than being rarer, leaders as the highest-point monster that fits, the theme table kept hand-written, one protected monster at every placement, a few bosses, titans rare outside level 25+ Dragon's Dens, themes and regions as leanings with something guaranteed, points never lost, the leader on the origin, Doom-owned spawning, Hell Mines as the only cap, fixed dungeons, Civil War in about 35% of dungeons, and drops out of scope.

---

## Appendix A: the math, for the curious

**Genome.** Number the dungeons 0 to 4,231 in a fixed, shuffled order. For dungeon `i`, set `s = 0` if `i < 2197`, otherwise `1`, and `n = i mod 2197`. Split `n` into three base-13 digits `a`, `b`, `c`. Gene `j`, for `j = 0..9`, is:

```
gene[j] = (a + b*j + c*j*j + s*j*j*j) mod 13
```

- **Why neighbors differ:** two different dungeons give two different polynomials of degree 3 or less, and those can agree at no more than 3 values of `j`. So they differ in at least 7 of 10 genes.
- **Why every three-way combination appears:** among the first 2,197 dungeons, each triple of settings for any 3 genes occurs exactly once.
- **Optional per-save variety:** dungeons are fixed by default. If the backlog's optional "random encounter theming" checkbox is built, adding a fixed offset to every gene keeps both guarantees, and one save seed can choose the offset.
- **Weighted genes:** to make some settings more likely while keeping the guarantees, map the 13 equally likely settings to slices of the desired distribution. The U-shaped size curve does this: setting `k` maps to the point `sin²(π(k + 0.5)/26)` between the smallest and largest monster cost.

**Budget split.** Each child receives a random share from a Dirichlet split, and a "spikiness" setting controls how uneven it is. For 20 rooms, spikiness settings of 0.1, 1, and 10 give about 3, 10, and 18 rooms that matter.

**Squads.** Pitman-Yor with discount 0.5 and strength 1 gives about `2.3 × √(rooms)` distinct squads, or about 23 per 100 rooms.

## Appendix B: Civil War in UZDoom

**Read from code, unrun.** For each monster:

```zscript
a.ChangeTid(FACTION_TID);
a.A_SetSpecies('FactionA');   // teammates stop hitting each other; enemies of the same kind can hit
Level.ExecuteSpecial(177 /*Thing_Hate*/, a, null, false, 0, ENEMY_TID, stance);
```

- `Thing_Hate` sets the monster's hate target, and stance 1, 3, or 5 sets its attitude to the player: retaliate if shot, hunt everyone, or ignore the player (`UZDoom/src/playsim/p_lnspec.cpp`).
- Rewriting species is needed because many DRLA projectiles pass through, and explosions spare, monsters of the shooter's species (`p_map.cpp:1564`, `p_map.cpp:6264`). Without it, a war between two imp armies partly fizzles.
- Monsters that hate the same faction act as allies (`p_interaction.cpp:1728`, `p_map.cpp:1277`), so three-way and coalition wars also work.
- When one faction is wiped out, survivors with stance 1 or 5 go idle until their hate is cleared with `Thing_Hate(0, 0, ...)`. That is the hook for "survivors turn on you."
- **Watch for:** summoned children need their parent's faction, DRLA's revived `*Reborn` monsters arrive with no faction, two DRLA actors change their own TID (`MonsterBoss.txt:21`, `ArmageddonRevenant.txt:631`), and a faction must never be told to hate its own TID.

## Appendix C: DRLA species × family grid

| Kind | Standard | Nightmare | Technophobia | Armageddon |
|---|---|---|---|---|
| Former Human | `RLFormerHumanPistol` | `RLEliteHumanCombatPistol` | `RLFormerCyborgBattleRifle` | `RLFormerAssaultTrooper` |
| Sergeant | `RLFormerSergeantShotgun` | `RLEliteSergeantDoubleShotgun` | — | `RLFormerOverwatch` |
| Commando | `RLFormerCommandoChaingun` | `RLEliteCommandoMinigun` | — | `RLFormerShocktrooper` |
| Captain | `RLFormerCaptainPlasmaRifle` | `RLEliteCaptainTristarBlaster` | — | — |
| Imp | `RLImp` | `RLNightmareImp` | `RLCyberneticImp` | `RLArmageddonImp` |
| Demon | `RLDemon` | `RLNightmareDemon` | `RLCyberneticDemon` | `RLArmageddonDemon` |
| Spectre | `RLSpectre` | `RLNightmareSpectre` | `RLCyberneticSpectre` | — |
| Lost Soul | `RLLostSoul` | `RLNightmareLostSoul` | `RLCyberneticLostSoul` | `RLArmageddonLostSoul` |
| Cacodemon | `RLCacodemon` | `RLNightmareCacodemon` | — | `RLArmageddonCacodemon` |
| Hell Knight | `RLHellKnight` | `RLNightmareHellKnight` | `RLCyberneticHellKnight` | — |
| Baron | `RLBaronOfHell` | `RLNightmareBaronOfHell` | `RLCyberneticBaronOfHell` | `RLArmageddonBaronOfHell` |
| Arachnotron | `RLArachnotron` | `RLNightmareArachnotron` | `RLCyberneticArachnotron` | `RLArmageddonArachnotron` |
| Pain Elemental | `RLPainElemental` | `RLNightmarePainElemental` | `RLCyberneticPainElemental` | `RLArmageddonPainElemental` |
| Revenant | `RLRevenant` | `RLNightmareRevenant` | `RLCyberneticRevenant` | `RLArmageddonRevenant` |
| Mancubus | `RLMancubus` | `RLNightmareMancubus` | `RLCyberneticMancubus` | `RLArmageddonMancubus` |
| Arch-vile | `RLArchvile` | `RLNightmareArchvile` | `RLCyberneticArchvile` | `RLArmageddonArchvile` |
| Cyberdemon | `RLCyberdemon` | `RLNightmareCyberdemon` | `RLCyberneticCyberdemon` | — |
| Mastermind | `RLSpiderMastermind` | `RLNightmareSpiderMastermind` | `RLCyberneticSpiderMastermind` | — |
| Wildcard | `RLBruiserBrother` | `RLAgonyElemental` | `RLTerminator` | `RLAbominant` |

Several cells have more than one class, for example other Former Human weapons. A dash means no usable class was found, and those cells fall back to the nearest family. `RLCC*` classes are the end-credits cast, `RLDRPG*` are DoomRPG summons, and `*Reborn` are revive products, so none of them are spawn candidates. The twelve `RLStealth*` classes are also in the pool, tagged as stealthy.
