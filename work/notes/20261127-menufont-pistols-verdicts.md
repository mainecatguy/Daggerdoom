# Game designer verdicts: menu font and Pistols perks questions (2026-11-27)

## Challenge pass

### FILE: 20261127-menufont-popup-row-case.md

## 2026-11-27: Should the live-text popup rows (Talk, Sell, Join Guild, Repair Item) be upper case or mixed case?

- **Verdict:** Leans.
- **Answer:** Upper case for every row (TALK, SELL, JOIN GUILD, REPAIR ITEM), as classic Daggerfall painted them. The
  existing mixed-case 'Sell' label changes to SELL so the rows match.
- **Rests on:** Owner (2026-11-26, card menufont 01): "Talk / sell options use inconsistent font on merchant interaction
  menu, use daggerfall font". Either case fixes the inconsistency, since all rows would match. Inference: classic
  Daggerfall's painted rows were upper case, and the rows now sit over that same classic art, so upper case keeps the
  popup looking as it did. `gamedesign.md` Aesthetics row ("look like Daggerfall") supports it only loosely, because it
  names environments, architecture, skies and props, not UI.
- **Challenge:** The Aesthetics row was stretched in the answer pass, since it does not name menus. Without it, the lean
  rests on the owner asking for Daggerfall's look in this popup, plus the fact that upper case matches the classic art
  the rows are drawn over. Mixed case is also consistent and matches the label that already existed. Daggerfall
  precedent alone strikes neither option. The two cases look different, so this is not minor. Kept at Leans; the owner
  sees it.

### FILE: 20261127-menufont-picture-buttons.md

## 2026-11-27: Should picture buttons such as the red EXIT also become live text so font mods reach them?

- **Verdict:** Leans.
- **Answer:** Leave picture buttons as pictures. Texture packs replace the picture itself, so a pack still reaches them.
  The card's done-when is met without changing them.
- **Rests on:** Owner (2026-11-26): "support daggerfall texture packs for text". Card done-when: "the merchant popup and
  a sample of other Daggerfall menus in Doom use Daggerfall's font, and a Daggerfall font replacement from a texture pack
  shows up." Inference: the owner's complaint was about the rows that clashed (Talk / Sell). A painted EXIT is a picture
  that texture packs already replace, as in Daggerfall Unity.
- **Challenge:** A pack that only replaces the font, with no new pictures, would change TALK and SELL but leave a classic
  painted EXIT next to them. That brings back a small version of the font mismatch the owner complained about. Against
  that, Daggerfall Unity has the same mix across all its painted buttons, and redrawing every painted button as text is a
  much bigger job than the card asked for. The owner's words point toward leaving pictures alone but do not settle it,
  and the result is visible, so this is not minor. Kept at Leans.

### FILE: 20261127-menufont-hud-replacement-font.md

## 2026-11-27: Should the converter pick up a Daggerfall replacement font (e.g. FONT0003-SDF.ttf) for Doom's HUD lines?

- **Verdict:** Leans (needs a one-line owner confirm).
- **Answer:** Probably yes. Doom's HUD messages already use a Daggerfall font, baked into ddruntime.pk3 from Daggerfall
  Unity's built-in font. Picking up a replacement font would keep those lines matching the menus when a texture pack
  changes the font. Confirm that the owner's "support daggerfall texture packs for text" covers Doom's HUD lines.
- **Rests on:** Owner (2026-11-26): "use daggerfall font, support daggerfall texture packs for text". Merged behavior: the
  HUD lines already use Daggerfall's font. Inference: once a pack changes the menu font, HUD lines in the old font would
  bring back the inconsistency the owner reported.
- **Challenge:** The card's scope is "Daggerfall menus shown in Doom", and the owner's words were about the merchant
  menu. AGENTS.md gives Doom the combat HUD, and the Aesthetics row says combat effects look like Doom/DRLX. So the owner's
  rule plainly was not written about HUD lines and cannot settle them; hence the confirm. Not Deferred: it changes only
  which font file the existing converter bakes, with no new system and no ripple into play. Not minor: the player sees the
  result. Kept at Leans with a confirm.

### FILE: 20261127-pistols-fire-rate-measure.md

## 2026-11-27: Pistols 25 and 75 fire-rate multipliers: how is fire rate measured, on which gun state, and which rates are fast and slow? [20261127-115755]

- **Verdict:** Leans (measure) / Not determined (unmodified or modded gun) / Not determined (fast and slow cut-offs and
  scaling).
- **Answer:** Measure: probably the tics between shots with the trigger held, leaving out magazine reloads, counted the
  same way for every pistol. Whether it is read from the unmodified gun or from the gun as currently modded, and which
  tic counts are "fast" and "slow" and how the multipliers scale between them, go to the owner. Data for the owner: the
  build measures stock Pistol, DRLA Pistol and Handcannon at 19 tics and Marksman Pistol at 16, so the suggested fast 10 /
  slow 30 puts all of them in the middle (about x2.05-2.2 at 25). The research note counted Pistol 14 and Handcannon 16
  (to `A_ReFire`), so the counting point differs by a few tics and must match whatever cut-offs are chosen. The research
  model used fast 4 / slow 35 and found the combined 25 x 75 multiplier spans only about 3.75-4.6 whatever the anchors, so
  the cut-offs matter mostly between skill 25 and 74.
- **Rests on:** Card 05 (owner design): "Fast-firing pistols deal about 2.5x damage, scaling down to 1.5x for slow-firing
  ones. This multiplies damage only. The gun does not fire faster." Card 05 holds "which fire rates count as fast and
  slow, and how the multipliers scale between them" for the owner. Inference for the measure: "fire rate" is shots over
  time, and tics between shots is the same quantity in Doom's unit; leaving out reloads keeps the 20/40/60% faster
  reloads (same card) from changing the multiplier, which the card keeps separate from rate.
- **Challenge:** Linear in tics and linear in shots per second give different numbers, so the unit is not a minor detail;
  that difference is folded into the open scaling question, which keeps the measure itself at Leans. Live versus
  unmodified: Systemic cause and effect (owner, 2026-11-27: systems "are allowed to interact") hints at live, but
  "allowed" does not strike reading the base gun, and the two differ in what the player sees when modding. No option is
  struck. Not Deferred: Daggerfall already sends the two cut-offs; no new system. Kept as answered.

### FILE: 20261127-pistols-pool-multiplied.md

## 2026-11-27: Do the Pistols fire-rate multipliers (25 and Deadeye 75) also multiply the skill 50 bonus damage pool? [20261127-115755]

- **Verdict:** Not determined.
- **Answer:** None. As built the pool is added after both multipliers, unmultiplied; this stays until the owner answers.
- **Rests on:** Card 05 lists "whether Deadeye also multiplies the bonus pool" as not decided and held for the owner.
  Card 05: the pool "is flat and added to the shot's damage". The research DPS figure (about 330-410) assumed "the bonus
  is not multiplied by Deadeye".
- **Challenge:** "Flat" points to unmultiplied and could be read as settling it, but the same card reserves the question
  for the owner, so it cannot be struck. Multiplying would raise the 75+ pool from 100 to up to about 460 per shot, a
  large balance difference, so it is not minor. Kept.

### FILE: 20261127-pistols-shrapnel-v-range.md

## 2026-11-27: Pistols 100 shrapnel: a V of centre and plus or minus 15 degrees, range 768; does a miss spend the bonus pool? [20261127-115755]

- **Verdict:** Not determined.
- **Answer:** None. The 15-degree V and 768 range are placeholders as built, and "only a hit spends the pool" stays as
  built until the owner answers.
- **Rests on:** Card 05 (owner, 2026-11-26): fragments "fork away behind the enemy in a V pattern" and turn only for an
  enemy "within 5 degrees of a fragment's path"; no angle or range is given. Card 05: "Shots spend it ... added to the
  shot's damage."
- **Challenge:** The angle and range are numbers the documents do not contain. On misses, "added to the shot's damage"
  hints that spending happens where damage happens (a hit), but "Shots spend it" can as well mean firing spends it, and
  the two differ in how forgiving the pool feels, so it is not minor. Kept.

### FILE: 20261127-pistols-carry-pitch.md

## 2026-11-27: Do Pistols carry-through and shrapnel fly level from the hit, or keep the shot's up or down angle? [20261127-115755]

- **Verdict:** Follows clearly (was Leans).
- **Answer:** They keep the shot's pitch: carry-through continues along the shot's 3D line, and the fragments fork
  around that line. The 5-degree turn toward an enemy is measured in 3D. When this sends fragments into the floor
  behind a close enemy, that is the expected result.
- **Rests on:** `gamedesign.md`, World logic (owner, 2026-11-27): "outside of cheats, nothing happens that makes no
  physical sense in that world." Card 05 (owner, 2026-11-26): fragments fork "as if the bullet exploded into shrapnel",
  and "Fragments are not smart, with one exception" (the 5-degree turn). Precedent: the Use-through-3D-floor entry
  (2026-11-27) was raised to Follows clearly on the same principle.
- **Challenge:** Options: (a) level flight, (b) keep pitch, (c) keep pitch with vertical aim toward targets. (a) has a
  bullet fired downward turn level at the hit, which makes no physical sense, so World logic strikes it; the owner's
  own framing ("as if the bullet exploded") is physical. (c) contradicts "not smart" beyond the 5-degree turn. One option
  remains. Argued against: level flight makes the perk land more often on slopes and from ledges, and the owner might
  prefer that for play; but World logic was written for exactly this kind of physics question, so no confirm is needed.
  The owner can overrule. Raised from Leans.

### FILE: 20261127-energy-splash-per-hit-or-gun.md

## 2026-11-27: Energy Weapons 25 splash: is "non-exploding" decided per hit or per gun? [20261127-124542]

- **Verdict:** Not determined.
- **Answer:** None. As built (per hit: explosion damage never splashes, any other hit does, so BFG ball impacts and rays
  and a Tristar's direct impact splash) stays until the owner answers. The alternative is per gun: every gun that
  explodes (every BFG, Tristars, Plasma Cannon, Tantrum, Zeus, BFG10K) never splashes. Per gun still leaves open the
  guns with token puff explosions (Mk II, Handcannon, Hell's Reign, Neural Stunner), an earlier unanswered question.
- **Rests on:** Owner (skills-in-doom.md:53): "Non-exploding energy weapon hits cause 30% of their hit in a small
  splash". Final owner design summary (skills-in-doom.md:84-85): "20% splash on non-exploding hits". Owner on the
  Automatic tag (skills-in-doom.md:92): "automatic weapons that do not cause explosions", decided per gun in
  20261127-triage-q04. Owner on BFG rays (burn): "Why are we nerfing the BFG as it currently is if we didn't give it more
  than other weapons?" The 2026-11-26 damage note read the splash per gun; that is an analysis note, not the owner.
- **Challenge:** Grammar is split: "non-exploding energy weapon hits" can attach "non-exploding" to the weapon or to the
  hit; the agent-written final summary says "hits", but it is a summary, not a quote. The owner's other use of the word
  ("weapons that do not cause explosions") is per gun, which pulls the other way. The BFG quote was about burn, not
  splash, and the damage note's suggestion "rays deal burn but no splash" was never answered. Neither option is
  struck. They differ greatly in balance (BFG rays each splashing in a pack) and in cost: the 20261127-124542 review
  found the uncapped splash may cost several hundred extra damage calls per BFG shot, which per gun would mostly remove.
  A splash cap is engineering either way. Not Deferred: no new system or architecture, only which hits qualify. Kept at
  Not determined.

### FILE: 20261127-burn-fire-look-pick.md

## 2026-11-27: Burn fire look: should a follow-up capture screenshots of the candidates, and who picks the look? [20261127-132535]

- **Verdict:** Follows clearly.
- **Answer:** Yes. Card 07 is not done until the look has been seen. A follow-up captures pictures (or a short clip) of
  the engine-particle fire, the Arch-vile flame and a lighter Schism cut on small and large monsters. The agent picks
  when one clearly meets the owner's tests (looks good, is reusable, works the same on any monster, works without DRLA)
  and clearly reads as fire. It shows the owner the pictures only if it can't tell which is best. Cost (actors per puff,
  frame hitch with hundreds burning) is part of "works consistently" and may decide between candidates that look about
  equally good. The chosen look also goes on the card's play-test list so the owner sees it in play.
- **Rests on:** Card 07 (owner, 2026-11-26): "decide what is best: it looks good, is reusable, and works consistently on
  monsters. If UZDoom already has a good burn effect, just use that. ... If you can't tell which is best, stop and show
  the owner pictures or a short video of the candidates." Done when: "they look on fire ... a dense pack of burning
  enemies (hundreds) shows no frame hitch." AGENTS.md: things only a human can judge go on the play-test list.
- **Challenge:** Options: (a) particles stand with no pictures; (b) pictures, agent picks if clear, else the owner; (c)
  pictures, owner always picks. (a) contradicts the owner's "it looks good" test and the done-when "they look on fire",
  which can't be judged without seeing the look. (c) contradicts the owner's delegation "decide what is best", with
  pictures to the owner only "if you can't tell". Argued against: visual quality is something only a human can judge,
  so maybe the owner should always see it. But the owner wrote the rule for exactly this pick, and the play-test list
  still puts it in front of the owner. Whether to spend budget on the follow-up now is scheduling, not design: the card
  is already approved todo and simply unfinished. Kept.

### FILE: 20261127-burn-pain-rate.md

## 2026-11-27: Burning monsters roll their normal pain chance on every 0.2 s burn payout, so Imps and ZombieMen can be pain-locked for most of a 3 s burn. Intended, or limit burn pain? [20261127-132535]

- **Verdict:** Not determined.
- **Answer:** None. As built (normal pain chance on every 0.2 s payout) stays until the owner answers. The alternatives
  are a rate limit (for example at most one burn flinch per second per monster) or one flinch when the burn starts.
- **Rests on:** Card 07 (owner, 2026-11-26): "Burning enemies also show pain, so it is clear they are taking damage:
  'enemies are not having a good time when they are on fire'." Energy Weapons owner decision (2026-11-26): burn stacks
  without limit; "All damage. We don't balance to make the game boring."
- **Challenge:** The owner wants burning enemies to visibly flinch, which strikes "no burn pain at all". But the stated
  reason is legibility ("so it is clear they are taking damage"), and once-per-second pain also makes that clear. The
  owner never mentioned pain-lock, which is a crowd-control effect: with unlimited stacking and Energy Weapons at 50 and
  up, every burning low-tier monster could be kept almost helpless. "Not having a good time" and "we don't balance to
  make the game boring" lean toward keeping it as built, but neither was about pain rate, so they can't settle it. The
  options differ in balance and in what the player sees, so this is not a minor detail. Not Deferred: it is a tuning
  choice inside the burn system, with no new system. Downgraded from a Leans keep to Not determined.
