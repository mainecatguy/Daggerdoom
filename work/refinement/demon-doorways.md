> **Sent back (2026-11-28):** waiting on an owner choice. Found by `hitboxcheck` 01 (branch
> agent/hitboxcheck-20261128-050238, notes work/notes/20261128-050238.md, logs D:\dev\DoomDaggerfall-loop\review\hitboxcheck).
> The hitbox check itself is done: narrowed monsters keep full-size hitboxes.

# Demons and open doorways

In Privateer's Hold a Demon gets through 0 of 46 open doorways; Zombieman and Imp get through 45. Demon radius is 30 and
squeezes to 19.7 (39.4 units wide). The solid open door leaf alone blocks it at 23 doorways; the other 23 are too narrow
even without the leaf. The 2026-11-24 notes accepted that big monsters that fit no doorway stay behind.

- (a) Keep as accepted: big monsters stay in their rooms.
- (b) A narrower squeeze width for large monsters.
- (c) Let monsters pass the open door leaf.

Either change would still cover only about half the doorways. Tested in one dungeon only, with no DRLA weapons or splash.
