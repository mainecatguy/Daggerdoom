# Game design decisions

The game designer's log. Each entry records a question, the verdict, the answer, the design text it rests on, and
the devil's-advocate challenge. The owner can overrule any entry; an overruled entry stays, marked as overruled.

Verdicts:
- **Follows clearly:** the answer falls out unambiguously and strongly from the documented design.
- **Leans:** the design points one way but does not settle it. The owner sees it before it is relied on.
- **Not determined:** the design does not answer it. It goes to the owner. This is a correct answer, not a failure.
- **Deferred:** the question has systems-architecture implications or consequences that ripple into other parts of
  the project, or it would create a new system. It goes to the owner.

---

## 2026-11-24: Do rounds emptied from a DRLA magazine on an ammo change go back to the inventory?

- **Verdict:** Follows clearly. (Answered by the owner, recorded as the first example.)
- **Answer:** Yes. They return to the inventory.
- **Rests on:** `gamedesign.md`, "In-engine object permanence": things that exist don't pop out of existence.
- **Challenge:** Returning rounds lets a player swap ammo for free. That is a balance point, not a reason for rounds
  to vanish, and nothing in the design asks for a swap cost.

## 2026-11-24: Should trapdoors exist before climbing does?

- **Verdict:** Follows clearly. (The owner's example, recorded as the second entry.)
- **Answer:** Yes. Climbing is a core Daggerfall skill and is planned, so trapdoors can go in first.
- **Rests on:** `gamedesign.md`, "Daggerfall's systems are all planned": a practical dependency on a planned
  Daggerfall system is not a reason to wait. Only a technical dependency is.
- **Challenge:** A player who falls through a trapdoor before climbing exists may be stuck. That is a practical gap
  that closes when climbing lands, not a technical dependency. Climbing has since been merged.

## 2026-11-24: When the player takes a DRLA gun they already hold, should Doom give DRLA's usual ammo? [20261123-233611]

- **Verdict:** Not determined (downgraded from Leans in challenge).
- **Answer:** None. It goes to the owner.
- **Rests on:** `gamedesign.md`, Loot & Economy: Daggerfall "decides how much drops and in which category". Object
  permanence: things don't "appear from nowhere".
- **Challenge:** AGENTS.md says "Doom may drop and place its own items", and the encounter note keeps native Doom
  drops "for now" pending a backlog review. Doom-native item behavior is tolerated until reviewed, so the loot row
  does not clearly forbid a native pickup bonus. Two documented positions pull opposite ways.

## 2026-11-24: Should Mantellan Crux get a fixed area level, and which? [20261123-233755]

- **Verdict:** Not determined.
- **Answer:** None. The area level proposal says Crux "should get an override" but gives no number.
- **Rests on:** `work/notes/20261123-225515-area-level-proposal.md`.
- **Challenge:** Could the formula's 23 just stand? Nothing says so, and choosing a number is a new value. Kept.

## 2026-11-24: Should outdoor guards be part of the next guard task? [20261123-233427]

- **Verdict:** Deferred.
- **Answer:** None. Outdoor guard bots need their own design through the treadmill registry, and the order of work is
  the owner's call.
- **Rests on:** `gamedesign.md`, Crime row: "hostile guards pursue and fight like Doom bots". Backlog
  `guard-behavior-and-pathfinding.md`: "Delayed indefinitely ... Do not raise".
- **Challenge:** The crime row clearly wants guards to be Doom bots everywhere, which argues for Follows clearly. But
  that settles only the end state, not the timing or the registry design. Kept as Deferred.

## 2026-11-24: Should killing a guard bot have crime effects, and should hostile bots block rest and travel? [20261123-233427]

- **Verdict:** Crime: Follows clearly. Rest: Leans yes. Travel: Not determined.
- **Answer:** Killing a guard should take Daggerfall's own crime and reputation effects. Hostile bots should probably
  block rest. Travel blocking waits on the owner.
- **Rests on:** `gamedesign.md`: "Daggerfall governs reputation, bounties, surrender, and court/jail" and "Resting ...
  blocked when Doom monsters are nearby". Backlog `doom-monsters-block-fast-travel.md`: "Waiting on: owner design".
- **Challenge:** The rest rule names "Doom monsters", and guard bots are bots, not monsters. But Daggerfall itself
  blocks rest for hostile guards, so the reading holds as a lean. Rest blocking needs Doom to tell Daggerfall about
  nearby enemies, but the design already implies that signal for monsters. Kept.

## 2026-11-24: Is it right to refuse DRLA armor and boots but use up stock Doom armor and bonuses? [20261124-002144]

- **Verdict:** Not determined.
- **Answer:** None. It depends on backlog `drla-armor-role.md`.
- **Rests on:** `gamedesign.md`: "Daggerfall controls damage, so Daggerfall armor is the armor that matters."
- **Challenge:** That line could support refusing all Doom armor, or allowing all of it as harmless. Neither
  follows. Kept.

## 2026-11-24: Does "no hotkeys yet" mean all five squares of the gun's number key are empty? [20261124-002144]

- **Verdict:** Leans yes.
- **Answer:** The whole key (three plain squares, Ctrl, and Alt) must be empty before a taken gun is drawn. This is what
  was merged in `bc3242e`.
- **Rests on:** the owner's rule as recorded in `work/notes/20261124-002144.md`: "A taken gun whose Doom slot key has
  no hotkeys goes on that key and is drawn".
- **Challenge:** A potion on a Ctrl square blocking a gun draw may not be what the owner pictured, and he may have
  meant the plain square. The literal text still reads as the whole key. Kept as Leans.

## 2026-11-24: Is a standing sleeper acceptable, or should sleepers lie in or beside beds? [20261124-004803]

- **Verdict:** Not determined.
- **Answer:** None. One limit holds: hiding sleepers would break object permanence ("They don't disappear").
- **Rests on:** `gamedesign.md`, "In-engine object permanence".
- **Challenge:** None stronger. This is an art and design choice. Kept.

## 2026-11-24: May time-passing services run inside Doom while Doom's monsters stay frozen? [20261124-002144]

- **Verdict:** Leans acceptable for now.
- **Answer:** Yes as interim behavior. A Daggerfall time skip does not move monsters either.
- **Rests on:** `gamedesign.md`: "The calendar ... govern the world" (Daggerfall owns time).
- **Challenge:** Resting is "blocked when Doom monsters are nearby", and a tavern room from inside Doom could bypass
  that. It also brushes the time-sync and off-window simulation questions, which the owner holds. But the services
  run in towns and buildings, the rest block applies to plain resting, and the interim behavior builds no new system.
  Kept as Leans.

## 2026-11-24: Is the pickup mix (40/30/30), the scaling for big areas, and pickups in buildings right? [20261124-002311]

- **Verdict:** Not determined.
- **Answer:** None. These are numbers and placement rules the design does not give.
- **Rests on:** no design text.
- **Challenge:** None. Kept.

## 2026-11-24: Should Daggerfall keep the list of taken pickups, the way it keeps dead monsters? [20261124-002311]

- **Verdict:** Deferred (upgraded from Leans in challenge).
- **Answer:** None. It goes to the owner.
- **Rests on:** AGENTS.md pillar: "its engine needs to be the mediator and controller of most permanent game state".
  "Shared by contract: ... loot creation. Doom may drop and place its own items."
- **Challenge:** The pillar says "most", not all, and Doom-placed items are explicitly Doom's to place. Pickups
  already persist through the bundled save. Moving the record changes which engine owns a class of saved state, which
  is a save-architecture decision in `architecture.md`'s engine ownership.

## 2026-11-24: Climbing: no rolls or slips while holding still, and Back climbs down? [20261124-002144]

- **Verdict:** Leans keep both.
- **Answer:** Keep both.
- **Rests on:** the owner's climbing design, "the player sticks to the surface" (`work/notes/20261124-002144-climb.md:47`),
  and Daggerfall's own advanced climbing mode.
- **Challenge:** Classic Daggerfall, the default mode, drops the player when forward is released, and the owner said
  nothing about Back. The owner's "sticks" covers holding still, and Back follows Daggerfall's advanced mode. Kept.

## 2026-11-24: Keep the 70-degree walkable slope on Daggerfall maps? [20261124-002144]

- **Verdict:** Leans keep (downgraded from Follows clearly in challenge).
- **Answer:** Keep 70 degrees, as in Daggerfall.
- **Rests on:** the owner's 70-degree climb threshold. Backlog index: "Match DF slope limits, climbing, and
  levitation".
- **Challenge:** The backlog detail file still says "Waiting on: owner design input after the research step" and
  "design the Doom behavior with the owner". Raising the walkable slope from 45 to 70 degrees also changes how
  traversal plays. The direction is clear, but the owner kept this for himself.

## 2026-11-24: Should Doom tell Daggerfall when the player climbs, so climbing fatigue is charged? [20261124-002144]

- **Verdict:** Follows clearly.
- **Answer:** Yes, charge Daggerfall's climbing fatigue. Exhaustion consequences follow backlog `exhaustion-rework.md`
  (owner): exhaustion "never kills them".
- **Rests on:** `gamedesign.md`: "Daggerfall's HP, attributes, armor, resistances, fatigue ... govern survival", and
  climbing is one of Daggerfall's movement abilities.
- **Challenge:** The rule could leave fatigue under-defined for a Doom-driven climb. But Daggerfall charges it, and
  "Daggerfall's systems are all planned" says to carry its systems over. Only the death part conflicts, and the owner's
  exhaustion design settles that. Kept.

## 2026-11-24: Should New Game keep, skip, or replace Daggerfall's tutorial quest? [20261124-044747]

- **Verdict:** Not determined.
- **Answer:** None. It is related to backlog `full-daggerfall-new-game-flow.md`.
- **Rests on:** no design text.
- **Challenge:** "Daggerfall's systems are all planned" argues for keeping it. But the tutorial teaches controls that
  no longer apply, so it does not settle the question. Kept.

## 2026-11-24: Should the Baron Blaster reload by itself, and may Doomerfall force DRLA's autoreload option on each launch? [20261124-072401]

- **Verdict:** Baron Blaster: Leans yes (downgraded from Follows clearly in challenge). Forcing the option on each
  launch: Not determined.
- **Answer:** The Baron Blaster probably falls under the one-shot rule. Whether to keep a player's off setting goes to
  the owner.
- **Rests on:** the card goal in `work/notes/20261124-072401.md:3`: guns whose magazine "empties from full in one shot
  ... reload by themselves".
- **Challenge:** That quote is the agent's restatement of the goal, not the owner's words. The owner named the pump
  shotgun, and an automatic 100-cell spend on a legendary gun is a real balance cost he may not have intended. The
  literal rule covers the gun, so it stays a lean.

## 2026-11-24: Should ammo touch pickups be refused when the player is over Daggerfall's weight limit? [20261124-075147]

- **Verdict:** Not determined (downgraded from Leans in challenge).
- **Answer:** None. It goes to the owner.
- **Rests on:** `gamedesign.md`: "There may be limits on how much ammo the player can carry. That is a future system."
  Also the Movement row: "modified by Daggerfall's encumbrance".
- **Challenge:** The "future system" line is about ammo-specific caps, not weight. Doom items taken with Use are
  already "checked against Daggerfall's carry limit" (CHANGELOG `e97c3c5`), so consistency argues for refusing. The
  documents point both ways.

## 2026-11-24: After a load, should Daggerfall's ammo count win over Doom's when they disagree? [20261124-075147]

- **Verdict:** Owner answered (2026-11-24).
- **Answer:** Split ownership. Doom owns the live ammo its guns spend (the loaded tier, and magazines), because it has
  the most accurate picture of it, and reports every change, losses included. Daggerfall owns all other ammo and keeps
  an exact mirror of Doom's live counts. On a normal load Doom's live count stands; if Doom's half cannot be restored,
  Daggerfall's mirror is used. `architecture.md` updated.
- **Rests on:** AGENTS.md: Daggerfall owns saves and "most permanent game state". `gamedesign.md`: "Daggerfall can
  tell Doom that the player has more than Doom's max ammo".
- **Challenge:** The merged ammo card made "Doom's ammo ... the live counter" (CHANGELOG `0699292`). The max-ammo line
  is about caps, not which engine wins a conflict. Which engine is authoritative on load is part of the save and load
  sync hurdle, a consequential architecture decision.

## 2026-11-24: Is the Letter of Credit placeholder acceptable for dropped ammo piles? [20261124-075147]

- **Verdict:** Not determined.
- **Answer:** None. This is an art choice. Using a placeholder for now is an engineering matter.
- **Rests on:** no design text.
- **Challenge:** None. Kept.

## 2026-11-24: Should piles dropped outdoors be listed in Doom and pickable there (backlog item)? [20261124-085156]

- **Verdict:** Follows clearly.
- **Answer:** Yes, outdoor piles should be reachable from Doom. File it as backlog work. How to build it is
  engineering.
- **Rests on:** `gamedesign.md`: "DFU loot should persist no matter where it is dropped if possible", and "In-engine
  object permanence".
- **Challenge:** "If possible" softens it, and outdoor actors go through the treadmill registry. But the design wants
  the result, and the on-hold off-window question covers monsters and projectiles, not items. Kept.

## 2026-11-24: What should Colourful Hell's non-EX Black and White monsters cost? [20261124-094754]

- **Verdict:** Leans.
- **Answer:** Price each one from its own section 8.3 value, as the EX titans are, rather than with a health-only
  multiplier.
- **Rests on:** `work/notes/20261123-205402-fractal-encounter-variety.md` 8.3: "Monster points = √(health × damage it
  lands per second)".
- **Challenge:** The EX values are placeholders because damage landed per second is hard to estimate, and the owner
  set some values by hand (Arch-vile at 20). The owner may want to set these too. The base rule still covers every
  monster. Kept.

## 2026-11-24: What values or rule should DRLA bosses use ("take their own values")? [20261124-094754]

- **Verdict:** Leans.
- **Answer:** Use their own section 8.3 value, not kind points × √(health ratio).
- **Rests on:** encounter note 8.2 ("own value") and 8.3 (the points rule).
- **Challenge:** "Own value" may mean values the owner will hand-assign. The 8.3 rule is the owner-approved default for
  pricing, so it stays a lean.

## 2026-11-24: What maximum share of an army's points do capped classes (Hell Mines) get? [20261124-094754]

- **Verdict:** Not determined.
- **Answer:** None. Section 5.3 gives no number. 0.10 is a placeholder.
- **Rests on:** encounter note 5.3.
- **Challenge:** None. Kept.

## 2026-11-24: Which shop types stock tiered ammo, and at what odds? [20261124-093041]

- **Verdict:** Not determined.
- **Answer:** None.
- **Rests on:** no design text gives shop types or odds.
- **Challenge:** None. Kept.

## 2026-11-24: Does Orichalcum's Orsinium abundance cover the whole region or only the city? [20261124-093041]

- **Verdict:** Not determined.
- **Answer:** None.
- **Rests on:** the ammo tiers card's phrase "sells fairly abundantly in Orsinium".
- **Challenge:** None. "Orsinium" names both the region and the city. Kept.

## 2026-11-24: Should the regional favourite monster kind be limited, and is a 90% "Oops All One" army acceptable? [20261124-100533]

- **Verdict:** Leans on both.
- **Answer:** The favourite should respect what the area level can afford. Which softer trait to use instead (a colour
  or a DRLA family) is not determined. A 90% "Oops All One" army is acceptable.
- **Rests on:** `gamedesign.md`: "Difficulty follows area level". Encounter note 4.1: a regional trait "such as a
  favourite monster kind", guaranteed "even when its genes roll an exception".
- **Challenge:** "Higher tiers are not rarer" and "leans, not bans" argue against excluding kinds. But the budget,
  which follows area level, already decides what an army can buy, so limiting to affordable kinds respects both. Kept.

## 2026-11-24: How should Covens keep their theme guarantee when Civil War bans summoners? [20261124-100533]

- **Verdict:** Not determined.
- **Answer:** None. Two owner rules collide: the theme guarantee (4.1) and the Civil War exclusion (5.5).
- **Rests on:** encounter note 4.1 and 5.5.
- **Challenge:** None. Choosing a stand-in would invent design. Kept.

## 2026-11-24: Should the loaded ammo tier belong to each gun rather than each ammo type? [20261124-101258]

- **Verdict:** Leans per gun.
- **Answer:** Per gun, as merged at `3805d1e`.
- **Rests on:** `gamedesign/damage.md`: tags clear "when the weapon changes". A DRLA magazine travels with its gun
  (`work/notes/20261124-101258.md`).
- **Challenge:** The tag line is about displaying tags, not storing the tier, and per type is simpler for the player.
  But per type would let a stored magazine fire rounds of the wrong tier. Kept.

## 2026-11-24: After an automatic tier change, should a stock gun come back up if Doom lowered it to fists? [20261124-101258]

- **Verdict:** Leans yes.
- **Answer:** Raise it again automatically.
- **Rests on:** common sense. The automatic change exists so the gun keeps firing.
- **Challenge:** No design text says so, and it may be a feel question for play-testing. Kept as a lean.

## 2026-11-24: Should the Change Ammo key have a default, and which? [20261124-101258]

- **Verdict:** Not determined.
- **Answer:** None. It is covered by backlog `sort-out-keybinds.md`.
- **Rests on:** no design text.
- **Challenge:** None. Kept.

## 2026-11-24: Does taking a gun give its ammo?

- **Verdict:** Follows clearly. (Answered by the owner.)
- **Answer:** No. Guns never give ammo, from any source, on a first take or a retake. Recorded in `gamedesign.md`,
  "Ammunition". Found by the gun ammo test (`tools/location_record/gunammo.py`): a stock Shotgun gave 8 shells on every
  take, so dropping and retaking it was infinite ammo.
- **Rests on:** the owner's answer.
- **Challenge:** None. Kept.

## 2026-11-25: Which monsters drop loot when they were not placed by Daggerfall?

- **Verdict:** Follows clearly. (Answered by the owner.)
- **Answer:** Summoned monsters (Lost Souls, summoners' minions, anything spawned during play) drop nothing on
  Daggerfall maps. A resurrected monster drops nothing on its second death, whether it comes back as itself (stock
  Arch-vile) or as a new Reborn form (DRLA Nightmare/Cybernetic Arch-vile). Dropping nothing on a reborn form is fine.
  In the rare case where a summoned monster takes a placed monster's id in the first seconds of a map, the result is
  acceptable as long as no drop is duplicated and no quest breaks.
- **Rests on:** the owner's answers (2026-11-25). Found by fixed drops card 05 (`work/notes/20261125-202715.md`).
- **Challenge:** None. Kept.

## 2026-11-25: Should DRLA's Adaptive skill variant pick be seeded from the placement id?

- **Verdict:** Deferred. **Owner decision (2026-11-25): remove DRLA's Adaptive difficulty from Doomerfall completely.**
  In the owner's words: "The world shouldn't adapt to the player, thats a game design pillar of ours."
- **Answer:** None. It goes to the owner. If the owner keeps Adaptive as DRLA built it, seeding its `Random` draws from
  the placement id leans yes, but that alone cannot make a place the same across characters.
- **Rests on:** `gamedesign.md`, Randomness: "events are fixed and not randomized per save", and the owner (2026-11-25):
  "Our randomization is always seeded deterministically." Also "The world does not scale to the player" and "Never
  adapt to the player. Randomness uses only fixed facts about the place and its area level." DRLA's
  `RLAdaptiveSpawnPicker` (`DRLAMONS_MAB.acs`, lines 43-83) starts from player 1's `RLDangerLevel` (player progress),
  forces Armageddon at danger 50 or more, and only then rolls ACS `Random`. Scope: the encounter planner spawns concrete
  classes with `NO_REPLACE` and excludes `RLAdaptive*`, so Adaptive applies only on the stock-roster fallback and on
  overworld seeds (`work/notes/20261125-220115-fixeddrops-finish.md`).
- **Challenge:** The owner's "always seeded deterministically" reads strongly, and seeding the draws is a small
  engineering change, which argues for Follows clearly on the narrow question. But the question as asked ("the same
  every time") cannot be met by seeding, because the pick depends on the player's danger level. The real fix (area
  level in place of danger, disabling Adaptive on Daggerfall maps, or exempting it as a player-chosen option) changes
  how a difficulty mode plays. Whether picking Adaptive counts as a planned "custom option" that may be random is also
  the owner's call. Kept as Deferred.

## 2026-11-25: Are DRLA's kill-counter pickups exempt from "summoned and revived monsters drop nothing"?

- **Verdict:** Leans exempt. **Overruled by the owner (2026-11-26): not exempt.** Summoned and revived kills do not
  count in the PDA bestiary; regular kills do. The owner is fine with that.
- **Answer:** Exempt `RLMonsterKillIncrementer` and its subclasses, so summoned and revived kills still count toward
  DRLA's kill stats, as in stock DRLA.
- **Rests on:** the owner's ruling "2026-11-25: Which monsters drop loot when they were not placed by Daggerfall?",
  which is framed as a loot question. `MonsterKillCounters.txt`: the counters are "USED BY THE PDA TO KEEP TRACK OF
  KILLS, AND LEARN ENEMY STATS". They are invisible `TNT1` items with no pickup message. In ExtractedData, `KillCounter`
  is referenced only by the DRLA Monsters actor files and DRLA Arsenal's `ACS_PDA.acs` and `bestiary.pdap`. DRLA's
  danger level reads the separate `RLDangerLevel` item, so the counters do not feed it.
- **Challenge:** The ruling's answer says "drop nothing", not "drop no loot", and the owner may have meant it
  literally. Exempting the counters lets a Pain Elemental's endless Lost Souls farm bestiary unlocks, but stock DRLA
  already allows that, and it gives no gear or loot. No object appears or vanishes in the world, nothing scales, and no
  Daggerfall loot rule is touched. The literal wording keeps this a lean, not Follows clearly. Kept as Leans.

## 2026-11-26: Should the level-up sound (and Daggerfall's window sounds) be heard, and should Doom add a HUD line? [20261126-003657]

- **Verdict:** Sound heard: Follows clearly. New HUD line: Not determined.
- **Answer:** Daggerfall's level-up sound and its window sounds should be heard in a bridge session. Whether Daggerfall
  plays them or Doom plays Daggerfall's sound is engineering. A "You have reached level N" line is new (Daggerfall
  Unity has none) and goes to the owner.
- **Rests on:** `gamedesign.md`, Audio row: "Daggerfall supplies music, UI sounds, and NPC barks; Doom supplies combat
  SFX." The owner's skill point card (`skillmenu` 02): "play a Daggerfall sound and show the notification message
  Daggerfall uses ... shown on Doom's screen."
- **Challenge:** The session-wide mute (`DoomerfallNewGame`) may have been a deliberate engineering choice, and Doom
  owns the window. But AGENTS.md does not give Doom sound, and the Audio row names UI sounds as Daggerfall's outright.
  Unmuting Daggerfall entirely would also bring back its music, which is a larger change; the verdict covers UI sounds
  only. Kept.

## 2026-11-26: Should Doom report skill uses to Daggerfall, and which Doom events count for which skills? [20261126-003657]

- **Verdict:** Report uses: Follows clearly. The event-to-skill mapping: Deferred.
- **Answer:** Yes, Doom play should drive Daggerfall skill uses. Already decided by the owner: Running from time spent
  running (1.5x), Backstabbing 10x faster from shooting unaware enemies, Climbing (already wired). The rest of the
  mapping and its rates belong to the Skill XP proposal awaiting owner approval.
- **Rests on:** `gamedesign.md`, Progression row: "Combat, spellcasting, and traversal drive Daggerfall's use-based skill
  leveling". `skills-in-doom.md`. `skillmenu` 01: "use-based gain at the approved reduced rates".
- **Challenge:** The owner is moving toward bought skills with Skill XP, which could make use-based gain minor. But his
  own card keeps use-based gain at reduced rates, so the direction holds; only the rates and mapping are open. Kept.

## 2026-11-26: Skill XP rate across area levels: 1 XP per HP, a per-area-level rate, or a softer start? [skillresearch 02]

- **Verdict:** Deferred.
- **Answer:** None. It goes to the owner.
- **Rests on:** `skillmenu` 01 gate: stop BLOCKED unless the owner approved the proposal. All three options respect "only
  cares about area level"; the softer start keys off the player's own skill, which is progression, not world scaling.
- **Challenge:** Option A could be called the plain reading of "XP from monsters". But it is a new progression system
  with new numbers and a large effect on pacing. Kept.

## 2026-11-26: Use-based gain rate for kill-driven skills, and does guild training stay at full rate? [skillresearch 02]

- **Verdict:** Use rates: Deferred. Guild training at full rate: Leans yes.
- **Answer:** Use rates go to the owner with the Skill XP proposal. Guild training probably stays as in Daggerfall.
- **Rests on:** `gamedesign.md`, "Daggerfall's systems are all planned". `skillbasics` 01 keeps window-based skills
  working "as in Daggerfall".
- **Challenge:** If buying is the main source of skills, full-rate paid training becomes a competing economy the owner
  may want to tune with the rest. That keeps it a lean, not Follows clearly. Kept.

## 2026-11-26: Skill purchase menu: which skills, what multiplier, where it opens, and do townspeople give Skill XP? [skillresearch 02]

- **Verdict:** Critical Strike excluded: Follows clearly. Every other skill buyable: Leans yes. Flat multiplier of 2:
  Not determined. Menu wherever the player could rest: Not determined. No Skill XP from townspeople or guards: Leans.
- **Answer:** Critical Strike and the nine removed languages cannot be bought. The rest probably can. The multiplier
  and where the menu opens go to the owner. Townspeople and guards probably give none.
- **Rests on:** `skills-in-doom.md`: "Critical Strike is out", languages "removed for now" (owner, 2026-11-26).
  `skillmenu` 01: "Skill XP from monsters", menu "probably reached from the character sheet".
- **Challenge:** Original weapon skills and Destruction do nothing in Doom yet, so buying them is a trap for now, but
  they still count toward level and are planned. Rewarding townsperson kills would push players toward crime, which
  supports "no", though "monsters" may or may not cover hostile NPC bots. Kept.

## 2026-11-26: How should Melee and the gun skills enter preset class skill lists? [skillresearch 02]

- **Verdict:** Deferred.
- **Answer:** None. It goes to the owner.
- **Rests on:** no design text. It changes Daggerfall's class system and level rule for every preset class.
- **Challenge:** "Daggerfall's systems are all planned" says nothing about new skills in old classes. Any rule chosen
  changes how fast every character levels. Kept.

## 2026-11-26: Which rifles join Rifles and Pistols, and where do the single-shot heavies go? [skillresearch 01]

- **Verdict:** Owner decided (2026-11-26).
- **Answer:** "Pistols and rifles becomes just pistols", and "no rifle is counted". The skill is Pistols. Rifles need a
  tag so Doomerfall can tell them apart (DRLA's `SingleShotRifle` token does not match), and "for rifles we need a
  skill". The skill is named Rifles, not Marksmanship. A rifle is "all ballistic semi-automatic weapons that are not
  explosives, energy weapons, shotguns or pistols", worked out from the weapons if possible. Heavy single-shot rifles
  are rifles. The Assault Chaingun, Assault Minigun and Autocannon are Automatics.
- **Rests on:** Owner, 2026-11-26, after the rifles research (`work/notes/20261126-003658.md`).

## 2026-11-26: Floor gun look label: show the plain Doom name until Daggerfall answers, or no label? [skillresearch]

- **Verdict:** Not determined (downgraded from Leans "no label" in challenge).
- **Answer:** None. It goes to the owner or play-testing.
- **Rests on:** AGENTS.md: Daggerfall owns inventory (item identity).
- **Challenge:** The plain Doom name is not wrong, only less specific, so the "Daggerfall owns identity" argument is
  weak. A blank first look may feel unresponsive, while the swap may feel like a flicker. That is a UI feel judgment,
  not something the design settles.

## 2026-11-26: Should saves made before the HP-from-Endurance change get the class Endurance bonus once on load? [hpformula]

- **Verdict:** Leans yes.
- **Answer:** Add the class bonus to Endurance once on load, capped, so older characters match new ones.
- **Rests on:** `gamedesign/hp.md`: the bonus "adds to the starting Endurance and to the maximum Endurance", and "the
  order Endurance is gained never matters".
- **Challenge:** The rule says the bonus adds to *starting* Endurance, and an old character's start is past; changing a
  stat by migration (a Mage loses 2) may surprise. But leaving old characters without the bonus would make them differ
  from the rule forever, and the project is exploratory with no released saves. Kept as Leans.

## 2026-11-26: Rest in Doom, and a level-up HUD line [owner]

- **Verdict:** Owner decided.
- **Answer:** Resting gets a card: Daggerfall's rest menu exactly as in Daggerfall, opened in Doom by a keybind like the
  other menus. Doom also shows "You have reached level N" on a level-up.
- **Rests on:** Owner, 2026-11-26.

## 2026-11-26: Older saves and the class Endurance bonus [owner]

- **Verdict:** Owner decided.
- **Answer:** Keep what is merged: saves from before the HP change get the class bonus added to Endurance once on load,
  so old and new characters follow the same rule.
- **Rests on:** Owner, 2026-11-26.
