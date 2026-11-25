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

- `resets`: done, **not merged** (owner, 2026-11-24). Its one change turned off DFU's scene cache wipe; the owner keeps the wipe. Its findings stay in `work/notes/20261124-190702.md`.

### Approved, ready to launch

- Running: `ammoinv` (critical): ammo does not appear in Daggerfall's inventory (owner play test, 2026-11-24). Card 02 after it: changing ammo type plays DRLA's reload, and the new type is loaded when it finishes.

- `flatcollision`: Daggerfall sprites such as braziers keep their original collision (owner, 2026-11-24). Waiting for a free lane.
- `doorsolid`: open doors are solid; reverses the earlier match with Daggerfall; door and parity tests update to the new rule (owner, 2026-11-24). Waiting for a free lane.
- `hotkeyunique`: hotkeying an item removes its other hotkeys (owner, 2026-11-24). Waiting for a free lane.
- `corpsekeep`: corpses vanish on leaving and re-entering Privateer's Hold (owner play test, 2026-11-24). **On hold** (owner): first see whether the location record rewrite fixes it. Card in `work/queue/corpsekeep/held`.
- `mainquestlevels`: main quest dungeons get levels from the main quest order; Privateer's Hold is level 1 with a humanoid theme (owner, 2026-11-24). Waiting for a free lane.
- `mapkeys`: Doom's forward, back and strafe keys pan Daggerfall's map screens (owner play test, 2026-11-24). Waiting for a free lane.
- `liftcollision`: moving objects (lifts, raising platforms, the Privateer's Hold throne dais) have no collision to stand on; solve it as a general problem (owner play test, 2026-11-24). **Not started**: owner will say when.
- `housepickups`: Doom health and ammo pickups appear in houses (owner play test, 2026-11-24). Waiting for a free lane.
- `quietlog`: no debug messages on screen in normal play, for example on weapon switches (owner play test, 2026-11-24). Waiting for a free lane.

### Proposed cards waiting on owner choices

- Quest types: 11 cards in `work/queue/quests/proposed`.
- Shop and town levels: 4 cards in `work/notes/20261124-124736-shoplevels-cards`, waiting on the shop level formula, town classes, restocks and house levels (`work/notes/20261124-124736-shop-levels.md`).

### Not cards yet

- **Rework the Doom HUD: chat with the owner first** (owner, 2026-11-23): remove Doom's weapon slot display, because guns come from Daggerfall hotkeys, and rework the HUD in general.
- **QA bot runs** are long and run only overnight, 2AM to 7AM.
- **Lightweight location record** is being built in its own session (`claude/location-record-d20944`).
