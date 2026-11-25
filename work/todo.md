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

### Quiet agent runs (owner, 2026-11-24): first priority

Agent and harness launches must never take the owner's mouse, focus, screen or sound, and every agent must use the quiet way (`work/queue/quiet`). Run it before other new lanes.

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
- Area level replaces player level everywhere (`work/queue/arealevelall`). The `ammotiers` lane it waited on is merged.

### From the quest and record surveys (owner, 2026-11-24)

- Show Daggerfall's quest follower faces on Doom's HUD. Rescued and escorted people stay hidden, as in Daggerfall (`work/queue/questfaces`).
- Light places where Daggerfall lights them: dungeon light records and light sprites (`work/queue/lights`). Ask the owner before falling back to baked sector light.
- Fix editor markers: remove the stray action record on passive castle guard markers, skip mobile type 99, and report the rest (`work/queue/markers`). Run after the `encounters` lane merges, because both touch the converter's enemy spawning.
- **Rework the Doom HUD: chat with the owner first.** No card yet and no lane takes it until the owner and orchestrator have talked it through. Owner request (2026-11-23): remove Doom's 2-3-4-5-6 weapon slot display, because guns come from Daggerfall hotkeys, and rework the HUD in general.
- Approved material odds for all loot: piles, shelves, containers, guild stock and enemy gear (`work/queue/oddseverywhere`). After `arealevelall` merges.

### Location state in Daggerfall (owner, 2026-11-24)

The owner approved the research's option C (`work/notes/20261124-105104-location-state-research.md`). Three cards in `work/queue/locationledger`, run in sequence after the `encounters` lane merges: stable place keys and changes only, the Daggerfall ledger for dungeons, then the ledger everywhere. The rebuild load is in the backlog.

### QA bot (owner, 2026-11-24)

Research a Daggerfall character that Claude can control for automated QA (`work/queue/qabot`). The research and its short prototype may run now. **QA runs themselves are long and run only while the owner sleeps (overnight lanes, 2AM to 7AM).** They are for Claude-run QA and finding bugs, not general testing or normal verification.

### Quest rewards (owner, 2026-11-24)

- Quest rewards are unscaled: treat the player as level 20 (`work/queue/questrewards`). After `oddseverywhere` merges.

### Shop and town levels (owner, 2026-11-24)

- Research shop levels (1-30, from size or quality) and the interim town exterior levels (5 small, 10 medium, 15 large, 20 capital), with proposed cards for owner review (`work/queue/shoplevels`). Planning only.

### Loading screen for long operations (owner, 2026-11-24)

Long operations must not block the main thread so that Windows shows the program as not responding. Build one generic way to run them: pause the game, show a loading message, keep the window responsive, and resume when the work is done. First use: re-entering a dungeon, where planning and spawning a cleared level-30 dungeon takes about 1.9 s (location record notes `work/notes/20261124-190017.md`). The owner accepts that wait once it shows the message and pauses. No card yet; the orchestrator writes one in `work/queue`. Then find the other long operations (bundled save and load, which blocks Daggerfall for 2-3 s, and map and town building) and list them in the card.
