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

### Fix first use of a town door (running)

Owner report (2026-11-23): the first use of a town door shows a message such as "opening" but does not work. After waiting a few seconds, using the door again loads the map.

### Autopickup  [Rework Doom autopickup](backlog/rework-doom-autopickup.md): As long as doom and daggerfall are running together, only health and ammo pick up by touch.
Other items need to be picked up.

### Enable the remaining hinged trapdoors

Owner decision (2026-11-23): getting stuck is not a concern during testing, because the owner has noclip, so this does not need to wait for climbing. Fix and enable the other 19 main quest tiles first, then the roughly 2,560 in other dungeons. Include the known broken walking surface and the Mantellan Crux record 46 chain that did not fire. Needs a card.

### Piles and containers and trade
Piles and containers open Daggerfall's real loot window as do NPCs when interacted with in modes that correspond to Daggerfall modes appropriately.

## Steal Mode
Daggerdoom does not have a separate steal mode button. Instead, when crouching,  you are "Sneaking".
For now: Show a message on the bottom of the screen that says this when crouching. 
Functionally, when using the interaction hotkey, perform Daggerfall actions in the Steal mode while crouching.
Next, make a list of features that need to be added for stealing. (E.g. can the player steal from NPCs, from their chests?) This may be one or two cards but it may be more based on what stealing does.

##Info Mode
Make a doom keybind for an info interaction. This triggers inspecting an item in Info mode as Daggerfall. If necessary, pause both games while interacting. The message popup should show in doom.


## NPC Dialogue (After Stationary NPCs)
NPCs should be interactible. An interact key should be added to Doom. 


### Recheck Daggerfall's reported location after New Game

Owner report (2026-11-23): with the Doom player in the overworld, Daggerfall's info button said "You are in Privateers Hold" while the character appeared to be in the wilderness. The cause is unknown, and the test start may be involved. Recheck with a character made through the real New Game flow, then find and fix the cause if it still happens.

### Report monster deaths to Daggerfall (running)

Each replaced monster gets an ID that can later cover a pack of mooks. Its death is reported to Daggerfall, which should update quests, fire death events and produce Daggerfall drops in doom. Runs after item pickup, so drops can use its path.

### Show stationary NPCs in Doom

NPCs, including wanderers, appear standing still with their real sprites and stable IDs. Talking, damage, and behavior are separate backlog tasks.

### Daggerfall publishes character skills to Doom

Daggerfall keeps Doom informed of the character's skills through shared memory. Daggerfall stays the authority. Depends on the generated bridge definitions.

### Climb function in Doom

Initial release target, to start fairly soon. Doom gets a climb function that uses the Daggerfall character's real climbing skill and matches Daggerfall's rules for starting, continuing, and failing a climb. Start from `FrictionMotor.cs` and `ClimbingMotor.cs`. Weapons stay usable while climbing (owner, 2026-11-23). Depends on skill publishing and three remaining owner decisions in `work/questions.md`. The research is in `work/notes/20261123-171304.md` on `integration`.

