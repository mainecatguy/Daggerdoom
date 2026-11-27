# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

### Top priority (owner, 2026-11-26)

1. (`dungeonsupport` 01 merged 2026-11-27.)
2. (Merged 2026-11-27.) `storeammo` 01 (`work/queue/storeammo/01.opus.general-stores-sell-ammo.md`), approved by the owner, 2026-11-26:
   shops sell Doom ammo and restock it often; "basically an unplayable game rn until that happens".
3. (`loadscreen` 01 merged 2026-11-27.)
4. (`magicmenu` 01 merged 2026-11-27.)
5. `tabmenu` 01 (`work/queue/tabmenu/01.opus.tab-tween-menu.md`), approved by the owner, 2026-11-27: Tab opens the
   Skyrim-style tween menu to the character sheet, magic, map and inventory. After `magicmenu` 01.

Owner decisions from earlier runs are recorded in `CHANGELOG.md`, `architecture.md` and `gamedesign/decisions.md`.

### Queued (owner, 2026-11-25)


### Skills (owner, 2026-11-25; rules in `work/backlog/skills-in-doom.md`)

In order. Lanes `skillresearch`, `skillcore`, `skillperks`, `skillmenu`, `levelup` in `work/queue`.
- `skillperks` 01 to 05: Jumping (adds fall damage first), Automatics, Explosives, Shotguns, then Pistols (no rifles).
  (2026-11-27: 01 and 02 merged. 03 Explosives and 04 Shotguns ran out of budget, work on
  agent/skillperks-20261127-024745 and -033904. `shotsource` 01 merged 2026-11-27: continue 03 on it.)
- `killdrops` 01 (`work/queue/killdrops/01.opus.luck-ammo-drop-chance.md`), approved by the owner, 2026-11-27: Luck gives
  a 0-50% chance (Luck/2) for a kill to drop ammo; the old Luck-in-100 extra-ammo rule goes.
- `skillperks` 06, 07, 08, approved by the owner, 2026-11-26, in order: 06 Energy Weapons perks before burn
  (scaling, splash, projectile speed); 07 a general burn damage system with a separate fire effect; 08 burn on energy
  weapons (burn, conversion, explosion). After `skillcore` 01 and 05.
- `skillmenu` 01: skill purchase menu with visible perks, Skill XP from damage; revised card approved by the owner,
  2026-11-26 (research 02 answers are in the card).
- `skillmenu` 02: Daggerfall sound and message when a skill point is gained.
- `skillbasics` 01: Lockpicking, Pickpocket, Mercantile, Etiquette, Streetwise and Medical work and level as in
  Daggerfall (checks the `lockpick` lane's work; perks TBD).
- `skillbasics` 02: Running levels from time spent running in Doom, at 1.5x Daggerfall's rate (perks and speed TBD).
- `skillbasics` 03: Backstabbing, up to 5x damage to unaware enemies, levels 10x faster from sneak shots (perks TBD).
- Tutorial: when the Doomerfall tutorial is made (backlog, after the game is complete), it must explain buying skills
  with Skill XP.

### Input (owner, 2026-11-26)
(noclass 01 and 02 merged 2026-11-26.)



### Ammo (owner, 2026-11-26)


### Fixes and small features (owner, 2026-11-26)

### Overworld (owner, 2026-11-26)

### Movement and maps (owner, 2026-11-26)

- `dungeonedges` 01 (`work/queue/dungeonedges/01.opus.diagonal-and-ramp-collision.md`), approved by the owner,
  2026-11-26: diagonal edges and ramps instead of jagged grid steps in dungeon collision. (2026-11-27: owner accepts the improvement. Next: a real paired walk on a quiet machine. Run 3 beats the old map overall in Privateer's Hold (distance 16,969 vs 15,097, snags 19 vs 22, jitter 191 vs
  342) but one heading at 931,1490 has one extra slow tic; accept? Then a real paired walk on a quiet machine. Work on
  `overnight/dungeonedges`, notes `work/notes/20261127-035402.md`.)
- `collisionmetric` 01 (`work/queue/collisionmetric/01.opus.collision-fidelity-metric.md`), approved by the owner,
  2026-11-27: the collision fidelity metric that gates all converter collision changes. After `dungeonedges` 01 merges.
- `collisionshape` 01 (`work/queue/collisionshape/01.opus.grid-shape-refactor.md`), approved by the owner,
  2026-11-27: grid-shape refactor (byte-identical output), then better grid shapes judged by the metric. After
  `collisionmetric` 01.

### Attributes and fixes (owner, 2026-11-26)


### Visual parity (owner, 2026-11-26: "take this as a task to queue up and get started on")


### Bugs from play (owner, 2026-11-26)


### More from the owner (2026-11-26)

- `townscorpse` 01 (`work/queue/townscorpse/01.opus.daggerfall-deaths-and-corpses.md`), approved by the owner, 2026-11-26: killed townspeople, guards and other Daggerfall entities die with Daggerfall's animation and leave corpses, read from Daggerfall's files. (2026-11-27: waiting on the owner about outdoor watchmen; everything else built, work on `overnight/townscorpse`.)

### Shops (owner, 2026-11-26)

- `shoplevels` 01 (`work/queue/shoplevels/01.opus.shop-level-table.md`), approved by the owner, 2026-11-26: the shop level table by quality band.
- `shoplevels` 02 (`work/queue/shoplevels/02.opus.shelves-use-shop-level.md`), approved by the owner, 2026-11-26: shelves roll at the shop's level.
- `shoplevels` 03 (`work/queue/shoplevels/03.opus.town-danger-level.md`), approved by the owner, 2026-11-26: town danger level (higher of terrain and class) on the town's Doom map; never affects shop quality.
- `shoplevels` 04 (`work/queue/shoplevels/04.opus.building-wealth-levels.md`), approved by the owner, 2026-11-26: houses and guild halls take wealth from their own quality.
- `shoplevels` 05 (`work/queue/shoplevels/05.opus.ledger-shelves.md`), approved by the owner, 2026-11-26: shelves are a ledger, seeded restocks; Daedric findable and slow to rotate out.
- `shoplevels` 06 (`work/queue/shoplevels/06.opus.shop-identity.md`), approved by the owner, 2026-11-26: fixed shop identity: lean, breadth, rhythm, suppliers.
- `shoplevels` 07 (`work/queue/shoplevels/07.opus.story-lots-and-exceptions.md`), approved by the owner, 2026-11-26: story lots (Doom guns by tier, worn items) and rare exceptions.

### Encounters (owner, 2026-11-26)

- `passiveguards` 01 (`work/queue/passiveguards/01.opus.passive-guard-bots.md`), approved by the owner, 2026-11-27: passive castle markers and friendly entities become passive Doom guard bots that look like Daggerfall's guard.
- `randomencounters` 01 (`work/queue/randomencounters/01.opus.random-encounter-packs.md`), approved by the owner, 2026-11-27: Daggerfall's random encounters (rest ambushes, reputation guards) as mook packs at area level.
- `questfoes` 01 (`work/queue/questfoes/01.opus.quest-foe-packs.md`), approved by the owner, 2026-11-27: quest foes in town buildings and quest ambushes as mook packs.
- **On hold for the owner's go-ahead (owner, 2026-11-26: ready, but run it when it won't waste tokens; do not start
  until the owner says).** `monsterdps` 01 (`work/queue/monsterdps/01.opus.monster-dps.md`), approved by the owner, 2026-11-26: measure damage
  per second of non-EX Black and White monsters and DRLA bosses with an erratically strafing 500 HP player, and price
  them with the square-law rule. Raises BlackImp1's placeholder first.

### Waiting on an owner answer from finished work

### Held by the owner

- `daynight` first-town season (owner, 2026-11-26: on hold "until there are plenty of tokens", defined as weekly and current usage both at or below 10%; then it may run without asking): in a winter save the first town after launch loads in summer textures, because Doom builds it before Daggerfall sends the season; later area loads are correct. Options in `work/notes/20261126-145333.md`. The rest of day/night is merged.

- `liftcollision`: moving objects (lifts, raising platforms, the Privateer's Hold throne dais) have no collision to stand on; solve it as a general problem. Owner will say when.
- `corpsekeep`: corpses vanish on leaving and re-entering Privateer's Hold. First see whether the location record rewrite fixes it. Card in `work/queue/corpsekeep/held`.
- `flatcollision`: results merged; solid sprites moved to `work/future-ideas.md` as a distant-future idea (owner, 2026-11-25). Card held in `work/queue/flatcollision/held`.

### Waiting on an owner answer before a card

- nodraw follow-ups: Doom should not call Daggerfall stale during its known loading freezes; the hidden world radius should come from Doom's loaded area.

### Proposed cards waiting on owner choices

- Quest types: 11 cards in `work/queue/quests/proposed`.
- Shop and town levels: 4 cards in `work/notes/20261124-124736-shoplevels-cards`, waiting on the shop level formula, town classes, restocks and house levels (`work/notes/20261124-124736-shop-levels.md`).

### Not cards yet

- **Rework the Doom HUD: chat with the owner first** (owner, 2026-11-23): remove Doom's weapon slot display, because guns come from Daggerfall hotkeys, and rework the HUD in general.
- **QA bot runs** are long and run only overnight, 2AM to 7AM.
- `qabot` 02 (approved by the owner 2026-11-26): god-mode gun tester that equips guns, locks on and fights, reports damage and findings, roams and opens doors (`work/queue/qabot/held/02.opus.god-mode-gun-tester.md`). On hold (owner, 2026-11-26) until token usage and limits are low (weekly and current both at or below 10%), or at night while the owner sleeps and nothing else is queued; then it may start without asking. Long runs stay overnight.
- **Lightweight location record:** merged into integration (`claude/location-record-d20944`, 2026-11-25).

### Loading screen for long operations (owner, 2026-11-24)

Long operations must not block the main thread so that Windows shows the program as not responding. Build one generic way to run them: pause the game, show a loading message, keep the window responsive, and resume when the work is done. First use: re-entering a dungeon, where planning and spawning a cleared level-30 dungeon takes about 1.9 s (location record notes `work/notes/20261124-190017.md`). The owner accepts that wait once it shows the message and pauses. No card yet; the orchestrator writes one in `work/queue`. Then find the other long operations (bundled save and load, which blocks Daggerfall for 2-3 s, and map and town building) and list them in the card.

### Downtime work (owner, 2026-11-26: "Lower priority, but do during downtime")

- `traveloptions` 01 (`work/queue/traveloptions/01.opus.transport-menu.md`), approved by the owner, 2026-11-26: transport menu: foot, horse, cart, ship (downtime).
- `menufont` 01 (`work/queue/menufont/01.opus.daggerfall-menu-font.md`), approved by the owner, 2026-11-26: Daggerfall font in menus, texture packs for text (downtime).
- `signs` 01 (`work/queue/signs/01.opus.readable-signs.md`), approved by the owner, 2026-11-26: readable signs placed as in Daggerfall (downtime).
<!-- merge check (orchestrator): when merging traveloptions 01, board each ship (small and the large one at 5,5) and screenshot that the player lands on deck; the KIND_TRAVEL event sends no height (report 20261127-113137). Owner 2026-11-27: if it works, fine; if not, merge the rest and put ship boarding in the backlog. -->
