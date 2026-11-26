# Lane hang: fake lane test and harness fix

Lanes did not log "Finished" until leftover test games were closed (2026-11-25/26, lockpick, daynight, skillcore all
finished at 11:38:29, the moment the owner killed their games).

## Cause

`queue.ps1` runs `run.ps1` as `& powershell.exe @runArgs *>> log`. PowerShell then reads `run.ps1`'s output through a
pipe until the pipe closes, not until `run.ps1` exits. Every process below `run.ps1` inherits that pipe:
`Start-Process` in `Invoke-Logged`, Claude's shell tools, and `quiet_run.py` (`CreateProcessW(..., bInheritHandles=True)`)
all pass inheritable handles on. A test game that outlives its agent (the agent's tool call timed out and killed
`quiet_run.py` but not the game, or the agent started it in the background) keeps the pipe open, so the lane waits
for that game to exit.

## Fix (`harness-fix.patch`, for `scripts/overnight/`, which agents may not edit)

- New `lane_job.ps1`, dot-sourced by both scripts. `Start-LaneChild` replaces `Start-Process` for these children:
  - The child inherits **only its three redirect files** (an explicit handle list). `Start-Process` in PowerShell 5.1
    passes on every inheritable handle the caller has, including PowerShell's own output pipe. Clearing the inherit
    flag on the standard handles was not enough: PowerShell holds another inheritable copy. A kept build helper below
    the child would then hold the caller's pipe open for as long as it lives (measured: 91.6 s, the fake helper's
    sleep, instead of 61 s).
  - The child starts suspended, joins a new Windows job, then runs, so nothing it starts escapes. Job membership passes
    to every descendant, even after its parent exits, and quiet_run's private desktop does not change that.
  - `.cmd`/`.bat` programs run through `cmd.exe /d /s /c` (claude here is `claude.exe`, but an npm install is a `.cmd`).
- `Stop-LaneJob` ends every process still in the job **except build helpers meant to stay open**, then closes
  the job without killing the rest. It returns the names it ended, and the scripts log them.
  - Kept (owner, 2026-11-26): `MSBuild.exe` (reuse nodes), `mspdbsrv.exe`, `VBCSCompiler.exe`, `vctip.exe`,
    `Unity.Licensing.Client.exe`, `Unity Hub.exe`, `conhost.exe` (ends by itself with its console program), and
    `dotnet.exe` only when its command line hosts `MSBuild.dll`, `VBCSCompiler.dll` or `rzc.dll`. The list is
    `$LaneJobKeep` at the top of `lane_job.ps1`.
  - A process is ended only if it is still in the job when it is opened, so a reused process id is never hit.
- `run.ps1`: `Invoke-Logged` runs each child (worker round, build check, verifier, reviewer) in its own job and ends
  its leftovers when it exits or times out. On a timeout it ends only the child itself and lets the job cleanup close
  the rest, so build helpers survive timeouts too (`taskkill /T` remains only for when no job could be made). The run
  log gets a line such as
  `Closed what round-1.log left running: python.exe, uzdoom.exe`.
- `queue.ps1`: `run.ps1`'s output goes to files (`queue-<lane>-run.log` and `.err`, appended to
  `queue-<lane>-output.log` afterwards), and the lane waits for `run.ps1` itself, not for a pipe. `run.ps1` also runs
  in a job, as a backstop if it dies before cleaning up; the queue log names anything this closes.

What was shown (tests below): the lane moves to its next card on time, no fake game survives, fake build helpers
survive, and a caller that reads the lane (or `run.ps1`'s `Invoke-Logged`) through a pipe sees it end on time even
while a kept helper runs. Not covered: a process that a child starts with "break away from job", or one started
outside the tree (Task Scheduler, WMI). Those are not closed and, if they inherited the caller's pipe some other
way, could still hold it open; neither happens in the tests.

Apply from the repo root with `git apply tools/lane_hang/harness-fix.patch`.

## Fake lane test

`run_fake_lane.py` builds a throwaway git repo in `%TEMP%\doomerfall-fake-lane`, copies a harness into it, and runs
`queue.ps1` on two cards with `fake_claude.py` in place of Claude. Each fake round leaves a "game" (a sleeping python
process that inherits handles) and a fake build helper (a small program named `MSBuild.exe`, built by the test), and
reports BLOCKED. PASS needs both cards to finish before the game would have ended, no game left afterwards, and every
fake build helper still running. It costs nothing and creates branches only in the throwaway repo.

```
python tools/lane_hang/run_fake_lane.py                                  # current harness: FAIL (hangs)
python tools/lane_hang/run_fake_lane.py --patch tools/lane_hang/harness-fix.patch --quiet-run   # PASS
```

`--quiet-run` starts the fake game through `quiet_run.py` on a private desktop, as real tests do. `--pipe` reads the
lane's output through a pipe and waits for EOF, as a background task does (the earlier patch: FAIL, held open by the
surviving fake helper; this patch: PASS).

## Timeout test

`run_timeout_test.py` applies the patch to a temp copy and calls the patched `Invoke-Logged` directly with a child
that never exits (about 65 s, its 60 s minimum wait). PASS needs a -1 return, the child and its fake game gone, and the
fake `MSBuild.exe` still running.

```
python tools/lane_hang/run_timeout_test.py          # PASS; the patch with taskkill /T: FAIL
python tools/lane_hang/run_timeout_test.py --pipe   # PASS (61 s); the patch using Start-Process: FAIL (91.6 s)
```
