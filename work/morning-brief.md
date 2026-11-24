# Morning brief, 2026-11-24

## The demo
Run `D:\dev\DoomDaggerfall-loop\play\play.bat` and choose New Game. It is built from `integration` at `e85e351`
with fresh map data. Your saves and settings in its `run` folder were kept. The "what to try" list is at the top of
`play.bat`:

1. New Game: make a character in Daggerfall's creation screens. You wake in Privateer's Hold. Daggerfall's tutorial
   question and Brisienna's message now appear inside Doom. Answer them to continue.
2. Rooms hold a stimpack, clip, or shells. Kill a monster, look at its drop, and press Use.
3. Pick up a Doom gun with Use. If its number key is empty, it is drawn at once.
4. Press Q on a ground item or monster for Info.
5. Climb a wall: walk into it and keep pushing forward.
6. Leave the dungeon and walk into town. Townspeople walk the streets, and at night they are in their homes.
7. Use on a shopkeeper or a standing NPC opens Daggerfall's talk or shop menu. Walking townspeople can't talk yet.
8. Crouch and Use on shop goods to steal. If you are seen, Doom guards come.
9. Press K for the travel map, and hover a place to see its danger hint.
10. Save from Doom's menu, quit, restart, and load.

## Done overnight (all on `integration`, each after a full build check)
- Townspeople: persistent, and inside their homes on schedule.
- Doom items held in Daggerfall's inventory. Guns go in the Weapons & Armor tab, and the auto-hotkey and pickup rules are in.
- Weapon hotkeys. NPC dialogue and the shopkeeper menu.
- Runtime area levels, and the travel map danger hint.
- Info works like vanilla. Fixed loot seeds. Ground loot uses Daggerfall's pile sprites.
- Trapdoor shaft floors. Health and ammo pickups, 1 or 2 per room.
- Climbing, with Daggerfall's Climbing skill rolls.
- Hostile Doom guards after a theft.
- The installer now builds the map data itself, so a refresh needs no hand work.
- Showstopper fixed: after New Game, Daggerfall's own popups opened unseen and froze it, so talk, items, and hotkeys
  were refused. Doom now shows those windows.

## What was tested and what wasn't
- Every feature passed a scripted test with both games against the play folder. A scripted New Game to town walk
  talked to a shopkeeper. New Game save and load passed. Stock and DRLA E1M1 still load.
- Nobody has played the whole route by hand. Each scripted test started at its own point.
- The travel map has not been opened in a session with both games. Scripted key presses don't reach a minimized Doom window.
- Not checked: whether a caught theft brings guards without the test flag, or how the trapdoor floors look in the game.

## Where the project stands
The four MVP hurdles from AGENTS.md all have working answers: live area loading, position sync, joint save, load,
and death, and Daggerfall's 3D world turned off. Daggerfall's main gameplay systems are now reachable from Doom:
talking, shops, loot, theft, quests starting, travel, and climbing. The roughest spots are game feel, and NPC and
guard behavior.

## Held for you
- `work/needs-owner-review.md`: the cards I ran unread on your approval. Two were added overnight: a demo card, and a
  fix card for the New Game freeze.
- `work/questions.md`: should shop and house restocks be seeded, and how should Doom items be priced and sold?
- `work/suspectedoversights.md`: the most relevant one is that Daggerfall's hidden wanderer pool still runs in towns.
- **Fixed on 2026-11-24:** the main checkout is now up to date on `integration` (`e85e351`), with only your doc edits left uncommitted. A backup is in `D:\dev\DoomDaggerfall-loop\backup-main-checkout-20261124`. What the problem was: Last night something switched it from `main` to `integration` at `d9cb86d`. I then moved
  `integration` forward to `e85e351` without updating that checkout. Its files are still at `d9cb86d`, so `git status`
  shows about 130 staged changes that are just the reverse of the night's merges. Nothing is lost. On top of that sit
  your uncommitted doc edits: AGENTS.md, architecture.md (the small-context principle), CHANGELOG.md, and the work
  files. I left it alone because fixing it rewrites your working copy. Tell me which branch you want it on, and I'll
  carry the doc edits over.
