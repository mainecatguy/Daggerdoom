# Locked doors with Daggerfall's requirements

**Waiting on:** the engine-sync contract.

Doors that were locked in Daggerfall must have the same requirements in Doom.

- Read each door's real lock data and requirements from Daggerfall. Do not infer them from appearance or assign them by hand.
- Daggerfall stays the authority for lock state, skill checks, keys, and whether a door has been unlocked. UZDoom asks it before opening the door.
- Monsters and scripted movement must not bypass a locked door unless Daggerfall's rules allow it.
- Verify with real locked, unlocked, lockpick, and key cases, including saving and reloading after a door is unlocked.
- Any other way past a lock, such as bashing or magic, follows Daggerfall's rules unless the owner decides otherwise.

Record survey findings (2026-11-24, `work/notes/20261124-104520-record-types.md` on branch `overnight/records`):

- 432 dungeon doors start locked in Daggerfall (`TriggerFlag_StartingLock >> 4`, index 1-15). The converter exports the
  lock for action doors only (`ActionExport.cs:397`), and nothing in `door_objects.zs` or `action_objects.zs` reads it.
- Dungeon action types 16 (lock door, 40 records) and 17 (unlock door, 18 records) only log `DFRULE` today. They belong
  to this item.
