# Encounter variety: armies, genomes, and points

**Status: design proposal, revised after owner feedback on 2026-11-23. Nothing is implemented.**

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
- The system must **stay simple and stay out of the way of the rest of the code.**

---

## 3. How a dungeon gets its monsters

1. **Read the genome.** The dungeon's identity gives 10 settings, called genes (section 4).
2. **Build the army.** Pick an anchor monster, then add monsters that resemble it, as tightly as the coherence gene says (section 5).
3. **Set the budget.** Area level gives the dungeon's total points. The genome splits them unevenly across rooms, so some rooms are empty and some are catastrophic (section 6).
4. **Fill each placement.** Daggerfall's enemy placements become squads drawn from the army. Common squads recur and new ones keep trickling in (section 7).
5. **Name each mook.** Every mook's ID is its placement plus its number in the squad, so the same dungeon always produces the same mooks. Only deaths are saved.

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
| **Budget texture** | How unevenly points spread across rooms | Even ↔ empty halls and one catastrophe |
| **Squad novelty** | How often rooms invent new squads instead of reusing old ones | Disciplined ↔ constantly new |
| **Exceptions** | How often and how hard a room breaks the army's pattern | Never ↔ often |

**Guarantee from the appendix:** any two of Daggerfall's 4,232 dungeons differ in at least 7 of these 10 genes. Every combination of any 3 settings, such as "Civil War + lone titan + all asleep," appears somewhere in the world.

**Dropped from the first draft** because they were not concrete enough: signposting, fake clues, "theme shown only at depth," and generic mutators. Colourful Hell's elite colours already cover the "titan" idea with real monsters.

---

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

Some monsters are fun alone and miserable in bulk. Each annoying class gets a maximum share of an army's points and can never be its anchor or core. The owner owns this list. Suggested starting members:

- `RLCyberneticLostSoul` and `RLTechnophobiaHellmine` (Hell Mines)
- `RLArmageddonLostSoul` (The Hungry)
- Pain Elemental variants, for their skull spam
- Arch-viles, while revives stay invisible to Daggerfall

### 5.4 Civil War

When the factions gene calls for it, a **second army** is built from the next seed, with its own anchor. The two must differ visibly, by kind or by at least two tiers, so the fight reads as a war rather than chaos. The budget is split between them. Each side's attitude to the player comes from the factions gene: hunt everyone, ignore you until shot, or ignore you entirely. When one side is wiped out, the survivors turn on the player.

Rigging factions needs no engine change (appendix B).

---

## 6. The budget

1. **Area level → dungeon points.** The exact formula is the owner's to set. A suggested shape is points that grow steadily with area level, so deeper regions always field more.
2. **Dungeon → rooms.** The budget texture gene splits the points. At one extreme, every room gets a similar share. At the other, most rooms get almost nothing and one or two get almost everything. The total never changes.
3. **Room → monsters.** The size gene picks where on the "many weak versus few strong" scale this army sits. A U-shaped curve makes the extremes common and the middle rarer:

| Size setting | What 300 points buys (equally dangerous in an open fight) |
|---|---|
| Swarm end | 300 Former Humans |
| Middle | About 29 Barons |
| Titan end | About 6 Cyberdemons |

Single monsters are capped below a share of the room budget, so a low-level area cannot spend everything on one far-too-strong monster. The owner sets the cap.

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

| Tier | Colourful Hell | DRLA | Point multiplier |
|---:|---|---|---:|
| 1 | Common | Standard | ×1 |
| 2 | Green | | ×1.25 |
| 3 | Blue | | ×1.5 |
| 4 | Purple, Cyan | Nightmare | ×1.75 |
| 5 | Brown, Fire-Blue, Yellow, Gray | | ×2.25 |
| 6 | Red | Technophobia | ×2.75 |
| 7 | Abyss | Armageddon | ×4 |
| 8 | EX titans | Bosses and wildcards | own value |

The multipliers are the health ratios, rounded slightly up. They assume a colour's damage rises roughly as much as its health. An automated attempt to read Colourful Hell's damage failed, because its elite attacks use multi-hit beams and repeated explosions, so this assumption is unchecked.

### 8.3 The points rule: Lanchester's square law

**Why simple sums fail.** While the player kills a group, every monster still alive keeps dealing damage. The number of attackers and the fight's length both grow with group size, so the damage the player takes grows with the **square** of the group's size. This is Lanchester's square law for ranged combat. Adding up health would make 8 Barons look as dangerous as 300 Former Humans, when the swarm is far deadlier.

**The rule (owner-approved approach, 2026-11-23):**

> **Monster points = √(health × damage it lands per second)**, normalized so a Former Human is 1. Squad points then add up normally.

With this scoring, two squads with equal points are about equally dangerous in an open fight, whatever their sizes. The damage a player takes from a squad is roughly **(squad points)² ÷ (2 × the player's damage per second)**.

**Damage landed per second** = damage per attack × the share of attacks that hit ÷ (attack time + about 1 second between attacks). The hit shares assume a decent player:

- Revenant homing missiles: 50% hit (owner).
- Baron and Hell Knight fireballs: 20% hit, so 80% dodged (owner).
- Imp and Cacodemon fireballs: 20% hit (assumed, slow projectiles).
- Hitscan: 30–40% hit at typical ranges (assumed).
- Melee: hits only while in reach, assumed 30–35%.
- Continuous firers, the Chaingunner, Arachnotron, and Mastermind: firing about half the time, since the player breaks line of sight.

**Results for the 17 stock Doom monsters, from Doom's own attack values.** These are estimates and have not been measured in play:

| Monster | Health | Damage landed/s | Points |
|---|---:|---:|---:|
| Former Human | 20 | 2.1 | **1.0** |
| Imp | 60 | 1.7 | **1.6** |
| Sergeant | 30 | 5.1 | **1.9** |
| Lost Soul | 100 | 2.2 | **2.3** |
| Demon | 150 | 3.9 | **3.8** |
| Spectre | 150 | 4.6 | **4.1** |
| Commando | 70 | 11.8 | **4.5** |
| Cacodemon | 400 | 3.2 | **5.5** |
| Pain Elemental | 400 | about 4 from its skulls | **6.2** |
| Hell Knight | 500 | 4.3 | **7.2** |
| Revenant | 300 | 12 | **9.3** |
| Mancubus | 600 | 6.5 | **9.7** |
| Baron | 1,000 | 4.3 | **10.2** |
| Arachnotron | 500 | 12.3 | **12.2** |
| Arch-vile | 700 | 18 | **17.4** |
| Mastermind | 3,000 | 29.5 | **46** |
| Cyberdemon | 4,000 | 26 | **50** |

**Check against the owner's example:** 300 Former Humans score 300. 8 Barons score about 82. By the square law, the swarm is about (300 ÷ 82)² ≈ **13 times** as dangerous. About 29 Barons would match it.

**Tiers.** A colour or family multiplier applies to points. If a colour multiplies both health and damage by `r`, its points rise by exactly `r`, which is why the ladder in 8.2 uses the health ratio.

**DRLA families,** whose danger comes from abilities, start at ×1.75 for Nightmare, ×2.75 for Technophobia, and ×4 for Armageddon, as in 8.2. These are guesses until measured.

**EX titans: a special case.** Colourful Hell's Black and White EX monsters have 8,600 to 18,000 health. The owner reports they are extremely dangerous, which fits their speed (19 to 31, against stock 8 to 12) and their heavy beam and explosion attacks. A placeholder of 80 to 150 damage landed per second gives **about 140 to 250 points each**, or 3 to 5 Cyberdemons. The square law also predicts what makes them terrifying. A lone monster deals damage for its whole life, so a decent player at about 50 damage per second would take about 16,000 damage killing one in the open. Fighting one needs cover, or very strong weapons.

### 8.4 Limits of the square law

- **The absolute numbers are too high.** The formula assumes every monster can shoot the player the whole time. In real Doom, corridors, doors, cover, and monsters blocking each other limit how many attack at once, which pushes danger toward a simple sum. Use the formula to **rank and price** monsters, not to predict exact damage.
- **Splash weapons** kill crowds faster than single targets, which also weakens swarms.
- **Budgets must allow for this.** Because danger grows with the square of points, doubling a room's points makes it about four times as dangerous. The area-level budget formula should grow more slowly than the difficulty it aims for.
- **Measure later.** An automated arena test that pits each monster against a scripted test player could replace every estimate in this section with a measurement.

### 8.5 Colourful Hell notes

- **Spawn the real classes directly.** Each colour has a stub, such as `BrownImp`, that consults Colourful Hell's settings and spawns the real monster, `BrownImp2`, or rerolls through the colour spawner. The genome must spawn the real class, such as `BrownImp2`, or it would lose determinism.
- **Colourful Hell monsters drop items,** including health, armor, ammo, and weapons such as `CH_Chainsaw`. That competes with Daggerfall's loot rules. The mod has settings to turn drops off (`CH_HealthDrops`, `CH_AmmoDrops`, `CH_ExtraDrops`, `CH_BackPackDrops`). This is a question for the loot session and the compatibility patch.

---

## 9. Staying simple and out of the way

The encounter generator should be **one self-contained piece** with a narrow interface:

- **Input:** dungeon identity, area level, and the list of Daggerfall placements.
- **Output:** for each placement, a list of (monster class, mook ID).
- **Data:** two small tables, base points and tier multipliers, plus the monster pool's tags, all in one data file.

Nothing else needs to know about genes. The spawner places the classes, Daggerfall saves dead mook IDs, and factions are applied at spawn time. Removing or replacing the generator would touch only that seam.

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
4. Budget: dungeon → room → monsters, using the U-shaped size curve.
5. Pitman-Yor squads.
6. Civil War as two armies, in one stance only at first.
7. Tests: the same dungeon always yields the same mooks, Civil War with 100 against 100, a save and reload mid-war, and a performance check at slaughter scale.

---

## 12. Decisions for the owner

1. **The area-level budget formula:** how many points a dungeon gets at each area level.
2. **The single-monster cap:** how large a share of a room one monster may take.
3. **The annoying list:** which classes are capped, and how hard.
4. **The point tables:** accept the starting values in section 8, or adjust them.
5. **Per-save variety:** should each new game reshuffle which dungeon gets which genome, or should every dungeon be the same in every playthrough?
6. **How common Civil War is:** a suggested starting point is about half of dungeons.
7. **Colourful Hell drops:** turn them off so Daggerfall owns loot, or keep some.

---

## Appendix A: the math, for the curious

**Genome.** Number the dungeons 0 to 4,231 in a fixed, shuffled order. For dungeon `i`, set `s = 0` if `i < 2197`, otherwise `1`, and `n = i mod 2197`. Split `n` into three base-13 digits `a`, `b`, `c`. Gene `j`, for `j = 0..9`, is:

```
gene[j] = (a + b*j + c*j*j + s*j*j*j) mod 13
```

- **Why neighbors differ:** two different dungeons give two different polynomials of degree 3 or less, and those can agree at no more than 3 values of `j`. So they differ in at least 7 of 10 genes.
- **Why every three-way combination appears:** among the first 2,197 dungeons, each triple of settings for any 3 genes occurs exactly once.
- **Per-save variety:** adding a fixed offset to every gene, or relabeling a gene's settings, keeps both guarantees. One save seed can choose such a transform.
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
