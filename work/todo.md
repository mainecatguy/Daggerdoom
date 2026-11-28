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

### Top priority (owner, 2026-11-28)

- `mapgen` 01 (`work/queue/mapgen/01.opus.shared-map-generator-proposal.md`), approved by the owner, 2026-11-28:
  research and proposal for one shared generator for towns, dungeon exteriors, interiors and dungeons.
- `loadprofile` 01 (`work/queue/loadprofile/01.opus.profile-conversion-load-times.md`), approved by the owner,
  2026-11-28: profile why dungeon and town conversion are slow; worst stages, why, and the offending code blocks.

Merging: ask the owner before every merge (owner, 2026-11-28: "talk to me first before merging").

### Verified, waiting for the next merge

Batches 13-17 merged 2026-11-28 (see CHANGELOG.md; batches 15-17 landed as 7e11cf8d). New lanes start from
`integration`. Waiting for batch 18:

- `netcommand` 01 (`agent/netcommand-20261128-093130`, built on busyheartbeat): Doom's "Unknown net command" crash after a long
  frozen save fixed; lands the busyheartbeat work (saves wait out Daggerfall). Verified 2026-11-28. Its test script killed every
  Daggerfall Unity (crashed the owner's game); fixed in a48bf820.
- `weaponmods` 01 (`agent/weaponmods-20261128-092715`): weapon mod packs in shops and loot at about 1/25 the rate of guns. Verified
  2026-11-28; a used, unfitted pack moves to Doom's ownership (question with the PO).
- `automaticspop` 01 (`agent/automaticspop-20261128-085803`): small explosion graphic on Automatics slow-band hits.
  Verified 2026-11-28.
- `gizmos` 01 (`agent/gizmos-20261128-085547`): DRLA X gizmos at about 2% of Doom pickup spots and in treasure piles.
  Verified 2026-11-28. Merge check: compare the pile rate with weapon mods' rate once `weaponmods` 01 lands.
- `interiordoors` 01 (`agent/interiordoors-20261128-064918`): report on whether interior doors exist and can lock.
  Verified 2026-11-28; its question is with the PO.
- `ammoprices` 01 (`agent/ammoprices-20261128-065910`): Regular ammo 3x its base reference, higher tiers by the table.
  Verified 2026-11-28.
- `luckdrops` 01 (`agent/luckdrops-20261128-064906`): Luck's extra ammo follows the dungeon pickup mix; guard kills
  roll, seeded per guard. Verified 2026-11-28.
- `encounters` 09 (`agent/encounters-20261128-073309`): local war rooms rigged like Civil War, asleep until the player
  opens the door. Verified 2026-11-28 with a paired run.
- `randomencounters` 01, dungeon part (`agent/randomencounters-20261128-072945`): rest ambushes in dungeons as mook
  packs at area level (rest_ambush 9/9). The outdoor and reputation-guard parts went to
  `work/refinement/randomencounters-01.md`. Merge check: the ambush plan takes 0.3-0.45 s on Doom's main thread after
  rest.

### Skills (rules in `work/backlog/skills-in-doom.md`)

- `shotgunpush` 01 (`work/queue/shotgunpush/01.opus.shotgun-knockback-by-true-fire-rate.md`), approved by the owner,
  2026-11-27, answered 2026-11-28: knockback about 10/20 ft extra at Shotguns 75/100. Continue from its branch. Medium priority (owner, 2026-11-28),
  unless shotguns turn out broken.
- Tutorial: when the Doomerfall tutorial is made (backlog, after the game is complete), it must explain buying skills
  with Skill XP.

### Movement and maps


### Bugs and small features


### Shops and encounters

- `shoplevels` 08 (`work/queue/shoplevels/08.opus.interior-quality-danger-and-armor-split.md`), approved by the
  owner, 2026-11-27: interiors take danger and loot from the building's quality (in and outside towns); leather and
  chain split Iron's slot, outside the stock limit.
- `outdoorguards` 01 (`work/queue/outdoorguards/01.opus.outdoor-guard-bots.md`), approved by the owner, 2026-11-27:
  crimes outdoors (failed pickpocket, a shot watchman) bring guard bots Doom can see, as indoor guards do.
- `questfoes` 01 (`work/queue/questfoes/01.opus.quest-foe-packs.md`), approved by the owner, 2026-11-27: quest foes in
  town buildings and quest ambushes as mook packs.

### Held until a condition is met (may start without asking once it is)

- `townoverhangs` 01 (`work/queue/townoverhangs/held/01.opus.town-overhang-3d-floors.md`): solid tops for town
  overhangs. Held until the owner reads the `mapgen` 01 proposal, which may solve it another way.
- `daynight` first-town season (owner, 2026-11-26: when weekly and current usage are both at or below 10%): in a
  winter save the first town after launch loads in summer textures, because Doom builds it before Daggerfall sends the
  season. Options in `work/notes/20261126-145333.md`.
- `qabot` 02 (`work/queue/qabot/held/02.opus.god-mode-gun-tester.md`): god-mode gun tester. When usage is at or below
  10% (weekly and current), or at night while the owner sleeps and nothing else is queued. QA bot runs are long and
  run only overnight, 2AM to 7AM.
- `corpsekeep` (`work/queue/corpsekeep/held`): corpses vanish on leaving and re-entering Privateer's Hold. First check
  whether the location record rewrite fixed it.

### Downtime work (owner, 2026-11-26: "Lower priority, but do during downtime")

- `skillconverter` 01 (`work/queue/skillconverter/01.opus.convert-out-of-date-skills.md`), approved by the owner,
  2026-11-27, low priority: convert out-of-date character sheets on load so old saves never break.
- `gunenchantments` 01 (`work/queue/gunenchantments/01.opus.gun-enchantments.md`), approved by the owner, 2026-11-27,
  low priority: guns accept weapon enchantments; damage enchantments use a 90x pool (3x per hit). After `enchantgunskills` 01.
- `enchantedguns` 01 (`work/queue/enchantedguns/01.opus.enchanted-gun-names.md`), approved by the owner, 2026-11-27:
  enchanted guns recognisable by name (research first). After `gunenchantments` 01.
- `attributes` 09 (`work/queue/attributes/held/09.opus.int-per-gun-enchantments.md`), approved by the owner,
  2026-11-27, low priority: Intelligence and Personality scale gun enchantments, multiplied with each other. After
  `gunenchantments` 01, before `attributes` 07.

### Lowest priority (owner, 2026-11-27)

- `monsterdps` 01 (`work/queue/monsterdps/01.opus.monster-dps.md`), approved by the owner, very low priority
  (2026-11-27): measure monster DPS against an erratically strafing player and price them by the square-law rule.
- `attributes` 05 (`work/queue/attributes/held/05.opus.speed-scales-climbing.md`), approved by the owner, 2026-11-27,
  lowest priority: Speed scales climbing.
- `attributes` 07 (`work/queue/attributes/held/07.sonnet.attribute-help-from-rules.md`), approved by the owner,
  2026-11-27, very low priority, only after every other attribute card is merged: correct the character sheet
  attribute help and add a check that catches drift.
- `damagestacking` 01 (`work/queue/damagestacking/01.opus.review-damage-stacking.md`), approved by the owner,
  2026-11-27, minimal priority (last in todo): review every damage bonus against "increased adds, more multiplies"
  and fix where appropriate.
