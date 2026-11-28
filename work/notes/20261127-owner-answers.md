# Owner answers to the Q&A sheet, 2026-11-27 (verbatim)

Answers to `work/notes/20261127-owner-qa.md`, by sheet number, as the owner gave them. The Product Owner processes
them five at a time: records each in `gamedesign/decisions.md`, makes cards or backlog items, and strikes the sheet.

Separate request in the same message: "equipped ammo should replace the symbol with its colored icon that's how players
will know what kind of ammo they have equipped and then we could show a message at the top in the daggerfall area as
well when they change their ammo we could push a notification there."

Owner instruction: "Put on hold qs in a separate document."

---

2. Does your "no gun skill in a language slot" rule also cover guild skill lists? A: No

3. What happens to the old monster-language enchantments? I guess reassign. Is this blocking? if it is, just make a
temporary decision that is simple and causes the slots to not be wasted. and we can take a backlog to gap analyze
enchantments later.
Should the item maker offer "Enhances Shotguns/Automatics/..." for gun skills? I don't understand the question.
Please explain it.

5. no such conflict exists because all gun skills get remapped to exactly one daggerfall skill. Invalid q.

6. Curve it, make a decision, that decision should be so that at a given jump height you can fall 1.5x as far before
taking damage there you go

7. Do mid-air double and triple jumps train Jumping too? Sure.

8. Keep the double jump after walking off an edge without jumping first. Yes.

9. Automatics perk numbers: unclear what is meant by 3 firerate bands elaborate

10. Should a dodged hit show or sound like anything? yes show the player a message in the top notification bar but at
the same time I think we need to rethink this whole system take a backlog item to rethink dodging with agility it
probably shouldn't be in the game in its current form

11. Explosives 50 direct-hit bonus: how much? Answer: 50%

12. Inpulsa's splash: Answer: As rocket.

13. Other bonuses: Inpulsa's always explodes for exactly 25% of the monsters HP without other bonuses.

14. Shotgun numbers use 200/400 - yes.

15. "Slower shotguns push harder": measured by reload time? Goal is to measure real speed with which weapon can be
fired. Estimate true fire rate using: Reload time vs. how much of magazine was spent and Fire Rate of weapon. However
use unmodified reload time. The reload speed bonuses from skills don't penalize this calculation. Neither do fire rate
bonuses if they exist. Use base values.

16. How strongly should slowness scale knockback? owner: Slower guns get significantly more total knockback than fast
shotguns. Being slower has some kind of mild exponential effect. Like maybe your true slowness quotient (calculated
above) also raised to the 1.2. You have leeway within this constraint. If this leads to guys getting knocked back quite
a lot, okay. By default I would have the double shotgun knock a guy back like five feet or so at the lower level and
maybe 10 at the higher level.

17. Shotguns 100: faster reload than the 25 perk's 35%? If it says you get faster reload then give the same amount of
faster reload.

18. Projectile shotguns get the +50%/+100% extra balls too? This is hard to code. Take a backlog item for this and
we'll look at doing it later since it's hard to make work.

20. nanomachic thing. leave current tag and backlog / future item it as very low priority.

22. Plain Daggerfall save with no Doom gun: still give the pistol? Yes

24. Should DRLA X's gizmos exist in some other form? I don't know how this got settled... I didn't ever review this.

25. Auriel's Shield quest reward (quest B0B71Y03), now that shields are out? Fine backlog very low priority to make it
a ring

26. Doom character look in bridged games? Remove this question I'll deal with it later

27. Darken dungeons to match Daggerfall Unity? Yes

28. Eye height and field of view. Keep doom however for our parity test do whatever you need to, for the parity test
use DFU values if you wish the problem is keep in mind we downscaled the geometry so just make sure the parity test is
like for like which like doesn't matter as long as it detects glitches and bugs

29. Outdoor trees and other flat sprites: take Daggerfall's flat daylight like the ground? Yes.

30. Outdoor monsters: flat daylight too, or keep Doom's distance darkening? Yes

31. Regional favourite monster: "affordable" means costs at most one average encounter at the area level? I don't care
to fully understand this specific question, just let the agent make a decision and document it.

32. Dear favourite still showing up through another pick: keep as a rare spike? I don't have enough context here to
understand the question.

33. Should Daggerfall creatures ever appear in Doom? Barring something I haven't thought of, NO. they should not.

34. Dungeon pickups: should health lean per dungeon too? Yes.

35. How common should hard pickup leans be? Fine - keep.

36. Ammo tier prices after Regular dropped to 1x base. This was handled wrong. Normal Ammo should be 3x base price.
Ammo is not the "base price" it's just a reference the other ammos multiply by. Nothing is 1x base.

37. Cap Doom weapon values? Let's instead make guns initially a fraction of the price. So instead of guns GOING UP TO
10x or whatever legendary is, they end up at 2x and start at a tiny fraction. But the proportions can stay the same. So
I don't remember what numbers I gave but rescale them without changing their relative proportions so Legendaries are
only 2x the price of a base Daggerfall weapon and then let's run that and test it.

38. Confirm: Doom weapon weight ignores material? Doom weapon weights should be affected by their Daggerfall materials
in terms of weight in whatever way Daggerfall material weights affect items in Daggerfall.

39-40. Ship travel: "For both of these ship questions we have a backlog item for this so remove them from here."

43. First visit to an unconverted dungeon takes 7-47 s on the loading screen. For sure this is too long and we need to
revisit this later. It's too slow.

44. Dungeon collision trade-off: player stops dead along some leaning walls. Drop question without answer it's too
specific I don't want to hear it again. The objective of the converter is to convert as accurately as possible in a
reasonable time and we have defined the parameters of what accurately is with scores we gave the agent we consistently
try to apply that principle unless it creates an issue where the player is completely trapped or will make the game
unplayable or something, this just sounds like a weird nitpick which doesn't necessarily matter.

45. Should Daggerfall always send rule numbers to Doom? Generally we will try to have daggerfall transfer its
character sheet to Doom and allow Doom to apply the rules based on that character sheet.

46. Replace the "which gun fired this" distance guess with an exact engine hook? yes I mean we're going to have this
at some point you have permission to do this but I think it's happening w/ explosives anyway

47. May overnight lanes build UZDoom into their own folder (or reuse a recent lane's build)? Sure I guess. Why not?

48. Texture packs: is loose PNG support enough? We probably need to build the scaffolding for the pngs to be shared
with doom and have daggerfall unpack the PNGs that just seems logical for performance.

49. make a decision

50. Live season swap in a loaded town causes a hitch and can delay doors. IF this is only when the season changes so
it's only 4x a year I don't care.

51. Guns dropped from the inventory window become Daggerfall piles: we already changed this, moot

52. okay, is there a simple technical solution to this? can we take a task to do it?

53. Travel from the level-up character sheet desyncs the engines. okay, when they click it, close the menu and then
open fast travel.

54. Agility can dodge scripted kills: thats fine

55. Door locks and taken pickups can reset: I guess take a backlog item for it and I'll see if this is true

56. Starting a game can drop a queued place record: we can take a backlog item for it

57. Untaken ammo pickups bloat the place record: Untaken pickups should be deterministic and procedural, they
shouldn't need a record right, backlog as low priority due to small size of it.

58. Schism mod weapon pickups are not treated as guns: strike, I don't care right now.

59. Outdoor sea and lakes are solid ground in Doom: agree implement them as daggerfall

60. Building interiors have no working doors for locks: If this is genuinely missing then we need to get it groomed

61. DRLA's Dragonslayer deals no damage: don't care

62. A ZScript code pattern crashes UZDoom at startup: if this isn't a blocker don't plan to do anything right now

63. Shared build and demo folders change or vanish under running lanes: it seems like separate lanes should indeed have
their own builds also the note taker should clean up and delete builds post verification

64. The bridge version check always fails: I guess fix ?

65. Parallel perk lanes claim the same character sheet slots: seems like a merge problem this is the wrong place for
this question

66. The paired New Game test driver stalls at message boxes: fix it if this is still an issue

67. Tests on the hidden desktop may check blank or tiny frames: I don't understand the problem

68. UZDoom builds fail at random when several lanes compile at once: yeah okay we may go to 3 lanes

69. Paired perk tests run with real HP and can kill the player; UZDoom also exited silently in 3 runs: is this a
problem ?

70. Greensmith Tower's dungeon entrance may be unreachable: IDK what to tell you we should probably get a daggerfall
test bot as well so that we can compare doom and daggerfall maybe they can be based off the same code largely IDK. but
yeah we may need to run DFU with a separate bot to see. This would be a future item.

## Unchecked questions (work/questions-unchecked.md)

- Burn fire look, 8 Schism flame frames committed in mods/doomerfall/src/sprites/burn/: "Yes, commit them."
- Shops 6, sparse top smith (about 7-10 goods vs target 75): no explicit answer (see the next two).
- Shops 6, general stores hold as many Daedric pieces as the best smith: "this is okay. I am not saying it must be one
  way or another."
- Shops 6, Daedric at the best smith, which rule gives: "This is good enough, we can revisit later."
- Skill XP for resurrected monsters: "I don't care. Don't bend over backwards to make it happen."
