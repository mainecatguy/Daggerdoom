# Future ideas

Ideas for after the initial release. These are not planned or approved work. If the owner picks one up, it moves to the backlog (`work/backlog.md` and `work/backlog/`).

- **DoomRPG:** Bring DoomRPG into Daggerfall's systems. It is not part of the initial release.
- **Daggerfall mods:** Add support for a number of Daggerfall Unity mods.
- **Exact terrain noise (low priority):** Daggerfall Unity deliberately adds noise to make natural small hills. Doomerfall has the same kind of bumps, but uses a stand-in for Unity's `Mathf.PerlinNoise`, so individual bumps differ by about 14.5 units on average across 83,205 samples. What the player sees and stands on still agree. A fix must change `dd_treadmill.cpp` and `WorldTerrain.cs` together and rebuild every cached town. See `work/notes/20261123-165107.md`.
- **Arch-vile resurrections reach Daggerfall:** when an Arch-vile (or anything else) raises a dead mook, Doom tells Daggerfall, so Daggerfall can undo the death: the death ledger, quest kills, and the corpse's loot pile (owner, 2026-11-24: a post-release item). Today Daggerfall keeps counting the raised mook as dead.
- **Stamp the damage bonus on fired projectiles:** today a shot in flight when the player switches guns lands with the new gun's bonus. Record the bonus on actors spawned with the player as owner, and prefer the inflictor's recorded bonus in `DD_BridgeDamageBonus` (owner, 2026-11-24: a future item).
- **Salvaging and scrapping guns:** DRLA's Technician can scrap a modded gun into a mod pack. Today it is blocked with Doom's drop paths (it uses the same DRLA token as the gun drop), because scrapping would destroy a gun Daggerfall still holds. As a feature, scrapping would go through Daggerfall: remove the gun item, then give the mod pack (owner, 2026-11-24: a long-term item).
