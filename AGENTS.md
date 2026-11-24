# Doomerfall

## What we are making

This software project combines Daggerfall Unity with UZDoom. The design goal is simple: "daggerfall, but oops we replaced all the monsters with slaughter map sized packs from doom, and that ebony mace that dropped got converted to an energy machinegun from the doom roguelike arsenal extended mod, and when NPCs get angry at you they behave like Doom NPCs."

**Current status:** Exploratory, preliminary development.

For gameplay work, see `gamedesign.md`. For planned design changes, see `architecture.md`. If you are not working on gameplay or designing a system, it is not necessary to review these files.

Two pillars must survive every decision:

- **Daggerfall's world is the place the player will visit, and its engine needs to be the mediator and controller of most permanent game state.** What the player does stays done.
- **Combat and movement are Doom Engine based.** Fast, real-time, and tactical. We will use the Doom Roguelike Arsenal Extended mod.

## Repository map

| Path | Contents |
|---|---|
| `UZDoom/` | Vendored UZDoom 5.0.3 source. Combat, movement, rendering, and collision. |
| `daggerfall-unity-master/` | Daggerfall Unity (Unity 2019.4.41f2). World, RPG rules, quests, UI, and saves. |
| `gamedesign.md` | Game design rules. |
| `architecture.md` | Milestones, technical hurdles, and engine ownership. |
| `designgoals.md` | Original design goals. |
| `work/goal.md` | The current goal. Written with the owner and not committed. |
| `work/todo.md` | Owner-approved work that is ready to do automatically. |
| `work/backlog.md` | One-line index of work that needs owner input or depends on unfinished work. |
| `work/backlog/` | One detail file per backlog item. Open only the items you need. |
| `work/future-ideas.md` | Unplanned ideas for after the initial release. Never start these unless the owner asks. |
| `work/notes/` | Plans, findings, and play-test lists, one file per run. |
| `work/agent-reports.md` | Raw questions and oversights from overnight agents, awaiting orchestrator triage. Not committed. |
| `work/questions.md` | Triaged open questions for the owner. Managed by the orchestrator and not committed. |
| `work/suspectedoversights.md` | Triaged major oversights outside any agent's task. Managed by the orchestrator and not committed. |
| `GameResources/` | Local copyrighted game data. Never commit it. |
| `GameMods/` | Local Doom mods. Never commit it. |
| `GameMods/ExtractedData/` | Extracted DRLA Arsenal, DRLA Monsters, and DRLAX PK3s. Look here to see what is in the mods. Read-only. |

## Work tracking

- **Todo** is ready: approved by the owner, needing no owner input, and depending only on finished work or earlier todo items. Automated loops take work only from `work/todo.md`.
- **Backlog** is not ready. Never start backlog work unless the owner asks. New ideas and owner-accepted discovered work go here, as one index line in `work/backlog.md` plus a detail file in `work/backlog/`.
- Only the owner approves moving an item from backlog to todo. If a todo item turns out to be blocked, move it to the backlog and say what it is waiting on.

## Current milestone

Reach the MVP in `architecture.md`. First prove these hurdles are solvable:

1. Load generated Daggerfall areas into a running UZDoom without restarting.
2. Keep coordinates and world interactions in sync between engines.
3. Coordinate save, load, and death without desyncing.
4. Turn off Daggerfall's 3D world while its logic and 2D UI keep running.


## Engine ownership

- **Daggerfall owns:** world, time, travel, saves, stats, HP, death rules, status effects, quests, dialogue, economy, and loot rolls.
- **UZDoom owns:** the window, input, movement physics, 3D rendering, collision, weapons, projectiles, monster AI, and combat HUD.
- **Shared by contract:** damage, inventory translation, spells, doors and locks, stealth, and encounters. See `architecture.md`.

## Game design belongs to the owner

Claude makes ordinary engineering calls, and constrained judgment calls within a design the owner has provided. For example, given a drop table's tier and weapon-type rules, Claude can choose the individual weapon mappings.

Do not make wholesale game system design choices without the owner's preferences. This includes an engineering choice that would substantially change how the game plays. Finish what does not depend on the answer and ask the owner. If nothing useful remains, `BLOCKED` is an acceptable result. Do not guess to avoid it.

## Open questions for the owner

If you are talking with the owner and `work/questions.md` is not empty, present its questions at the start of the conversation. Remove each question once it is answered.

Worker agents never edit this file. In an overnight run, report questions through the `questions` status field. Otherwise, put them in a "Questions for the owner" section of your final report. The orchestrator triages them into this file.

@work/questions.md

## Suspected oversights

Report only major missed dependencies, missed gaps, or critical bugs that are outside your current task. Do not report minor issues, style, or ideas. Give what is wrong, the evidence, what it could break, and your confidence. Do not investigate further or fix it.

In an overnight run, use the `oversights` status field. Otherwise, use a "Suspected oversights" section of your final report. Worker agents never edit `work/suspectedoversights.md`. The orchestrator triages reports into it.

## Working rules

- Solve the assigned task and avoid unrelated refactors.
- Prefer the simplest approach that solves the problem.
- Inspect the real code and data before relying on an assumption.
- Report uncertainty and failed approaches honestly. A clear negative result is useful.
- Keep vendored engine changes small and easy to identify.
- Test hooks in game code are allowed behind a command-line flag, but use them sparingly. Put the test logic in its own file, such as a separate test component or a derived class, and keep the hook in a main class to a line or two, so agents reading that class do not load test code.
- Never commit game data or files derived from it, including generated maps and textures.
- Code changes go to the `integration` branch. Agents never push to or merge into `main`. Only the owner does that.
- The project owner is one person on a limited budget. Avoid wasteful builds, broad searches, and unnecessary subagents.
- The owner may be using the computer. When possible start programs minimized through: `python D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py --timeout <seconds> [--cwd <dir>] -- <program> <args>`. Add `-noactivate` to UZDoom's arguments to prevent focus stealing. UZDoom pauses in background so add `+i_pauseinbackground 0 +vid_activeinbackground 1 +vid_lowerinbackground 0` as well. Minimized frame rates are not necessarily real performance. Start paired games through the launcher with `--minimized`. Pass `-dfmute` when starting Daggerfall Unity directly, and use `quiet_run.py --desktop` for Unity and Daggerfall Unity. Between 2AM and 7AM, consider this rule relaxed.
- Keep in mind that your dev machine has an RTX 5080 and the fastest available solid state drive on the entire hardware market, so performances are kind of an upper bound, it's the best it's gonna do on any machine.

## Building

Run from the repo root. Build output stays outside the repo, in `../DoomDaggerfall-build`.

**UZDoom** (needs VS 2026 with C++ CMake tools, and Python 3):

```powershell
cmake -S UZDoom -B ../DoomDaggerfall-build/uzdoom -G "Visual Studio 18 2026" -A x64
cmake --build ../DoomDaggerfall-build/uzdoom --config Release --parallel 6
```

Startup check: run `uzdoom.exe -iwad <wad> -norun -nosound -stdout`. Exit code 1337 means success.

**Daggerfall Unity** (needs Unity 2019.4.41f2 on `PATH`). Build in windowed mode, because `-batchmode` fails its license check on this machine. A Unity window will open and close by itself. Close any editor using this project first.

```powershell
Start-Process Unity.exe -Wait -ArgumentList '-projectPath daggerfall-unity-master -buildTarget Win64 -executeMethod CliBuild.BuildWindows64 -logFile daggerfall-unity-master/Logs/cli-build.log'
```

Success means `daggerfall-unity-master/Logs/cli-build.log` contains `CliBuild result: Succeeded`. The game is written to `daggerfall-unity-master/Builds/Windows64/`, which git ignores.

## Verification

Run the real thing whenever practical: build it, launch it, execute a test, or measure it. Claims should cite the command, log, file, or data that supports them. Anything only a human can judge, such as game feel or visual quality, goes on the play-test list in the task notes.
