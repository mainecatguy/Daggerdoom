# Game design decisions

The game designer's log, as an index: one line per decision, oldest first. The full text of each decision (question,
verdict, answer, what it rests on, the challenge) is in its own file in `decisions/`. The owner can overrule any entry.

Verdicts:
- **Follows clearly:** falls out of the documented design. **Leans:** the design points one way; the owner sees it before it is relied on.
- **Not determined:** the design does not answer it; it goes to the owner. **Deferred:** it has architecture or ripple effects, or would create a system; it goes to the owner.

How this is read and written:
- Read `gamedesign.md` first, then this index whole, then grep and open only matching topic files in `gamedesign/` (for example `hp.md`, `damage.md`) and detail files in `decisions/`.
- Topic files hold the current rules; this log is history. A settled owner decision also goes in the right topic file.
- Detail files are never edited. An index line changes only to mark it overruled, for example "Overruled by <link>".
- To record: add `decisions/YYYYMMDD-<short-slug>.md` and one line here: `- YYYY-MM-DD **Verdict**: <one-sentence summary of the answer> ([details](decisions/<file>.md))`.

---

- 2026-11-24 **Follows clearly**: Rounds emptied from a DRLA magazine on an ammo change return to the inventory. ([details](decisions/20261124-rounds-return-to-inventory.md))
- 2026-11-24 **Follows clearly**: Trapdoors may exist before climbing does, since climbing is a planned Daggerfall system. ([details](decisions/20261124-trapdoors-before-climbing.md))
- 2026-11-24 **Not determined**: Open: whether taking a DRLA gun already held gives DRLA's usual ammo (settled later by the owner's "guns never give ammo"). ([details](decisions/20261124-retaken-gun-ammo.md))
- 2026-11-24 **Not determined**: Open: Mantellan Crux needs a fixed area level, but the design gives no number. ([details](decisions/20261124-mantellan-crux-level.md))
- 2026-11-24 **Deferred**: Outdoor guard bots need their own design through the treadmill registry; the order of work is the owner's call. ([details](decisions/20261124-outdoor-guards.md))
- 2026-11-24 **Follows clearly / Leans / Not determined**: Killing a guard takes Daggerfall's crime and reputation effects; hostile bots probably block rest; travel blocking is open. ([details](decisions/20261124-guard-bot-crime-rest.md))
- 2026-11-24 **Not determined**: Open: whether to refuse DRLA armor and boots but use stock Doom armor; depends on backlog drla-armor-role. ([details](decisions/20261124-drla-armor-refusal.md))
- 2026-11-24 **Leans**: "No hotkeys yet" means all five squares of the gun's number key (three plain, Ctrl, Alt) are empty, as merged. ([details](decisions/20261124-hotkeys-whole-key.md))
- 2026-11-24 **Not determined**: Open: standing versus lying sleepers; hiding sleepers would break object permanence. ([details](decisions/20261124-standing-sleepers.md))
- 2026-11-24 **Leans**: Time-passing services may run inside Doom while its monsters stay frozen, as interim behavior. ([details](decisions/20261124-time-services-in-doom.md))
- 2026-11-24 **Not determined**: Open: the 40/30/30 pickup mix, scaling for big areas and pickups in buildings are numbers the design does not give. ([details](decisions/20261124-pickup-mix.md))
- 2026-11-24 **Deferred**: Open for the owner: whether Daggerfall should keep the list of taken Doom pickups instead of the bundled Doom save. ([details](decisions/20261124-taken-pickups-list.md))
- 2026-11-24 **Leans**: Keep both: no rolls or slips while holding still while climbing, and Back climbs down. ([details](decisions/20261124-climb-holding-still.md))
- 2026-11-24 **Leans**: Keep the 70-degree walkable slope on Daggerfall maps, as in Daggerfall. ([details](decisions/20261124-slope-70-degrees.md))
- 2026-11-24 **Follows clearly**: Doom tells Daggerfall when the player climbs and Daggerfall charges its climbing fatigue; exhaustion never kills. ([details](decisions/20261124-climb-fatigue.md))
- 2026-11-24 **Not determined**: Open: whether New Game keeps, skips or replaces Daggerfall's tutorial quest. ([details](decisions/20261124-new-game-tutorial.md))
- 2026-11-24 **Leans / Not determined**: The Baron Blaster probably reloads by itself under the one-shot rule; forcing DRLA's autoreload option on each launch is open. ([details](decisions/20261124-baron-blaster-autoreload.md))
- 2026-11-24 **Not determined**: Open: whether ammo touch pickups are refused when the player is over Daggerfall's carry limit. ([details](decisions/20261124-ammo-pickup-weight-limit.md))
- 2026-11-24 **Owner answered**: Doom owns the live ammo its guns spend and reports every change; Daggerfall owns all other ammo and mirrors Doom's counts; on load Doom's live count stands unless it cannot be restored. ([details](decisions/20261124-ammo-ownership-on-load.md))
- 2026-11-24 **Not determined**: Open: whether the Letter of Credit picture is acceptable as a placeholder for dropped ammo piles (art choice). ([details](decisions/20261124-ammo-pile-placeholder.md))
- 2026-11-24 **Follows clearly**: Piles dropped outdoors should be listed in and pickable from Doom; filed as backlog work. ([details](decisions/20261124-outdoor-piles-in-doom.md))
- 2026-11-24 **Leans**: Non-EX Black and White monsters are priced from their own section 8.3 value, like the EX titans. ([details](decisions/20261124-black-white-monster-cost.md))
- 2026-11-24 **Leans**: DRLA bosses use their own section 8.3 value, not kind points times the square root of the health ratio. ([details](decisions/20261124-drla-boss-cost.md))
- 2026-11-24 **Not determined**: Open: the maximum army share for capped classes such as Hell Mines (0.10 is a placeholder). ([details](decisions/20261124-capped-class-share.md))
- 2026-11-24 **Not determined**: Open: which shop types stock tiered ammo, and at what odds. ([details](decisions/20261124-tiered-ammo-shops.md))
- 2026-11-24 **Not determined**: Open: whether Orichalcum's Orsinium abundance covers the whole region or only the city. ([details](decisions/20261124-orichalcum-orsinium.md))
- 2026-11-24 **Leans**: The regional favourite monster kind should respect what the area level can afford, and a 90% one-class army is acceptable. ([details](decisions/20261124-regional-favourite-monster.md))
- 2026-11-24 **Not determined**: Open: Covens' theme guarantee collides with Civil War's ban on summoners. ([details](decisions/20261124-covens-vs-civil-war.md))
- 2026-11-24 **Leans**: The loaded ammo tier belongs to each gun, not each ammo type, as merged. ([details](decisions/20261124-ammo-tier-per-gun.md))
- 2026-11-24 **Leans**: After an automatic tier change, a stock gun Doom lowered to fists is raised again automatically. ([details](decisions/20261124-stock-gun-raise-after-tier-change.md))
- 2026-11-24 **Not determined**: Open: whether the Change Ammo key gets a default and which; covered by backlog sort-out-keybinds. ([details](decisions/20261124-change-ammo-key-default.md))
- 2026-11-24 **Follows clearly (owner)**: Guns never give ammo from any source, on a first take or a retake; a DRLA gun's loaded magazine travels with it. ([details](decisions/20261124-guns-never-give-ammo.md))
- 2026-11-25 **Follows clearly (owner)**: Summoned and resurrected monsters drop nothing on Daggerfall maps; a revived monster drops nothing on its second death. ([details](decisions/20261125-unplaced-monster-loot.md))
- 2026-11-25 **Deferred (owner removed Adaptive)**: The owner decided to remove DRLA's Adaptive difficulty completely, because the world must not adapt to the player. ([details](decisions/20261125-adaptive-variant-seeding.md))
- 2026-11-25 **Leans exempt, overruled**: Overruled by [the owner's ruling inside this entry](decisions/20261125-kill-counter-pickups.md): summoned and revived kills do not count in the PDA bestiary (it first leaned that DRLA kill counters are exempt from the no-drop rule).
- 2026-11-26 **Follows clearly / Not determined**: Daggerfall's level-up and window sounds should be heard; a new level-up HUD line was open. ([details](decisions/20261126-level-up-sound-and-hud.md))
- 2026-11-26 **Follows clearly / Deferred**: Doom play drives Daggerfall skill uses (running, backstabbing and climbing already decided); the rest of the event-to-skill mapping is open. ([details](decisions/20261126-skill-uses-from-doom.md))
- 2026-11-26 **Deferred**: Open: Skill XP rate across area levels (1 XP per HP, per-area-level, or softer start) goes to the owner. ([details](decisions/20261126-skill-xp-rate.md))
- 2026-11-26 **Deferred / Leans**: Use-based gain rates for kill skills go to the owner; guild training probably stays at full rate. ([details](decisions/20261126-use-gain-rate.md))
- 2026-11-26 **Follows clearly / Leans / Not determined**: Critical Strike and the removed languages cannot be bought; other skills probably can; multiplier, menu location and townsperson XP lean or are open. ([details](decisions/20261126-skill-purchase-menu.md))
- 2026-11-26 **Deferred**: Open: how Melee and the gun skills enter preset class skill lists. ([details](decisions/20261126-melee-gun-skills-classes.md))
- 2026-11-26 **Owner decided**: Pistols is the pistol skill and a new Rifles skill covers ballistic semi-automatic non-explosive guns (heavy single-shot rifles included); chainguns, miniguns and autocannons are Automatics. ([details](decisions/20261126-rifles-skill.md))
- 2026-11-26 **Not determined**: Open: whether a floor gun shows the plain Doom name or no label until Daggerfall answers. ([details](decisions/20261126-floor-gun-label.md))
- 2026-11-26 **Leans**: Saves from before the HP change get the class Endurance bonus once on load, capped. ([details](decisions/20261126-old-saves-endurance-lean.md))
- 2026-11-26 **Owner decided**: Rest gets a card: Daggerfall's rest menu exactly, opened by a keybind; Doom shows "You have reached level N" on a level-up. ([details](decisions/20261126-rest-and-level-hud.md))
- 2026-11-26 **Owner decided**: Saves from before the HP change get the class Endurance bonus once on load, so old and new characters follow one rule. ([details](decisions/20261126-old-saves-endurance-owner.md))
- 2026-11-26 **Owner decided**: Doom holds the live lock for doors in the current area; Daggerfall owns the lock rules, the player's chance and picks, and long-term facts. ([details](decisions/20261126-door-locks-doom-owns-live.md))
- 2026-11-26 **Owner decided**: The Doomerfall mod is required; it adds the Light Carbine (Battle Rifle with 20% higher base damage); the starting gun follows the highest weapon skill; starting ammo amounts set. ([details](decisions/20261126-light-carbine-starting-gun.md))
- 2026-11-26 **Owner decided**: 1 Skill XP per 100 HP of damage across all enemies, each counting at most its max HP; Doom keeps the unsaved remainder and must not spam the bus; prices still open. ([details](decisions/20261126-skill-xp-rate-owner.md))
- 2026-11-26 **Owner decided**: Every skill in the game can be bought; skills not in the game cannot. ([details](decisions/20261126-buyable-skills-owner.md))
- 2026-11-26 **Owner decided**: A floor gun shows the plain Doom name until Daggerfall's name arrives, for now; a backlog item revisits it. ([details](decisions/20261126-floor-gun-label-owner.md))
- 2026-11-26 **Owner decided**: With guns enabled, standard weapon skills reroute to Doom weapon skills by a mapping the owner approves. ([details](decisions/20261126-weapon-skill-reroute-owner.md))
- 2026-11-26 **Owner decided**: Bosses may break more selection rules to get a strong leader, rare weak ones stay as surprises; titans below area level 20 are allowed as rare surprises. ([details](decisions/20261126-boss-leaders-and-titans-owner.md))
- 2026-11-26 **Owner decided**: Unpriced monsters use the square-law rule with measured DPS (BlackImp1 raised for now); a Civil War Coven keeps its theme with non-summoning casters. ([details](decisions/20261126-monster-prices-and-covens-owner.md))
- 2026-11-26 **Owner decided**: Removed class skills (languages, Critical Strike) become other Daggerfall skills first; then, with guns on, Daggerfall weapon skills reroute to Doom skills; filling a language slot with a gun skill is rejected. ([details](decisions/20261126-two-step-skill-remap.md))
