# Restore autosaves on location changes

**Waiting on:** runtime town loading being merged.

Owner decision (2026-11-22): keep normal autosaving. The runtime work skipped autosaves on stitched map changes because each added a 220 to 240 ms hitch, and the owner considers that acceptable during a load.
