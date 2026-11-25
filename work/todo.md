# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

Every lane approved before 2026-11-24 evening has run and is merged. Owner decisions from earlier runs are recorded in `CHANGELOG.md`, `architecture.md` and `gamedesign/decisions.md`.

### Approved and running (owner, 2026-11-24 evening)

- `testhooks`: move test hooks out of game classes.
- `resets`: done, **not merged** (owner, 2026-11-24). Its one change turned off DFU's scene cache wipe; the owner keeps the wipe. Its findings stay in `work/notes/20261124-190702.md`.
- `doommaterial`: Doom weapons have a Daggerfall material (01), then the material damage bonus (02).
- `nodraw`: turn off Daggerfall's 3D world (milestone hurdle 4).

### Approved, ready to launch

- Running: `usekey` (critical): Doom's base Use key and Doomerfall's interact key are separate; they must be one (owner play test, 2026-11-24).
- Running: `ammoinv` (critical): ammo does not appear in Daggerfall's inventory (owner play test, 2026-11-24). Card 02 after it: changing ammo type plays DRLA's reload, and the new type is loaded when it finishes.
- Running: `newgameesc`: Escape during Daggerfall's New Game screens opens Doom's menus and breaks the game (owner play test, 2026-11-24).
- Running: `cleanlaunch`: the launcher's startup is a mess: Doom windowed, Daggerfall fullscreen, random timing (owner play test, 2026-11-24).

- `flatcollision`: Daggerfall sprites such as braziers keep their original collision (owner, 2026-11-24). Waiting for a free lane.
- `doorsolid`: open doors are solid; reverses the earlier match with Daggerfall; door and parity tests update to the new rule (owner, 2026-11-24). Waiting for a free lane.
- `quietlog`: no debug messages on screen in normal play, for example on weapon switches (owner play test, 2026-11-24). Waiting for a free lane.

### Proposed cards waiting on owner choices

- Quest types: 11 cards in `work/queue/quests/proposed`.
- Shop and town levels: 4 cards in `work/notes/20261124-124736-shoplevels-cards`, waiting on the shop level formula, town classes, restocks and house levels (`work/notes/20261124-124736-shop-levels.md`).

### Not cards yet

- **Rework the Doom HUD: chat with the owner first** (owner, 2026-11-23): remove Doom's weapon slot display, because guns come from Daggerfall hotkeys, and rework the HUD in general.
- **QA bot runs** are long and run only overnight, 2AM to 7AM.
- **Lightweight location record** is being built in its own session (`claude/location-record-d20944`).
