# Future ideas

Ideas for after the initial release. These are not planned or approved work. If the owner picks one up, it moves to the backlog (`work/backlog.md` and `work/backlog/`).

- **DoomRPG:** Bring DoomRPG into Daggerfall's systems. It is not part of the initial release.
- **Daggerfall mods:** Add support for a number of Daggerfall Unity mods.
- **Exact terrain noise (low priority):** Daggerfall Unity deliberately adds noise to make natural small hills. Doomerfall has the same kind of bumps, but uses a stand-in for Unity's `Mathf.PerlinNoise`, so individual bumps differ by about 14.5 units on average across 83,205 samples. What the player sees and stands on still agree. A fix must change `dd_treadmill.cpp` and `WorldTerrain.cs` together and rebuild every cached town. See `work/notes/20261123-165107.md`.
- **Stamp the damage bonus on fired projectiles:** today a shot in flight when the player switches guns lands with the new gun's bonus. Record the bonus on actors spawned with the player as owner, and prefer the inflictor's recorded bonus in `DD_BridgeDamageBonus` (owner, 2026-11-24: a future item).
