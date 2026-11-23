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


### Generate the C# bridge definitions (highest priority)

Owner decision (2026-11-23): `bridge/doomerfall_bridge.h` is the single definition of the bridge. A script generates the C# side, and a normal build fails if the generated file is stale. Do this before further bridge work, starting from `integration` once position sync is merged. The card is `work/queue/bridge/01.opus.generate-bridge-definitions.md`.

### Piles and containers and trade
Piles and containers open Daggerfall's real loot window as do NPCs.


## NPC Dialogue (After Stationary NPCs)
NPCs should be interactible. An interact key should be added to Doom. 


### Sync player position at about 10 Hz, including indoors (running)

Daggerfall's hidden player follows the Doom player at about 10 updates per second in towns, the wilderness, interiors, and dungeons, so Daggerfall's map shows the right place. Measure the overhead.

### Speed up town and interior transitions

Owner request (2026-11-23): going between towns and interiors works, but with big stuttering. Find where the time goes and make it much smoother. Measure with the connected Daggerfall transitions in place.

Scripted timings so far: entering a converted building takes 44 to 84 ms, returning to the City of Daggerfall group takes 1.8 to 2.5 s, returning to the Gothway Garden group takes 0.66 to 1.4 s, entering Privateer's Hold takes 0.32 to 0.58 s, and a first interior conversion takes 4 to 8 s in the background. Returning to the big city is the slowest common step, and its cause is unknown. It is also slower than the 1.0 s recorded for walking into that city.

These timings come from the fastest consumer SSD available, so they are a best case. Players will have slower drives. Measure CPU and disk time separately, and do not accept a fix that only feels smooth because this drive is fast. Reduce how much is read and rebuilt on each transition, and estimate how the result holds up on a slower SSD.

Owner's suggestion, not a required solution: keep the town cached in memory while the player is in an interior, even if Doom can only run one map at a time, so returning does not rebuild it from scratch.

### New Game through Daggerfall's real menus

New Game runs Daggerfall's real character creation and cutscenes inside Doom, then a temporary difficulty prompt and fixed Doom class, and starts in Privateer's Hold.

### Pick up Daggerfall items from inside Doom and Daggerfall Interaction
As one task:
Interaction should be generic. Doom should have an interact button that works like daggerfall's.
Daggerfall items appear in Doom, and Interact puts them into the real Daggerfall inventory. 

### Report monster deaths to Daggerfall

Each replaced monster gets an ID that can later cover a pack of mooks. Its death is reported to Daggerfall, which should update quests, fire death events and produce Daggerfall drops in doom. Runs after item pickup, so drops can use its path.

### Show stationary NPCs in Doom

NPCs, including wanderers, appear standing still with their real sprites and stable IDs. Talking, damage, and behavior are separate backlog tasks.

### Document the shared memory bus

Write one document that shows where the Daggerfall and Doom shared memory bus lives and how it is organized: the shared state, events, surfaces, owners, and where to add a field. Run it after the map and position sync lanes land, because both change the bridge. It comes before the skill and climbing tasks.

### Daggerfall publishes character skills to Doom

Daggerfall keeps Doom informed of the character's skills through shared memory. Daggerfall stays the authority. Depends on the bus document.

### Climb function in Doom

Initial release target, to start fairly soon. Doom gets a climb function that uses the Daggerfall character's real climbing skill and matches Daggerfall's rules for starting, continuing, and failing a climb. Start from `FrictionMotor.cs` and `ClimbingMotor.cs`. Depends on skill publishing. A read-only research card on Daggerfall's climbing rules is running first.

### Enable main quest trapdoors (running)

Owner decision (2026-11-23): trapdoors work as they do in Daggerfall. Enable the 4 static trapdoors in Wayrest and Lysandus' Tomb, and check the 3 existing action 8 trapdoor records in Wayrest. Their pits need climbing to escape until the climb function lands, so report any soft lock this creates.

### High-level code quality audit (running)

Review the code we have written, not vendored engine code. Is it unnecessarily complex, can it be simplified, and should it be? Keep this a high-level review with a short ranked list of recommendations. Do not change code.
