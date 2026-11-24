# Sort out keybinds

**Waiting on:** the late development and polish phase.

Resolve keybind conflicts across Doom, Daggerfall, and Doomerfall. F9 is quicksave in Daggerfall but quickload in Doom. The owner chose to leave quick keys and quit behavior alone for now (2026-11-23).

Owner decision (2026-11-23): Ctrl stays crouch and also works as a hotkey modifier. Strafe is unbound. UZDoom's default preset already leaves Alt unbound and binds Ctrl to crouch (`defbinds.txt`). Only the classic preset uses Ctrl for fire and Alt for strafe (`origbinds.txt`), so Doomerfall's defaults must not use that preset's bindings.

Agent question [20261124-101258]: the Change Ammo key has no default yet. Decide its default here.
