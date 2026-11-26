# Backlog

Work that needs owner input or depends on unfinished work. **Automated loops never take work from this index or `work/backlog/`.**

This is a one-line-per-item index. Open an item's file only when you need its details. Each file starts with what the item is waiting on. To add an item, create `work/backlog/<slug>.md` and add one line here. When an item moves to `work/todo.md` or is finished, move its details there or to `CHANGELOG.md` and `work/notes/`, then delete its file and line.

## Engine bridge

- [Turn off Daggerfall's 3D simulation](backlog/turn-off-daggerfalls-3d-simulation.md): Run DFU logic and 2D UI without its 3D world.

## MVP

- [Remove the city return freeze](backlog/city-return-freeze.md): Returning to the City of Daggerfall still freezes for about 1.2 s.
- [Run the trapdoor checks on every dungeon (low priority)](backlog/run-all-trapdoors.md): Full run across all dungeons. Not now (owner, 2026-11-24).
- [Rotating walk-on trapdoors (axis 10)](backlog/axis10-trapdoors.md): Find how classic Daggerfall turns them. Not now.
- [Guard variety](backlog/guard-variety.md): More kinds of Doom guards than one Doomguy bot type.
- [Turn off Daggerfall's resets and respawns](backlog/turn-off-daggerfall-resets.md): Total persistence, no vanilla resets.
- [Lightweight location record](backlog/location-record.md): Rebuild places from the seed and store only dead, wounded and awake mooks, used-up things and doors, in one Daggerfall copy. Replaces location ledger cards 2-3.
- [Rebuild load](backlog/rebuild-load.md): A save survives a broken Doom snapshot by rebuilding from Daggerfall's ledger. Stage 4 of the location state plan.
- [Quest reward scaling](backlog/quest-reward-scaling.md): Future design for how quest rewards scale.
- [Persistent Info toggle (on hold)](backlog/persistent-info-toggle.md): On hold until play-tested.
- [Guard behavior and pathfinding (delayed indefinitely)](backlog/guard-behavior-and-pathfinding.md): Do not raise. Owner, 2026-11-24.
- [Moonstone and Mithril ammo are quiet](backlog/elven-ammo-quiet.md): Silent on one-shot kills, and `reduced_noise` halves aggro and gun volume.
- [Revisit languages](backlog/revisit-languages.md): The nine monster languages are removed for now (their slots hold the gun skills). Maybe re-add them later.
- [Silver ammo bonus against certain enemy types](backlog/silver-ammo-enemy-bonus.md): Also on Daedric. Needs the enemy types and bonus size.
- [Check the magic rework against potions (before release)](backlog/magic-rework-potions.md): Waits on the magic rework; potion and healing HP restoration must end up 3x.
- [Megasphere gives max HP plus 100](backlog/megasphere-max-plus-100.md): Daggerfall max + 100 instead of 200. Future.
- [Decide Doom item weights](backlog/doom-item-weights.md): Replace the default weight once Doom items live in Daggerfall's inventory.

The MVP target is that the player can run around the world, kill enemies, enter and exit towns, use the fast travel menu, and do other basic things. Position sync, the fast travel menu, and synchronized saving and loading are in `work/todo.md`. Everything in this section is required before MVP is complete. Items come after the others and depend on the inventory menu.


## NPCs

The initial scope is stationary and passive NPCs, including wanderers, that follow Daggerfall's rules on being killed (owner, 2026-11-23). Each interaction is its own task.

- [Talk to stationary NPCs](backlog/talk-to-stationary-npcs.md): Interact opens Daggerfall's real talk window.
- [NPC shops and services](backlog/npc-shops-and-services.md): Open real trade and service windows.
- [NPC quest givers](backlog/npc-quest-givers.md): Run real quest offers and turn-ins.
- [Hostile NPC sprites](backlog/hostile-npc-sprites.md): Choose visuals for NPCs that fight.
- [NPC self defense with one Doom bot](backlog/npc-self-defense-doom-bot.md): Hostile NPCs use one bot template.
- [Sync wandering NPCs](backlog/sync-wandering-npcs.md): Add real wandering and decide what must sync.

## Overworld and towns

- [Distant terrain LOD](backlog/distant-terrain-lod.md): Show distant mountains beyond the loaded window.
- [Distant town view](backlog/distant-town-view.md): Show real towns from outside their playable area.
- [Town gates follow day and night](backlog/town-gates-follow-day-and-night.md): Gates follow Daggerfall's time cycle.
- [Identify and sort problem location groups](backlog/identify-and-sort-problem-location-groups.md): List and rank locations that do not fit one map.
- [Revisit performance of generating fresh cities](backlog/revisit-performance-of-generating-fresh-cities.md): Profile and reduce 5 to 7 second conversions.
- [Overworld monsters outside the loaded window](backlog/overworld-monsters-outside-the-loaded-window.md): Decide their fate off-window. On hold.
- [Overworld area level](backlog/overworld-area-level.md): Whether the wilderness inherits a level bonus from its area or nearby places. Needs a chat.

- [Reach outdoor loot piles from Doom](backlog/reach-exterior-piles.md): List piles dropped outdoors in Doom and let the player take them.

## Dungeons

- [Audit and fix dungeons](backlog/audit-and-fix-dungeons.md): Convert main quest and sample dungeons, fix breakage.
- [Support main quest dungeon quest steps](backlog/support-main-quest-dungeon-quest-steps.md): Reverse engineer and support their quest steps.
- [Investigate sealed 5-block graveyards](backlog/investigate-sealed-5-block-graveyards.md): Check two dungeons with disconnected blocks.
- [Climbing, levitation, and steep surfaces](backlog/climbing-levitation-and-steep-surfaces.md): Match DF slope limits, climbing, and levitation.
- [Exhaustion rework](backlog/exhaustion-rework.md): Slow and collapse instead of passing out or dying.
- [Dungeon actions: text and riddles](backlog/dungeon-action-text-and-riddles.md): Types 11 and 12 only log today. Defines the shared trigger route.
- [Dungeon actions: dialogue](backlog/dungeon-action-dialogue.md): Type 29 on 79 NPC flats only logs today.
- [Dungeon actions: set quest global](backlog/dungeon-action-set-quest-global.md): Type 31, two main quest steps, only logs today.
- [Dungeon actions: door info text](backlog/dungeon-action-door-text.md): Type 99 on 120 castle doors. Needs an owner answer on angering guards.
- [Dungeon actions: traps](backlog/dungeon-action-traps.md): Types 21-27 hurt and poison only log today.
- [Dungeon actions: cast spell](backlog/dungeon-action-cast-spell.md): Type 9 only logs today.
- [Dungeon actions: drain magicka](backlog/dungeon-action-drain-magicka.md): Type 28 only logs today.

## Inventory

- [Rethink the inventory window](backlog/rethink-inventory.md): Daggerfall's tabs fit Doom gear poorly. Design chat with the owner first.
- [Doom weapon equipping and hotkeys](backlog/doom-weapon-equipping-and-hotkeys.md): Assign Doom weapons, items, and spells to hotkeys.
- [Inventory translation](backlog/inventory-translation.md): Translate DF items and DRLA gear both ways.
- [Ammunition system](backlog/ammunition-system.md): Add material-tiered ammo as real inventory items.
- [What DRLA armor does](backlog/drla-armor-role.md): Decide its role beside Daggerfall armor.
- [Area loot identity](backlog/area-loot-identity.md): Fixed per-dungeon lean on which kinds of gear drop. Never changes tier odds or fixed loot.
- [DRLA recipes as Daggerfall rewards](backlog/drla-recipes-as-daggerfall-rewards.md): Make PDA recipes an item Daggerfall can award, only when DRLA is loaded.
- [Hotkey clothing](backlog/hotkey-clothing.md): Allow clothing on hotkeys later.
- [Doom items replace most weapon loot](backlog/doom-weapons-in-weapon-loot.md): 80% of weapon rolls, including 5% modpacks and 1% recipes. Revisit the rate later.
- [DRLA rarity tiers](backlog/drla-rarity-tiers.md): Five tiers, rarer per weapon in each tier. Proposal needs the owner's yes.
- [DRLA drops from a fixed Daggerfall seed](backlog/drla-fixed-drop-seed.md): Same drop every rebuild, so drops need no storage. Waits on the lightweight location record.
- [Doom weapon prices](backlog/doom-weapon-prices.md): Daggerfall base price times material times rarity.
- [Doom weapons have a Daggerfall material](backlog/doom-weapon-materials.md): Material metadata on Doom weapons, rolled with the approved odds.
- [Weapon material damage bonus](backlog/weapon-material-damage-bonus.md): Daggerfall's hit chance bonus becomes a damage modifier, through the existing damage bonus path.
- [Weapon damage bonus coverage test](backlog/weapon-damage-bonus-coverage-test.md): Check every weapon's direct and indirect damage gets the bonus. Part of mod compatibility checks.
- [Area level replaces player level](backlog/area-level-replaces-player-level.md): Scale by area and reroll Daedric results.
- [Grid inventory (shelved by owner, 2026-11-22)](backlog/grid-inventory.md): Diablo-style inventory grid. Shelved.

## Collision and combat polish

- [Remaining collision mismatches](backlog/remaining-collision-mismatches.md): Reduce false walls and openings in parity tests.
- [Weapon collision with the Daggerfall mesh](backlog/weapon-collision-with-the-daggerfall-mesh.md): Make shots hit the visible mesh.
- [Monsters at doors](backlog/monsters-at-doors.md): Decide door opening and oversized monster behavior.
- [Locked doors with Daggerfall's requirements](backlog/locked-doors-with-daggerfalls-requirements.md): Use DF's real lock data and rules in Doom.
- [Doors that swing in both directions](backlog/doors-that-swing-in-both-directions.md): Experiment with two-way swinging doors.

## Magic

- [Casting and self spells](backlog/magic-casting-and-self-spells.md): Cast key, Daggerfall-run self effects, Doom mirrors flight, invisibility, light, and so on. First slice.
- [Effects on enemies](backlog/magic-effects-on-enemies.md): Generic Pacify and Charm, Paralyze, Soul Trap, Ranged Attack Suppression, Detect.
- [Open and Lock](backlog/magic-open-and-lock.md): After the lockpicking work is finished; check first.
- [Mark and Recall](backlog/magic-mark-and-recall.md): Recall plus a new Mark with up to 12 places.
- [Fractional magicka](backlog/fractional-magicka.md): Costs under one point for big packs; fraction carry for now.
- [Damage magic rework](backlog/damage-magic-rework.md): Stock damage spells cannot compete with DRLA guns; needs owner design.
- [Enemy-class enchantments](backlog/magic-enemy-class-enchantments.md): Potent Vs, Low Damage Vs, Health Leech, Vampiric, Ring of Namira; waits on enemy tagging.
- [Strike artifacts](backlog/magic-strike-artifacts.md): Mace of Molag Bal, Mehrunes' Razor, Wabbajack; waits on Cast When Strikes.
- [Lycanthropy and vampirism](backlog/lycanthropy-and-vampirism.md): Whole conditions and beast forms; needs owner design.
- [Enchantment drawbacks](backlog/magic-enchantment-drawbacks.md): Item Deteriorates, User Takes Damage, Extra Weight, Weakens Armor; later.
- [Soul Bound](backlog/magic-soul-bound.md): Bind trapped souls into items; a broken item releases its creature in Doom.

## Before initial release

- [Daggerfall skills in Doom](backlog/skills-in-doom.md): Owner decisions: new gun skills, perks at 25/50/75/100, Jumping. In discussion.
- [Original weapon skills in Doom](backlog/original-weapon-skills.md): Short Blade, Long Blade, Axe, Blunt, Archery stay; make them work.
- [Brutal Doom and a melee mod](backlog/brutal-melee-mods.md): Later, after mod compatibility research.
- [Rifles skill](backlog/rifles-skill.md): New skill for rifles (was Marksmanship); no rifle counts as a pistol (owner, 2026-11-26). Later.
- [Mod compatibility research](backlog/mod-compatibility-research.md): Specialist reviews history; new mods' weapons work with Daggerfall systems.
- [Player manual](backlog/player-manual.md): Started at `manual.md` with HP; a specialist task decides its full scope.
- [Final Doom class and difficulty for New Game](backlog/full-daggerfall-new-game-flow.md): Replace the temporary prompt and fixed class.
- [Doom monsters block fast travel](backlog/doom-monsters-block-fast-travel.md): Decide whether and how nearby Doom monsters block travel.
- [Improve the random enemy roster](backlog/improve-the-random-enemy-roster.md): Weight or tier the uniform random roster.
- [Random or deterministic options](backlog/random-or-deterministic-options.md): Checkboxes for random loot and random encounter theming. Deterministic is the default.
- [Quest targets in mook packs](backlog/quest-targets-in-mook-packs.md): Decide how quest targets map onto packs.
- [Quest packs steal points](backlog/quest-packs-steal-points.md): Quest placements take points from neighbours for bigger packs and high-point leaders.
- [Decorative corpses](backlog/decorative-corpses.md): Rare gene for zero-point corpses, such as the losing side of a finished Civil War.
- [Handle Arch-vile resurrection](backlog/arch-vile-resurrection.md): Research how revived mooks affect saves and quests, then propose handling.
- [Monster mix on stock Doom maps](backlog/monster-mix-on-stock-doom-maps.md): DRLA only for now. Decide later how stock maps mix DRLA and Colourful Hell.
- [Oblivion Portals](backlog/oblivion-portals.md): Portals that lead to Doom and custom WAD maps.

## After initial release

- [Revisit damage and resistances](backlog/revisit-damage-and-resistances.md): Rework how DRLA, Schism and DF damage rules combine; map damage types (Schism freeze, lightning) to DF elements; generic freezing.
- [Greater NPC bot variety](backlog/greater-npc-bot-variety.md): Add bot types for guards and classes.
- [Status effects on mooks](backlog/status-effects-on-mooks.md): Extend DF status effects to Doom mooks.
- [Should open doors block monster sight?](backlog/should-open-doors-block-monster-sight.md): Decide whether to match DF's door sight rule.
- [Support texture packs and lighting mods](backlog/support-texture-packs-and-lighting-mods.md): Carry DF visual mods into the converter.

## Late development polish

- [Review native Doom monster drops](backlog/review-native-doom-monster-drops.md): Doom monsters keep native drops for now. Decide later whether to keep them.
- [Sort out keybinds](backlog/sort-out-keybinds.md): Resolve Doom, DF, and Doomerfall key conflicts.
- [Graceful save and load screen](backlog/graceful-save-and-load-screen.md): Stop showing "paused" during saves and loads.
