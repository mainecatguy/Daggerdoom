# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

Merged work is recorded in `CHANGELOG.md`, not here. Items waiting on owner input go to `work/refinement/` with a
"Sent back" note, unless they block an urgent item (owner, 2026-11-27).

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input, send it back to `work/refinement/` with a "Sent back" note saying what it is waiting on, and continue with the next item that does not depend on it.
- When an item is merged, remove it from this file; `CHANGELOG.md` records it.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

### Top priority

- `findnpc` 01 (`work/queue/findnpc/01.opus.find-npc-by-name.md`), approved by the owner, 2026-11-27, top priority
  for debugging: type an NPC's name or pick a quest NPC; an on-screen chevron points to their building or to them until
  the area changes.

### Verified, waiting for the next merge

- `skillbasics` 03 (`agent/skillbasics-20261127-194856`): Backstabbing, up to 5x damage to unaware enemies. Merge
  checks: DD_BackstabHeard runs for every actor per noise alert (early return for non-monsters); the heard history is
  not saved, so a loaded monster that heard the player counts as alerted.
- `attributes` 08 (`agent/attributes-20261127-194930`): Strength and Agility gun damage by weapon type, Agility dodge
  removed, Luck 5x super crit. Built multiplying; leave it (owner, 2026-11-27), `damagestacking` 01 reviews it.
- `outdoorwater` 01 (`agent/outdoorwater-20261127-193328`): outdoor sea and lakes swim and drown as in Daggerfall.

### Skills (rules in `work/backlog/skills-in-doom.md`)

- `skillperks` 09 (`work/queue/skillperks/09.opus.automatics-bands-and-tuning.md`), approved by the owner, 2026-11-27:
  Automatics 25 ammo skip, 50 band bonuses, 75 suppression slow, 100 stack +2% per hit to +30% (one ammo per 4 shots stays).
- `enchantgunskills` 01 (`work/queue/enchantgunskills/01.opus.gun-skill-enchantments.md`), approved by the owner,
  2026-11-27: gun-skill powers in the item maker; dead language enchantments spread deterministically to other skills.
- Tutorial: when the Doomerfall tutorial is made (backlog, after the game is complete), it must explain buying skills
  with Skill XP.

### Movement and maps

- `collisionmetric` 01 (`work/queue/collisionmetric/01.opus.collision-fidelity-metric.md`), approved by the owner,
  2026-11-27: the collision fidelity metric that gates all converter collision changes.
- `collisionshape` 01 (`work/queue/collisionshape/01.opus.grid-shape-refactor.md`), approved by the owner,
  2026-11-27: grid-shape refactor (byte-identical output), then better grid shapes judged by the metric. After
  `collisionmetric` 01.

### Bugs and small features

- `sheettravel` 01 (`work/queue/sheettravel/01.opus.travel-from-sheet-closes-menu.md`), approved by the owner,
  2026-11-27: travel from the logbook closes the menu and opens normal fast travel. (Running.)
- `rulepattern` 01 (`work/queue/rulepattern/01.opus.one-rule-pattern.md`), approved by the owner, 2026-11-27: Daggerfall
  sends the sheet, Doom applies rules in one shared place. (Running.)
- `gunsource` 01 (`work/queue/gunsource/01.opus.exact-gun-source-hook.md`), approved by the owner, 2026-11-27: exact
  engine hook for which gun fired a spawned projectile. (Running.)
- `weaponvalues` 02 (`work/queue/weaponvalues/02.opus.rescale-gun-values-and-material-weight.md`), approved by the
  owner, 2026-11-27: rescale gun values so legendaries cost 2x a base weapon; material changes gun weight.
- `pickuplean` 01 (`work/queue/pickuplean/01.opus.health-leans-per-dungeon.md`), approved by the owner, 2026-11-27:
  health pickups lean per dungeon like ammo.
- `lightparity` 01 (`work/queue/lightparity/01.opus.light-like-daggerfall.md`), approved by the owner, 2026-11-27:
  dungeons as dark as Daggerfall Unity; outdoor sprites and monsters in flat daylight.
- `shotgunpush` 01 (`work/queue/shotgunpush/01.opus.shotgun-knockback-by-true-fire-rate.md`), approved by the owner,
  2026-11-27: shotgun knockback by true base fire rate (^1.2); Shotguns 100 gets another 35% faster reload.
- `perknumbers` 01 (`work/queue/perknumbers/01.opus.perk-numbers-batch.md`), approved by the owner, 2026-11-27:
  send the owner's numbers for Explosives 50, Inpulsa chain blasts and Shotgun slams.
- `jumpfollowup` 01 (`work/queue/jumpfollowup/01.opus.fall-damage-curve-and-air-jumps.md`), approved by the owner,
  2026-11-27: fall damage safe height 1.5x jump height; mid-air jumps train Jumping.
- `weaponmaterials` 01 (`work/queue/weaponmaterials/01.opus.doom-weapon-material-tidy.md`), approved by the owner,
  2026-11-27: Iron starter guns, no "Iron" in Doom weapon names, melee weapons get materials.
- `lockpickshops` 01 (`work/queue/lockpickshops/01.opus.where-lockpicks-come-from.md`), approved by the owner,
  2026-11-27: lockpicks at pawn shops, general stores, sometimes other traders and in Daggerfall-engine loot.
- `qafly` 01 (`work/queue/qafly/01.opus.qa-bot-flies.md`), approved by the owner, 2026-11-27: the QA bot can fly where
  only levitation would reach, until Levitate exists.
- `questgold` 01 (`work/queue/questgold/01.opus.quest-gold-by-area-level.md`), approved by the owner, 2026-11-27:
  quest rewards follow the area level instead of a fixed level 20.
- `hitboxcheck` 01 (`work/queue/hitboxcheck/01.sonnet.verify-monster-hitboxes.md`), approved by the owner, 2026-11-27:
  verify narrowed monsters keep full-size hitboxes and narrow only to squeeze through.

### Shops and encounters

- `shoplevels` 08 (`work/queue/shoplevels/held/08.opus.interior-quality-danger-and-armor-split.md`), approved by the
  owner, 2026-11-27: interiors take danger and loot from the building's quality (in and outside towns); leather and
  chain split Iron's slot, outside the stock limit.
- `encounters` 09 (`work/queue/encounters/09.opus.local-war-rooms.md`), approved by the owner, 2026-11-27: local war
  rooms rigged like Civil War, asleep until the player opens the door.
- `passiveguards` 01 (`work/queue/passiveguards/01.opus.passive-guard-bots.md`), approved by the owner, 2026-11-27:
  passive castle markers and friendly entities become passive Doom guard bots that look like Daggerfall's guard.
- `outdoorguards` 01 (`work/queue/outdoorguards/01.opus.outdoor-guard-bots.md`), approved by the owner, 2026-11-27:
  crimes outdoors (failed pickpocket, a shot watchman) bring guard bots Doom can see, as indoor guards do.
- `randomencounters` 01 (`work/queue/randomencounters/01.opus.random-encounter-packs.md`), approved by the owner,
  2026-11-27: Daggerfall's random encounters (rest ambushes, reputation guards) as mook packs at area level.
- `questfoes` 01 (`work/queue/questfoes/01.opus.quest-foe-packs.md`), approved by the owner, 2026-11-27: quest foes in
  town buildings and quest ambushes as mook packs.

### Held until a condition is met (may start without asking once it is)

- `daynight` first-town season (owner, 2026-11-26: when weekly and current usage are both at or below 10%): in a
  winter save the first town after launch loads in summer textures, because Doom builds it before Daggerfall sends the
  season. Options in `work/notes/20261126-145333.md`.
- `qabot` 02 (`work/queue/qabot/held/02.opus.god-mode-gun-tester.md`): god-mode gun tester. When usage is at or below
  10% (weekly and current), or at night while the owner sleeps and nothing else is queued. QA bot runs are long and
  run only overnight, 2AM to 7AM.
- `corpsekeep` (`work/queue/corpsekeep/held`): corpses vanish on leaving and re-entering Privateer's Hold. First check
  whether the location record rewrite fixed it.

### Downtime work (owner, 2026-11-26: "Lower priority, but do during downtime")

- `automaticspop` 01 (`work/queue/automaticspop/01.opus.slow-band-pop-graphic.md`), approved by the owner,
  2026-11-27, low priority: the small explosion graphic on Automatics slow-band hits. After `skillperks` 09.
- `gunenchantments` 01 (`work/queue/gunenchantments/01.opus.gun-enchantments.md`), approved by the owner, 2026-11-27,
  low priority: guns accept weapon enchantments; damage enchantments use a 90x pool (3x per hit). After `enchantgunskills` 01.
- `enchantedguns` 01 (`work/queue/enchantedguns/01.opus.enchanted-gun-names.md`), approved by the owner, 2026-11-27:
  enchanted guns recognisable by name (research first). After `gunenchantments` 01.
- `attributes` 09 (`work/queue/attributes/held/09.opus.int-per-gun-enchantments.md`), approved by the owner,
  2026-11-27, low priority: Intelligence and Personality scale gun enchantments, multiplied with each other. After
  `gunenchantments` 01, before `attributes` 07.

### Lowest priority (owner, 2026-11-27)

- `attributes` 05 (`work/queue/attributes/held/05.opus.speed-scales-climbing.md`), approved by the owner, 2026-11-27,
  lowest priority: Speed scales climbing.
- `attributes` 07 (`work/queue/attributes/held/07.sonnet.attribute-help-from-rules.md`), approved by the owner,
  2026-11-27, very low priority, only after every other attribute card is merged: correct the character sheet
  attribute help and add a check that catches drift.
- `damagestacking` 01 (`work/queue/damagestacking/01.opus.review-damage-stacking.md`), approved by the owner,
  2026-11-27, minimal priority (last in todo): review every damage bonus against "increased adds, more multiplies"
  and fix where appropriate.
