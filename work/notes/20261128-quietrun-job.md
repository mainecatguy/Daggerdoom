# quiet_run.py: every launch in a job object (2026-11-28)

Owner-approved fix for test games outliving their timeout, and for the kill-by-name cleanups that crashed the
owner's game.

## What changed

- `scripts/overnight/quiet_run.py` starts every launch (private desktop and `--user-desktop`) suspended, puts it in
  its own job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, then resumes it. Everything the program starts joins
  the job, including games a .bat starts with `start` and then exits.
- quiet_run returns only when the program and every process in the job have exited
  (`JobObjectBasicAccountingInformation.ActiveProcesses == 0`), with the program's own exit code. On timeout it calls
  `TerminateJobObject` and exits 124. If quiet_run is killed, its job handle closes and Windows ends exactly that set.
- The private desktop stays open until the whole job is done (it used to close when the main process exited).
- CLI, quiet arguments, minimizing (still the main program's windows only) and exit codes are unchanged. One small
  difference: `--user-desktop` now starts the program with the same `CreateProcessW` call as the private path, so it
  inherits handles like the private path does (child output reaches a caller's pipe).
- `scripts/overnight/verifier.md` fails, and `reviewer.md` flags, any change that adds a kill by program name or by a
  filter that can match processes it did not start.
- Removed two kill-by-name/filter cleanups that the job now covers: `tools/item_pickup/item_pickup.py` (stopped every
  process whose path was under its review folder) and `tools/hp_sync/run_hp.py` (a dead `taskkill /IM` line).
- New test: `tools/quiet_probe/job_test.py`.

## What callers must know

- A script that only starts a game (`start`, a launcher that exits) used to return at once. It now waits for the game.
  Always pass `--timeout`.
- A caller that read output with `capture_output` could hang until orphans holding its pipe exited; now the job ends
  them at the timeout, so that hang is gone.
- To stop a launch early, kill the quiet_run process by its pid (or use `taskkill /T /PID` on it). Never by name.

## Host job and nesting

The Claude Code host already runs agents inside a job: `IsProcessInJob(GetCurrentProcess(), NULL)` is true for python
started from both the Bash and PowerShell tools. Nested jobs (Windows 8+) work: quiet_run inside quiet_run, and the
launcher's own job inside quiet_run's job, both passed below.

## Tests

1. Baseline, the old script from a copy, harmless sleepers (a copy of ping.exe named `qrsleeper.exe`):
   `python quiet_run_orig.py --timeout 200 -- python test_quietrun.py quiet_run_orig.py` gave 2/11: quiet_run returned
   after 0.1 s, timeouts left the sleeper running, and killing quiet_run left it running.
2. New script, from a scratch copy, then the real file:
   `python scripts/overnight/quiet_run.py --timeout 200 -- python tools/quiet_probe/job_test.py` gave 11/11, on both
   desktops: waits for the `start`-ed child (3.2 s for a 4-ping sleeper, exit code 7 from the .bat); `--timeout 2`
   ends it and exits 124 in 2.1 s; `taskkill /F /PID <quiet_run pid>` (no /T) ends it; nested quiet_run timeout and
   normal finish; a same-name sleeper started outside quiet_run survived everything. The test is itself run inside
   quiet_run, so it was nested two and three jobs deep. `loud_launch_lint.py` warns that the test passes
   `--user-desktop`: it must, to test that path, and it runs on a private desktop because it is wrapped in quiet_run.
3. UZDoom startup: `quiet_run.py --timeout 120 -- uzdoom.exe -iwad GameResources\wads\DOOM.WAD -norun -stdout` exit
   1337 on the private desktop and with `--user-desktop`.
4. UZDoom timeout: `+map e1m1` with `--timeout 6` exited 124; our UZDoom was gone, and two UZDoom processes started by
   others (pids 26024, 29536) kept running.
5. Paired launcher: `quiet_run.py --timeout 40 -- review\netcommand\doomerfall-launcher.exe --minimized ...` started
   UZDoom (pid 10952) and Daggerfall Unity (pid 48576) inside the job (the launcher's own job nested fine), exited 124
   at 40 s, and both were gone afterwards; unrelated UZDoom pids 29536 and 40504 survived.

## Remaining process kills in tools/ and scripts/

No other `taskkill /IM`, `Stop-Process -Name`, module or window-title filter, `killall` or `pkill` remains. The other
kills are by pid or by a handle the script started. Name-filtered listings remain that only read
(`tools/dungeon_reentry/catch_stall.py`, `tools/lane_hang/*`): they find their own processes by command line and do
not kill by name.
