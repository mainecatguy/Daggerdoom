
## Pre-Mininimum Viable Product Goals
1. Doom Running.
2. In the daggerfall world.
3. With exterior world travel at full scale (going anywhere in the world).
4. And the daggerfall map.
5. And working combat.
(Nothing fancy beyond that).


## Minimum Viable Product Goals (we are here)
Goals: 

Be able to move through the world of daggerfall with area transitions intact, including moving across the world map in real time, and able to use the fast travel map.

Be able to use Doom weapons, combat and systems inside of this simulation that has the Daggerfall maps.

Replace Daggerfall enemies with Doom enemies.

Doom movement and tactical combat should be present.

Be able to open both a daggerfall and doom menu without a problem in a way that reflects the determined architectural choice.

Have working Doom GUI.

Demonstrate that daggerfall and doom keybindings are consolidated.

Demonstrate that some basic game synchronization works through implementation of one system.

We need to ensure that all four of these technical hurldes are provably overcomable:
Runtime Dynamic Map & Asset Loading: UZDoom normally mounts maps and textures from static archives at startup. Proving you can generate a Daggerfall area on the fly and hot-load it into a running UZDoom instance—without restarting the process—is one of the biggest engine-level risks.

Coordinate Sync & World Interactions: Keeping area transitions intact requires a deterministic coordinate transform between UZDoom and DFU (so DFU tracks player position for chunk boundaries and triggers) plus basic Use raycast forwarding for doors and building/dungeon portals.

Minimal Coordinated Save, Load, and Death: Even with only one synced system (e.g., player HP), you need to prove both engines can freeze, save, reload, and handle player death—suppressing Doom's unilateral pistol-start—without desyncing.

Suppressed DFU 3D Rendering: Proving DFU can disable its own 3D world rendering and entity physics (so you aren't paying to render and simulate two 3D worlds) while keeping its simulation loop and 2D UI overlay active.

## World Scale and Player Size

The Daggerfall world is at **75% scale** in Doom (owner decision, 2026-11-22): 1 Daggerfall unit = 0.75 Doom map units. Doomguy is shorter than Daggerfall characters, so this keeps the world feeling the same size.

| | Daggerfall units | Doom units at 75% |
|---|---:|---:|
| Terrain tile | 256 | 192 |
| World map pixel | 32,768 | 24,576 |

- The player stays stock Doom on Daggerfall maps: height 56, eye height 41, step height 24, with stock crouch, speed, weapons, and monsters.
- The one exception is collision width, which matches Daggerfall's character at world scale: radius 10.5 (21 wide). Regular Doom maps keep radius 16.
- The dungeon converter defaults to 0.75. `--world-scale` overrides it.
- So far this scale has been applied to dungeons. The terrain treadmill test predates it.


## Long-Term Direction:

| Domain | Primary Owner | Secondary / Mirror | Boundary Contract |
|---|---|---|---|
| **Process Lifecycle & Mod Loading** | **Launcher** | UZDoom, DFU | Spawns both processes inside a Job Object / process group, passes mod load orders and IPC session ID, and enforces clean teardown on exit or crash. |
| **Canonical World, Time & Weather** | **DFU** | UZDoom | DFU owns calendar, seasons, regions, and weather; pushes ambient lighting, skybox, and weather states to UZDoom. |
| **Geometry & Asset Conversion** | **DFU** (source) -> **UZDoom** (render/sim) | — | DFU exports location geometry (UDMF), textures, 3D prop/building models, and skyboxes on first visit (cached on disk). UZDoom owns 3D rendering, BSP, collision, and raycasts. |
| **Wilderness Streaming & Fast Travel** | **DFU** | UZDoom | DFU owns the overworld grid, fast travel, and ship/horse travel; triggers UZDoom map teardowns and chunk loads at cell boundaries or fast-travel arrivals. |
| **Saves & Per-Location Persistence** | **DFU** | UZDoom | DFU owns save slots, macro-world state, and DFU mod saves. On save or area exit, DFU runs a two-phase IPC commit instructing UZDoom to serialize active level snapshots and DRLX inventory into DFU's save folder, keyed by location ID. |
| **Window, Input & Keybinds** | **UZDoom** | DFU | UZDoom owns the single OS window, raw FPS input, and unified keybind table. In `DFU_UI` mode, UZDoom pauses playsim and routes pointer/key events into DFU's patched `InputManager` / `UserInterfaceManager`. |
| **Menus, UI & HUD Compositing** | **DFU** (RPG menus) / **UZDoom** (combat HUD) | — | UZDoom renders Doom/DRLX HUDs and menus natively. DFU renders its UI onto a transparent buffer composited over UZDoom's viewport; DFU signals `UIStackEmpty` to resume gameplay. |
| **Player Movement & Traversal** | **UZDoom** (physics) / **DFU** (rules) | — | UZDoom executes 35 Hz movement, jumping, swimming, climbing, and levitation. DFU pushes speed/encumbrance multipliers, climbing skill checks, and levitation/water-breathing flags. |
| **Player Vitals, Stats & Death** | **DFU** | UZDoom | DFU owns authoritative stats, HP, armor/resistances, fatigue, magicka, and death. UZDoom intercepts hits (`DamageMobj`), forwards raw damage to DFU, and mirrors returned HP/death state on the Doom pawn. |
| **Status Effects & Transformations** | **DFU** | UZDoom | DFU ticks poison, disease, paralysis, buffs, vampirism, and lycanthropy; pushes active state modifiers (movement freeze, speed/jump boosts, vision tints, sunlight damage) to UZDoom. |
| **Combat, Weapons & DRLX Systems** | **UZDoom** | DFU | UZDoom natively runs DRLX weapons, ammo, weapon mods, recoil, projectiles, hitscans, and splash damage; reports hits and kills to DFU. |
| **Magic & Spellcasting** | **DFU** (rules) / **UZDoom** (execution) | — | DFU owns spellbooks, magicka costs, and effect formulas; sends cast commands so UZDoom spawns physical projectiles, AoE volumes, light sources, or actor effects. |
| **Loot, Inventory & Economy** | **DFU** (rolls/economy) / **UZDoom** (combat carry) | — | DFU rolls loot tables and translates drops (e.g., Ebony Mace -> DRLX weapon) into UZDoom spawns. UZDoom holds active Doom weapons/ammo/mods and exports item descriptors to DFU when opening shops, wagons, or bank storage. |
| **Interactive Geometry & Locks** | **UZDoom** (motion) / **DFU** (checks) | — | UZDoom handles door/lift/secret-wall movement and player `Use` rays; queries DFU for lock ratings, lockpicking/bashing checks, traps, and container loot rolls. |
| **Monsters, Slaughter Packs & AI** | **UZDoom** (behavior) / **DFU** (lifecycle) | — | DFU determines encounter composition and quest targets; UZDoom owns slaughter-pack spreading, `RandomSpawner` resolution, pathing, infighting, and combat AI. |
| **NPCs, Dialogue & Quests** | **DFU** (logic) / **UZDoom** (actors) | — | DFU runs `QuestMachine`, dialogue, guilds, and passive `QuestResourceBehaviour` stubs. UZDoom hosts NPC actors, fires `OnUse`/`OnInjured`/`OnKilled`, and swaps attacked/hostile NPCs into ZScript Doom-bot combat AI. |
| **Stealth, Sound & Detection** | **UZDoom** | DFU | UZDoom owns sector light levels, BSP line-of-sight, and sector sound propagation (`P_NoiseAlert`); applies DFU stealth skill modifiers to detection thresholds and backstab triggers. |
| **Crime, Bounties & Arrests** | **DFU** | UZDoom | UZDoom reports assaults, thefts, and weapon discharge in towns; DFU tracks bounties/reputation, flags town factions hostile, spawns guards, and runs surrender/court/jail flows. |
| **Resting, Loitering & Ambushes** | **DFU** | UZDoom | DFU owns rest/loiter UI, time advancement, and recovery; queries UZDoom for nearby enemies before allowing rest and instructs UZDoom to spawn ambush packs on rest interrupts. |
| **Progression & Skill XP** | **DFU** | UZDoom | UZDoom streams coarse action telemetry (kills by weapon category, hits taken, jumps, climbs); DFU maps events to native Daggerfall skill XP and level-ups. |
| **Audio & Music** | **UZDoom** (music + combat SFX) / **DFU** (UI + barks) | — | Both processes output independently; the OS audio mixer blends streams natively. |
