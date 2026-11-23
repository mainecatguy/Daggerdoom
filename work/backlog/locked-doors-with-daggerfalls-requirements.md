# Locked doors with Daggerfall's requirements

**Waiting on:** the engine-sync contract.

Doors that were locked in Daggerfall must have the same requirements in Doom.

- Read each door's real lock data and requirements from Daggerfall. Do not infer them from appearance or assign them by hand.
- Daggerfall stays the authority for lock state, skill checks, keys, and whether a door has been unlocked. UZDoom asks it before opening the door.
- Monsters and scripted movement must not bypass a locked door unless Daggerfall's rules allow it.
- Verify with real locked, unlocked, lockpick, and key cases, including saving and reloading after a door is unlocked.
- Any other way past a lock, such as bashing or magic, follows Daggerfall's rules unless the owner decides otherwise.
