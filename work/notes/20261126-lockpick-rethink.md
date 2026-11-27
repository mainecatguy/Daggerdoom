# Door locks: what went wrong conceptually, and the fix (2026-11-26)

The owner's question: lockpicking keeps breaking (cards 02 to 05), and adding locked objects should not be this
complicated. This run looked for the conceptual mistake and removed it.

## Finding 1: card 05's open failure was a stale install, not a door bug

Card 05 left `run_paired.py load` at 17/19 (a picked door came back locked, a lever-locked door came back unlocked).
Its install (`review\arrival-pause`, `install.py --keep-data`) copied its data from card 04's folder
(`review\autosave-setup`). Card 04 predates the location-record merge, so that folder's `ddruntime.pk3` holds a door
script with no `DFDoorHandler.Distill` or `Restore`:

| install | `zscript.zs` in `ddruntime.pk3` has `Distill` | has the lock field |
|---|---|---|
| `review\autosave-setup` (card 04) | no | no |
| `review\door-record` (card 03) | yes | yes |
| `review\arrival-pause` (card 05) | **no** | **no** |

The logs agree. `DoorRecord()` (dd_treadmill.cpp) finds no `Distill`, so the place record carries no door fact.
Card 05's load run: `DDLOC report D187853213 on leaving: 50 facts (... 50 items, 0 gone)`, then on re-entry no
`doors restored` line. Card 03's run of the same case: `51 facts (... 1 gone)` (the door fact counts as "gone" in that
log line) and `DFDOORS locks from the record: 2 of 58 doors differ`. The arrival freeze did not break anything.

Lesson for the harness: an install that keeps data must still refresh `ddruntime.pk3`'s door script
(`tools/lockpick/patch_runtime_doors.py`), or the run tests old code.

## Finding 2: the conceptual mistake (cards 02 to 04)

**"Do locks apply?" was treated as a fact Daggerfall delivers later, and it is not.** Doom already knows both inputs
at map load: the converted map holds each door's starting lock (`startingLock`), and whether Daggerfall is attached is
known before the map exists. But the design made every door start unlocked and wait for a Daggerfall round trip
(`dfdoor_facts` -> `DFB_KIND_DOOR_FACTS` -> Daggerfall checks it is in the same dungeon -> `DFB_DOOR_ARM` ->
`dfdoor_arm` -> `dfdoor_ready`) before it would lock, with a per-door `armed` flag to remember whether that had
happened.

That one choice created a window ("before the doors were armed"), and every bug since lived in it:

- Card 04: the arrival autosave landed inside the window -> a setup gate wait for "doors".
- Card 03: a save made inside the window -> the record's three-state lock field (none / `L` / `L...`), "a record
  made before the arm leaves live locks alone", and a re-ask for the arm after loading an unarmed save (a transient
  `ticked` flag, found only after a failed first try).
- Every reader of the lock had to check `armed` (actions 16/17/18/20, Distill, Restore, the harnesses).

The only real asynchronous input is the location record, and that is generic. It brings dead monsters, taken items and
door open bits by the same path, and the arrival wait already covers it (the `place` setup wait, and card 05's
freeze). Doors need nothing of their own.

A smaller second mistake: saved locks were keyed by door **index**, under a stamp of the whole DFDOORS lump, so any
converter change dropped every saved lock. Daggerfall's door LoadID is stable and already exported.

## The fix

- Every door's live lock is set from `startingLock` when the map is built (`DFDoorHandler.WorldLoaded`). The location
  record's door fact then applies the changes, when it arrives during the arrival wait.
- Locks **hold** only while Daggerfall is attached: `DFDoor.Toggle` skips the lock check unless
  `DFDoorHandler.LocksHold()`, which reads `dd_bridge_session`. That is a new CVar the bridge sets on attach
  (`dd_bridge.cpp`, 2 lines). One check in one place replaces the `armed` flag and its guards in `RunAction`. A
  converted map played alone, or a stock WAD, still never has a door nobody can open.
- The door fact's lock field is `<LoadID>.<lock>` entries for doors that differ from their starting lock. It is absent
  when none differ. `Restore` applies locks even when the DFDOORS stamp differs; only the open bits depend on the stamp.
- Removed: `armed`; the arm and facts protocol (`DFB_KIND_DOOR_FACTS`, `DFB_DOOR_ARM`, `dfdoor_facts`, `dfdoor_arm`,
  `dfdoor_ready`); the `doors` setup wait; the re-ask after load (`WorldTick`/`ticked`); Daggerfall's
  `OnFactsRequest`/`InDoomsDungeon`/`Update`; the `L` marker and its "never armed" meaning; the Doom-only harness's
  `--saveload` mode, which only tested the arm-on-load path.
- Kept: the setup gate (`dd_setup.cpp`), which still waits for the place record. Kept: card 05's arrival freeze. It
  still holds play while the place record is applied (and while any slow setup runs), though doors no longer need
  anything from it. It no longer covers the monster spawn on a normal entry (Finding 3).

### Size

Rough line counts (`wc -l`), before -> after:

| file | before | after |
|---|---|---|
| `tools/dungeon_converter/door_objects.zs` | 411 | 392 |
| `UZDoom/src/dd_doors.cpp` | 112 | 98 |
| `DoomerfallDoors.cs` | 170 | 136 |
| `bridge/doomerfall_bridge.h` (door block) | -2 constants | |
| `UZDoom/src/dd_bridge.cpp` | | +2 |
| Doom-only harness (`zscript.zs` + `run_doorgate.py`) | 313 + 114 | 254 + 69 |

Overall `git diff --stat` (code and tests, before these notes): 16 files changed, 143 insertions(+), 320 deletions(-).

## Results

Builds: UZDoom into `D:\dev\DoomDaggerfall-build\lockpick-rethink\uzdoom` (`zdoom.vcxproj -> ...\uzdoom.exe`, 0
errors). Daggerfall Unity `CliBuild result: Succeeded` (`daggerfall-unity-master/Logs/cli-build-rethink.log`, on the
private desktop; the Library was copied from the lockpick checkout to skip the import). `generate_bindings.py --check`:
up to date. **Fresh install with fresh data** (`install.py D:\dev\DoomDaggerfall-loop\review\lock-rethink --build-dir
D:\dev\DoomDaggerfall-build\lockpick-rethink`, no `--keep-data`). Its `ddruntime.pk3` was checked to contain
`LocksHold` and no `armed`. Later reinstalls used `--keep-data` from that same folder.

- Doom-only `run_doorgate.py --root ...lock-rethink`: alone `DGTEST done 3/3` (Use opens a door with starting lock 2,
  no ask), attached `DGTEST done 26/26`. Both also pass with `--drla` (only the 3 known DRLA script errors). The new
  checks: every door is at its starting lock when the map loads; the record keeps locks by LoadID
  (`3498d199 000000000000000 29550249.16,29539363.0`); a record from another conversion drops its open bits but keeps
  its locks.
- Paired (both games, minimized), take then load. Load checks after the load, then after leaving and re-entering:
  - pick: take `passed=12 failed=0`, load `passed=19 failed=0` (card 05 had 17/19 here).
  - lever: take `11/0`, load `18/0`.
  - relock: take `13/0`, load `20/0`.
- Early save. `entry` loads the take run's arrival autosave: `passed=2 failed=0` (`door 29539363 is locked after the
  load (lock 2 of 2)`, `1 of 1 lockable doors are at their starting lock`). It must run straight after `take`: a load
  run's own autosaves replace the arrival save it looks for.
- New Game (inside quiet_run): `passed=8 failed=0`, `lockpick: new character starts with 3`.
- Arrival freeze (`run_freeze.py`): slow `PASS` (2496 ms, `changed=0 monsters=73`), lost `PASS` (4996 ms, gate
  timeout), nosave `PASS`, use `PASS`. **normal `FAIL`, `freezes 0`**: see Finding 3.
- Stock: `run_paired.py check`: stock exit 0, 0 script errors, 0 fatal; DRLA exit 0, the 3 known script errors.
  `stock_autosave.py`: stock PASS, drla PASS.

## Finding 3: the arrival freeze covered the monster spawn only because of the door arm

Card 05 wrote that the dungeon's monster spawn tic "now runs inside the freeze". That was true only because the door
arm's Daggerfall round trip (~30 ms) held the setup gate open until the spawn tic. The encounter spawn is not a
setup system. With the arm gone, setup on a normal entry is done in under 10 ms (`place ready`), the freeze lasts a
few tics (`frozen 7 tics, 0.6 ms`), and `DDENC spawned 73 mooks` comes after it. As before card 04, the monsters
spawn in visible play, and the arrival autosave is taken before they exist. Loading that save re-plans them
(`entry` passes, and `DD_MonstersResync` re-asks on load).

- `run_freeze.py normal` therefore fails. No frame runs during a sub-millisecond freeze, so the test never snapshots.
  The slow, lost, nosave and use modes keep setup longer and still pass with all 73 monsters held.
- I tried making the encounter spawn a setup system (`DD_SetupWait("monsters")` on entering a bridged dungeon,
  `DD_SetupDone` after `SpawnEncounters`). Normal entries then froze about 440 ms and held the spawn. But in the New
  Game flow Daggerfall's monster list came about 5.4 s after the map loaded, so every New Game arrival waited the full
  5 s gate timeout behind "Loading...". I reverted it: it is not a door change, and it trades one problem for a visible
  one. It is a question for the owner (below).
- Same cause in the paired New Game run: the door cases began before the late spawn, and the spawned armies' civil war
  killed the test player during the hit. The harness now keeps clearing monsters while its door cases run
  (`harness.zs`, test only).

## Questions for the owner

- Should the arrival wait (card 05's freeze, and the arrival autosave) also wait for the dungeon's encounter spawn? It
  holds monsters still at spawn and puts them into the arrival autosave. The cost: in the New Game flow Daggerfall
  sends the monster list about 5 s late, so that arrival would show "Loading..." for 5 s unless that delay is found
  and fixed first. Without it (now), monsters appear in the first moments of visible play, as before card 04.

## Known gaps

- Lock and Open spells still write Daggerfall's hidden door, not Doom's (unchanged, card 01).
- Card 03's saved records, with an `L` lock field keyed by index, are not migrated. Card 03 never reached `main`.
- `dd_bridge_session` is a plain CVar so tests can set it. A player who sets it by hand in a game without Daggerfall
  gets locked doors that nobody answers.

## Play-test list

1. `D:\dev\DoomDaggerfall-loop\review\lock-rethink\play.bat`: you start at the locked door in Privateer's Hold. For
   the first 20 s Use is refused (no picks); then pick it (Fire on the white arc). Miss: one pick gone. Hit: it opens.
2. Leave by the entrance and come back: the picked door is still unlocked, other locked doors still say "Locked.".
3. Save, reload: still unlocked.
4. `play-newgame.bat` (normal game): enter a dungeon. Monsters now appear in the first moments of play rather than
   behind the arrival hold (Finding 3). Is that acceptable?
