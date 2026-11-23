# Load Daggerfall saves with no Doom data

**Waiting on:** position sync being merged, the startup flow, and synchronized loading.

Owner decision (2026-11-23): required before initial release, and useful for testing. Doomerfall should be able to load a regular Daggerfall save that has no Doom data:

- Create a default Doom character.
- Identify the player's Daggerfall location and sync Doom to it.

More generally, provide default Doom data whenever Daggerfall state loads without any.
