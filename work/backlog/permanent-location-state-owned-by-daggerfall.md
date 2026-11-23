# Permanent location state owned by Daggerfall

**Waiting on:** runtime town loading being merged, and synchronized saving and loading.

The game never forgets what the player did in a location, apart from any Daggerfall dungeon resets the owner chooses to keep. Doom's world table holds this history for now and stores it in Doom saves. Move its authority to Daggerfall by extending Daggerfall's save data, since Daggerfall does not track Doom monsters or packs on its own.

Monster packs come from fixed seeds, so store only what changed, such as deaths, drops, pickups, and unlocked doors. Keep this in a stable format separate from Doom's save snapshots, so progress survives engine or mod updates.
