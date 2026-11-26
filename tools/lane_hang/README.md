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

- `run.ps1`: `Invoke-Logged` puts each child (worker round, build check, verifier, reviewer) in a Windows job. Job
  membership passes to every descendant, even after its parent exits, and `quiet_run.py`'s private desktop does not
  change that. When the child exits or times out, the job is ended, so no test game outlives the round that started
  it. The job also ends if `run.ps1` dies. Programs that ask to break away from a job may (none of ours do).
- `queue.ps1`: `run.ps1`'s output goes to files (`queue-<lane>-run.log` and `.err`, appended to
  `queue-<lane>-output.log` afterwards), and the lane waits for `run.ps1` itself. Anything that escapes the job can no
  longer stall a lane. As a side effect the output log is plain UTF-8 instead of UTF-16 interleaved with UTF-8.

Apply from the repo root with `git apply tools/lane_hang/harness-fix.patch`.

## Fake lane test

`run_fake_lane.py` builds a throwaway git repo in `%TEMP%\doomerfall-fake-lane`, copies a harness into it, and runs
`queue.ps1` on two cards with `fake_claude.py` in place of Claude. Each fake round leaves a "game" (a sleeping python
process that inherits handles) and reports BLOCKED. PASS needs both cards to finish before the game would have ended
and no game left afterwards. It costs nothing and creates branches only in the throwaway repo.

```
python tools/lane_hang/run_fake_lane.py                                  # current harness: FAIL (hangs)
python tools/lane_hang/run_fake_lane.py --patch tools/lane_hang/harness-fix.patch --quiet-run   # PASS
```

`--quiet-run` starts the fake game through `quiet_run.py` on a private desktop, as real tests do.
