# Remove the city return freeze

**Waiting on:** the owner saying to start it. It is a problem but not an emergency (2026-11-23).

Returning to the City of Daggerfall from a building still freezes for about 1.2 s. The largest remaining cost scales with the city's 43.5 MB of generated map text, and a return does a full level load every time. Details are in `work/notes/20261123-185345.md`.

A draft card, not yet reviewed by the owner, is at `work/queue/cityload/01.opus.city-load-freeze.md`. It is likely to touch the same town loading code as the first town door fix, so run it after that lands.
