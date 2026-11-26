# Future ideas

Ideas for after the initial release. These are not planned or approved work. If the owner picks one up, it moves to the backlog (`work/backlog.md` and `work/backlog/`).

- **DoomRPG:** Bring DoomRPG into Daggerfall's systems. It is not part of the initial release.
- **Daggerfall mods:** Add support for a number of Daggerfall Unity mods.
- **Exact terrain noise (low priority):** Daggerfall Unity deliberately adds noise to make natural small hills. Doomerfall has the same kind of bumps, but uses a stand-in for Unity's `Mathf.PerlinNoise`, so individual bumps differ by about 14.5 units on average across 83,205 samples. What the player sees and stands on still agree. A fix must change `dd_treadmill.cpp` and `WorldTerrain.cs` together and rebuild every cached town. See `work/notes/20261123-165107.md`.
- **Stamp the damage bonus on fired projectiles:** today a shot in flight when the player switches guns lands with the new gun's bonus. Record the bonus on actors spawned with the player as owner, and prefer the inflictor's recorded bonus in `DD_BridgeDamageBonus` (owner, 2026-11-24: a future item).
- **Comprehend Languages:** out for now (owner, 2026-11-25). Only matters if monsters keep Daggerfall's language rules.
- **Diseases and poisons from Doom monsters:** Daggerfall already runs diseases and poisons, but Doom monsters never infect the player. A future possibility (owner, 2026-11-25).
- **Dispel Undead and Dispel Daedra as extreme damage:** Daedra hits demons; Undead hits every other non-NPC monster. Open question: does Doom know which enemies are demons? Stock Doom has no demon flag; check DRLA Monsters and DRLAX in `GameMods/ExtractedData/` (owner, 2026-11-25: no plan for now).
- **Dispel Magic on monsters:** ends Doom-side effects such as Paralyze or Charm. Player only for now (owner, 2026-11-25).
- **Cast When Strikes enchantment:** a weapon casts its spell on hit (owner, 2026-11-25). The strike artifacts in the backlog wait on it.
- **Akimbo pistols:** with a pistol drawn, a different pistol's hotkey draws it in the other hand; each pistol keeps its own properties, and each trigger pull fires the one that did not fire last if ready, otherwise whichever is ready. Feasible; a generic akimbo weapon is medium effort, truly independent DRLA pistols high (owner, 2026-11-25: future list). Analysis in git history: `work/backlog/akimbo-pistols.md` at `831b8a3`.
- **Solid sprites (distant future):** bulky Daggerfall sprites (braziers, barrels, statues, wells, carts) block movement. No Daggerfall rule makes any sprite solid (Daggerfall Unity and, it seems, classic are walk-through), so the list would be our own choice. If done, the solid ones probably need to be destructible so they never trap the player or block a pack (owner, 2026-11-25). Research and a census tool (`--flat-census`, `tools/dungeon_converter/FlatCensus.cs`): `work/notes/20261124-201628.md`.
