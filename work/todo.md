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

- `lockpick` card 02 (`work/queue/lockpick/02.opus.door-lock-bridge.md`): the door bridge step in one full run. Start the lane with `-From agent/lockpick-20261125-073553`. Thieves Guild sales are cancelled.
- `daynight` card 01 (`work/queue/daynight/01.opus.fog-sky-windows-winter.md`): distance fog, foggy sky, lit windows at night, winter textures. Starts from integration (the day/night branch is merged).
- `lanehang` card 01 (`work/queue/lanehang/01.opus.lane-hang-at-run-end.md`, approved by the owner 2026-11-26, "fix hang issue immediately"): lanes hang after a run ends until leftover test games are stopped. Starts from integration.


### Skills (owner, 2026-11-25; rules in `work/backlog/skills-in-doom.md`)

In order. Lanes `skillresearch`, `skillcore`, `skillperks`, `skillmenu`, `levelup` in `work/queue`.

- `skillresearch` 02: research Skill XP from monsters and skill purchase costs; proposes the menu card.
- `skillcore` 01: the new skills (Shotguns, Automatics, Explosives) in the slots of the monster languages, which are removed for now (owner, 2026-11-26). `skillcore` 03 then adds Pistols (owner, 2026-11-26: "pistols and rifles becomes just pistols", "no rifle is counted").
- `rifletag` 01 (owner, 2026-11-26): Doomerfall's own rifle tag on every DRLA rifle, after `skillcore` 01. Rifles get their own skill later (backlog: Rifles).
- `skillcore` 02: perk popup (pause and show what the perk is).
- `skillperks` 01 to 05: Jumping (adds fall damage first), Automatics, Explosives, Shotguns, then Pistols (no rifles).
- `skillmenu` 01: skill purchase menu with visible perks, Skill XP from kills. Gated on the owner approving research 02.
- `skillmenu` 02: Daggerfall sound and message when a skill point is gained.
- `levelup` 01: Daggerfall's level-up flow (rest, message, attribute points) shown and usable in Doom. Independent.
- `skillbasics` 01: Lockpicking, Pickpocket, Mercantile, Etiquette, Streetwise and Medical work and level as in
  Daggerfall (checks the `lockpick` lane's work; perks TBD).
- `skillbasics` 02: Running levels from time spent running in Doom, at 1.5x Daggerfall's rate (perks and speed TBD).
- `skillbasics` 03: Backstabbing, up to 5x damage to unaware enemies, levels 10x faster from sneak shots (perks TBD).
- Tutorial: when the Doomerfall tutorial is made (backlog, after the game is complete), it must explain buying skills
  with Skill XP.

### Waiting on an owner answer from finished work

- Main quest level table for the other main quest dungeons: `work/notes/20261124-202353-mainquestlevels.md`.

### Held by the owner

- `liftcollision`: moving objects (lifts, raising platforms, the Privateer's Hold throne dais) have no collision to stand on; solve it as a general problem. Owner will say when.
- `corpsekeep`: corpses vanish on leaving and re-entering Privateer's Hold. First see whether the location record rewrite fixes it. Card in `work/queue/corpsekeep/held`.
- `flatcollision`: results merged; solid sprites moved to `work/future-ideas.md` as a distant-future idea (owner, 2026-11-25). Card held in `work/queue/flatcollision/held`.

### Waiting on an owner answer before a card

- Mouse lost in Daggerfall menus: likely fullscreen Doom never releasing the mouse (`i_mouse.cpp`); fix waits on the owner confirming the cause.
- nodraw follow-ups: Doom should not call Daggerfall stale during its known loading freezes; the hidden world radius should come from Doom's loaded area.

### Proposed cards waiting on owner choices

- Quest types: 11 cards in `work/queue/quests/proposed`.
- Shop and town levels: 4 cards in `work/notes/20261124-124736-shoplevels-cards`, waiting on the shop level formula, town classes, restocks and house levels (`work/notes/20261124-124736-shop-levels.md`).

### Not cards yet

- **Rework the Doom HUD: chat with the owner first** (owner, 2026-11-23): remove Doom's weapon slot display, because guns come from Daggerfall hotkeys, and rework the HUD in general.
- **QA bot runs** are long and run only overnight, 2AM to 7AM.
- **Lightweight location record:** merged into integration (`claude/location-record-d20944`, 2026-11-25).

### Loading screen for long operations (owner, 2026-11-24)

Long operations must not block the main thread so that Windows shows the program as not responding. Build one generic way to run them: pause the game, show a loading message, keep the window responsive, and resume when the work is done. First use: re-entering a dungeon, where planning and spawning a cleared level-30 dungeon takes about 1.9 s (location record notes `work/notes/20261124-190017.md`). The owner accepts that wait once it shows the message and pauses. No card yet; the orchestrator writes one in `work/queue`. Then find the other long operations (bundled save and load, which blocks Daggerfall for 2-3 s, and map and town building) and list them in the card.
