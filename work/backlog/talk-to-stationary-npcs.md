# Talk to stationary NPCs

**Waiting on:** owner approval to move to todo, "Show stationary NPCs in Doom", and the inventory menu's input path.

Owner decision (2026-11-23): Use opens Daggerfall's real UI, and each kind of NPC interaction is scoped as its own task because this is not trivial.

Pressing the Interact control on a stationary NPC opens Daggerfall's real talk window for that same NPC inside the Doom window, with input routed to it. Doom pauses, and closing the window resumes Doom. Shops, services, and quest offers are separate tasks.

Known risk: interior position is not synced, so Daggerfall stands at its landing spot while Doom walks around. Talk must not depend on Daggerfall's player being near the NPC, or this task must handle that.
