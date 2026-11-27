# Game designer dry run: proposed "strike settled options first" rule (2026-11-26)

The game designer's report, verbatim apart from formatting. It edited no files. Proposed rule under test:
"List the realistic options. Strike any option that contradicts a fact already settled. If one option is left, the
verdict is Follows clearly. If every remaining option leads to the same build, it's a minor detail: decide it. Only a
real fork goes to the owner, with the settled parts stripped out."

Skipped 8 entries the owner has since decided or overruled. 28 re-examined.

## Entries that would change (11 of 28)

| Entry | Old verdict | Under the new rule | Options struck and why | Confidence / risk |
|---|---|---|---|---|
| 11-24 guard-bot rest (rest part) | Leans | **Follows clearly**: hostile guard bots block rest. | Struck "don't block": the Rest row says rest runs "exactly as in Daggerfall" (owner, 11-26), and Daggerfall blocks rest with hostile guards near. | High. Settled by the owner's later rest ruling. |
| 11-24 hotkeys-whole-key | Leans | **Follows clearly**: whole key must be empty, as merged. | Struck "plain squares only": the owner's words "has no hotkeys" read literally. | Medium. **Risk:** the old challenge noted he may have pictured only the plain square. Build difference tiny, already merged. |
| 11-24 time-services-in-doom | Leans | **Follows clearly** (interim): services run in Doom with monsters frozen. | Struck "simulate monsters during the skip" (owner put off-window simulation on hold) and "block services in Doom" (DF's 3D world is off, so they can only run in Doom; "Daggerfall's systems are all planned"). | Medium-high. **Risk:** a tavern room could bypass the rest block, a separate question not to fold in. |
| 11-24 climb-holding-still | Leans (both) | Holding still: **Follows clearly** (no rolls/slips). Back: **stays Leans**, narrowed: "Back climbs down (DF advanced mode) or lets go (DF classic)?" | Struck "drop when forward released": contradicts the owner's "the player sticks to the surface". | High for holding still; Back is feel, stays with the owner. |
| 11-24 ammo-pile-placeholder | Not determined | **Minor detail, decided**: keep the Letter of Credit picture until real art exists. | None struck; every option ships the same build today; the art stays a backlog/art item. | High. |
| 11-24 black-white-monster-cost | Leans | **Follows clearly**: section 8.3 value, marked placeholder. | Struck the health-only multiplier (contradicts approved 8.3). "Owner hand-sets values" not struck (same build: an overridable table). | Medium. **Risk:** the owner hand-set some values (Arch-vile 20) and may want to here. |
| 11-24 drla-boss-cost | Leans | Same: **Follows clearly** with the 8.3 value. | Struck "kind points × √(health ratio)": 8.2 says bosses use their "own value". | Medium. Same risk: "own value" may mean values he assigns. |
| 11-24 regional-favourite-monster | Leans (both) | 90% one-class army: **Follows clearly**, allowed. Affordability narrowed: "If the favourite kind is too expensive for the area level, fall back to a colour/DRLA family, or occasionally break budget as a rare surprise?" | Struck "cap one-class armies": conflicts with "Favor extremes" and the owner's 11-26 "maximize variety and surprise". | Medium. **Risk:** the new boss rule lets rules break for surprise, so affordability must stay a question. |
| 11-24 ammo-tier-per-gun | Leans | **Follows clearly**: loaded tier belongs to each gun. | Struck "per ammo type": "A DRLA gun's loaded magazine is part of the gun and travels with it" (owner); per-type tiers would let a stored magazine fire rounds of the wrong tier. | High. |
| 11-24 stock-gun-raise | Leans | **Minor detail, decided**: raise the gun again. | Nothing settled contradicts "stay on fists", but it defeats the automatic change and the build difference is trivial. | Medium-high. Add a play-test note. |
| 11-26 skill-purchase-menu, townsperson XP | Leans no | **Lean reversed, sent as a narrowed confirm**: "Your XP rule says damage 'across all enemies'. Does that include hostile townspeople and guards?" | Nothing struck honestly. | **Main risk case.** Read literally, "all enemies" would give Follows clearly yes, but the owner very likely wasn't thinking about crime incentives. |

## Entries that stay the same (17 of 28)

- Mantellan Crux level (ND): a number. Narrowed: "Keep the formula's 23 or set another level?"
- Outdoor guards (Deferred): registry design and work order; backlog says "do not raise".
- Guard-bot travel part (ND): waits on owner design.
- DRLA armor refusal (ND): depends on drla-armor-role; real fork.
- Standing sleepers (ND): "hide" already struck by object permanence; standing vs lying is an art/feel fork.
- Pickup mix (ND): numbers.
- Taken pickups list (Deferred): save architecture.
- Slope 70 (Leans): owner reserved it ("design the Doom behavior with the owner"); changes traversal.
- New Game tutorial (ND): real fork.
- Baron Blaster (Leans/ND): balance cost of autoreload and forcing the setting are real forks.
- Ammo pickup weight limit (ND): DF's rule pushes to Follows clearly, but refusing touch pickups changes Doom feel and could starve the player.
- Capped class share (ND): a number.
- Tiered ammo shops (ND): shop types and odds.
- Orichalcum (ND): region or city is a real fork.
- Covens vs Civil War (ND): two owner rules collide. (Since answered by the owner: option b.)
- Change Ammo key default (ND): parked under sort-out-keybinds.
- Skill-uses mapping (Deferred): the owner said "the mapping is yours".
- Use-gain rates (Deferred), guild training full rate (Leans): paid training competes with the Skill XP economy.
- Purchase menu multiplier and location (ND): a number and a UI fork.

## Summary

- 11 of 28 change: 8 become Follows clearly or a decided minor detail (some in part), 2 narrowed, 1 lean reversed
  into a narrowed confirm.
- About 5 questions.md lines would disappear (guard bots block rest, "no hotkeys yet", time services, Letter of Credit
  placeholder, stock-gun raise / per-gun tier). The monster cost line would too, but it would rather keep it.
- Risks: striking options on broad owner wording (townsperson XP), hand-tuned numbers (monster costs), feel questions
  the owner reserved (slope, Back, ammo pickup weight).

## Suggested wording changes to the rule

1. A settled fact must be quotable: an owner statement, a pillar, a gamedesign.md line, or merged behavior the owner
   approved. "Daggerfall did it this way" or common sense alone never strikes an option (except where the owner said
   "exactly as in Daggerfall").
2. Don't strike an option on general owner wording that plainly wasn't about this case; send a one-line confirm.
3. Options that differ in numbers, balance, economy, feel or art, or that add or remove a player-visible behavior,
   never count as "the same build".
4. Leave alone anything the owner reserved, and run the Deferred test before this step.
5. When a minor detail is decided, say "decided as minor" in the log line so the owner can spot and overrule it.
