# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

Owner decisions from earlier runs are recorded in `CHANGELOG.md`, `architecture.md` and `gamedesign/decisions.md`.

### Queued (owner, 2026-11-25)

- Arrival wait covers the dungeon's monster spawn (owner, 2026-11-26: "fix this tonight"). Since the door arm was removed (lockpick rethink, merged), a normal dungeon entry's setup is done in milliseconds, so the arrival freeze ends before `DDENC spawned`. Monsters then appear about 0.1 s into visible play, and the arrival autosave is written before they exist. `run_freeze.py normal` fails. First find why Daggerfall's monster list arrives about 5 s late in the New Game flow. Then register the encounter spawn with the setup gate: `DD_SetupWait("monsters")` on bridged dungeon entry and `DD_SetupDone` after `SpawnEncounters` in `dd_monsters.cpp`. A trial of exactly that worked on normal entries (a ~440 ms hold, spawn inside the freeze) but hit the 5 s gate timeout in New Game. Done when: `run_freeze.py normal` passes with the 73 monsters held; a New Game arrival does not wait for the gate timeout; the paired lockpick take/load/entry/newgame runs still pass. Details: `work/notes/20261126-lockpick-rethink.md`, Finding 3.

### Skills (owner, 2026-11-25; rules in `work/backlog/skills-in-doom.md`)

In order. Lanes `skillresearch`, `skillcore`, `skillperks`, `skillmenu`, `levelup` in `work/queue`.
- `lightcarbine` 01 (owner, 2026-11-26): the Light Carbine (semi-auto Battle Rifle, +20% damage) in the Doomerfall mod, working without DRLA; half of the assault-rifle monsters' Battle Rifle drops become carbines.
- `startgun` 01 (owner, 2026-11-26): a new character's starting gun follows the highest weapon skill and replaces the starter pistol. After `skillcore` 01, 03, 04 and `lightcarbine` 01.
- `skillperks` 01 to 05: Jumping (adds fall damage first), Automatics, Explosives, Shotguns, then Pistols (no rifles).
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
- `noclass` 01 (`work/queue/noclass/01.opus.no-drla-class.md`), approved by the owner, 2026-11-26: no DRLA class menu and no DRLA class perks in bridged games. Then `noclass` 02 (owner, 2026-11-26): the fist always on hotkey 1, not unbindable, not in the Daggerfall inventory.


- `dmgnumbers` 01 (`work/queue/dmgnumbers/01.opus.damage-numbers.md`), owner, 2026-11-26: "show damage numbers"
  option over hit enemies, off by default, on by default with a dev flag. Check for an existing one first.

### Ammo (owner, 2026-11-26)

- `ammopile` 01 (`work/queue/ammopile/01.opus.ammo-pile-look.md`), approved by the owner, 2026-11-26: dropped ammo
  looks like that ammo and is remembered; mixed piles use the loot pile graphic.
- `ammoname` 01 (`work/queue/ammoname/01.opus.plain-regular-ammo-name.md`), owner, 2026-11-26, not urgent: run it at night while the owner sleeps. Regular ammo is just "Bullets", "Rockets", "Energy Cells", no "Regular".

### Fixes and small features (owner, 2026-11-26)
- `takenpickups` 01 (`work/queue/takenpickups/01.opus.daggerfall-remembers-taken-pickups.md`), approved by the
  owner, 2026-11-26: Doom reports taken seeded pickups by ID and Daggerfall keeps them gone.
- `weapontypes` 01 (`work/queue/weapontypes/01.opus.weapon-types-in-description.md`), approved by the owner,
  2026-11-26: weapon descriptions show name and types ("Plasma Rifle. Types: Energy, Automatic"). After `rifletag` 01
  and `skillcore` 05.

### Overworld (owner, 2026-11-26)
- `terrainflats` 01 (`work/queue/terrainflats/01.opus.overworld-terrain-objects.md`), approved by the owner,  2026-11-26: Daggerfall's terrain objects in the overworld, town surroundings and dungeon exteriors, procedural and  never saved.
- `distantlod` 01 (`work/queue/distantlod/01.opus.distant-terrain-lod.md`), approved by the owner, 2026-11-26:  distant terrain view in the wilderness and dungeon exteriors.

### Movement and maps (owner, 2026-11-26)

- `climb` 03 (`work/queue/climb/03.opus.climb-steep-stairs.md`), approved by the owner, 2026-11-26: climbing stays
  engaged on steep stair-like surfaces such as Privateer's Hold's cliff.
- `dungeonedges` 01 (`work/queue/dungeonedges/01.opus.diagonal-and-ramp-collision.md`), approved by the owner,
  2026-11-26: diagonal edges and ramps instead of jagged grid steps in dungeon collision.

### Attributes and fixes (owner, 2026-11-26)

- `attributes` 01 to 04 (`work/queue/attributes/`), approved by the owner, 2026-11-26, in order: Strength and Speed
  (and the manual's Attributes section), Agility, Willpower, Luck.
- `weatherseam` 01 (`work/queue/weatherseam/01.opus.streamed-terrain-texture-and-light.md`), approved by the owner,
  2026-11-26: streamed-in terrain keeps the snow ground texture and natural lighting.
- `maptextinput` 01 (`work/queue/maptextinput/01.opus.daggerfall-text-boxes-get-keys.md`), approved by the owner,
  2026-11-26: Daggerfall text boxes get all keys (map Find).
- `restsync` 01 (`work/queue/restsync/01.opus.hold-view-after-rest.md`), approved by the owner, 2026-11-26: hold the
  Doom view after rest or loiter until NPCs are in place.

### Bugs from play (owner, 2026-11-26)

- `outdoortalk` 01 (`work/queue/outdoortalk/01.opus.talk-to-outdoor-npcs.md`), approved by the owner, 2026-11-26: talking to generic outdoor NPCs works.
- `menubackdrop` 01 (`work/queue/menubackdrop/01.opus.doom-view-behind-menus.md`), approved by the owner, 2026-11-26: the Doom view shows behind small Daggerfall menus.
- `looklabel` 01 (`work/queue/looklabel/01.opus.item-names-in-look-labels.md`), approved by the owner, 2026-11-26: look labels show item names; no phantom "You got a pickup" label.

### Encounters (owner, 2026-11-26)

- `mainquestlevels` 01 (`work/queue/mainquestlevels/01.opus.main-quest-levels.md`), approved by the owner,
  2026-11-26: main quest dungeon level overrides in quest order; no invisible enemies in Privateer's Hold; plain
  Former Humans only there.
- `mainquestlevels` 02 (owner, 2026-11-26, "take a card"): Privateer's Hold's first enemy room (just outside the
  starting cave) holds Former Humans who drop battle rifles, no chaingunners. Runs after 01 in the same lane.

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
