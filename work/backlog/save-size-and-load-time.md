# Save size and load time at slaughter scale

Waiting on: the owner moving it to todo.

Measured (`work/notes/20261124-133643.md`): one cleared area-level-30 dungeon adds about 3,800 facts (101 hurt or moved
monsters, 1,749 corpses, 1,932 items), about 71 KB packed. The owner is fine with saves growing and wants total
persistence kept. Owner (2026-11-26): "One thing we could do is *segment* the files for world facts into independent
files that way we don't have to read the whole file ... If we even need that. I guess the question would be do we know
how this affects load times. Note we're on the fastest SSD ... players may not have the fastest SSD."

First measure: save and load time with many cleared high-level dungeons (for example 20, 50, 100), on this machine and
estimated for an ordinary SSD and a hard drive. Only if it matters, propose segmenting world facts into per-place
files read on demand.
