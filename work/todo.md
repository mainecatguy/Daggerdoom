# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

The owner approved this work on 2026-11-23. Each item runs from its reviewed card in `work/queue`.

**Owner decisions on the research (2026-11-23):**

- Each Doomerfall save is one bundled UZDoom `.zds` file using Doom's save and load menus. It must still make a real Daggerfall save and carry it in the bundle.
- After death, show Doom's death view, then a screen offering Load Last Save, Load Game, and Main Menu.
- New Game temporarily uses one difficulty prompt after Daggerfall character creation and a fixed default Doom class. See "Full Daggerfall new game flow" in the backlog.
- Leave quick keys and quit behavior alone for now.
- Autosaves on Daggerfall maps use the bundled save. Their frequency can be revisited if they slow the game down a lot.
- Doom's Use button is the interaction button. It triggers Daggerfall's Grab action, or Steal while crouching, as well as Doom's normal use.
- Dungeons have a difficulty level (area level) from 0 to 30, and loot and encounter systems must be compatible with it.

### Mook packs: the encounter module (owner, 2026-11-24)

Pulled in now, ahead of MVP. Replace the one random enemy per Daggerfall placement with deterministic Doom packs. The approved design is `work/notes/20261123-205402-fractal-encounter-variety.md`. Seven cards run in sequence in `work/queue/encounters`: monster pool and data file, planner genome and army, budget with squads, bosses, and titans, area facts from Daggerfall, mook placer, Civil War factions, and whole-system checks.

- Doom owns the spawning algorithm and must be deterministic, with a seed built only from the place. Two players in separate games get the same spawns in the same dungeon.
- **Hard requirement:** each encounter's leader stands exactly where Daggerfall would have spawned its monster. The leader is the only mook Daggerfall counts, for its drops and quest completion. It is the highest-point monster that fits there, or the cheapest monster if none does.
- Every placement keeps at least one monster. Points that do not fit are never lost.
- Packs are expanded into concrete classes, never `RandomSpawner`, which uses Doom's shared random generator.
- Dungeons only. Outdoor and town enemies keep today's spawning.

### New Game start polish (owner, 2026-11-24)

Three cards in `work/queue/newstart`, run in sequence:

1. Remove the Reflexes choice from character creation and run as if Normal was chosen (`01`).
2. Start new characters at Daggerfall's real Privateer's Hold start point, not the entrance (`02`).
3. Make a normal bundled save once a new game has arrived at the start (`03`).

### Quest types: survey and per-type cards (owner, 2026-11-24)

Find every kind of quest in the game and plan how to make each work, starting with one proposed card per quest type. Also answers whether any quest depends on NPCs moving. Planning only. Card: `work/queue/quests/01.opus.quest-type-survey.md`. Its proposed cards go to `work/queue/quests/proposed` for owner review.

### Daggerfall data record types: survey and review cards (owner, 2026-11-24)

List every record type in Daggerfall's game data that matters here, how Doomerfall handles each today, and one proposed review card per group of gaps. Planning only. Card: `work/queue/records/01.opus.record-type-survey.md`. Its proposed cards go to `work/queue/records/proposed` for owner review.

### Second group from the backlog (owner, 2026-11-24)

Each has one card. The owner confirmed the assumptions on 2026-11-24. Run 3 to 4 lanes at a time.

- NPC damage and death, following Daggerfall's rules (`work/queue/npckill`).
- Load plain Daggerfall saves with default Doom data and the owner's starting weapon rule (`work/queue/plainsaves`).
- Restore autosaves on stitched location changes (`work/queue/autosaves`).
- Research whether Daggerfall needs to own permanent location state, with a class map and the theory tested against the code, for the owner to review (`work/queue/locationstate`). The implementation card is held until the owner decides.
- Area level replaces player level everywhere (`work/queue/arealevelall`). The `ammotiers` lane it waited on is merged.
