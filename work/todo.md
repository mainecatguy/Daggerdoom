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

### Running

- `fixeddrops` and `doorsolid` card 04: run by the owner's own sessions. Leave alone.
- `ammosize` lane: ammo pickups and drops back to stock Doom amounts.
- `uselabels` lane, in order: NPC refusal message, building look, Doomerfall HUD text one size up (only our own
  messages, not global), look-at label (reuses the HUD text display from the card before it).
- `menus` lane, in order: New Game while playing, journal with hotkey.

### Passed, waiting for the owner's merge

- `expandedinv`: merged into integration 2026-11-24 23:31.

### Waiting on an owner answer from finished work

- Main quest level table for the other main quest dungeons: `work/notes/20261124-202353-mainquestlevels.md`.

### Held by the owner

- `liftcollision`: moving objects (lifts, raising platforms, the Privateer's Hold throne dais) have no collision to stand on; solve it as a general problem. Owner will say when.
- `corpsekeep`: corpses vanish on leaving and re-entering Privateer's Hold. First see whether the location record rewrite fixes it. Card in `work/queue/corpsekeep/held`.
- `flatcollision`: blocked. Daggerfall has no solid flag for sprites and Daggerfall Unity makes all of them walk-through, so which sprites block is the owner's call (`work/notes/20261124-201628.md` on `agent/flatcollision-20261124-201628`).
- `resets`: done, not merged (owner). Findings in `work/notes/20261124-190702.md`.

### Waiting on an owner answer before a card

- Mouse lost in Daggerfall menus: likely fullscreen Doom never releasing the mouse (`i_mouse.cpp`); fix waits on the owner confirming the cause.
- nodraw follow-ups: Doom should not call Daggerfall stale during its known loading freezes; the hidden world radius should come from Doom's loaded area.

### Proposed cards waiting on owner choices

- Quest types: 11 cards in `work/queue/quests/proposed`.
- Shop and town levels: 4 cards in `work/notes/20261124-124736-shoplevels-cards`, waiting on the shop level formula, town classes, restocks and house levels (`work/notes/20261124-124736-shop-levels.md`).

### Not cards yet

- **Rework the Doom HUD: chat with the owner first** (owner, 2026-11-23): remove Doom's weapon slot display, because guns come from Daggerfall hotkeys, and rework the HUD in general.
- **QA bot runs** are long and run only overnight, 2AM to 7AM.
- **Lightweight location record** is being built in its own session (`claude/location-record-d20944`).
