
Goals:
The basic design goal of this project is simple: "daggerfall, but oops we replaced all the monsters with slaughter map sized packs from doom, and that ebony mace that dropped got converted to an energy machinegun from the doom roguelike arsenal extended mod, and when NPCs get angry at you they behave like Doom NPCs."


An essential pillar is state persistence of everything the player does and faithful enforcement of Daggerfall's world state.

We also have lots of daggerfall aesthetics. 



Entity and Effect Rendering: TBD
Hud & UI: Doom (specifically DRLA Extended HUD), with ability to access daggerfall inventory menu with keypresses. DRLAX inventory system needs to be overhauled. We need to scan the daggerfall inventory and tell the player what that translates to in doom inventory.

World and actor behavior including player controls should be mostly managed by Doom.
Pause button: synchronized.
Keybinds: Both.
Playerstate: Daggerfall stats are the authority.
Movement: Doom
Death & reload: We need to keep both engines in sync across state changes.
Damage resolution: TBD.
Magic SYstem: TBD.
Status effects: Daggerfall, needs implementation.

Inventory ownership: we create a common inventory module, initially this will be the daggerfall inventory system, doom items and artifacts will go in here, this will be an area of significant development.
Loot & pickups: Daggerfall engine primarily manages these, but daggerfall drop tables need to eventually be modified to translate to DRLX weapons and items. THis is convenient because the number of tiers, item and material variants are fairly similar between DRLX and Daggerfall: there are about 4-5 tiers of items and 10-20 basetype "variants" so we translate Daggerfall weapon drops into Doom drops.


Music => Daggerfall
Intro Cutscene, Menus, Character Creation => Daggerfall

NPC interaction, menus and so on should be managed by daggerfall.