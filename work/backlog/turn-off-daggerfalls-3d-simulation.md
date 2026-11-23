# Turn off Daggerfall's 3D simulation

**Waiting on:** the stationary NPC tasks, which will show what Daggerfall must keep alive for NPCs to work. The initial NPC design is settled: stationary and passive (owner, 2026-11-23).

Daggerfall Unity should eventually run with its 3D world rendering and entity physics turned off while its simulation loop and 2D UI keep working. This is one of the four core technical hurdles. Daggerfall must still keep the same world objects in memory as Doom, and drawing must stay switchable by the launcher's `--nodraw` flag so tests can compare screenshots from both games. Disabling entities and physics may break NPC behavior, so it should not start until the NPC design is settled. Normal Daggerfall Unity launches must behave as they do today.
