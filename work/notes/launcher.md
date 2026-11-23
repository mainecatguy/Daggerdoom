# Launcher

Branch `agent/launcher`. Demo: `D:\dev\DoomDaggerfall-loop\review\launcher\play.bat`.

## What it does

`launcher/` is a small native Windows program, `doomerfall-launcher.exe`. It makes no UZDoom or Daggerfall Unity code changes.

- Starts both games suspended inside one Job Object, then resumes them.
- When either game exits or crashes, it asks the other to close (`WM_CLOSE`), waits up to 5 seconds (`--grace-ms`), then force-ends whatever is left in the job. The wait also gives a Unity crash handler time to finish.
- If the launcher itself dies, Windows closes the job and ends both games.
- Passes mods to UZDoom in order through `--mod` and `--mod-list <file>`. A list has one path per line, `#` comments, and paths relative to the list.
- Exit code is that of the game that exited first, 2 for bad arguments, 3 for a failed launch. Log: `--log`.

No message channel or transport was added.

Build:

```powershell
cmake -S launcher -B ../DoomDaggerfall-build/launcher -G "Visual Studio 18 2026" -A x64
cmake --build ../DoomDaggerfall-build/launcher --config Release
```

## Rename

Commit `17ea32a` renames 41 `DoomDaggerfall` markers in comments to `Doomerfall`. One string stays: `PlayerSettings.productName` in `CaptureBuild.cs`. It is not a comment, and changing it would move that tool's data folder and registry key.

## Verified

Run minimized and unfocused with private configs.

| Check | Result |
|---|---|
| `uzdoom.exe -iwad DOOM.WAD -norun -nosound -stdout` | Exit 1337 |
| Stock `DOOM.WAD` E1M1 | Entered "E1M1 - Hangar", ran 12 s, clean exit, 0 errors |
| DRLA set E1M1 | Entered, ran 12 s, clean exit |
| DRLA diagnostics vs. the `uzdoom-mesh` build used by `play_drlax.bat` | Identical, 767 lines each. These mod load messages are not new |
| Real games: force-kill UZDoom, force-kill DFU | Other game closed on request |
| Real games: close UZDoom window, close DFU window | Other game closed on request, launcher exit 0 |
| Real games: force-kill launcher | Both ended, no crash handler left |
| Stand-in processes: native crash (`0xC0000602`), child process cleanup, missing file, argument quoting, mod order | Pass |
| `play.bat` command line, with quiet flags added | Both games ran, then shut down together |

## Daggerfall profile isolation

The demo uses a private DFU copy in `review\launcher\dfu`, with `Portable.txt` and windowed settings. Portable mode alone does not isolate Unity's registry values, and neither does editing `app.info`. The copy's product name is patched to `Doomerfall Local` in `globalgamemanagers`, which gives it its own key, `HKCU\Software\Daggerfall Workshop\Doomerfall Local`.

**Incident:** early test launches, before that patch, changed four values in the owner's real `HKCU\Software\Daggerfall Workshop\Daggerfall Unity` key: window width and height (2771x1487 became 960x540), session count, and session id. They were restored from a snapshot taken before the first launch, and an export of the key now matches that snapshot exactly. The owner's `settings.ini` and `KeyBinds.txt` hashes never changed.

Any future launcher path that uses the normal DFU build will write to the owner's DFU display settings unless it is isolated the same way.

## Known gaps

- A hung game is not detected. Only process exit triggers shutdown.
- A UZDoom fatal error dialog keeps its process alive, so both games stay open until the dialog is dismissed. This keeps the error readable.
- Shutdown does not coordinate saves. A game force-ended after the grace period could lose in-progress work. This belongs to the synchronized save task.
- A real engine access violation was not triggered. Crash handling was tested with force-kills of the real games and a native crash in a stand-in, so a Unity crash dump finishing inside the grace period is untested.
- Daggerfall's window is visible. Hiding it belongs to later work.
- `play.bat` uses absolute paths on this machine and is not an installer.

## Human play-test list

1. Run `play.bat`. Both games should open windowed, with UZDoom in E1M1 and DRLA weapons present.
2. Quit UZDoom from its menu. Daggerfall should close within a few seconds.
3. Run it again and quit Daggerfall from its menu. UZDoom should close.
4. Run it again and end `doomerfall-launcher.exe` in Task Manager. Both should close.
5. Confirm your normal Daggerfall Unity still opens at its usual window size.
