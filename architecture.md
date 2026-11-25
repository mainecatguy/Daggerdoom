
## Pre-Mininimum Viable Product Goals
1. Doom Running.
2. In the daggerfall world.
3. With exterior travel across the full world (going anywhere in the world).
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


## Standing Requirements

- **Bridge speed:** The FIFO bridge between the games must be instantaneous. Speed and performance are paramount, so server-style designs such as gRPC are out.
- **Doom WAD compatibility:** Preserve compatibility with Doom WADs and mods. UZDoom must keep reading existing WADs, maps, and mods as stock UZDoom does.
- **Platforms:** Testing is on Windows only, but do not kill Linux support if possible. Keep OS-specific code behind small, replaceable seams.
- **Small context per task:** Our main software goal is that an agent can do a job while reading as little code as possible. Keep clear boundaries between classes and files, so a class's inputs, outputs, and side effects can be understood from its public surface and a short header comment, without reading its body. New features go in their own files behind a narrow hook, not spread through large shared classes. When a contract changes, update the header comment in the same commit.
- **No debug output in normal play (owner, 2026-11-24):** a normal launch shows the player only messages meant for the player. Diagnostic and test output goes to log files, and reaches the on-screen messages or the game console only with a special logging flag or setting. This holds for both games.
- **Daggerfall's world is inert:** Daggerfall's 3D world is not rendered, and its entity logic is disabled, so nothing in it can act on the player. When Daggerfall spawns an object or entity, such as guards after a crime, it tells Doom, and Doom creates and runs the real thing.

## Doomerfall PK3

Doomerfall's gameplay changes to Doom and DRLA live in our own PK3, built from `mods/doomerfall/src/` by `scripts/doomerfall/build_pk3.py`.

- It loads after DRLA and changes behavior from there. Never edit the original mods or `GameMods/ExtractedData/`.
- It must still load and work when DRLA is absent.
- Do not commit copied DRLA assets or other game data.
- All DRLA monsters are used unchanged for now (owner, 2026-11-23). Monsters may push and move the player, because Doom owns player movement and position.
- Possible future customization: better handling of Arch-vile resurrection. See "Handle Arch-vile resurrection" in `work/backlog.md`.
## State ownership: live and permanent

The rule behind the engine split (owner, 2026-11-24): **UZDoom is the authority on moment-to-moment tactical state.
DFU is the authority on permanent state and on everything the player is not in.** Exceptions need a good engineering
reason and are written down here.

| UZDoom owns (live) | DFU owns (permanent) |
|---|---|
| The current map, exactly: monsters where they stand, their health and alertness, projectiles in flight, summoned monsters | Every other place, as a compact location record |
| The equipped weapon and its magazine, and the live count of the loaded ammo tier | The inventory: unequipped items, other ammo tiers, gold, Doom weapons and mods held |
| Monster AI, movement, collision, combat | Deaths, quests, crime, loot rolls, container and loot pile contents, time |

**Places (planned, `work/backlog/location-record.md`).**

- Every Daggerfall place is rebuilt from its map and fixed seeds. DFU's location record holds only what differs from
  the seed: dead, wounded and awake mooks (one 64-bit entry each, low-resolution position), map things used up
  (bitset), and door, switch, lift and action states. Untracked mooks are alive, unhurt and asleep on their spawn spot.
  Class, drops, death frames and spawn spots are never stored. Quest foes are added on top of the seeded army and never
  change it.
- When the player leaves a map, UZDoom distills it into record entries and sends them to DFU. UZDoom keeps no place
  history of its own.
- Monsters spawned during play (summons, lost souls) are not kept once the player leaves.
- Target size: a cleared high-level dungeon about 16-20 KB, an untouched one a few bytes.

**Saves.**

- A bundled save holds DFU's save and ledgers, plus UZDoom's snapshot of the current map. Loading restores the snapshot
  exactly, and DFU's record is not applied over it.
- At every save UZDoom also sends the current place's record entries. If the snapshot cannot be restored (a mod or map
  changed), the place is rebuilt from the record and only live combat details are lost (`work/backlog/rebuild-load.md`).
- The snapshot leaves out what UZDoom generates from DFU's data, such as the overworld treadmill's terrain sectors
  (88% of an overworld save today). Those are rebuilt on load.

**DFU objects on the current map.** Loot piles, containers, NPCs and townspeople belong to DFU even on the current map.
UZDoom draws them and forwards Use; DFU holds their contents and decides whether they exist. The snapshot's copy is
presentation only and follows DFU's list.

**DFU's scene cache stays short-lived (owner, 2026-11-24).** Daggerfall Unity's own scene cache keeps wiping on every
map pixel change, as in vanilla. Doomerfall's stores are the only permanent copy: `DoomerfallItems` for opened
containers (it overwrites the cached copy on every revisit), and the location record for places, including piles the
player drops through DFU's inventory in towns, buildings and dungeons. Turning the wipe off would make a second,
ever-growing copy (`work/notes/20261124-190702.md`).

**Ammo.** UZDoom owns the live loaded count and magazines and reports every change (pickups, shots, losses). DFU owns
all other ammo and keeps an exact mirror of UZDoom's live counts, current at every save. On a normal load UZDoom's
count stands; if its half cannot be restored, DFU's mirror is used.

Scope: Daggerfall maps only. Doom maps (later, through Oblivion gates) use normal Doom saves.

## Long-Term Direction:

| Domain | Primary Owner | Secondary / Mirror | Boundary Contract |
|---|---|---|---|
| **Process Lifecycle & Mod Loading** | **Launcher** | UZDoom, DFU | Spawns both processes inside a Job Object / process group, passes mod load orders and IPC session ID, and enforces clean teardown on exit or crash. |
| **Canonical World, Time & Weather** | **DFU** | UZDoom | DFU owns calendar, seasons, regions, and weather; pushes ambient lighting, skybox, and weather states to UZDoom. |
| **Geometry & Asset Conversion** | **DFU** (source) -> **UZDoom** (render/sim) | — | DFU exports location geometry (UDMF), textures, 3D prop/building models, and skyboxes on first visit (cached on disk). UZDoom owns 3D rendering, BSP, collision, and raycasts. |
| **Wilderness Streaming & Fast Travel** | **DFU** | UZDoom | DFU owns the overworld grid, fast travel, and ship/horse travel. UZDoom rewrites exterior terrain in place around the player (the "treadmill"), and towns load as dedicated maps. |
| **Saves & Per-Location Persistence** | **DFU** (permanent) / **UZDoom** (current map) | — | DFU owns save slots, macro-world state, DFU mod saves, and the location record of every place. UZDoom's snapshot of the current map rides in the same bundled save and is the authority for that map only. See "State ownership: live and permanent" below. |
| **Window, Input & Keybinds** | **UZDoom** | DFU | UZDoom owns the single OS window, raw FPS input, and unified keybind table. In `DFU_UI` mode, UZDoom pauses playsim and routes pointer/key events into DFU's patched `InputManager` / `UserInterfaceManager`. |
| **Menus, UI & HUD Compositing** | **DFU** (RPG menus) / **UZDoom** (combat HUD) | — | UZDoom renders Doom/DRLX HUDs and menus natively. DFU renders its UI onto a transparent buffer composited over UZDoom's viewport; DFU signals `UIStackEmpty` to resume gameplay. |
| **Player Movement & Traversal** | **UZDoom** (physics) / **DFU** (rules) | — | UZDoom executes 35 Hz movement, jumping, swimming, climbing, and levitation. DFU pushes speed/encumbrance multipliers, climbing skill checks, and levitation/water-breathing flags. |
| **Player Vitals, Stats & Death** | **DFU** | UZDoom | DFU owns authoritative stats, HP, armor/resistances, fatigue, magicka, and death. UZDoom intercepts hits (`DamageMobj`), forwards raw damage to DFU, and mirrors returned HP/death state on the Doom pawn. |
| **Status Effects & Transformations** | **DFU** | UZDoom | DFU ticks poison, disease, paralysis, buffs, vampirism, and lycanthropy; pushes active state modifiers (movement freeze, speed/jump boosts, vision tints, sunlight damage) to UZDoom. |
| **Combat, Weapons & DRLX Systems** | **UZDoom** | DFU | UZDoom natively runs DRLX weapons, ammo, weapon mods, recoil, projectiles, hitscans, and splash damage; reports hits and kills to DFU. |
| **Magic & Spellcasting** | **DFU** (rules) / **UZDoom** (execution) | — | DFU owns spellbooks, magicka costs, and effect formulas; sends cast commands so UZDoom spawns physical projectiles, AoE volumes, light sources, or actor effects. |
| **Loot, Inventory & Economy** | **DFU** | UZDoom | DFU rolls loot tables and translates drops (e.g., Ebony Mace -> DRLX weapon) into UZDoom spawns. DFU owns the player's inventory, Doom weapons and mods included. Ammo is split: UZDoom owns the live ammo its guns spend (the loaded tier of each ammo type, and rounds in magazines) and reports every change (pickups, shots, losses) to DFU. DFU owns all other ammo (other tiers, piles, wagon, shops) and keeps an exact mirror of UZDoom's live counts, current at every save. On a normal load UZDoom's live count stands; if UZDoom's half cannot be restored, DFU's mirror is used (owner, 2026-11-24). |
| **Interactive Geometry & Locks** | **UZDoom** (motion) / **DFU** (checks) | — | UZDoom handles door/lift/secret-wall movement and player `Use` rays; queries DFU for lock ratings, lockpicking/bashing checks, traps, and container loot rolls. |
| **Monsters, Slaughter Packs & AI** | **UZDoom** (composition, spawning, behavior) / **DFU** (facts, lifecycle) | — | DFU sends each area's facts: area level, dungeon type, location, region, world position, enemy placements, and dead mook IDs. It owns deaths and quest targets. UZDoom deterministically decides encounter composition, bosses, and placement, with each pack's leader on DFU's placement point, then runs pathing, infighting, and combat AI (owner, 2026-11-24; see `work/notes/20261123-205402-fractal-encounter-variety.md`). No `RandomSpawner`. |
| **NPCs, Dialogue & Quests** | **DFU** (logic) / **UZDoom** (actors) | — | DFU runs `QuestMachine`, dialogue, guilds, and passive `QuestResourceBehaviour` stubs. UZDoom hosts NPC actors, fires `OnUse`/`OnInjured`/`OnKilled`, and swaps attacked/hostile NPCs into ZScript Doom-bot combat AI. |
| **Stealth, Sound & Detection** | **UZDoom** | DFU | Detection bar similar to Blood West (see `gamedesign.md`). Doom monsters stay idle until the bar fills or the player fires a gun. UZDoom owns the bar and its inputs, such as enemies facing the player with line of sight, and sounds. DFU supplies the Stealth skill, which slows how fast the bar fills. |
| **Crime, Bounties & Arrests** | **DFU** | UZDoom | UZDoom reports assaults, thefts, and weapon discharge in towns; DFU tracks bounties/reputation, flags town factions hostile, spawns guards, and runs surrender/court/jail flows. |
| **Resting, Loitering & Ambushes** | **DFU** | UZDoom | DFU owns rest/loiter UI, time advancement, and recovery; queries UZDoom for nearby enemies before allowing rest and instructs UZDoom to spawn ambush packs on rest interrupts. |
| **Progression & Skill XP** | **DFU** | UZDoom | UZDoom streams coarse action telemetry (kills by weapon category, hits taken, jumps, climbs); DFU maps events to native Daggerfall skill XP and level-ups. |
| **Audio & Music** | **DFU** (music, UI + barks) / **UZDoom** (combat SFX) | — | Both processes output independently; the OS audio mixer blends streams natively. |
