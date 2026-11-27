# Changelog

What is done on the project, newest first. Agents do not need to read this unless a task asks them to. Details live in `work/notes/`, and planned work lives in `work/backlog.md`.

## Current state

- **Playable demo:** Privateer's Hold with Daggerfall visuals, Doom movement and combat, 42 Doom monsters, swinging doors, and angled collision. Run `D:\dev\DoomDaggerfall-loop\review\angled-demo\play.bat`.
- **Other demos:** City of Daggerfall at `D:\dev\DoomDaggerfall-loop\review\city-texture-fix\play.bat`, overworld at `D:\dev\DoomDaggerfall-loop\review\overworld-demo\play.bat`, and DRLAX on E1M1 at `D:\dev\DoomDaggerfall\play_drlax.bat`.
- **Launcher:** starts Daggerfall Unity and UZDoom as one package. Run `D:\dev\DoomDaggerfall-loop\review\launcher\play.bat`.
- **Current game:** run `D:\dev\DoomDaggerfall-loop\play\play.bat`, then choose New Game. It is built from `integration` at `9cfd0177` (2026-11-26), with locked doors, menu mouse release, the rifle tag and damage numbers, and its "what to try" list is at the top of `play.bat`. Rebuild that folder with `python scripts/play/install.py`, which now also builds the map data.
- **Branches:** `integration` is at `dc90a52`, with steal mode, real enemy drops, the fixed dungeon harness, the area level proposal, automatic hinged trapdoors, container windows, quiet agent launches, the reported location recheck, Use-button pickup, character sheet publishing, stationary NPCs, the DRLA launcher, monster deaths, the first town door fix, New Game, the transition speedup, Daggerfall item pickup, the dungeon re-entry fix, generated bridge definitions, main quest trapdoors, 10 Hz position sync, the wilderness height fix, the Daggerfall map command, door route fixes, both overnight lanes, the bridge and door fixes, dungeon flats, Daggerfall items, synchronized saving and loading, the death screen, fast travel arrival, connected door transitions, and the inventory menu.
- **Roughest spots:** some walls still bend where they stayed tied to the grid, and false walls and openings remain.

## 2026-11-26
- **Climbing stays engaged on steep stair-like surfaces (on `integration`):** a staircase of tall risers with treads up to 16 units deep (Privateer's Hold's steep stairs, 32/12 units) is one continuous climb instead of four; wider ledges, strafing and ordinary walls top out as before. Verified on `verify/climb`: 22/22 climb tests, the cliff probe is one climb walking and running, stock E1M1 0 errors. Notes: `work/notes/20261126-223019.md`.
- **Automatics weapon type (on `integration`):** the Assault Rifle Chaingun, Minigun and Autocannon are Automatics, never Rifles; a gun's description reads "Type:" when it has one type. Verified on `verify/batch`: weapon category and types tests PASS, types line 5/5. Notes: `work/notes/20261126-220430.md`.
- **Travel map danger word only for dungeons (on `integration`):** the travel map's "(Beginner)" style word and the confirm box's "Danger:" line show only for dungeons, not towns, temples or covens. Verified: `-dftravelhintshots` report and exit 0 on `verify/batch`. Notes: `work/notes/20261126-222729.md`.
- **Privateer's Hold first room with stairs holds battle rifle Former Humans (on `integration`):** the hall at the top of the cave stairs gets battle rifle Former Humans as start rooms. Verified on `verify/batch`: budget 123/123, planner 62/62, drop test PASS; the paired New Game and stair-walk checks were verified on the card's branch. Notes: `work/notes/20261126-222235.md`.
- **Daggerfall remembers taken Doom pickups (on `integration`):** a seeded pickup you take stays gone after leaving and returning, after loading a save, and when the dungeon is rebuilt from Daggerfall's record. Verified on `verify/batch` with `tools/taken_pickups/run_taken.py all` (5/5, 5/5, 2/2) and `check` (stock clean, DRLA the 3 known script errors). Notes: `work/notes/20261126-212713-takenpickups.md`.
- **Light Carbine (on `integration`):** a new rifle that is always in the game: DRLA's Battle Rifle made semi-automatic with +20% damage (6 x 1d3). About half the Battle Rifles that Battle Rifle monsters drop become carbines. Tagged as a rifle; Daggerfall gives it its own item and material. Tests: `tools/light_carbine/run_carbine_test.py`.
- **Dropped ammo looks like that ammo and is remembered (on `integration`):** a pile you drop that holds only one ammo type shows Doom's clip, shells, rocket or cell sprite (the box sprite at 50/20/5/100 or more); a pile with anything else keeps the loot sack. Piles keep their look after leaving and coming back and after save and load. Notes: `work/notes/20261126-201527.md`.
- **No DRLA class menu in a Daggerfall game (on `integration`):** a bridged New Game goes straight to the start map as the Doomerfall player with no class perks (no class menu, no DRLA class kit); standalone DRLA still offers its classes, and DRLA's stamina kick and armor still work. Verified: bridged New Game, stamina/armor checks, E1M1 stock and DRLA, standalone, and the fist test. Notes: `work/notes/20261126-184738.md`, `work/notes/20261126-200147.md`.
- **Weapon types in a gun's description (on `integration`):** a Doom gun's Daggerfall Info text now reads "<name>. Types: <skills>" plus DRLA's one-line summary, using the same rules as the skill code (167 DRLA and 9 stock guns checked); Doom sends the text with the item art, so bridge bindings changed and both games need rebuilding together. Notes `work/notes/20261126-192645.md`.
- **Arrival wait covers the dungeon's monster spawn (on `integration`):** the arrival freeze now waits for the dungeon's monsters to spawn and holds one more frozen tic, so all 73 Privateer's Hold monsters are already there, held, on the first frame and no 5 s gate timeout is needed. Tests: freeze normal/slow/lost/nosave/use, paired lockpick take/entry/load/newgame, plain load, stock E1M1. Notes: `work/notes/20261126-185032.md`, `work/notes/20261126-194746.md`.
- **Main quest dungeon levels and Privateer's Hold start room (on `integration`, `5985c8f1`):** every main quest dungeon plans at the approved fixed level and story theme (one `MainQuest` table in `DoomerfallAreaLevels.cs`, mirrored in `area_level.py`); Privateer's Hold admits only plain Former Humans (new `PlainHumanoid` theme), and its first room beside the cave holds battle rifle Former Humans. Verified on `verify/mql`: planner 62/62, budget 123/123, battle rifle drop test pass, E1M1 stock and DRLA reach Hangar; the Daggerfall Unity build and paired New Game were verified on the cards' own branches and not rerun here.
- **Fist always on hotkey 1 (on `integration`, `ad0f42ce`):** key 1's first square is always the fist; it cannot be reassigned or removed, is not an inventory item, and pressing 1 raises it in Doom while the active gun stays lowered. Verified on `verify/fist`: `-dffisttest` 8 checks pass on New Game and after a load, E1M1 stock and DRLA start clean.
- **Show damage numbers option (on `integration`, `15c87a54`):** `DoomerfallDamageNumbers` draws the player's hits as small gold numbers over the monster; Options > HUD Options > "Show damage numbers", off by default, on by default with `+dd_dev 1` (which `scripts/play/install.py` now passes); the launch default is never saved. Tests after merge: `-norun` exit 1337 (stock, DRLA, DRLA + doomerfall), `damage_numbers.py` dev/normal/off/on/resetdev/resetnormal/stock/cross1 all PASS on E1M1 with DRLA. Notes: `work/notes/20261126-190312.md`.
- **Rifle tag (on `integration`, `80e4504b`):** `DoomerfallRifleTag.IsRifle` marks the 7 semi-automatic ballistic DRLA rifles (Marksman, HP Marksman, Scoped Rifle, Sniper, Elephant Gun, Anti-Materiel, Gauss), generated from DRLA's DECORATE by `tools/rifle_tag/derive_rifles.py`; it changes no category or skill yet. Tests after merge: `-norun` exit 1337, E1M1 with DRLA, `run_rifletag_test.py` 11/11 PASS, `run_weaponcat_test.py` PASS. Notes: `work/notes/20261126-185032.md`.
- **Mouse in Daggerfall menus over fullscreen Doom (on `integration`, `2ca51325`):** `System_WantNativeMouse` releases the mouse while a Daggerfall menu is open, so fullscreen menus get a cursor and clicks. Tests after merge: stock E1M1 38/38 lines identical, DRLA 2149/2150 (one random DRLA level message), `-norun` exit 1337. Fullscreen grab needs a play test. Notes: `work/notes/20261126-185033.md`.
- **Locked doors and lockpicking (on `integration`, lockpick cards 01-05 plus the rethink):** Lockpick items and loot, Daggerfall's lockpicking chance in a Doom minigame, locked labels, and Daggerfall's door order run by Doom. Doom owns each live lock; it is set from the converted map's starting lock at map load and holds only while Daggerfall is attached. Lock changes (picks, levers) are kept in the location record's door fact, keyed by LoadID. Daggerfall answers only the player's attempt. The setup gate holds the arrival autosave until the place record is applied, and the playsim freezes during that wait. Tests: Doom-only harness 3/3 alone, 26/26 attached; paired pick 12/19, lever 11/18, relock 13/20, entry 2/0, New Game 8/0; stock check. Open: on a normal entry the freeze no longer covers the monster spawn (todo). Notes: `work/notes/20261126-lockpick-rethink.md` (the conceptual fix), `20261126-131954.md`, `20261126-142733.md`, `20261126-150155.md`, `20261126-154857.md`.

- **Ammo tiers same size (on `integration`):** every tier's pickup and shop pack holds Regular's amount (clip 10, shop pack 80 bullets); only odds differ. Verified on `verify/ammosizefix`: startup 1337, E1M1 stock and DRLA, `ammo.py sizes` (34 PASS), `ammo.py tiers` (packs PASS, counts MATCH). Notes: `work/notes/20261126-180338.md`.

- **Two-skill weapons (on `integration`):** energy pistols are Pistol + Energy and energy shotguns Energy + Shotgun; `DoomerfallWeaponCategory.SkillSlotOf` uses the higher live skill (new read-only `Actor.DD_SheetSkill`, so UZDoom must be rebuilt). Verified on `verify/skillcore7`: startup 1337, weapon category test (73 PASS), paired two-skill check, class card test (74 ok). Notes: `work/notes/20261126-174427.md`.

### Weapon skills, weapon categories and class cards (on `integration`)

- **Seven new skills in the removed monster-language slots:** Shotguns, Automatics, Explosives, Pistols, Rifles, Energy Weapons and Melee (slots 4-10). They show on the sheet, train, save, and are sent to Doom in the character sheet (format 6, `DFB_SKILL_*`). Monster languages are gone; their old enchantments stay but do nothing.
- **Weapon categories:** every stock and DRLA gun maps to at most one skill (`DoomerfallWeaponCategory.zs`); fists stay Hand-to-Hand. Nothing in combat reads the category yet.
- **Hand-made class cards** for guns and no-guns modes (guns mode on): presets get their card, custom classes convert by the default rule, the class maker offers the Doom skills and no Critical Strike. Old saves load at the same level and progress (level-up sum rebased).
- Bridge schema changed: bridge DLL, launcher, UZDoom and Daggerfall Unity must be rebuilt together. Verified on `verify/skillcore`: class card test (74 ok), weapon category test, E1M1 stock and DRLA, perk popup, rest, one day/night town step. The sheet test's strict "Doom read every version" check still misses back-to-back publishes, as on the branch.
- Notes: `work/notes/20261126-005053.md`, `work/notes/20261126-114057-skillcore.md`, `work/notes/20261126-145138.md`, `work/notes/20261126-154815.md`, `work/notes/20261126-161434.md`, `work/notes/20261126-164636.md`.

### Day/night: fog, fogged sky, lit windows and winter textures (on `integration`)

- **Doom draws Daggerfall's live fog** (clear haze, weather, interiors, dungeons) from a new `fog ...` bridge text, and heavy fog also fogs the sky as Daggerfall's does.
- **Town windows glow** with Daggerfall's window colour (`windows r g b`): blue glass by day, orange at night, fading with distance and fog. The converter writes window masks into `ddruntime.pk3` (regenerate it).
- **Winter textures:** Daggerfall's `sky` line carries the season; outdoor places convert with ClimateSwaps' winter sets at the next area load.
- Known gaps (owner accepted, on hold): the first town after launch in a winter save loads in summer textures; the overworld is not seasonal yet.
- Plain bridge texts only, no schema change; UZDoom, converter and Daggerfall Unity must be rebuilt. Verified on `verify/daynight`: paired town, interior and dungeon runs, Doom-only winter shots, E1M1 stock and DRLA, rest and perk popup regressions.
- Notes: `work/notes/20261125-202716.md`, `work/notes/20261126-114057.md`, `work/notes/20261126-145333.md`.

### Player HP from Endurance and level (on `integration`)

- **Max HP = 50 + Endurance + (level - 1) x Endurance / 15**, from live Endurance (Fortify and Drain count while they last), recomputed on every change. A rise in max HP raises current HP by the same amount; a fall only clamps it. Rules: `gamedesign/hp.md`.
- **Class HP per level becomes an Endurance (and max END) bonus** (class HP per level - 8): added to the rolled Endurance, and the Endurance cap becomes 100 + bonus. Older saves get it once. The custom class editor shows the bonus under the new label.
- Daggerfall only, active only in a bridge session; no UZDoom or bridge schema change. Test: `-dfhpformulatest`, `tools/hpformula/run_hpformula.py` (97 passed, stock and DRLA).
- Notes: `work/notes/20261125-231947.md`, `work/notes/20261125-235942.md`.

### Drop labels: guns on the floor show their material (on `integration`)

- **A Doom gun on the floor now shows its Daggerfall material in the look label** ("Iron Battle Rifle"), the same name the inventory gives it after pickup. Daggerfall still rolls the material, from the gun's lasting floor id, by the same rule as the take; Doom asks once per gun in view, with no per-spawn round trip.
- **Guns dropped from Daggerfall's inventory keep their material** on the floor and when taken back, and **fixed-drop guns keep theirs after leaving and returning** (the location record now keeps a floor gun's id). Script-spawned guns get a lasting id the first time they are named, taken or recorded.
- Bridge schema changed: the bridge DLL, launcher, UZDoom and Daggerfall Unity must be rebuilt together. Fixed-drop gun floor ids changed shape (bit 58), so fixed-drop gun materials moved (owner accepts seed changes).
- Verification fix: a slow Doom art answer is no longer lost for the rest of the session (asked again, late answers used).
- Open for the owner: the roll uses the area level where the player stands, not where the gun lies.
- Notes: `work/notes/20261125-221820.md`, `work/notes/20261126-003718-droplabel-verify.md`.

## 2026-11-25

### Adaptive removed; overworld seeds with DRLA (on `integration`)

- **DRLA's Adaptive skill is gone whenever the Doomerfall mod is loaded** (owner: the world does not adapt to the player): the mod's MAPINFO says `removeskill adaptive`, a small new UZDoom MAPINFO keyword. Other skills keep their indices; a `-skill`, skill CVAR or savegame asking for it gets the default skill. Plain DRLA and stock WADs are unchanged. The spawner handoff no longer looks for Adaptive spawners.
- **Overworld packs under DRLA now drop seeded loot:** the seed's id went to DRLA's RandomSpawner, so the real monster had none (dropped nothing) and leaving the area tombstoned the seed. The id now passes to the monster through the existing spawner handoff; leave-and-return keeps the dead dead and the living in place, with no duplicates.
- Paired fixed drops series still passes unchanged. Notes: `work/notes/20261125-230756-adaptive-overworld.md`.

### Fixed drops finished on `integration`

- **Card 05 merged** (`agent/fixeddrops-20261125-202715`: summoned monsters drop nothing on Daggerfall maps; travel arrival). Merge fix: its session-id test also matched every placed monster's id (tags 5-7 have bit 63); it now tests for a session id only.
- **Revived monsters drop nothing:** a monster whose seeded loot dropped is marked; an Arch-vile's revive keeps the mark through saves and the treadmill's park/restore.
- **DRLA's Monster-flagged spawners** (Adaptive skill's `RLAdaptiveSpawner`, Armageddon's `RLTheHungrySpawner`): a placed monster's id passes to the first real monster the spawner makes; the spawner is never a mook or a stored monster. The encounter planner never places these classes (only the stock-roster fallback does).
- Paired fixed drops series passes unchanged (112 kills, 183 drops); new `tools/fixed_drops/rules.py` tests revive, leave-and-return, Adaptive and Armageddon. Notes: `work/notes/20261125-220115-fixeddrops-finish.md`.

### Merged to `integration` (`8c78edf`)

- **Stock Doom ammo amounts (`overnight/ammosize`):** pickups and drops give stock Doom's small, large and dropped amounts (from id's `p_inter.c`); other tiers take their share of Regular. The tier rounding is a proposal awaiting the owner (`work/questions.md`). Notes: `work/notes/20261124-233842.md`.
- **New Game while playing and the journal (`overnight/menus`):** New Game from inside a game confirms, drops it, and starts over in both games. J opens Daggerfall's quest journal; tabs, paging and closing pass a paired test 9/9, and travel from it works only outdoors. Notes: `work/notes/20261124-233842-menus.md`.
- **Use and look labels (`overnight/uselabels`):** an NPC that will not talk shows Daggerfall's refusal message; Use on a town building's wall runs Daggerfall's Info (name and town map); Doomerfall's own HUD labels (Sneaking, loaded ammo, Climbing) are one size larger through their own scale, stock text unchanged; a label under the crosshair names what is in Use reach (paired test 11/11). Notes: `work/notes/20261124-233842-uselabels.md`.
- The three lanes shared a notes file name, so the menus and uselabels notes were renamed at merge, and the bridge bindings were regenerated (the new bridge IDs do not collide). Merged UZDoom builds and passes the startup check with the Doomerfall mod, and merged Daggerfall Unity builds (`CliBuild result: Succeeded`). The three features have not been played together.

## 2026-11-24

### Merged to `integration` (`9242824`)

- **Expanded Inventory (`overnight/expandedinv`):** the Expanded Inventory mod is decompiled into our repo and built with Daggerfall Unity; player list 4 columns, other list 2, scroll bar between. Its pictures are derived from Daggerfall, never committed; `install.py` extracts them from the zip in `GameMods/ExpandedInventory`. Review flags: layout cut from the art at fixed pixels; ~1800 decompiled lines replace the stock window; shops keep the stock trade window. Notes: `work/notes/20261124-215049.md`.
- **Play folder** reinstalled from `9242824`.

### Merged to `integration` (`9172d09`)

- **Map keys (`overnight/mapkeys`):** Doom's forward, back and strafe keys pan the automaps; on the travel map they pan the zoomed view or step between map parts. Notes: `work/notes/20261124-202831.md`.
- **No pickups in houses (`overnight/housepickups`):** house interiors get no Doom pickups; shops and other buildings keep them. Notes: `work/notes/20261124-205249.md`.
- **Play folder** reinstalled from `9172d09`.

### Merged to `integration` (`8722921`)

- **One hotkey per item (`overnight/hotkeyunique`):** putting an item on a hotkey clears its other hotkeys. Notes: `work/notes/20261124-202337.md`.
- **No debug messages on screen (`overnight/quietlog`):** debug output shows only with the `dd_debugmessages` setting. Review flags: each debug call looks up the setting even when off; a new print that skips the gate would show again. Notes: `work/notes/20261124-202353.md`.
- **Ammo in inventory and ammo change reload (`overnight/ammoinv`):** ammo shows in Daggerfall's inventory; the change ammo key plays DRLA's reload and loads the new tier. Review flags: it relies on the FIFO bridge (now written in `architecture.md`); reload logic sits in both `dd_items.cpp` and `DoomerfallAmmo.zs`. On merge the material test's harness phases moved to 80-85. Notes: `work/notes/20261124-195226-ammoinv.md`, `work/notes/20261124-201245.md`.
- **Main quest levels (`overnight/mainquestlevels`):** Privateer's Hold armies are humanoid only (a new `only=1` story theme). A level table for the other main quest dungeons waits on the owner. Review flag: the level and theme table is kept in C# and in `tools/area_level` by hand. Notes: `work/notes/20261124-202353-mainquestlevels.md`.

### Merged to `integration` (`cf0f54e`)

- **Test hooks moved out (`overnight/testhooks`):** bridge test drivers (load, HP, save, new game, plain load, pause) moved from `dd_bridge.cpp` to `dd_bridge_test.cpp`; Daggerfall test hooks (sync test start, plain load, save, monster quest) moved to their own files. Each hook's keep-or-remove decision is in `work/notes/20261124-191013.md`.
- **Clean launch (`overnight/cleanlaunch`):** Daggerfall runs on the launcher's private desktop, stays windowed and never locks the cursor (`--show-dfu` shows it); `tools/cleanlaunch/check_launch.py` checks the windows. Review flags: Daggerfall's own dialogs are invisible in normal play; `DoomerfallWindow` overrides the cursor lock every frame. Notes: `work/notes/20261124-195345.md`.
- **One Use key (`overnight/usekey`):** Doom's Use is the only interact key; the separate Interact control is gone. Old configs with E bound to `netevent df_interact` must be fixed in the config (owner: no migration code). Notes: `work/notes/20261124-195226.md`.
- **Doom weapon materials (`overnight/doommaterial`):** Doom guns carry a Daggerfall material rolled at the area level, and the drawn gun's material scales damage (Iron -10% to Daedric +60%), multiplied with the ammo bonus. Notes: `work/notes/20261124-190702-doommaterial.md`, `work/notes/20261124-194205.md`.
- **Hidden Daggerfall world (`overnight/nodraw`, hurdle 4):** most of the hidden world was already inert; Daggerfall now streams radius 1 (9 map pixels, not 49) in sessions, and the random encounter gap is closed. Exterior memory 324-363 MB to 207-217 MB; dungeon exit and fast travel hitches roughly halved or better. Review flags: the radius is hard-coded to Doom's window; city builds still freeze Daggerfall 0.7-1.4 s against Doom's 1 s stale limit. Notes: `work/notes/20261124-191013-nodraw.md`.
- **Escape in New Game (`overnight/newgameesc`):** Doom's main menu stays shut during New Game and plain load; Escape at the difficulty prompt asks to abandon the character. On merge its test mode moved into `dd_bridge_test.cpp`. Notes: `work/notes/20261124-195345-newgameesc.md`.

### Merged to `integration` (`b48037d`)

- **Lights (`overnight/lights`):** converted places are lit where Daggerfall lights them, with GZDoom dynamic lights: dungeon light records, interior lamps, and town lamps that follow Daggerfall's night hours (bridge text `citylights`). The Daggerfall mesh had been drawn full-bright and now takes sector light and nearby dynamic lights. Interior flats are now all drawn, as in Daggerfall Unity (a tavern went from 11 billboards to 31). Up to about 3 ms a frame in the worst dungeon, 1.5-4.5 ms in a town at night. Tuning cvars and a play-test list are in `work/notes/20261124-124736.md`.
- **Editor markers (`overnight/markers`):** the converter no longer turns enemy markers into action records, since Daggerfall Unity makes them inactive, and skips the one mobile type 99 marker (Wayrest). `--list-markers` prints a census. The 70 passive castle guard markers still spawn hostile monsters, waiting on the owner. Notes: `work/notes/20261124-130608.md`.
- **Plain Daggerfall saves and map change autosaves (`overnight/plainsaves`):** a plain Daggerfall save loads from Daggerfall's Load window at Doom's title (`dd_load_daggerfall`), with the default Doom class in the saved place and the owner's starting weapon rule. Stitched map changes autosave again at the seam, holding the last frame through one stall. Bridge kinds renumbered to 220-221 on merge. Its test hooks sit inside main classes; a card to move them is drafted. Notes: `work/notes/20261124-113528.md`, `work/notes/20261124-123655.md`.
- **Quest rewards unscaled (`overnight/questrewards`):** quest gold and magic item rewards use reward level 20 in a Doomerfall session; guild quests still use guild rank. Notes: `work/notes/20261124-130536-questrewards.md`.
- **Shop and town level research (`overnight/shoplevels`):** research only. 14,790 shops; shop quality is the only real signal. Four proposed cards wait on owner choices (shop level formula, town classes, restocks, house levels). Notes: `work/notes/20261124-124736-shop-levels.md`.
- **Harness:** the overnight verifier fails test logic added to game classes and plain rule breaks, and after a pass its session is resumed as a reviewer whose flags go to the owner. Cards are short, with standing rules in the worker prompt. `check.ps1` no longer reports a Unity build as passed when Unity never ran.

### Merged to `integration` (`3805d1e`)

- **Ammo system (five cards, `work/queue/ammotiers`):** Daggerfall calculates the player's damage bonus and Doom scales the player's damage by it (own splash damage excluded). Ammo can be picked up in Daggerfall's inventory: split stacks stay ammo. Equipping a gun gives Doom Daggerfall's count for its ammo type and the damage modifier. Material tiers (Regular to Daedric) have tinted items, descriptions with their bonus, prices, weights, stacks, shop stock, and dungeon drops by area level with 2% jackpots. Z changes the loaded tier, with a HUD icon and name. A change empties the magazine back to the inventory, and ammo switches automatically when the tier runs out. UZDoom changes are in `dd_*` files plus a two-line damage hook in `p_interaction.cpp`. Notes: `work/notes/20261124-083825.md`, `-085156`, `-090831`, `-093041`, `-101258`. Demo: `D:\dev\DoomDaggerfall-loop\review\ammo-change\play.bat`.

### Merged to `integration` (`0699292`)

- **Doom ammo in Daggerfall's inventory, and arrow weight:** bullets, shells, rockets, and cells are stacks in Daggerfall's inventory at the owner's weights (0.02, 0.1, 0.2, 0.02 kg per round) and plain-ammo prices of 3x the owner's base prices (3, 9, 30, 15 gold per round). Doom's ammo stays the live counter. Bridge kinds 171 and 172 sync both ways with numbered deltas, so drops, wagon moves, and piles in Daggerfall reach Doom, and Doom pickups and shots reach Daggerfall. Arrows now weigh 0.01 kg each and count toward carried weight (they had been weightless). Paired take and load runs matched counts on both sides across save and load. Stock and DRLA E1M1 load cleanly. Notes: `work/notes/20261124-075147.md`.

### Merged to `integration` (`dccc114`)

- **Doom guns show their own picture in the inventory:** DRLA pickups inherit a spawn chain that statically lands on the pistol's frame. Guns Doom had not seen on the floor showed the pistol: the starting gun, guns put away by a hotkey, and every gun after a load. Doom now uses DRLA's `SpawnFrame` label first. This is a one-line UZDoom change. Notes: `work/notes/20261124-071038-gunicons.md`.

### Merged to `integration` (`52117f0`)

- **DRLA one-shot guns reload by themselves:** with DRLA loaded, our mod turns on DRLA's own "1-shot weapons autoreload" option at startup, and covers the Baron Blaster and the single Marathon Shotguns, which skip that option. 31 guns in all, including the pump and double-barrel shotguns. Side effect from DRLA's own option: the Gauss rifle and the Shredder pistol also reload after each shot. Nothing changes without DRLA. Notes: `work/notes/20261124-072401.md`.

### Merged to `integration` (`1706dc6`)

- **Hotkeys menu looks like Daggerfall's inventory:** stone background, item slots, REMOVE buttons, and yellow text, all cut at runtime from Daggerfall's inventory images. The hotkeys work as before. Screenshots: `D:\dev\DoomDaggerfall-loop\review\hotkey-look\old` and `new`. Notes: `work/notes/20261124-071038.md`.
- **Health pickups follow Daggerfall's max HP:** DRLA's stimpack and medikit checked a fixed 100, and `HealThing` always reported success, so pickups were used up without healing. Several pickups taken in one tic also each counted as useful. Doom now uses Daggerfall's max HP (including after a level up) and the HP after heals still in flight, and a pickup that cannot heal stays on the floor. These are UZDoom engine changes, inactive without a bridge session. Notes: `work/notes/20261124-071606.md`.

## 2026-11-23

### Merged to `integration` (`e85e351`)

- **Daggerfall's own windows show in Doom:** after a real New Game, the tutorial question and Brisienna's message opened behind Doom and left Daggerfall paused, so talk, Info, items, and hotkeys were all refused. Daggerfall now asks Doom (bridge kind 25, menu 7) to show any window it opens by itself. A scripted New Game to town walk then talked to Gothway Garden's general store keeper, and New Game save and load passed. The play folder is rebuilt with the fix. Notes: `work/notes/20261124-044747.md`.

### Merged to `integration` (`842aa95`)

- **Combined demo:** `scripts/play/install.py` now builds the play data from this checkout's converter and item tool (about 30 s, `--keep-data` skips it), so the play folder gets every converter change, including 58 pickups in Privateer's Hold. The real play folder is refreshed from `9b5ae27`, and its `play.bat` starts with a "what to try" list. Scripted runs each exercised one feature against that install: New Game, pickups, loot, gun hotkeys, a monster drop, the shop menu, theft and guards, townspeople at home, climbing, and save and load. Each passed. One scripted New Game to town walk found that Use on NPCs is refused after a real New Game. That is being fixed. Walking townspeople cannot be talked to yet, by design. The travel map hint was checked in Daggerfall alone. Notes: `work/notes/20261124-033918.md`.

### Merged to `integration` (`9b5ae27`)

- **Townspeople at home:** townspeople whose schedule puts them at home appear inside their house when the player enters, on any storey, at seeded spots that stay the same across visits. At 2:00 a house's residents were all inside, and by day they were outdoors again. They are as passive indoors as outdoors. Notes: `work/notes/20261124-004803.md`.

### Merged to `integration` (`ec8e0bd`)

- **Shopkeeper menu:** Use on a shopkeeper or service NPC opens Daggerfall's own service menu inside Doom, as in Daggerfall, so talking and shop services both work. Selling at a general store changed gold and inventory in Daggerfall. Guild, bank, tavern, repair, and identify services are untested. Doom items have no sale value yet (owner question). Notes: `work/notes/20261124-002144-shopmenu.md`.

### Merged to `integration` (`08419ee`)

- **Hostile Doom guards:** when Daggerfall spawns guards after a detected crime, Doom spawns one guard-looking bot per guard with a random non-BFG vanilla weapon, using UZDoom's bot code. Daggerfall's copies stay inert: in one run Daggerfall's HP fell by exactly the sum of the Doom hits. Guard deaths remove Daggerfall's copies. The crash came from spawning during UZDoom's prediction step and is fixed. Bots do not path around counters and sometimes shoot furniture (play-test). Notes: `work/notes/20261124-002144-guards.md`, `work/notes/20261123-233427.md`.

### Merged to `integration` (`fc6f918`)

- **Climbing:** on Daggerfall maps, pushing into a surface of 70 degrees or steeper for 1 second starts a climb with a "Climbing" message, at Daggerfall's climb-to-walk speed ratio. The player can climb up, down, and sideways, hold still, shoot, and jump off. Daggerfall's Climbing skill rolls decide slips, and Doom reports skill uses back to Daggerfall. Ground of 45 to 70 degrees is walkable on Daggerfall maps. Test map 14 of 14, and a paired climb onto a store roof with the uses tallied. Not done: climbing fatigue and fall damage. Notes: `work/notes/20261124-002144-climb.md`, `work/notes/20261124-025531.md`.

### Merged to `integration` (`ba8f3bc`)

- **Health and cheap ammo pickups:** the converter places about 1 to 2 seeded health or cheap ammo pickups per room in dungeons and buildings (DRLA versions when DRLA is loaded). Taken pickups stay taken across re-entry, save, and load. In-game 7 of 7 and load 3 of 3. Notes: `work/notes/20261124-002311-pickups.md`.

### Merged to `integration` (`283a81b`)

- **Fixed loot seeds:** dungeon and building treasure, enemy corpse loot, quest foe loot, and Doom enemy drops roll from seeds built only from the place and placement, and Unity's shared random state is restored afterwards. Two separate runs gave identical items for 8 piles and 30 drops, and re-entry gave the same piles. Results still depend on player level until area level replaces it. House containers and shop restocks are not seeded (owner question). Notes: `work/notes/20261123-233755-lootseeds.md`.

### Merged to `integration` (`5aef802`)

- **Travel map danger hint:** hovering a place on the travel map shows its danger word, such as `Castle Necromoghan (Very hard)`, and Find Location's confirmation adds a `Danger:` line. Words split area levels 1 to 30 into five equal bands. Travel itself is unchanged. Notes: `work/notes/20261124-002814.md`.

### Merged to `integration` (`bc3242e`)

- **Doom gun pickup rules:** guns taken with Use go to Daggerfall's inventory, and fill and equip their Doom slot's number key when it has no hotkeys yet. Doom guns and armor sit in the Weapons & Armor tab, and the paper doll refuses them with the hotkey message. Modded DRLA guns keep their mods. Swap 9 of 9, load 3 of 3. Old saves' Doom items stay in Clothing & Misc. Notes: `work/notes/20261124-002144.md`.

### Merged to `integration` (`67210da`)

- **Trapdoor shaft floor:** under bottomless lever trapdoors, the converter puts the floor at the base of the hidden pillar on the tile's chain instead of 1,024 units down, falling back to the old depth when nothing is hidden. Verified in Castle Lhishen, Orsinium, Direnni Tower, and the Tower of Caect'kern. 1,128 of 1,218 lever tiles have a pillar. Converter only. Notes: `work/notes/20261124-003059.md`.

### Merged to `integration` (`982f60d`)

- **Ground loot sprites:** real game loot (treasure, drops, dropped piles) already used Daggerfall's pile sprites at vanilla size. Only the item gallery test map drew inventory art in the world, which made the giant pauldron. The gallery now shows vanilla treasure piles. No game code changed. If world sprites still look too big in play, the eye height question returns. Notes: `work/notes/20261124-002311.md`.

### Merged to `integration` (`c59a2b9`)

- **Runtime area levels:** Daggerfall computes each location's area level (and the terrain level outside locations) from the approved formula at runtime, and enemy drops and monster placements use it. `-dfarealevel` remains a test override. Notes: `work/notes/20261123-233755-arealevel.md`.
- **Info like vanilla:** Info on a building door shows its name and then enters, as in Daggerfall, and messages appear at Daggerfall's top and middle HUD positions. Walking townspeople now stop the Info ray. Messages still use Doom's font. Notes: `work/notes/20261123-233755-infovanilla.md`.

### Merged to `integration` (`e97c3c5`)

- **Doom weapon hotkeys:** Daggerfall holds every Doom gun and the hotkey table, and Doom holds only the active gun. Number keys 1 to 0 swap guns on Daggerfall maps, with Ctrl and Alt squares. Each gun keeps its magazine and DRLA mods across swaps, saves, and loads. A number key over an item in Daggerfall's inventory opens the hotkey squares, and potions and armor can be hotkeyed too. Swap test 8 of 8. Known gap: modded DRLA pickups lose their mods (todo). Notes: `work/notes/20261123-233611.md`.

- **NPC dialogue:** Use on a stationary NPC runs Daggerfall's own activation and opens its real talk window, or its quest offer window, drawn into Doom while Doom pauses. Too far away gives Daggerfall's own message. Shopkeepers open plain talk for now (a one-line `doomerfallTalkOnly` flag), pending the shop menu follow-up. Accepting quests was not tested. Notes: `work/notes/20261123-233304.md`.
- **Daggerfall holds Doom items:** pressing Use on a Doom item puts it in Daggerfall's inventory with its Doom sprite and name and a default weight, checked against Daggerfall's carry limit. Guns go to Doom at once. Other items take effect when used from Daggerfall's inventory. Verified in both games: 4 of 4 takes, save and load, and E1M1 stock and with DRLA. Daggerfall pile pickup and containers were not rerun. Notes: `work/notes/20261123-223740.md`.
- **Persistent townspeople (`d9cb86d`):** each town's wanderers come from a fixed seed, follow daily schedules, go home at night, and stay dead across save and load. Verified across launches, at night, through a tavern trip, and into the wilderness. Notes: `work/notes/20261123-215225-townspeople.md`.
- **Info mode (`b457f4c`):** a Doom key runs Daggerfall's Info interaction. It does not yet match vanilla on doors and message style, and a follow-up card is drafted. Notes: `work/notes/20261123-225143-info.md`.

### Merged to `integration` (`dc90a52`)

- **Steal mode (`721088c`):** crouching shows "Sneaking" on Daggerfall maps, and Use then runs Daggerfall's own activation in Steal mode. In Daggerfall, Steal only changes lockpicking and pickpocketing, which Doom does not route yet. Notes: `work/notes/20261123-225143.md`.
- **Real enemy drops (`07ce6c3`):** each slain Doom enemy rolls a real Daggerfall drop for the enemy Daggerfall would have placed there, using the area level instead of player level and the approved material tiers. Audited against Daggerfall's tables, then verified in the dungeon, stock and with DRLA: piles, taking, save, load, re-entry, and the quest kill. Loading a save from before a kill re-rolls its drop until fixed loot seeds land. Notes: `work/notes/20261123-212059-drops.md`.
- **In-dungeon test harness (`7909c31`):** the death route harness never ran because a constant-false `if` with a `break` stopped its `WorldTick`. Fixed in `tools/monster_deaths/harness.zs`. Notes: `work/notes/20261123-223511.md`.

### Merged to `integration` (`e2fa033`)

- **Area level proposal (`2cef0a8`):** a proposal, not a game change. Every dungeon gets a level from region lean, a smooth map-wide field, dungeon type lean, and per-place noise with rare exceptions, ranked within its size class so each level 1 to 30 holds 140 to 145 dungeons. Towns and wilderness get a terrain level from region and the field. All fixed seeds. Script: `tools/area_level/area_level.py`. Proposal: `work/notes/20261123-225515-area-level-proposal.md`. Waiting on owner review.

### Merged to `integration` (`143ec39`)

- **Automatic hinged trapdoors (`9e1c624`):** the converter finds every hinged trapdoor from Daggerfall's data with one rule (TRP model, action 8, 18, or 20, lying flat), with no per-dungeon lists. Bottomless shafts under tiles get a floor 1,024 units down, and hidden pillars stay below the floor as in Daggerfall. The census found 2,586 hinged records in 23 kinds. `trapdoor_regress.py` checks every hinged kind in 14 dungeons, and all pass. Nobody has played it by hand, and the play folder's maps were not regenerated. Notes: `work/notes/20261123-212059-trapdoors.md`.

### Merged to `integration` (`efd097e`)

- **Container windows from Use (`7fab6fa`):** Use on a loot pile or furniture container calls Daggerfall's own `ActivateLootContainer`, so piles open the loot window, house containers ask the private property question, and shop shelves open the Buy window, exactly as in Daggerfall. Furniture boxes reach Doom as bridge kind 80. Partial takes, emptied house containers, and stocked dates survive re-entry and load. Buying by hand and selling are not done; selling waits on an owner question. Notes: `work/notes/20261123-221130.md`. The play folder is refreshed to `efd097e`.

### Merged to `integration` (`1ef394c`)

- **Quiet agent launches (`b50a8b0`):** the launcher's `--minimized` test mode starts Daggerfall Unity on a private desktop and mutes it with the new test-only `-dfmute`, and adds `-nosound -noactivate` for UZDoom. Under `-noactivate`, a UZDoom crash writes `CrashReport.zip` and exits with no dialog. `quiet_run.py --desktop` hides Unity editor builds, and `check.ps1` uses it. `AGENTS.md` tells agents to launch this way. Measured with `tools/quiet_probe`: no windows, focus changes, flashes, or sound in the covered paths. Normal play is unchanged. Minimized UZDoom still shows a taskbar button. Notes: `work/notes/20261123-215225.md`.
- **Owner docs:** the owner's design rules and work tracking, committed on `main` at `eec5778`, merged in `bda5799`.

### Merged to `integration` (`8de998f`)

- **Reported location recheck (`1ca908f`):** the owner's "You are in Privateers Hold" in the wilderness is not a desync. Daggerfall Unity names the location that owns the whole map pixel, about 800 m across, and Doomerfall matches it after a real New Game, town exit on foot, a pixel border crossing, and fast travel. No game code changed. Test tools are in `tools/reported_location`. Notes: `work/notes/20261123-212059-location.md`. Whether to depart from Daggerfall here is an open question.

### Merged to `integration` (`7520c8f`)

- **Use-button pickup (`9979eeb`):** on generated Daggerfall maps in a bridge session, only health and ammo pick up by touch. Everything else, including DRLA weapons and armor and Daggerfall loot piles, is taken with Doom's Use button, and crouching sends Steal instead of Grab. Use still opens doors when no item is in view. Regular WADs are unchanged, stock and with DRLA. Use on a real door could not be scripted and needs a hand test. Notes: `work/notes/20261123-212059-autopickup.md`.
- **Installer:** `scripts/play/install.py` now rebuilds UZDoom from its own checkout, so the engine always matches the bridge it ships with. The play folder is refreshed to `7520c8f`.

### Merged to `integration` (`a947cfb`)

- **Character sheet publishing (`e3a45db`):** Daggerfall publishes level, fatigue, magicka, stats, skills, armor, resistances, and saving throw inputs to Doom through bulk slot 0, base and live values both. Doom keeps a read-only copy and drops it when the character changes. Proven with both real games through training, level-up, armor, effects, save, load, and a new character. The real New Game wizard path was reviewed, not run. Nothing in Doom uses the values yet. Bridge protocol 6.

### Merged to `integration` (`634977f`)

- **Stationary NPCs (`48d9c26`):** NPCs appear in Doom with their real sprites and stable IDs. They are passive, do not block movement, and take no damage. Not yet tested: the overworld walk-in spawn path, indoor visibility after a load, idle animation, and owned houses or guild access.
- **Play install (`634977f`):** the installer now uses the NPC converter output and replaces the whole data folder, so cached towns match it.

### Merged to `integration` (`d9ed76c`)
UZDoom and Daggerfall Unity both build from this merge. New Game, save and load, and death passed through a test install without the DRLA mods. The main launcher with the mods was not launched, at the owner's request. Nobody has hand-played it.

- **Monster deaths:** monsters in converted dungeons have stable IDs. A Doom kill is recorded once in Daggerfall, updates a real quest foe, and rolls a Daggerfall drop that Interact can pick up. Dead monsters stay dead through save, load, and re-entry.
- **Main launcher mods:** `play.bat` now always loads DRLA, DRLA Monsters, and DRLAX.
- **Merge fix:** a new character no longer inherits the last character's dead monsters. This was fixed by reading the code and not run with a second character.
- **Known gaps:** quest foes work in dungeons only, quest popups after a kill are closed unseen, and quests cannot be turned in yet because NPC dialogue does not exist.

### Merged to `integration` (`a85fa24`)
UZDoom builds from this merge and passes its startup check. The lane's scripted door tests used both real games. Nobody has hand-played it.

- **First town door use:** one press now stays pending while the interior converts, as long as the player stays within 768 units. Going farther prints "You left the door." The pressed door also converts ahead of nearby doors.
- **Known gaps:** the first visit to an interior still waits about 4 seconds or more for conversion. A player who wanders during the wait is pulled inside when it finishes.

### Merged to `integration` (`e6a658c`)
UZDoom and Daggerfall Unity both build from this merge. Scripted runs through the current install made a character, arrived in Privateer's Hold, saved and loaded, and died, returned to the title, and loaded. Nobody has played it by hand.

- **New Game:** Doom's New Game runs Daggerfall's real character creation and cinematics, then a temporary difficulty prompt and fixed Doom class, and starts in Privateer's Hold.
- **Merge fixes:** a new character no longer inherits the last character's taken loot, which was fixed by reading the code and not run. New Game now survives Daggerfall stalling while it builds the start location.
- **Current install:** `scripts/play/install.py` assembles one playable folder at `D:\dev\DoomDaggerfall-loop\play`.
- **Known gaps:** quicksave is not bundled, gamepad input does not reach Daggerfall's menus, cinematic sound is unchecked, and the game uses DOOM2 without the DRLA mods.

### Merged to `integration` (`a0e1d6c`)
UZDoom builds from this merge and passes its startup check. The lane's door, save, and stock Doom checks ran before the profiler was removed and were not rerun. No independent verifier ran, and nobody has felt it in play.

- **Transition speedup:** median return to the City of Daggerfall fell from 1674 to 1169 ms, Gothway Garden from 609 to 533 ms, and Privateer's Hold exit from 623 to 556 ms. The player's town can no longer be evicted from the cache while they are in it or its interiors.
- **Stock code:** render section building and map checksums also run on stock maps, with the owner's approval. Section output was identical on 11 maps.
- **Known gaps:** the city still freezes for about 1.2 s. The profiler was removed from the game code, so `analyze.py` and `sechash.py` in `tools/transition_speed` no longer work.

### Merged to `integration` (`bedfc49`)
UZDoom and Daggerfall Unity both build from this merge, UZDoom passes its startup check, and the generated files are current. The lane's scripted tests used both real games. Nobody has hand-played it.

- **Item pickup:** Interact (a bindable Doom control) moves a Daggerfall treasure pile in a dungeon into the real Daggerfall inventory. Weight limits, gold, maps, and quest item state follow Daggerfall's transfer rules. Taken loot stays gone after re-entry, save, and load.
- **Known gaps:** Interact takes everything that fits until the loot window task lands. Exterior items, single placed quest items, shop shelves, house containers, and corpses are not reachable from Doom yet. Tavern and guild piles and indoor dropped items use the same code but were not run.

### Merged to `integration` (`180efd9`)
UZDoom builds from this merge and passes its startup check. The lane's scripted door, save, travel, and stock Doom regressions passed before the merge. Nobody has hand-played the fix.

- **Dungeon re-entry:** going town, dungeon, town, dungeon no longer draws the town's mesh over the dungeon's collision map. Ten scripted enter and exit cycles passed with and without the bridge and a live imp.
- **Known gaps:** projectiles in flight are removed at every door trip, as they were before. "Can no longer exit" was not reproduced separately and needs a hand test. One scripted run stalled once and did not recur in 20 further runs.

### Merged to `integration` (`2860fc1`)
UZDoom and Daggerfall Unity both build from this merge, UZDoom passes its startup check, and the generated files are current. Scripted runs used both real games.

- **Generated bridge definitions:** `bridge/doomerfall_bridge.h` is the single definition. Run `python bridge/generate_bindings.py` after changing it. Stale generated files fail the UZDoom, launcher, bridge, and Unity builds, and mismatched DLLs are refused at startup.

### Merged to `integration` (`cfde24d`)
This merge changes only the converter tools and notes, and they match the lane's verified version. Scripted regressions passed, and nobody has hand-played it.

- **Main quest trapdoors:** all 7 in Wayrest and Lysandus' Tomb now trigger, move, and collide through their real action chains. **A player who falls through one cannot walk back out until climbing exists.**
- **Known gap:** other dungeons' hinged trapdoors are not enabled or fixed yet.

### Merged to `integration` (`a2e9d75`)
UZDoom and Daggerfall Unity both built with this work, UZDoom passed its startup check, and an independent verifier passed it. Nobody has hand-played it.

- **10 Hz position sync:** Daggerfall's hidden player follows Doom at 10 Hz in the wilderness, towns, buildings, and dungeons. Average lag fell from 344 to 35 units in the wilderness and 81 to 10 in buildings. The cost did not show in frame time, measured minimized with drawing off.
- **Not tested:** death indoors, loading an older save, whether a save restores the exact indoor spot, and walking through a real trap. Whether this fixes the blank dungeon map has not been rechecked.

### Merged to `integration` (`c73f16c`)
Notes only, with no code changes.

- **Code quality audit:** the core design is sound. The two fixes recommended soon are pointing regression scripts at the current engine and generating the C# bridge definitions from the header. See `work/notes/20261123-170733.md`.
- **Climbing research:** Daggerfall's climbing rules, a proposed Doom implementation, and four owner questions. Nothing was run in Daggerfall Unity itself. See `work/notes/20261123-171304.md`.

### Merged to `integration` (`cdfbc1a`)
This merge changes only the overworld tools and notes, so no engine rebuild was needed. Nobody has hand-played it.

- **Wilderness terrain height:** the player sank because overworld collision used raw heights while town meshes used Daggerfall's smoothed and flattened heights. The largest measured mismatch fell from 1,095.9 units to 0.146 across 131,696 mesh vertices. Existing demo folders keep their old `overworld.pk3` until they are reassembled.
- **Known gap:** small terrain bumps still differ from real Daggerfall, because the engine and converter use a stand-in for Unity's Perlin noise.

### Merged to `integration` (`70625fc`)
The engine code is identical to the map lane's verified build, and the merge only adds the separate door route tools. Scripted tests used both real games, and nobody has hand-played it.

- **Daggerfall map command:** Doom's map key opens Daggerfall's town map, interior or dungeon automap, or the travel map in the wilderness, which the owner confirmed on 2026-11-23. Regular Doom maps keep Doom's map. Fast travel closes Doom's map and leaves the collider view.
- **Known gap:** the dungeon automap opens but reveals no rooms in the Privateer's Hold test.

### Merged to `integration` (`72bd692`)
The converter builds from this merge. No engine files changed. Scripted door regressions passed, and nobody has hand-played the panels.

- **Door 15:** a false alarm from the test setup. It passes at the real player width of 10.5, and the door test now uses that width.
- **Secret door panels:** 3 non-door panels in Orsinium and Lysandus' Tomb now swing open through their real triggers. They guard small pockets, not a main route.
- **Trapdoors:** 4 main-quest trapdoors stay inert, because they open onto sealed pits that need climbing.

### Merged to `integration` (`079c841`)
UZDoom builds from this merge and passes its startup check. Its Daggerfall Unity code is identical to the engine lane's verified build. Nobody has hand-played these features.

- **Connected transitions:** Daggerfall follows the player through building and dungeon doors. Scripted runs passed 16 building types and Privateer's Hold, including saves and loads inside. Daggerfall does not track the player's position within a room yet.
- **Inventory menu:** the Open Inventory control shows Daggerfall's real inventory inside Doom. Scripted mouse input equipped a weapon. Real window mouse mapping, item use, and dropping are not proven.
- **Sprite scale:** `DaggerfallItem` now displays at the 75% world size with its images unchanged. Dungeon and town billboards were measured and already matched.
- **Survey:** the Daggerfall data and quest survey is in `work/notes/20261123-154554.md`.

### Merged to `integration` (`a954b0e`)
UZDoom builds from this merge and passes its startup check. Its Daggerfall Unity code is identical to the engine lane's verified build.

- **Fast travel arrival:** Daggerfall's real travel map now charges gold, advances time, and moves both games to the same place. Scripted trips to a hamlet, village, and farm ended with 0 world units of difference. A first visit freezes Doom for about 5 seconds while the location converts. Nobody has played it by hand.

### Merged to `integration` (`f97ed3b`)
UZDoom builds from this merge and passes its startup check. Its Daggerfall Unity code is identical to the engine lane's verified build. Scripted tests used both real games, but nobody has used the menus by hand.

- **Synchronized saving:** real bundled saves of both games, including autosaves on Daggerfall maps. Each save freezes the game for about 0.2 seconds.
- **Synchronized loading:** both games restore from one save, with a load freeze of about 2 seconds. Loading was only tested in the city, not in a building or dungeon.
- **Death screen:** Doom's death view leads to Load Last Save, Load Game, or Main Menu. Daggerfall no longer restarts itself in a bridge session.
- **Known gaps:** indoors, Daggerfall's half of a save records the player outside at the door until transitions are connected. New Game is refused until the real start flow exists.

### Merged to `integration` (`3816407`)
UZDoom builds from this merge and passes its startup check. Nobody has hand-played these features, and neither `play.bat` has been launched.

- **Animated textures and flats:** dungeons now show animated textures and ordinary flats such as torches and plants, with no measurable frame cost in Orsinium. Fixed treasure and NPC flats are not drawn yet, because loot and talking do not work on them.
- **Daggerfall items:** all 311 items exist as `DaggerfallItem` actors in a test gallery. 283 use their original sprite, and 28 show a placeholder because the game data has no usable image. Dye colors are not applied.

### Merged to `integration` (`3e74e18`)
UZDoom and Daggerfall Unity both build from this merge, and UZDoom passes its startup check. Most tests were scripted, and nobody has hand-played the combined build.

- **Startup and save research:** full proposal, with the owner's decisions recorded in `work/todo.md`.
- **Bridge:** position sync, Daggerfall's real travel map inside Doom, and HP sync. Daggerfall now stays at the door while Doom is indoors.
- **Dungeons:** tilted and flipped doors, doors that block like Daggerfall's, a traversal report for 19 dungeons, one random enemy per placement, and a texture pass. None of the 19 is proven fully traversable.
- **Towns:** roof-height building colliders with real slopes, and Doom-side entry and exit for buildings and Privateer's Hold.
- **Synchronized saving, not proven:** merged at the owner's request. It passed 45 of 45 checks against a scripted Daggerfall stand-in, but no real Daggerfall save has gone through it.

## 2026-11-22

### Bridge core
- UZDoom and Daggerfall Unity exchange messages and shared state through the launcher. The owner confirmed the IPC demo works.

### Parity test, action system, and water
- Closed-door parity stages use swinging doors, dungeon water is swimmable, and Daggerfall action objects move. The owner confirmed the Scourg Barrow coffin works, and textures need a second pass.

### Launcher (`7e80862`)
- A native launcher runs both games in one Job Object and closes both when either exits or is killed. It passes an ordered mod list to UZDoom. There is no message channel yet.
- The owner tested it and confirmed it works. Doom had no sound because the launcher build lacked `sndfile.dll` and `soft_oal.dll`. They were copied in, and OpenAL now initializes.
- Known gaps: hung games are not detected, a UZDoom fatal dialog holds both games open, and shutdown does not coordinate saves.

### Doomerfall mod (`b564fc0`)
- Our own mod adds unbound "Open Fast Travel" and "Open Inventory" controls that log when fired. It works with and without the DRLA set. The owner tested it.

### Project renamed to Doomerfall (`17ea32a`)
- Engine code markers now use the new name. The local folder keeps its old name.

### Town stitch and runtime towns (`e2181f0`)
- The overworld stitches to generated towns, and Daggerfall locations convert and load during play with a disk cache.

### Work tracking
- Added `work/todo.md` for owner-approved work that is ready to run automatically. `work/backlog.md` now holds only work that needs owner input or depends on unfinished work.

### City cart texture fix (`fb172ee`, not merged)
- Carts, hedges, and some furniture no longer pick up the wrong textures from an overly broad climate swap. Not yet checked in game.

### Overworld treadmill (`88674d4`, not merged)
- Real Daggerfall terrain streams around the player at 75% scale in any direction, with a saved world table for touched monsters, corpses, and drops.
- Owner decisions: dropping a frame or two during shifts with huge packs is fine, and frozen monsters return idle for now.
- The owner tried the demo and it functioned.

### City of Daggerfall (`d9a7313`, not merged)
- The full city and nearby terrain run as a Doom map using Daggerfall's real models, ground tiles, billboards, and sky.
- The owner play-tested it and found it went well, apart from the cart texture bug.

### DRLAX on stock Doom
- DRLA, DRLA Monsters, and DRLAX run on E1M1 with no engine changes. Added the missing OGG sound decoder to the local build.

### Angled collision (`e997464`)
- Generated sectors now follow Daggerfall's real wall edges and sloped planes where they fit, and fall back to the grid elsewhere.
- On Privateer's Hold, test bullets landing on the visible surface rose from 106 to 142 of 200, and sectors fell from 4,975 to 3,036.
- Some straight walls have small bends, and false walls and openings remain.
- The owner play-tested it and called it a huge improvement.

### Converter scale default (`77c48c5`)
- The dungeon converter and comparison tools now default to 75% world scale.

### Swinging doors (`c1c103c`)
- Doors are now separate objects that show the real Daggerfall model and swing on a hinge.
- Rows of small invisible actors give each door collision that follows the model, closed and open.
- 46 of 58 Privateer's Hold doors lead through. The other 12 are dead ends in the Daggerfall data.
- The owner play-tested the doors and confirmed they work.

### Test launches (`32006bd`)
- UZDoom launched with `-noactivate` stays off-screen, does not take focus, and exits on fatal errors.

### World scale and player size (`f5012b2`)
- Daggerfall maps use 75% world scale.
- The player keeps stock Doom height, eye height, step, speed, and weapons, with a 21-wide collision box on Daggerfall maps only.
- The earlier Daggerfall-size player remains available as an opt-in converter setting.
- The owner play-tested this and confirmed the proportions are fixed.

### Player size and collision parity goal, completed (`5ad3f37` to `131a13e`)
- Measured the Daggerfall and Doom player sizes and added an opt-in Daggerfall-size player layer.
- Added a two-way test comparing where Daggerfall and Doom each let the player move, plus a simple bullet check.
- Reduced some false openings and limited ceiling relief. Large mismatches remain.

### Daggerfall mesh layer (`56c6872`, `15b264d`)
- Generated maps can draw Daggerfall's real meshes and textures over invisible Doom collision.
- F1 toggles between the Daggerfall view and the Doom collision view. Regular Doom maps are unaffected.

### Terrain treadmill test (`dbc58d0`)
- Rewriting real sloped terrain while running fit within one 60 FPS frame for all 32 shifts on one straight route with few actors.
- Slaughter-sized packs, saves, decals, sounds, and north-south shifts are untested.

### Dungeon connectivity (`15e0552`)
- Fixed false walls found by the comparison test. Privateer's Hold matched at 15 of 16 viewpoints at the time.

## 2026-11-21

### Dungeon converter (`510ddb5`)
- Built the converter from real Daggerfall dungeon data, with an automated map check.
- Tried Scourg Barrow as a stress test. Its route past the entrance crypt depends on moving dungeon objects, which are not built yet.

### World conversion research (`c8f3d4a`)
- Researched how to convert Daggerfall's world and recorded the open design questions.
