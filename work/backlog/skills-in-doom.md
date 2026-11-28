# Daggerfall skills in Doom

**Waiting on:** owner design (in discussion, 2026-11-25).

Proposal (undecided where this file does not say otherwise): `work/notes/20261125-skills-armor-proposal.md`.
This file holds the owner's decisions so far and is the source of truth over the proposal.

## General (owner, 2026-11-25)

- No Doom class. The Doom player is a normal character with no class effects; Daggerfall skills apply all perks and
  modifiers. DRLA classes are inspiration only.
- Each skill grants a perk at 25, 50, 75 and 100, besides its continuous scaling.
- New gun skills are **new skills**, added beside Daggerfall's. They do not replace or rename existing skills.
  Short Blade, Long Blade, Axe, Blunt Weapon, Archery and Destruction stay and will be supported later
  ([original weapon skills](original-weapon-skills.md)). Critical Strike is out (bad for balance).
- New skills and the perk framework: in todo, `work/queue/skillcore/01.opus.new-skills-and-perk-framework.md`.
- Stay within Daggerfall's 35 skills. **Owner (2026-11-26): remove the nine monster languages for now; their slots make room for the new skills.** (Earlier: "Open: the new skills need more than 35.") (Facts: hard cap 64 until the
  skill-raised bitfield is widened; each new skill needs skill tables, character sheet and class maker entries, guild
  training, bridge sheet slots and save compatibility.)
- Skill effects in Doom are milder than Daggerfall's die rolls.

**Open owner answers the cards wait on:** perks follow live or base skill value
(`skillcore` 01 uses base until answered).

## New skills

Melee, Pistols, Shotguns, Automatics, Explosives, Energy Weapons. Rifles is planned but in the backlog
([rifles skill](rifles-skill.md)).

### Melee
Raises close combat and greatly raises damage reduction while a melee weapon is held, to make melee viable. Numbers
and perks open. Hand-to-Hand stays separate: it governs martial arts attacks such as vanilla Doom's fist.

### Pistols
Owner (2026-11-26): "pistols and rifles becomes just pistols", "no rifle is counted". In todo: `skillcore` 03
(the skill) and `work/queue/skillperks/05.opus.rifles-and-pistols.md` (perks). Rifle tag: `rifletag` 01.

### Automatics
In todo: `work/queue/skillperks/02.opus.automatics.md`.

### Shotguns
In todo: `work/queue/skillperks/04.opus.shotguns.md`.

### Explosives
In todo: `work/queue/skillperks/03.opus.explosives.md`.

### Energy Weapons
Owner design (2026-11-26), replacing the earlier "25: ammo consumption increases" idea. Proposal history:
`work/notes/20261126-energy-weapons-proposal.md`; damage check: `work/notes/20261126-energy-weapons-damage.md`.
- Theme: logistically expensive guns, carried by expensive cells, not by the perks: "what if we just make Energy Cells
  expensive. I think they already are." "Not every perk should force wedge that theme."
- Scaling: "+0% to +60% damage at max level."
- **25:** "Plasma Burn for 50%. Non-exploding energy weapon hits cause 30% of their hit in a small splash damage which
  triggers other abilities and does not hurt the player."
- **50:** "Plasma Burn. enemies are set on fire for 100% of the damage over 3 seconds. This is a stacking DOT effect.
  There is no limit to how much you can stack this effect. Non-Hitscan Energy weapon projectiles are 30% faster."
- **75:** "Strip Resistances. These weapons escalatingly strip resistance from enemies. Enemies get stripped of up to
  30% allres when they are hit based on firerate. Enemies cannot lose more than 100% allres this way. Enemies cannot
  take more than 30% allres in resistance loss every 3 seconds or so. Think about how we would balance this with a big
  enemy. Plasma burn damage can be stripped when an enemy is hit and converted into additional direct damage taken.
  40% of the total plasma burn debuff damage remaining is stripped and converted this way."
- **100:** "Plasma burn is now +150% and when you hit an enemy with plasma burn stripping that 40%, the enemy explodes,
  dealing a fraction of that as more damage and plasma burn to nearby enemies, you pitch some numbers."
- "Doom tracks plasma burn in engine or whatever is performant in general. Persistence of these debuffs is not as
  critical as performance."
- Numbers: Revision 2 in `work/notes/20261126-energy-weapons-damage.md` proposes tuned values (about 3.9x at 100).
  **Approved by the owner, 2026-11-26:** "I approve on revision 2 numbers we'll watch it." So: scaling +0-50%; 25 burn
  40%, splash 20%; 50 burn 70% (stacking, +30% projectile speed); 75 strip capped at 30% total, decays when not hit,
  pull 40%; 100 burn 100%, explosion 25% of the pulled burn, radius 128, at most once per target per 0.25 s.
  Cell price: 10 gold per cell (owner, 2026-11-26: "Cell price 10"). BFG rays apply burn like any other hit ("If it doesn't skew the game balance, then yes. Why are we nerfing
  the BFG as it currently is if we didn't give it more than other weapons?"). Strip boosts all damage the enemy takes
  ("All damage. We don't balance to make the game boring."). Still open: burn stacking from 25 or only from 50. Owner answers on it (2026-11-26):
  - 100 explosion: "yes to no chaining but it can still do burn but then the next thing does have to get hit to
    trigger another explosion. so it's kinda partial."
  - Withdrawn: "strip effects are halved on hitscan weapons" (owner: "i never intended. I was considering burn but
    let's not do that."). Hitscan and projectile energy guns get the same strip and burn.
  - "Cells should cost even more."
  - "this works like 'poison damage' which will tend to give it a very high theoretical DPS with very bad quality of
    life."

Final owner design (2026-11-26), replacing the approved Revision 2 set above: scaling +0-50%; burn stacks without
limit; 25 burn 50%; 50 burn 100% and 20% of the burn pool converts to direct damage on hit; 75 burn 125% and 40%
converts; 100 burn 150% and the converted 40% is an explosion (no player damage) that sets nearby enemies burning at
40% of its value, convertible by later direct hits; +15% projectile speed at each of 25/50/75/100; 20% splash on
non-exploding hits that neither causes nor converts burn; no strip ("Exposed is gone"); cells 10 gold. Card:
`work/queue/skillperks/06-08`.

### Weapons in two skills (owner, 2026-11-26)
A weapon that is both a Shotgun or Pistol and an Energy Weapon uses whichever skill is higher, never both at once.
Tags may be reassigned for weapons where this is technically hard, as long as every weapon's tags are consistent and
make sense.
Future (owner, 2026-11-26): "tag automatic weapons that do not cause explosions as also automatics and let them be
treated by whichever skill is higher." For example, a non-exploding automatic energy gun is also an Automatic.

## Jumping
Built (skillperks 01, then jumpfollowup 01): jump height +1% per point, +25% from 25; double jump at 50, triple at
100 (also after walking off an edge). Falling damage (owner, 2026-11-27, Q&A item 6, curve chosen in jumpfollowup 01):
a fall up to 1.5 times the current jump height is free, then 5 HP per metre past it (Daggerfall's rate), so the safe
fall grows with the jump: 1.8 m at Jumping 0, 2.6 m at 25, 3.1 m at 50, 3.5 m at 75, 3.9 m at 100 (Doom's default
JumpZ). The old Jumping 75 perk (no falling damage) is gone, so 75 has no perk now. Every jump, from the ground or in
mid-air, is one Jumping use (Daggerfall's rate). Rules: `mods/doomerfall/src/zscript/DoomerfallRules.zs`.

## Other skills (placeholders, owner is detailing)

Not designed yet unless noted. Brainstormed perks for many of these are in section 3 of the proposal note.

- **Hand-to-Hand:** governs martial arts attacks, such as vanilla Doom's fist (owner).
- **Short Blade, Long Blade, Axe, Blunt Weapon, Archery:** stay; supported later ([original weapon
  skills](original-weapon-skills.md)).
- **Destruction:** stays; supported later.
- **Restoration, Illusion, Alteration, Thaumaturgy, Mysticism:** placeholders.
- **Medical:** In todo (works and levels as in Daggerfall): `work/queue/skillbasics/01.opus.daggerfall-interaction-skills.md`. Perks TBD.
- **Running:** In todo (levels from time spent running, 1.5x Daggerfall's rate; owner calls it Athletics): `work/queue/skillbasics/02.opus.running-levels.md`. Perks and the movement speed formula TBD, to be defined here.
- **Dodging:** placeholder.
- **Swimming:** placeholder.
- **Climbing:** placeholder. (Already wired: Doom runs climbs with Daggerfall's Climbing chances and reports skill
  uses.)
- **Stealth:** placeholder. (Planned to slow the detection bar, `gamedesign.md`.)
- **Backstabbing:** In todo (up to 5x damage to unaware enemies; levels 10x faster from shooting unaware enemies): `work/queue/skillbasics/03.opus.backstabbing.md`. Perks TBD as a separate task.
- **Lockpicking:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Pickpocket:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Mercantile:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Etiquette:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Streetwise:** In todo (as in Daggerfall): `skillbasics` 01. Perks TBD.
- **Languages (Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan, Centaurian, Impish):** removed for now
  (owner, 2026-11-26); their slots hold the new skills (`gamedesign.md`; [revisit languages](revisit-languages.md)).
- **Critical Strike:** out (owner).
- **Rifles (new):** backlog ([rifles skill](rifles-skill.md)).

## Perk popups
In todo: `work/queue/skillcore/02.opus.perk-popup.md`.

## Skill XP and buying skills
In todo: research `work/queue/skillresearch/02.opus.skill-xp-system.md`, then the purchase menu with visible perks
(`skillmenu` 01) and the skill point sound and message (`skillmenu` 02). Daggerfall's level-up flow in Doom:
`levelup` 01.

Owner answers on the research 02 proposal (2026-11-26). All answered; the revised `skillmenu` 01 card was approved 2026-11-26.
- Rate: "1XP per HP everywhere. Overkill doesn't give xp it's up to max enemy hp of damage." Then: "Let's call it 1xp
  per 100hp damage total dealt across all enemies ... that just makes the numbers less crazy." So 1 Skill XP per 100 HP
  of damage, summed across all enemies, each enemy counting at most its max HP.
- "We don't need to save/load the remainder. Doom would keep track of that and accumulate all the damage the player
  deals."
- "We do need to be careful not to spam the message bus with XP gains, we should do something smart with that."
  Clarified: "don't do this to an extent that causes a problem, be efficient and logical, consider performance."
- Prices: "How much XP stuff costs is the real question, it will be a lot. These numbers will get big. very big."
  Still open.
- Which skills can be bought: "Every skill that is playable, not skills that are removed." Critical Strike and the
  removed languages cannot be bought.
- New skills and class lists: "Detect if Guns are enabled (currently they always are but we have a backlog to review
  this). If guns are enabled, we reroute standard weapon skills with a mapping to Doom weapon skills. You propose the
  mapping and I'll approve/deny it." Mapping proposed in chat 2026-11-26, not yet approved.
- Use: "weapons get skill from use" (owner, 2026-11-26), beside buying ("skills also level from use right so I mean
  this is not all of the xp"). "it should be like 1/4 normal skill growth", then: "Most skill gains should come
  from use not from buying." This reverses 2026-11-25's "buying is the main source". Buying supplies about a quarter
  of growth. Owner agreed: weapon use 1 per 250 HP with that weapon type, other skills at Daggerfall's normal use
  rate; price = Daggerfall's uses for the point × 7.5 XP, with one flat skill multiplier (2) for every skill.
- Dodging: "Dodging is a mess stick that in the backlog. It may be removed IDK." See [dodging-skill](dodging-skill.md).
- Menu: "The menu opens from a button I guess figure out what you recommend make a proposal." Approved: a "Skills"
  button on Daggerfall's character sheet, plus its own keybind in Doom like Rest.
- Townspeople and guards: "Yes guard and people injuries count as long as they take damage."

## Tutorial (owner, 2026-11-25: backlog item, after the game is complete)

Update Daggerfall's tutorial into a Doomerfall tutorial that covers how all this works, including buying skills with
Skill XP.
