# Graceful save and load screen

**Waiting on:** the late development and polish phase.

Owner note (2026-11-23): save and load times are fine for now, but the screen handles them poorly. It shows "paused" at the top during the operation. Make this look intentional. The owner suggests it may be better to block the UI thread during the load, or otherwise avoid showing the pause state.
