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

### Daggerfall holds Doom items (running)

Owner request (2026-11-23, very important): Daggerfall is aware of Doom items. A picked-up Doom item is held in Daggerfall's inventory and shows its Doom sprite. Plain Doom item types only for now, with a default weight. Materials and other systems come later, and real weights are in the backlog. Draft card: `work/queue/doomitems`.

### Doom weapon hotkeys (next, after Daggerfall holds Doom items)

Owner direction (2026-11-23): hotkeys come next, because until then picked-up weapons are hard to use. Doom holds only the active gun, given to it by the hotkey. Design: `work/backlog/doom-weapon-equipping-and-hotkeys.md`. All design questions are answered. Approved card: `work/queue/hotkeys`, starting after Doom items lands.


### Compute area levels in Daggerfall

The owner approved the area level proposal on 2026-11-23 (`work/notes/20261123-225515-area-level-proposal.md`, script in `tools/area_level/`). Daggerfall computes every location's area level, and the wilderness terrain level, at runtime from that formula, with the proposal's engineering notes on rank stability. Doomerfall's existing area level input (`-dfarealevel` in the enemy drops work) reads it. Replacing player level everywhere stays in the backlog. No card yet.

### Show area difficulty in the travel menu

Owner request (2026-11-23): players can see the area level of a place before they go, in Daggerfall's travel map menu. Show it as a hint or feeling instead of a number, on a scale like beginner, weak, moderate, very hard, legendary. Depends on "Compute area levels in Daggerfall". No card yet.

### Persistent townspeople (blocked: waiting on the owner's test-hook decision)

Two runs spent $14.82. The work is on `agent/townspeople-20261123-223832` (it holds everything). Passed: same people across launches, usual places, night, a death surviving save and load, a tavern round trip, leaving into the wilderness, and stationary NPCs. Open: test-only `-dftownreport` and `-dftownhour` hooks in `DoomerfallTownspeople.cs`, re-entering town from the wilderness, and Daggerfall city's size.

Owner decision (2026-11-23): wandering townspeople are persistent and deterministic. The same town always gives the same people from a fixed seed. Nothing is computed until the player first observes it. A living person's position is a periodic function of the seed and world time along a simple route around the places they hang out, so only deaths are recorded. Most people have a randomized daily schedule from the same seed, and they go home at night to a procedurally chosen house when possible. The owner's design is the intent, and a better way is welcome. Keep it simple and in its own file. Draft card: `work/queue/townspeople`. Runs before NPC Dialogue, since talking to a wanderer needs a stable identity.

### NPC Dialogue (next, after Persistent townspeople)

NPCs can be interacted with through Doom's Use button, which opens Daggerfall's real talk window. Draft card: `work/queue/dialogue`.

### Real Daggerfall drops from slain Doom enemies

Each slain Doom enemy drops what its corresponding Daggerfall enemy would have dropped, from that enemy's real drop table. Draft card: `work/queue/drops`. Blocked (2026-11-23): the code is on `agent/drops-20261123-212059` and passed a full audit against Daggerfall's tables, but the in-dungeon test harness never runs, so kills, piles, save, and re-entry are unverified. The harness fix lane (`work/queue/harness`) is running and finishes this verification.

### Fixed loot seeds for Daggerfall's random loot

Owner decision (2026-11-23): Daggerfall's random loot rolls use a fixed loot seed, so the same place always gives the same loot. Two players who loot the same pile or kill the same enemy get the same items. See "Fixed seeds, not per-save randomness" in `gamedesign.md`. No card yet.

- Cover every random loot roll: dungeon and building treasure piles (`LootTables.GenerateLoot`, `DaggerfallLoot.GenerateItems`) and enemy corpse loot (`LootTables.GenerateRandomLoot`, which today reseeds with `Random.InitState(items.GetHashCode())`, not a fixed seed).
- Build the seed only from fixed facts about the place, such as region, location, block, and the pile's or enemy's placement. Never use the save, the time, or the player. The loot seed is its own definition, separate from the seed later used for encounter theming.
- Restore Unity's shared random state after each seeded roll, so nothing else becomes deterministic by accident.
- Out of scope: the player-level inputs in these rolls (gold and material level). Until "Area level replaces player level" lands, results also depend on player level, gender, and race. Record that in the notes.
- Verify by rolling the same pile and enemy in two fresh games, or two runs of a test, and comparing the items.

## Steal Mode (running)
Daggerdoom does not have a separate steal mode button. Instead, when crouching,  you are "Sneaking".
For now: Show a message on the bottom of the screen that says this when crouching. 
Functionally, when using the interaction hotkey, perform Daggerfall actions in the Steal mode while crouching.
Next, make a list of features that need to be added for stealing. (E.g. can the player steal from NPCs, from their chests?) This may be one or two cards but it may be more based on what stealing does.

## Info Mode (running)
Make a doom keybind for an info interaction. This triggers inspecting an item in Info mode as Daggerfall. If necessary, pause both games while interacting. The message popup should show in doom.


### Climb function in Doom

Initial release target, to start fairly soon. Doom gets a climb function that uses the Daggerfall character's real climbing skill and matches Daggerfall's rules for starting, continuing, and failing a climb. Start from `FrictionMotor.cs` and `ClimbingMotor.cs`. Weapons stay usable while climbing (owner, 2026-11-23). Skill publishing is merged. Depends on three remaining owner decisions in `work/questions.md`. The research is in `work/notes/20261123-171304.md` on `integration`.

