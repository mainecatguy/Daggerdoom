# Hidden world streaming radius follows Doom's loaded area

Waiting on: the owner moving it to todo; must fit the distant LOD work (`distantlod` 01).

Daggerfall's hidden world streams terrain at a fixed radius of 1 (9 map squares) in bridge sessions
(`DoomerfallHiddenWorld.cs`, `work/notes/20261124-191013-nodraw.md`). It should follow what Doom actually has loaded, so
it never builds more than needed or misses something. Owner (2026-11-27): "we have plans to make distant LODs so this
needs to be compatible with distant LODs."
