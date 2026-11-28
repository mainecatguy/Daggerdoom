> **Answered (owner, 2026-11-28): (a).** Saves keep waiting; `netcommand` 01 fixes the Doom bug and lands this work.
> **Sent back (2026-11-28):** waiting on an owner choice. Busy announcements are built (branch
> agent/busyheartbeat-20261128-061011, commits 46464875, 81db9cfd, c3d3c910; notes work/notes/20261128-061011.md).
> A hang during a load is untested. Demo: D:\dev\DoomDaggerfall-loop\review\busy-wait\play.bat (play-slow.bat adds
> 2.5 s stalls). Card: work/queue/busyheartbeat/done/01.opus.no-false-not-responding.md.

# No false "not responding": how should long saves behave?

Busy announcements let a save succeed when Daggerfall takes over 1 s (it used to fail). A save that freezes Doom for over
about 2 s can then set off an existing Doom bug: the next load drops to the console with "Unknown net command"
(d_net.cpp, root cause not found). It crashed in 3 of 16 test runs with a 2.5 s save stall, and 0 of 19 with freezes of
1.2 s or less. A 0.7-2 s city build can happen inside a save.

- (a) Keep saves waiting out Daggerfall, and approve a separate card to fix the Doom net-stream bug.
- (b) Keep saves waiting, but cap the wait at about 1.5 s while the bug is open, so long saves fail cleanly.
- (c) Go back to the old 1 s rule for saves (false save failures come back); busy announcements only for menus, loads
  and city builds.
