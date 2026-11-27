# Agent report triage, first pass (2026-11-27)

Source: `work/agent-reports/` (93 files, runs 20261125-202715 to 20261127-113137). No report file, `work/questions.md`,
`work/suspectedoversights.md` or gamedesign file was changed. Checked against `work/questions.md`,
`gamedesign/decisions.md` (and detail files where needed), `gamedesign.md`, `CHANGELOG.md`, `work/todo.md`,
`work/backlog.md`, `git log --oneline integration -300`, and the current code where an oversight's status mattered.

## 1. Summary

The files hold 359 bullets (`[question]`, `[oversight]` and 38 `[review]` items). Many runs wrote the same bullet
several times. Collapsing word-for-word repeats inside one run leaves 291 distinct items.

| Category | Distinct items | Raw bullets |
|---|---|---|
| DROP-ANSWERED | 120 | 150 |
| DROP-MINOR | 20 | 23 |
| DUPLICATE (merged into a kept item below) | 85 | 100 |
| DESIGN (kept, section 2) | 37 | 45 |
| OWNER-ENGINEERING (kept, section 3) | 8 | 10 |
| OVERSIGHT-MAJOR (kept, section 4) | 21 | 31 |
| **Total** | **291** | **359** |

So 66 items remain: 37 design questions, 8 owner engineering questions and 21 major oversights. Counting their
duplicates, they cover 186 bullets.

Stale entries found in `work/questions.md` (not edited):
- [20261127-005245] asks whether to build one shared "which gun fired this shot" mechanism. It has been built and
  merged (shotsource 01, CHANGELOG 2026-11-27). What remains is the child-attribution heuristic in Owner engineering 4.
- [20261127-034545] Luck's extra-ammo rule. The owner replaced it on 2026-11-27 with `killdrops` 01 in `work/todo.md`
  (Luck/2 chance of an ammo drop per kill).

## 2. Design questions

For the `game-designer` (answer, then challenge) before the owner. Each item lists its source ids. A run id repeats
when the run asked the question more than once.

1. **Gun skill placeholders: governing stats, advancement rate, Fighters Guild.** The placeholders were built, and no
   decision or topic file records an answer. Shotguns use Strength, Automatics Agility, Explosives Intelligence,
   Pistols Agility, Rifles Agility, Energy Weapons Intelligence and Melee Strength. All advance at rate 2, "like
   Daggerfall's melee weapon skills". The Fighters Guild is the only trainer of the gun skills. "Now Shotguns and
   Explosives [count toward promotion] (they took Orcish's and Giantish's places in the list)". Options: approve, or
   give other stats, rates and guild rules. Sources: [20261126-005053] [20261126-114057] x4 [20261126-145138] x2
   [20261126-154815] [20261126-161434].

2. **Enchantments for the removed monster languages.** "Powers that enhance a language (Dragonish..Impish), including
   the Enhances Daedric power that bound Fire and Frost Daedra souls force, are kept with their classic item-maker cost
   but do nothing". The CHANGELOG confirms "their old enchantments stay but do nothing". Old Orcish/Harpy/Giantish powers
   (params 4-6) share the slots now used by Shotguns/Automatics/Explosives, so the item maker does not offer "Enhances
   Shotguns/Automatics/Explosives". Allowing it "would need a marker on new items". Options: (a) keep them inert,
   (b) drop them from items and souls (this changes item-maker cost and capacity), (c) replace them with something.
   Separately: should the item maker offer gun-skill enhancements? Evidence: SoulBound.cs lines 278 and 290 force the
   Daedric enchantment. Sources: [20261126-005053] x2 [20261126-114057] x3.

3. **Custom class reroute collision.** "When an old custom class's Daggerfall weapon skill maps to a Doom skill the
   player already picked in a lower slot (for example Axe as a primary and Shotguns as a minor), the build gives the
   Axe slot the next free gun skill and leaves the player's own Shotguns pick alone. The proposal says the lower slot
   should take the fallback". Keep the build's way, or follow the proposal? This belongs with the open reroute-map
   question in `work/questions.md` [20261126] (decisions 20261127-weapon-skill-reroute-map). Source: [20261126-164636].

4. **A new Energy + Automatic two-skill pair?** The owner's example description was "Plasma Rifle. Types: Energy,
   Automatic". Under the approved order and the two-skill rule (Energy pairs only with Pistol or Shotgun), a cell-fed
   Plasma Rifle is Energy only. The Plasma Uzi "stays Pistol + Energy pending the owner" (CHANGELOG weapontypes 03).
   Taking it off the Pistol rule makes it Energy only "because Energy comes before Automatic". Options for the Plasma
   Uzi: (a) Automatic, (b) Energy only like the Plasma Rifle, (c) a new Automatic + Energy pair, (d) Pistol + Energy
   unchanged. For cell-fed or recharging automatics in general: Energy only, or Energy + Automatic? Sources:
   [20261126-192645] [20261127-081504] x2.

5. **DRLA guns with no clear skill.** (a) Not on the recharge-energy list because "not clearly energy guns":
   Lightweaver, Nano-shrapnel Plasma Shotgun, Duke 2 Rifle, Mother-in-Law, Dragonslayer. Should any be Energy Weapons?
   (b) Duke 2 Rifle (Rigelatin Assault Weapon: "no ammo or type tag; fires basic shots, lasers and rockets") and
   Mother-in-Law ("Fire damage, no type tag") report no skill. Should they get one? (c) The Rigelatin fires one shot per
   press but "fires projectiles and uses no ammo", so the rifle rule leaves it untagged. Rifle or not? (d) The Nanomachic
   Armament Generator has a semi-automatic M14 mode but fires automatically by default: never a rifle, always a rifle,
   or a rifle only in M14 mode (needs a runtime check)? (e) The Shredder Pistol "loads shotgun shells into a 10-round
   clip and empties the whole clip on one trigger pull": Pistol, Shotgun or Automatic? Sources: [20261126-161434] x2
   [20261126-185032] x2 [20261127-081504].

6. **Look of the Doom character in bridged games.** Bridged games use "DRLA's generic player body ... (stock Doom
   marine sprites, DRLA 'Scout' voice)", and "DRLA's PDA class page now shows 'No Doom class' with no portrait". Keep
   that, or take the Marine's sprites, voice and PDA portrait only (still no perk)? Sources: [20261126-184738] x2.

7. **DRLA X gizmos in Daggerfall areas.** The familiar deployer, mod reviser, weapon recycler, mod extractor,
   dimensional box, demon statue and quest objects "spawn every 2 to 3 map loads on Daggerfall maps too". The Maestro
   familiar "gives a random temporary DRLA class perk for one level". It unlocks only by finishing a game, so today it
   appears only through the console or a debug event. Keep them, or disable class perks and/or the gizmos in bridged
   games? Source: [20261126-200147].

8. **Fall damage reduction below Jumping 75.** Today there is none below 75 and immunity from 75, "as the card asked".
   Options: no reduction (as built), or a curve "for example linear from no reduction at 0 to full immunity at 75".
   Sources: [20261126-200628] x2 [20261126-231932].

9. **Jumping skill use and the coyote double jump.** (a) "In Daggerfall, jumping trains the Jumping skill. Should each
   jump in Doom count as a Jumping skill use?" Today jumping does not train it. Related decision: 20261126-skill-uses-from-doom
   (event-to-skill mapping open apart from running, backstabbing and climbing). (b) "Should a mid-air jump be allowed
   after walking off an edge without jumping first? It currently is." Sources: [20261126-200628] x3.

10. **Automatics fire-rate bands and suppression.** Open on the card and not built: at which skill level the three
    fire-rate bands unlock, the band boundaries in shots per second, the lowest band's exploding-round splash radius
    ("+15 light splash"), and the size and length of the 75 suppression slow. "The rest of the 75 perk (+1% damage taken
    per hit up to +15%) is built." Sources: [20261126-222743] x2 [20261127-005245].

11. **Starting gun when loading a plain Daggerfall save.** "Loading a plain Daggerfall save whose character has no Doom
    gun still gives the pistol and its bullets (your 2026-11-24 rule). Should that case also follow the highest gun
    skill, like a New Game does now?" Source: [20261126-231433].

12. **Starting gun material.** "Each starting gun uses the same fixed per-gun material roll the old pistol adoption
    used, so some come out Steel or Silver (the DRLA shotgun is Silver, the stock pistol Silver)." All Iron, "to match
    'the weakest, most basic gun'", or keep the fixed roll? Source: [20261126-231433].

13. **Dodge feedback.** Agility's dodge scope was built as the owner wrote it (bebf965c: any damage except telefrag and
    forced). "A dodged hit is currently silent, with no message, sound or damage-number popup." Add a cue (a "Dodged"
    popup or a whoosh sound) or keep it silent? Sources: [20261126-235534] x2.

14. **Crime for picking into a closed building.** "Adding Daggerfall's building locks means closed shops and houses
    refuse entry at night unless picked. Daggerfall also counts a successful pick into a closed building as a crime".
    Raise Daggerfall's breaking-and-entering crime as vanilla does, or only the lock and minigame for now? Source:
    [20261126-114215].

15. **Ammo tier prices.** "The card sets Regular ammo at the base prices (bullets 1, shells 3, rockets 10, cells 10
    gold), but your earlier tier table had Regular at 3x base. I set Regular to 1x and left the other tiers' gold prices
    as they were, so Steel is now 5x Regular instead of 5/3x. Cells also doubled at every tier." Keep this, or scale the
    higher tiers to match? (Cells at 10 gold follows decisions 20261126-energy-weapons-owner.) Source: [20261127-005134].

16. **Explosives 50 direct-hit bonus amount.** "The mechanism is built and tested with a test value of +50%, but
    Daggerfall sends 0". Percentage of impact damage (as built, impact only, no splash) or a flat amount, and how much
    (for example +25%, +50%, +100%)? Sources: [20261127-024745] [20261127-101856].

17. **Inpulsa's Broken Heart details** (choices made inside the design, to confirm): chain blast radius 128 (a
    rocket's); damage falls off with distance like any Doom explosion (25% of max health at the centre); chain blasts do
    not get the +0-60% Explosives bonus; townspeople and guards caught in a chain take damage (only the player is
    spared). Source: [20261127-024745].

18. **Shotguns 75/100 collision damage.** Built and tested (once per shot, scaled by impact speed like the wall slam),
    sent as 0. "Your tentative numbers were 200 at 75 and 400 at 100; confirm or give others." Sources:
    [20261127-033904] x2 [20261127-100612] [20261127-110332].

19. **How "slower shotguns push harder" is measured.** "Today knockback only scales with pellets that hit (the Double
    Shotgun gets full effect; Shotgun, Assault Shotgun and Autoshotgun all fire 7 pellets and get half)". Options:
    reload time (the owner suggested reload speed), shot-to-shot cycle time compared with the Double Shotgun, or a fixed
    list (for example Autoshotgun x0.5), and how strongly it scales. Sources: [20261127-033904] x2 [20261127-100612]
    [20261127-110332].

20. **Shotguns 100 reload speed.** It stays at the 25 perk's 35%, "the perk window text no longer promises more".
    Faster at 100, and by how much? Sources: [20261127-033904] [20261127-100612] [20261127-110332].

21. **Extra pellets for projectile shotguns.** Projectile shotguns (DRLA Plasma Shotgun when Shotguns is its higher
    skill) get the damage and knockback perks but not +50%/+100% balls per shot, because "the engine has no pellet hook
    for projectile fire, so extra balls would need their own spread". Multiply them too? Sources: [20261127-033904]
    [20261127-100612] [20261127-110332].

22. **Dungeon brightness.** "Doomerfall dungeons are about twice as bright as Daggerfall Unity (mean brightness 39-50
    against 19-33 at the same spots), with much less darkening toward distant walls." Match Daggerfall Unity, or keep
    the brighter look? Evidence: review/visualparity/scenes/*.side.png; CHANGELOG visual parity. Source: [20261127-052057].

23. **Eye height and field of view.** Doomerfall: 48 units (1.60 m), 90° horizontal. Daggerfall Unity: 1.71 m, 65°
    vertical (80.7° horizontal). Match Daggerfall Unity or keep Doom's defaults? Evidence: s1_00.native.side.png
    against s1_00.side.png. Source: [20261127-052057].

24. **Outdoor sprite and monster lighting.** Exterior floors now take Daggerfall's flat daylight (DD_ExteriorGroundLight,
    hw_flats.cpp:308-317), but "billboards and monsters ... still use Doom's sector light, which darkens with distance".
    "At a snowy night, Doom's trees and monsters are much darker than Daggerfall's." Flat daylight on sprites matches
    Daggerfall Unity "but it changes how visible monsters are at range (combat visibility)". Also, the paired comparison
    used only a winter month, so summer and rain ground lighting were not checked. Options: flat daylight for sprites
    outdoors, or keep Doom's distance darkening. Sources: [20261127-043610] [20261127-051951] x2.

25. **Auriel's Shield as a quest reward.** With shields out, "Auriel's Shield (quest B0B71Y03) and Spell Breaker (quest
    50C00Y00)" stay as rewards that can be carried but not equipped (now stated in manual.md). Spell Breaker is covered by
    backlog `spellbreaker-ring`, which says "Auriel's Shield (quest B0B71Y03) is not covered by this item". For Auriel's
    Shield: (a) carry-only (the goal said shields should not appear anywhere, so this needs approval as an exception),
    (b) swap it for another artifact, (c) the quest gives no artifact. Sources: [20261127-054419] x2.

26. **Corpse decay.** "Corpses never decay right now: Daggerfall keeps every corpse forever in the save. Should corpses
    in towns go away after some game time, the way Daggerfall Unity's scene cache eventually forgets loot piles, or stay
    permanently?" Context: the pillar "what the player does stays done" and backlog `turn-off-daggerfall-resets` (total
    persistence). Source: [20261127-084126].

27. **Dungeon pickup lean.** (a) "I kept health at a flat 30% in every dungeon. Only the four ammo kinds lean ...
    because a health-leaning dungeon would reach about 84% health and you asked to restrict health." Should health
    also lean? (b) "About 1 dungeon in 5 leans hard (for example over 50% shells, or about 50% rockets in Yagertor's
    Nest), and most lean only a little." Right amount, or rarer or more common hard leans (PickupLeanMax and the cube in
    PickupExport.cs)? Owner rule: decisions 20261126-slope-climb-pickups-owner ("made uneven by the loot system").
    Sources: [20261127-091736] x2.

28. **What "affordable" means for the regional favourite** (game designer already ruled **Leans**, decisions
    20261127-favourite-affordable-threshold; needs the owner's yes). Built: purchasable "when one of its classes costs at
    most one average encounter at the area level (`region_afford 1`)". In stock Doom that gives Spider Mastermind
    regions stand-ins up to level 21 and Cyberdemon regions up to level 20. "3 averages would bring the favourite back
    around level 12; 6 would bring it back around level 5." The review notes the planner's bound "disagrees with what
    the budget can buy" (EncounterPlanner.zs:419, 730-736): giant rooms and bosses still buy dearer monsters, and the
    reverse gap exists (an army can hold only a dearer class and get no stand-in). Sources: [20261127-093608] x3.

29. **Dear favourite left in the army** (game designer **Leans** keep, decisions 20261127-giant-rooms-dear-favourites).
    When a stand-in is added but the core, support or wildcard pick already rolled the dear favourite, "Giant rooms or
    bosses then sometimes spawn it anyway: 7 of 66 stock test dungeons, for example 11 Spider Masterminds at level 14."
    Keep it as a spike, or drop or replace that entry (this changes the core, support and wildcard rules)? Sources:
    [20261127-093608] x2.

30. **Stand-in ranking order.** "The stand-in is ranked by theme fit first, then your colour or family preference, then
    nearest kind on the ring. So ... at level 0 in an Orc Stronghold ... a zombie stands in for a Spider Mastermind."
    The owner decision (20261126-favourite-fallback-owner) reads "by theme and region (its colour or DRLA family first,
    then the nearest kind)". Theme first, or colour/family first? Source: [20261127-093608].

31. **Cap on Doom weapon values.** "Doom weapon values reach 768,000 gold before shop pricing for a Daedric legendary
    superweapon (very rare: 460,800). Daggerfall's dearest weapon, a Daedric Dai-katana, is worth 76,800. Shops pay in
    letters of credit with no gold limit". Cap (for example at 76,800; WeaponValues.txt has a `cap` line ready) or
    uncapped? Source: [20261127-095003].

32. **Doom weapon weight by material.** "Right now it depends only on the kind of weapon and its sprite size, per your
    rule." Should it change with material, as Daggerfall weapon weights do? Source: [20261127-095003].

33. **Daggerfall creatures in Doom.** "Doom can now show a Daggerfall creature (DFCreature ...), but nothing spawns one
    yet and the base creature only stands still. Which Daggerfall creatures, if any, should appear in Doom instead of a
    Doom monster, and how should they fight?" (for example a Doom monster's AI with Daggerfall's damage numbers). This
    would create a system, so it is likely Deferred. Source: [20261127-100846].

34. **Material odds on shop shelves.** "Shelves call FormulaHelper.RandomMaterial with Daggerfall's classic curve
    (DaggerfallLoot.cs:227, 229, 273, 278). The approved odds are applied only through DoomerfallMaterialRoll in
    DoomerfallDrops.RollEnemy". gamedesign.md line 26 says the material tier comes from the approved odds for the area
    level. With shop levels up to 30, "a single level 30 weapon smith shelf had a Daedric item 90.5% of the time (the
    notes' approved-odds figure is 50.0%). Level 15 gave 43.3% against 12.8%", restocking daily. Switch shelves to the
    approved odds (they would need their own seed or plain random)? The shoplevels lane is not merged. Sources:
    [20261127-103953] x2.

35. **Several towns on one Doom map.** "The City of Daggerfall's map (group 9183) also holds the village Ripwych
    Commons, and each keeps its own town level on the same map (Daggerfall 20, Ripwych Commons 5). Should every town on
    one Doom map share the group's highest level instead?" Source: [20261127-110527].

36. **Ship in the transport menu.** "Ship teleports the world to your ship's map pixel ... without a fast travel, so
    Doom cannot follow it today. For now, choosing Ship in a paired run says 'You cannot board your ship yet.'" Is holding
    it OK, and later should boarding go through Doom's travel path (which also needs a Doom map of the ship)? Source:
    [20261127-113137].

37. **Riding in Doom.** Daggerfall keeps Horse or Cart, but Doom's movement does not change. In Daggerfall Unity,
    riding changes speed, changes jumping, turns off climbing, draws a horse or cart sprite, and dismounts at doors.
    Which of these should Doom get? Ride speeds from Daggerfall, or relative to Doom's run speed? Can you fight while
    mounted, "given that Doom's weapon sits where Daggerfall draws the horse"? Source: [20261127-113137].

## 3. Owner engineering questions

1. **Long first visit to an unconverted dungeon.** The loading screen now holds the game during the wait (CHANGELOG
   loadscreen 01), but the wait is long: "7 to 11 s on a quiet machine and 13 to 47 s tonight with other work running,
   because the converter runs at BELOW_NORMAL priority, one conversion at a time" (dd_towncache.cpp:226, :324;
   dd_treadmill.cpp:1979-1983). A conversion already running for another place must finish first. Options: (a) normal
   priority, (b) prefetch every dungeon of a town or overworld tile when it loads, not only within 768 units of the door,
   (c) ship all ~4,200 dungeons pre-converted ("much longer install, a few GB on disk"), (d) accept it for now. Sources:
   [20261127-005009] x2.

2. **Dungeon collision trade-offs (dungeonedges).** (a) "Where a 45-degree bevel floor runs under an inward-leaning
   wall ... a player hugging that wall now stops dead instead of sliding along it." Options: accept it as faithful;
   drop steep leaning ceiling slopes so the head can pass into the wall ("about 1,100 sloped-ceiling sectors"; the view
   can clip); or make the low strip solid collision (new converter work, keeping crawl spaces of 28 units or more).
   (b) "At 931,1490 running south-east ... the old map has one 8-unit floor step, and the new map instead has one
   slightly slow tic (4.95 units against a typical 11)". Count it as not worse? `work/todo.md` (dungeonedges 01) already
   asks (b) inline. Sources: [20261127-035402] x2.

3. **Where Doom-side rule numbers live, and one attribute pattern.** (a) "DoomerfallJump.zs:30-35 and :63-77 hardcode
   the falling damage numbers (5 m threshold, 5 HP per metre) from Daggerfall's code, and the Jumping perk values".
   Automatics instead receives its values through DFB_SHEET_AUTO_* sheet values. AGENTS.md: Daggerfall owns the rules
   and passes them to Doom. Risk: a Daggerfall-side change (or a DFU mod) does not reach Doom, and later skill cards may
   copy either pattern. (b) Agility has its own item and handler (DoomerfallAgility.zs) beside card 01's
   DoomerfallAttributeEffects (DoomerfallAttributes.zs). Both are merged today, so "cards 03 and 04 could follow either
   pattern". Decide one pattern for each before more skills and attributes are built? Sources: [20261126-231932]
   [20261126-235534].

4. **Shot attribution for children is a distance guess.** Shot tags are merged, but a child takes "the tag of the
   nearest tagged actor within 128 units, alive or destroyed this tic" (DoomerfallShots.zs:137-170; `ChildReach = 128`
   at line 58 today). Mixed-gun fights can mis-credit hits, and children beyond 128 units get no tag. "A small engine
   hook that passes the tag from the actual spawning actor would be exact, and is cheaper to adopt before those perks
   are built." Cost: Classify scans the whole tagged list per new actor (FindInventory and Distance3D each), and
   WorldTick deletes dead entries one at a time. "Hundreds of live entries could cause frame drops" (unmeasured).
   Replace it with a spawn hook before the Explosives, Shotguns, Pistols and Energy Weapons perks? Sources:
   [20261127-080929] x2.

5. **Build folders and build permission for lanes.** "To verify paired work I need a UZDoom built from this checkout.
   A UZDoom build and copying another lane's UZDoom build were both denied tonight. May overnight lanes build UZDoom
   into their own folder under DoomDaggerfall-build, or reuse a recent lane's build?" This ties to Major oversight 17
   (shared folders change under lanes). Source: [20261127-054419].

6. **Texture packs in .dfmod form.** "Doom can read Daggerfall Unity texture packs installed as loose PNG files
   (StreamingAssets/Textures), but not packs packed as .dfmod files, which are Unity asset bundles. ... If .dfmod packs
   must work too, the likely way is for Daggerfall Unity to send the image pixels to Doom over the bridge, which is a
   larger job." Is loose-file support enough? Related backlog: `support-texture-packs-and-lighting-mods`. Source:
   [20261127-084126] (asked 3 times).

7. **Weapon values: one more verification run?** The rest needs "a new run with budget": convert a town with a
   weaponsmith and a pawn shop, make the sync-test start position configurable, walk into both shops in a paired run,
   then rebuild and re-verify. "Or is the current evidence enough for now: real priced sales at the general store, plus
   Sell windows set to weaponsmith and pawn-shop pricing?" `weaponvalues` 01 is still in todo. Source: [20261127-095003].

8. **Live season swap in a loaded town.** RefreshTownSeason (dd_treadmill.cpp:1572-1606) does it all in one tic:
   destroys and respawns every DFCityFlat (3585 in Gothway Garden), then re-uploads the mesh ("138 ms for that town's
   mesh upload and 360 ms for a large mesh"). It asks for the town at distance 0, "the same priority as a pressed door"
   (dd_treadmill.cpp:2177), so a background conversion "can hold up an uncached interior or dungeon, including one the
   player has just pressed". SetWinter drops interior cache slots too. It uses a third copy of the DFFLATS parser, does
   not rebuild wilderness flats, and "a save resumed in another season restores old-season billboards". A winter start
   triggers it about 10 s into play. Spread or share the rebuild, and lower its priority? This ties to the owner-held
   first-town season item in todo. Sources: [20261127-051951] x3.

## 4. Major oversights

Each item gives what is wrong, the evidence, what it could break, the confidence, the sources, and whether it is still
present.

1. **Doom items dropped from the Expanded Inventory window become Daggerfall piles.** `ExpandedInventoryWindow.OnPop`
   calls `LootTextureUpdate()` (ExpandedInventoryWindow.cs:349-352), which moves `droppedItems` into a new Daggerfall
   loot container (lines 1343-1348) before `base.OnPop` reaches `DoomerfallDoomItems.DropToDoom(droppedItems)`
   (DaggerfallInventoryWindow.cs:697). The expanded window is the registered inventory (ExpandedInventory.cs:19).
   Could break the gun drop route and the gun's Doom state. "Existing tests call DropToDoom directly, so they would not
   catch it." Report confidence medium. **Still present**: I confirmed the call order in the current code (not run).
   Source: [20261126-201527] (x2).

2. **Doom poison bypasses Daggerfall's HP ownership.** `P_PoisonDamage` (p_interaction.cpp, about line 1860-1900) now
   applies Willpower (line 1871) but still subtracts from `player->health` and runs Doom's own death check. It never
   calls `DD_BridgeHpHit` (used by P_DamageMobj, line 1416). "Daggerfall only learns of it a tic later through
   DD_BridgeHpThink's direct-assignment path. A lethal poison tick could therefore kill the player in Doom outside
   Daggerfall's death rules." Not checked whether DRLA or DRLAX poison the player. Report confidence high for the path.
   **Still present** (checked in code). Sources: [20261127-004045] x2.

3. **Travel from the level-up character sheet desyncs the engines.** When Daggerfall opens the sheet itself for a
   level-up (DFB_UI_DAGGERFALL), the player can go Logbook > quest > travel map. `RefuseJournalTravel` refuses only when
   `openId` is UI_JOURNAL or UI_CHARACTER (DoomerfallUi.cs:506), and `OnPostFastTravel` ignores the trip because
   `showingTravelMap` is false. "Daggerfall would move its player while Doom stays where it is". Report confidence
   medium, from the code. **Still present**: line 506 has no UI_DAGGERFALL case. Source: [20261127-023449] (x2).

4. **Agility can dodge non-forced kill calls.** `DoomerfallAgility.ModifyDamage` exempts only `DMG_FORCED` and
   telefrags (DoomerfallAgility.zs:97). "`Thing_Destroy` (no flags) and `A_Kill*` (`DMG_NO_ARMOR | DMG_NO_FACTOR`) would
   fail to kill the player about 15% of the time at Agility 100." Willpower got an explicit DD_KillCall exemption
   (efa8d625); Agility did not. Report confidence high. **Still present** (checked line 97). Source: [20261127-004045].

5. **Doom can report a place before Daggerfall's record arrives and overwrite permanent state.** (a) Doors: "Doors are
   armed only by a one-time answer to the fresh map's request, and a loaded save never asks again. On timeout the
   autosave is taken anyway with the doors unarmed ... Manual saves from the menu are not gated at all" (dd_setup.cpp:77,
   dd_doors.cpp:105, g_level.cpp:1547). Also, Distill "omits the lock field while the doors are unarmed" and Doom's report
   on save or leave replaces Daggerfall's record (dd_locations.cpp DD_LocationsSave, DD_LocationsLeaving), so "earlier
   picks, lever unlocks and relocks for that dungeon are lost". (b) Taken pickups: "The setup gate that holds autosaves
   is off for restored maps (dd_setup.cpp:41, 49). A save or exit before the reply therefore reports the place from live
   actors only (dd_locations.cpp:153-171, 367-379) ... Leaving also sets waiting=false (dd_locations.cpp:317)". Could
   break the persistence pillar (doors and pickups reset). Report confidence high from code that it happens in the
   window, low on how often (mainly a slow or lost Daggerfall answer). **Probably still present**: the loading screen
   blocks saving during holds, but I found no change to these paths. Not verified. Sources: [20261126-142733]
   [20261126-150155] [20261126-212713].

6. **Daggerfall's game start drops queued place records.** `DoomerfallLocations.OnStartGame` > `ForgetWorld()` calls
   `sendQueue.Clear()` (DoomerfallLocations.cs:117), which drops a record logged as sent but not yet put on the bridge.
   Seen once: "Doom never received it ('DDLOC no record from Daggerfall'), and the gate timed out after 5 s". Doom now
   avoids the race in that flow by waiting for the place record before reporting arrival. Any other flow that starts a
   game while a reply is queued "loses that record, and Doom then builds the place from its cache, ignoring Daggerfall's
   saved state". Report confidence high for the mechanism. **Still present** (line 117). Sources: [20261126-185032] x2.

7. **Untaken tiered ammo pickups bloat the location record.** `IsUnchanged` (dd_treadmill.cpp, about line 713-715)
   compares a pickup's amount with the class default (`Inventory.Amount` 1), so every untaken ammo pickup is written as a
   changed item row on each leave. "In Privateer's Hold the record on leaving is 49 item rows / 4288 bytes. With the
   comparison fixed it was 21 / 2240". The fix was reverted as out of scope (6e6301b0). Caution: a fix must keep tier
   and rounds, or Convert would re-roll them at whatever area level the handler holds. Breaks architecture.md engineering
   rule 8 (record size). Report confidence high that the leak exists. **Still present** (the comparison is unchanged).
   Source: [20261126-212713].

8. **Schism weapon pickups are not treated as guns.** `IsGun` (dd_items.cpp:271-277) accepts only `Weapon` and
   `RLBaseWeaponPickup` descendants. Schism's floor weapons are CustomInventory givers (for example
   `Schism_ShotgunGiver`; Schism_097D/Actors/Weapons/Slot 3/Shotgun.txt). A Schism weapon taken into Daggerfall becomes a
   plain Doom item with "no material, no hotkey equip, no gun state", valued at the Iron price, so the owner's
   Steel-to-Daedric Schism values never apply. Fixing it changes bridge item classification, and saved items may need
   converting. Report confidence medium-high, not seen in a running game. **Still present.** Sources:
   [20261127-095003] [20261127-110242].

9. **Outdoor water is ground in Doom.** The town and overworld export draws sea and lakes as ground mesh. Their floors
   use only FLOOR0_1 or GRASS1 (CityExport.cs:1393, 1403), and only dungeon pools are swimmable (Water.cs). The
   fall-damage exemption now arrives as a flag (69945dd2). Swimming, the Swimming skill, drowning and resting while
   swimming still cannot work outdoors, because "Doom's waterlevel stays 0 and the player walks on the sea surface". No
   backlog item found for it. Report confidence medium-high, from the converter. **Still present.** Source:
   [20261126-200628] (x2).

10. **Building interiors export no hinged action doors.** "tools/dungeon_converter/SiteExport.cs writes no DFDOORS;
    only MeshExport.cs:209 (dungeons) does." Interior locked doors cannot work "until interiors export their action
    doors with Daggerfall's LoadID". This is a missing dependency for backlog `locked-doors-with-daggerfalls-requirements`.
    Report confidence high. **Still present** (no DFDOORS in SiteExport.cs). Source: [20261126-114215].

11. **DRLA's Dragonslayer deals no damage.** Its Fire state (DRLA 1.1.5 actors/weapons/legendary/DragonSlayer.txt lines
    76-87) "only alerts monsters, waits 10 tics and plays a swing sound; the projectile line is commented out". It is
    in DRLA's item spawners (ItemSpawners.txt), is filed under Melee (DoomerfallWeaponCategory.zs:128), and is named in
    manual.md's Melee bullet. A player can get a legendary melee weapon that cannot hurt anything. Report confidence
    high. **Still present** (DRLA content, not a Doomerfall change). Source: [20261127-041725].

12. **UZDoom crash on a ZScript pattern.** "UZDoom crashes with C0000005 during LoadActors when a ZScript EventHandler
    has constant-false 'if (CONST) { ...; break; }' blocks inside a large switch." It happened every time with the DRLA
    set. Making the constants members fixed it. Evidence: work/notes/20261126-114215.md. CHANGELOG 2026-11-23 records a
    related constant-false-`if`-with-`break` fault in a harness. "Any mod or test script with that pattern could crash
    startup." Report confidence medium on the trigger, high that the crash is real. **Unknown**: the engine is not
    fixed as far as I found. Source: [20261126-114215].

13. **The bridge bindings drift check always fails.** bridge/test/check_bindings_drift.py:16 looks for `#define
    DFB_PROTOCOL_VERSION 4u`, and the header is at `7u` (doomerfall_bridge.h:37). "The drift check reports FAILED on
    every run, so it no longer protects anything." Report confidence high. **Still present.** Source: [20261126-231932].

14. **Parallel perk lanes claim the same character sheet slots.** Automatics took values 155-161 (format 7), and the
    Shotguns lane added 162-167 (format 8, 168 ints). "The Explosives perks lane (skillperks 03) and later lanes will
    likely also append at 162+ and bump the format version". A merge must renumber bridge/doomerfall_bridge.h, the
    generated bindings, each lane's ZScript constants and tests that hard-code SHEET_INTS/version (automatics_test.py,
    shotguns_test.py). Otherwise "Doom will read the wrong rules". The skillperks continue branches were cut from
    4df924e4, which has neither integration (DoomerfallShots) nor the earlier Shotguns branch. Report confidence high.
    **Still present** for skillperks 03 and 04 (todo: both unmerged). Sources: [20261126-222743] x2 [20261127-033904]
    [20261127-100612].

15. **The paired New Game driver stalls, and posted keys may not reach Daggerfall message boxes.**
    `tools/new_game/run_new_game.py create` (also used by paired_walk.py and fixed_drops/paired.py) repeatedly stalls at
    "ui: top window is DaggerfallMessageBox" after race select, or at CreateCharRaceSelect. This happened in 4 of 4, then
    5 attempts on 2026-11-27 from about 04:30 to 06:15, including a control with an older Daggerfall build
    (D:/dev/DoomDaggerfall-build/shields-control/results/fresh1-df.log). It passed at about 04:00 and on 2026-11-26.
    "Y/Enter/Esc via PostMessage" stopped closing message boxes while clicks still worked (workaround:
    tools/shields/shields_paired.py --click-boxes). Separately, the Find test saw Daggerfall's "travel to X?" box ignore N
    and Escape while other keys worked (HotkeySequence path in DaggerfallUI.OnGUI). Also seen: a bridged New Game failed
    in 2 of 6 runs under load ("the start location did not load"), and the fixed_drops "fresh" run stayed in the menu
    state in 2 of 3 runs. CHANGELOG loadscreen and Luck entries record the stalls as driver or machine load. "If it is
    the second [a change in how keys reach Daggerfall's message boxes], the real New Game confirmation box could be
    broken for players", and keyboard yes/no could be broken in every Daggerfall popup in Doom. Report confidence medium;
    cause unknown. **Unknown**: no fix found. Sources: [20261126-200147] [20261127-034855] [20261127-035402]
    [20261127-044701] [20261127-045928] [20261127-054419] x2 [20261127-081218].

16. **Tests on the private desktop may check blank or tiny frames.** Doom screenshots under quiet_run are "always
    320x200" ("every Screenshot_Doom_*.png under D:\dev\DoomDaggerfall-build is 320x200"). Doom's screenshot of an open
    Daggerfall window is all black, although "the bridge reported 180+ frames shown". A Daggerfall Unity player on an
    unseen desktop "got no IMGUI events at all". The launcher's nested private desktop without --show-dfu gives black UI
    frames (review/menu-text-runs base-1280 against base-show). Test-only mouse positions look doubled with -dfuitest
    ((25,180) missed Find; a right-click at (160,100) zoomed at (320,200)). `-dfhotkeyshots` throws
    ArgumentOutOfRangeException in ItemBuilder.CreateRandomPotion and writes no screenshots. Could break: "overnight UI
    tests (-dfuitest and the menu, travel and rest harnesses) can pass on window-opened and closed log lines while the
    window's picture was never drawn", and frame-time numbers from private-desktop runs. CHANGELOG menubackdrop 01 also
    notes empty Daggerfall renders on the private desktop. Report confidence high for 320x200 and the launcher setup,
    medium for the rest. **Still present.** Sources: [20261126-220954] (x3) [20261127-044701] [20261127-052057]
    [20261127-055457] [20261127-061016] x2.

17. **Shared or linked build and demo folders change or vanish under running lanes.** Examples: uzdoom-items was
    rebuilt from another source with a different bridge layout (DFB_ERR_LAYOUT -5). verify-agility vanished mid-run, and
    merge-skillcore, review\doom-items and review\pickups no longer exist. uzdoom-quiet/bridge-quiet/launcher-quiet are
    configured from lane-quiet's worktree (CMakeCache), which caused "bridge DLL does not match this build: schema
    6d78e01b08bb0c58, expected da13cdd1f973cba8", and old builds lack natives the mod now uses ("Unknown function
    DD_SheetValue"). The lane-travel worktree's Builds\Windows64 is a link into another session's scratchpad. Mixing a
    launcher or bridge DLL from another branch gives error -5, and CliBuild output lacks Portable.txt and
    PortableAppdata, which -dfsynctest needs. Review demos link data by junction (perk_popup.py assemble), so
    explosives-perks and shotguns-perks fail with "File not found ...\data\ddruntime.pk3" after automatics-perks was
    deleted. daynight-sync's play.bat and tools/daynight/paired.py point at the deleted review\doom-items. mapkeys.py
    pointed at deleted folders. gen_overworld.py's DEFAULT_WORLD_DIR (D:\dev\DoomDaggerfall-build\stitch-data) no longer
    exists, so demo overworld.pk3 files lack DDNATURE (scripts/play/install.py passes --world-dir and is not affected).
    Could break: lanes testing another branch's binaries without knowing, results that do not reflect the branch they
    claim, and owner demos that fail to start. Report confidence high (seen directly in several runs). **Still present**
    as a process gap. Sources: [20261126-184614] (x2) [20261126-213115] [20261127-005134] x3 [20261127-043610] x2
    [20261127-044701] [20261127-055226] x2 [20261127-075528] [20261127-080929] [20261127-101856] [20261127-110332].

18. **UZDoom builds fail at random when several lanes compile at once.** "A fresh build of unchanged code at --parallel
    6 had CL.exe exit with code 1 and no message on abseil projects. Rerun at --parallel 2, it succeeded. The verifier's
    build had link.exe exit with code 1 and no LNK message". Likely memory exhaustion (not confirmed). "This can make the
    verifier fail good work at random." Report confidence medium-high. **Unknown.** Source: [20261126-213115].

19. **Paired perk tests run with real HP, and an unexplained UZDoom exit.** "Imps took Daggerfall HP to 0, Doom logged
    'player hurt 1000000 by None' and 'Player died.', and the run stopped cycling with no error". Other perk paired
    harnesses (automatics_paired, Shotguns, perk_popup) "probably have the same exposure". Separately, UZDoom "exited
    without any fatal message, crash file or log line in three paired runs ... after an encounter RLDemon had bitten the
    player to 18 HP and a chain blast went off" (review/explosives-paired/log-exppair.txt, uz.log). The first finding
    may explain the second (a death handoff), but that is not confirmed. If it is a real crash, "players lose their
    game". Report confidence low to medium that it is a real game bug. **Unknown.** Sources: [20261127-024745] (x2)
    [20261127-101856].

20. **Possibly unreachable dungeon entrance: Greensmith Tower (group 1457, SpiderNest).** Its town map has "13 dungeon
    door planes, all at z 198.5 or 392 and none at ground level" (DDDOORS lump). The paired run failed with "DTFAIL door
    did not open" (D:\dev\DoomDaggerfall-build\dungeon-runtime\paired\run-1457). A later continuation entered "a spider
    nest" through a real door (CHANGELOG 2026-11-26), possibly a different one. Report confidence low-medium; "it may
    only be the harness's placement". **Unknown.** Source: [20261127-005009] (x2).

21. **Jump height is saved pre-scaled and guessed on load.** DoomerfallJump.zs:108-125 treats a loaded JumpZ as the
    default only if it matches "default x sqrt(HeightFactor(k)) under the current formula". "If the height formula is
    later tuned, saves made under the old formula will mostly fail to match, the old scaled value will be taken as the
    base and scaled again, and the too-high jump will persist". A map's or mod's own JumpZ that happens to match is
    misread. Suggested fix: store the unscaled base. Report confidence high from code; the formula-change case was not
    tested. **Probably still present** (b352fa2d and a5af4ced came before the review). Source: [20261126-231932].

## 5. Dropped

One line per distinct item: source id, report type, category, the item's opening words, and the reason or citation.
DUPLICATE lines name the kept item (G = Design question, E = Owner engineering question, O = Major oversight, by
number).

- [20261125-202715] question, DROP-MINOR: "When a locked door is used with no lockpicks,..." - Lock message wording; cosmetic text choice.
- [20261125-202715] oversight, DROP-MINOR: "The overnight lane for this goal was branched from..." - queue.ps1 passes -From straight to git branch (line 41); not reproduced since; one-off.
- [20261125-202715] oversight, DROP-ANSWERED: "quiet_run.py loses track of programs started through a .bat..." - Lane hang fix applied: rounds run in Windows jobs that close leftover games (ed520f6c).
- [20261125-202716] question, DROP-MINOR: "Clear-weather fog: the goal card says Daggerfall's clear fog..." - Doom copies the fog Daggerfall actually draws; the 2400 m figure was only a code default.
- [20261125-202716] question, DROP-ANSWERED: "Winter textures switch at the next area load, not..." - Winter at next load accepted by owner (CHANGELOG day/night known gaps); live town season swap since merged (53ab0c1c).
- [20261125-202716] oversight, DROP-ANSWERED: "Hidden game sessions can outlive quiet_run. If a launcher..." - Same leak; fixed by ed520f6c (Windows jobs).
- [20261125-235942] oversight, DROP-ANSWERED: "Paired-run scripts that kill quiet_run with proc.kill() leave the..." - Same leak class; fixed by ed520f6c; hpformula runner fixed in its own run.
- [20261126-005053] question, DROP-ANSWERED: "Weapon categories: when a gun fits more than one..." - Precedence merged (CHANGELOG weapon categories), since refined by owner rulings (decisions 20261126-rifles-skill, 20261126-two-skill-weapons-owner; Uzi a594d521; Beretta 0f953acc).
- [20261126-005053] oversight, DROP-ANSWERED: "bridge/test/sheet_test.py requires Doom to read every sheet version Daggerfall..." - Documented: CHANGELOG 2026-11-26 weapon skills entry says the sheet test's strict check misses back-to-back publishes.
- [20261126-005053] question, DUPLICATE of G2: "Existing magic items that enhance a monster language (Enhances..."
- [20261126-021025] question, DROP-MINOR: "Perk popup: no perk has an effect yet, so..." - Perk popup wording; perks since built, placeholder text moot.
- [20261126-021025] oversight, DROP-ANSWERED: "skillcore lane base is missing card 01: overnight/skillcore and..." - Card 01 since merged (CHANGELOG weapon skills, 2026-11-26).
- [20261126-021025] oversight, DROP-ANSWERED: "Leaked game processes from review demos: after demo smoke..." - Leak fixed by ed520f6c.
- [20261126-113251] question, DROP-ANSWERED: "Rest in Doom: pressing the rest key again while..." - Owner: rest is "Daggerfall's rest menu exactly" (decisions 20261126-rest-and-level-hud); the rest key ending a rest without Daggerfall's wake-up is a bug to fix, not a question.
- [20261126-114057] oversight, DROP-ANSWERED: "The goal card asks the agent to merge a..." - Orchestrator now joins lanes itself (6b3623ed, 71740976).
- [20261126-114057] oversight, DROP-ANSWERED: "play.bat demos that use 'start' detach from quiet_run: quiet_run..." - Leak fixed by ed520f6c.
- [20261126-114057] question, DROP-ANSWERED: "Merging agent/daynight-20261125-202716 into agent/daynight-20261126-114057 is refused by this session's..." - Orchestrator joined the lanes; day/night merged (CHANGELOG 2026-11-26).
- [20261126-114057] question, DROP-ANSWERED: "The lockpick continue goal says to merge agent/lockpick-20261125-202715 first,..." - Lockpick merged (CHANGELOG 2026-11-26).
- [20261126-114057] question, DUPLICATE of G1: "Gun skills placeholders (work/notes/20261126-005053.md), each needing your yes or..."
- [20261126-114057] oversight, DROP-ANSWERED: "bridge/test/sheet_test.py requires Doom to read every sheet version Daggerfall..." - Documented in CHANGELOG (sheet test strict check).
- [20261126-114057] question, DUPLICATE of G1: "Gun skills placeholders, each needing your yes or a..."
- [20261126-114057] oversight, DROP-ANSWERED: "bridge/test/sheet_test.py requires Doom to read every sheet version Daggerfall..." - Documented in CHANGELOG (sheet test strict check).
- [20261126-114057] question, DUPLICATE of G2: "Removed monster languages on magic items: powers that enhance..."
- [20261126-114057] question, DUPLICATE of G1: "Fighters Guild: which gun skills count toward promotion? Now..."
- [20261126-114057] question, DROP-ANSWERED: "Class skill lists: a class that listed a removed..." - Owner: removed class skills become other Daggerfall skills, gun filler rejected (decisions 20261126-two-step-skill-remap, 20261126-class-cards-hand-made).
- [20261126-114057] question, DUPLICATE of G2: "Should the item maker offer Enhances Shotguns/Automatics/Explosives? It is..."
- [20261126-114057] question, DUPLICATE of G2: "Enhances Skill powers for the removed languages (including the..."
- [20261126-114057] question, DUPLICATE of G1: "Gun skills placeholders needing your yes or a change:..."
- [20261126-114648] question, DROP-ANSWERED: "The lane-hang fix is in scripts/overnight/ (run.ps1 and queue.ps1),..." - Owner applied the patch (ed520f6c).
- [20261126-131954] question, DROP-ANSWERED: "Locked doors: manual.md exists on integration but not on..." - Lockpick merged with manual.md (CHANGELOG 2026-11-26).
- [20261126-131954] review, DROP-ANSWERED: "Look at this before merging: it is a real..." - Setup gate holds the arrival autosave until the place record is applied (CHANGELOG 2026-11-26 locked doors).
- [20261126-131954] review, DROP-ANSWERED: "Door persistence is now split in a way that..." - Rethink: lock changes kept in the location record's door fact keyed by LoadID, ledger gone (CHANGELOG 2026-11-26 locked doors).
- [20261126-135825] question, DROP-ANSWERED: "The real location record (`claude/location-record-d20944`) isn't on this branch,..." - Same rethink; location record merged (todo "Lightweight location record: merged").
- [20261126-135825] question, DROP-ANSWERED: "Door locks need the lockpick branch and `claude/location-record-d20944` merged..." - Same rethink.
- [20261126-142733] review, DROP-ANSWERED: "Frozen screen with the game still running (UZDoom/src/dd_bridge.cpp:1258 PumpArrival,..." - Playsim freezes during the setup wait (CHANGELOG locked doors); loading screen since merged (CHANGELOG 2026-11-27).
- [20261126-145138] question, DROP-ANSWERED: "Pistols: some DRLA guns carry the pistol token plus..." - Owner Pistols/Rifles decision (decisions 20261126-rifles-skill); Uzi ruled Automatic (a594d521); Beretta Pistol+Automatic (0f953acc).
- [20261126-145138] question, DUPLICATE of G1: "Pistols took slot 7 (classic Dragonish), so by slot..."
- [20261126-145138] oversight, DROP-ANSWERED: "Card 01 (gun skills core, Shotguns/Automatics/Explosives) lives only on..." - Card 01 merged.
- [20261126-145138] question, DROP-ANSWERED: "Class skill lists for the removed monster-language slots (blocks..." - Owner two-step remap and hand-made class cards (decisions 20261126-two-step-skill-remap, 20261126-class-cards-hand-made).
- [20261126-145138] question, DROP-ANSWERED: "Pistols now covers every DRLA pistol-token gun, as the..." - Same as the Pistols/Uzi rulings.
- [20261126-145138] question, DUPLICATE of G1: "Pistols placeholders: governing stat Agility, advancement multiplier 2. Should..."
- [20261126-145138] oversight, DROP-ANSWERED: "Card 01 (gun skills core) lives only on agent/skillcore-20261126-114057..." - Card 01 merged.
- [20261126-145333] question, DROP-ANSWERED: "If the seasonal overworld (winter terrain and trees outside..." - Weather seam merged: overworld snow ground (CHANGELOG 2026-11-27).
- [20261126-145333] question, DROP-ANSWERED: "To give Doom the season before the first town..." - Owner holds the first-town season item (todo "Held by the owner").
- [20261126-150155] oversight, DROP-MINOR: "Since the integration merge (open doors solid, a swinging..." - Test-harness note; harnesses fixed in their runs.
- [20261126-150155] review, DUPLICATE of O5: "Permanent lock history can be overwritten by a map..."
- [20261126-150155] review, DROP-ANSWERED: "Saved lock state is now tied to the exact..." - Lock state now keyed by LoadID (tools/dungeon_converter/door_objects.zs:314; CHANGELOG locked doors).
- [20261126-154815] question, DUPLICATE of G1: "Rifles skill placeholders (same kind of choice as the..."
- [20261126-154815] oversight, DROP-ANSWERED: "The todo order puts `startgun` 01 after `skillcore` 04..." - rifletag, lightcarbine and startgun all merged (CHANGELOG 2026-11-26).
- [20261126-154857] question, DROP-ANSWERED: "Arrival waits now show "Loading..." in the big font,..." - Superseded by loadscreen 01 (CHANGELOG 2026-11-27).
- [20261126-161434] question, DROP-ANSWERED: "Energy Weapons and Melee: the fist now has its..." - Built and merged: fists stay Hand-to-Hand (CHANGELOG weapon categories), per backlog skills-in-doom.
- [20261126-161434] question, DUPLICATE of G5: "Energy Weapons: two DRLA guns still report no skill...."
- [20261126-161434] question, DUPLICATE of G1: "Energy Weapons and Melee: the fist has its own..."
- [20261126-164636] question, DROP-ANSWERED: "Critical Strike is now gone from every class list..." - Owner: skills not in the game cannot be bought (decisions 20261126-buyable-skills-owner); removed by the remap (20261126-two-step-skill-remap).
- [20261126-164636] review, DROP-ANSWERED: "Hard to undo once a no-guns option exists: the..." - Owner: guns mode fixed per save (decisions 20261126-guns-mode-fixed-per-save).
- [20261126-174427] question, DROP-MINOR: "Weapons in two skills: when Pistols and Energy Weapons..." - Tie between two equal skills; same value either way, rare; engineering call.
- [20261126-174427] oversight, DROP-ANSWERED: "gamedesign/decisions.md line 76 links to decisions/20261126-two-skill-weapons-owner.md, which is not..." - decisions/20261126-two-skill-weapons-owner.md exists and is tracked now.
- [20261126-174427] review, DROP-ANSWERED: "Architecture, for the next card that reads weapon skills:..." - Shot tags merged: every shot carries its gun (shotsource 01, CHANGELOG 2026-11-27).
- [20261126-180338] oversight, DROP-ANSWERED: "gamedesign/decisions.md line 84 links to a detail file that..." - decisions/20261126-ammo-pickups-baron-taken-guards-owner.md exists and is tracked now.
- [20261126-180338] oversight, DROP-MINOR: "Since the summoned-monsters-drop-nothing rule (UZDoom/src/dd_lootrng.cpp), any test that spawns..." - Test-harness note; the rule is intended (decisions 20261125-unplaced-monster-loot).
- [20261126-184614] question, DROP-ANSWERED: "Main quest levels: a city's area level is its..." - The same lane later found street drops use terrain level; danger word now dungeons only (df84d3a5).
- [20261126-184614] question, DROP-ANSWERED: "Privateer's Hold's plain Former Humans: DRLA has no class..." - Owner: plain Former Humans only, no DRLA variants (decisions 20261126-privateers-hold-plain-humans).
- [20261126-184614] question, DROP-ANSWERED: "Main quest levels: a city's travel hint danger word..." - Danger word now only for dungeons (df84d3a5, CHANGELOG 2026-11-26).
- [20261126-184614] question, DROP-ANSWERED: "Privateer's Hold now admits only DRLA's base Former Humans:..." - Owner: no DRLA variants (decisions 20261126-privateers-hold-plain-humans).
- [20261126-184738] question, DUPLICATE of G6: "Bridged games use DRLA's generic player body for the..."
- [20261126-185032] question, DROP-ANSWERED: "For the arrival-wait goal, the freeze test in normal..." - One frozen tic after setup added (6be50bff, CHANGELOG arrival wait).
- [20261126-185032] oversight, DUPLICATE of O6: "Daggerfall's start clears replies it has already queued for..."
- [20261126-185032] question, DUPLICATE of G5: "Rifle tag: the Nanomachic Armament Generator (RLNanomachicArmamentGenerator) is one..."
- [20261126-185032] question, DUPLICATE of G5: "Rifle tag: the Rigelatin Assault Weapon (RLDuke2Rifle, Legendary) fires..."
- [20261126-185033] question, DROP-ANSWERED: "The Light Carbine counts as a rifle (rifle tag),..." - Rifles skill now exists (CHANGELOG weapon skills).
- [20261126-190312] question, DROP-MINOR: "Damage numbers currently show only for the player's own..." - Dev-only option, off by default (CHANGELOG damage numbers).
- [20261126-192455] question, DROP-ANSWERED: "Privateer's Hold first room: on foot (walk flood with..." - Room settled: hall with stairs (acef0fc2, CHANGELOG 2026-11-26).
- [20261126-192745] question, DROP-MINOR: "Fist on hotkey 1: I fixed only the fist's..." - Doom-style slot cycling on key 1; low impact.
- [20261126-200147] question, DROP-ANSWERED: "In bridged games, DRLA armor worn on the Doom..." - Tracked in backlog drla-armor-role and armor-damage-reduction (card ready).
- [20261126-200554] question, DROP-ANSWERED: "Privateer's Hold first room: you remembered 3 chaingunners in..." - Room settled (acef0fc2).
- [20261126-200628] question, DUPLICATE of G8: "Jumping: should the Jumping skill reduce falling damage below..."
- [20261126-200628] question, DUPLICATE of G9: "Jumping: in Daggerfall, jumping trains the Jumping skill. Should..."
- [20261126-200628] question, DROP-ANSWERED: "Falling into outdoor water: Daggerfall skips fall damage when..." - Outdoor water and Slowfall exemptions sent to Doom (69945dd2, CHANGELOG skill perks).
- [20261126-200628] question, DUPLICATE of G9: "Jumping: should each jump in Doom count as a..."
- [20261126-200628] question, DROP-ANSWERED: "Falling damage exemptions: in Daggerfall you take no falling..." - Option (a) built (69945dd2).
- [20261126-200628] oversight, DROP-ANSWERED: "Daggerfall's magic movement effects (Slowfall, Levitate, Water Walking) do..." - Slowfall sent (69945dd2); Levitate and Water Walking belong to backlog magic-casting-and-self-spells.
- [20261126-200647] review, DROP-ANSWERED: "Two rifle tags after merge (duplicated system). This branch..." - Fixed at merge: uses DoomerfallRifleTag.IsRifle (dec97b33).
- [20261126-212713] review, DUPLICATE of O5: "Taken pickups can still be forgotten just after a..."
- [20261126-213115] question, DROP-ANSWERED: "Distant trees: the overworld window has no wilderness trees..." - Nature flats and distant ring merged as a pure function of the tile (CHANGELOG 2026-11-26/27).
- [20261126-213115] oversight, DUPLICATE of O17: "The daynight-sync review demo is probably broken. D:\dev\DoomDaggerfall-loop\review\daynight-sync\play.bat and..."
- [20261126-220954] oversight, DROP-ANSWERED: "Doom's overworld ground is green grass everywhere, desert included..." - Ground tiles by climate and season (db3d356e).
- [20261126-222235] question, DROP-ANSWERED: "Privateer's Hold: the first room with stairs on foot..." - Room settled (acef0fc2).
- [20261126-222743] question, DUPLICATE of G10: "Automatics 75 suppression slow: how much should it slow..."
- [20261126-222743] question, DROP-ANSWERED: "DRLA's Uzi carries the pistol token, so under the..." - Uzi ruled Automatic (a594d521).
- [20261126-222743] oversight, DUPLICATE of O14: "The character sheet layout grows by appending values: this..."
- [20261126-223019] question, DROP-ANSWERED: "Climbing steep stairs (Privateer's Hold cliff): with a new..." - Climb merged: crossing narrow ledges stays one climb (dc33b17b, eb7e4ffc; CHANGELOG climbing).
- [20261126-225039] question, DROP-ANSWERED: "Dungeon ramps steeper than 45 degrees (Privateer's Hold has..." - Owner: 70-degree slope limit stays (decisions 20261126-slope-climb-pickups-owner).
- [20261126-225039] question, DROP-ANSWERED: "The new collision smoothing (45-degree ramp slopes, smoothed-staircase fallback)..." - Covered by backlog collision-improvement-ideas (towns and more).
- [20261126-225318] question, DROP-ANSWERED: "Strength's melee bonus applies to damage dealt while the..." - Strength follows the attack's source (7d03d318).
- [20261126-225318] question, DROP-ANSWERED: "Should the Speed attribute also scale climbing speed? Doomerfall..." - Owner: Speed scales climbing (decisions 20261127-speed-scales-climbing-owner).
- [20261126-230950] question, DROP-ANSWERED: "Looking back from a town or dungeon-exterior map: every..." - Distant ring covers the town look-back (CHANGELOG distantlod).
- [20261126-230950] question, DROP-ANSWERED: "From a town or dungeon exterior map, wilderness trees..." - Same (CHANGELOG distantlod).
- [20261126-231433] question, DROP-ANSWERED: "Starting gun (startgun 01): to stop untrained skill rolls..." - Literal rule kept: highest of the six (fb6b4385, 5ca222f2; CHANGELOG startgun).
- [20261126-231433] question, DROP-ANSWERED: "Starting gun (startgun 01): untrained skills roll 3-6 at..." - Same.
- [20261126-231823] question, DROP-ANSWERED: "The paired walk found two new jitter traps from..." - Owner accepts the improvement; next a quiet paired walk (todo dungeonedges 01).
- [20261126-231932] question, DROP-ANSWERED: "Jumping/Slowfall: Doom now applies Slowfall's falling-damage exemption, but Doom's..." - Mirroring Slowfall's descent is backlog magic-casting-and-self-spells ("Doom mirrors flight...").
- [20261126-231932] question, DUPLICATE of G8: "Jumping below 75: the card leaves the falling damage..."
- [20261126-231932] oversight, DROP-ANSWERED: "The orchestrator's join commit 6b3623ed ('Join skillperks 01 (jumping)..." - Fixed in bfc0ffeb.
- [20261126-235534] oversight, DROP-ANSWERED: "Card 01's attribute test and demo kill the player...." - Card 02 test uses Agility 1 (4e5d3be9); card 01 paired PASS at merge (CHANGELOG attributes 01).
- [20261126-235534] question, DUPLICATE of G13: "Agility dodging (card 02): which damage can Agility dodge?..."
- [20261126-235534] review, DUPLICATE of E3: "Architecture, to check before merging: this branch builds a..."
- [20261127-004045] question, DROP-ANSWERED: "Willpower (attributes card 03) now scales all damage Doom..." - Already in work/questions.md [20261127-004045].
- [20261127-004045] question, DROP-ANSWERED: "Willpower (attributes card 03) now scales the damage Doom..." - Part (a) already in questions.md [20261127-004045]; part (b), script health costs such as Soul Shatter, built unscaled (31c2be00); add to that question if wanted.
- [20261127-004045] oversight, DUPLICATE of O2: "Doom's poison damage (`P_PoisonDamage` in `UZDoom/src/playsim/p_interaction.cpp`) lowers the bridged..."
- [20261127-004045] question, DROP-ANSWERED: "Willpower (attributes card 03) scales the damage Doom deals..." - Same as [20261127-004045] above.
- [20261127-004045] review, DROP-ANSWERED: "Willpower covers only damage that passes through Doom. The..." - Already in questions.md [20261127-004045].
- [20261127-004045] review, DROP-MINOR: "Kill calls are exempted by guessing from the hit..." - Kill-call exemption is explicit now (DD_KillCall, efa8d625, f61fc6c6); low impact.
- [20261127-005009] review, DROP-ANSWERED: "New Game or a plain load into an unconverted..." - Loading screen holds the game during the wait (CHANGELOG loadscreen 01).
- [20261127-005009] review, DUPLICATE of E1: "The first visit to a dungeon that was not..."
- [20261127-005134] question, DROP-ANSWERED: "Shop ammo: I made armorers carry half a general..." - Already in questions.md [20261124-093041].
- [20261127-005134] question, DROP-ANSWERED: "Shop ammo pricing: Daggerfall rounds each unit's price down..." - Whole-stack pricing removed, stock formula kept (a37eb466).
- [20261127-005134] oversight, DUPLICATE of O17: "Shared build folders get deleted mid-run: D:\dev\DoomDaggerfall-build\verify-agility (UZDoom, bridge..."
- [20261127-005134] question, DROP-ANSWERED: "Shop ammo pricing: Daggerfall prices each unit at 1..." - Stock formula kept (a37eb466).
- [20261127-005134] oversight, DUPLICATE of O17: "daggerfall-unity-master\Builds\Windows64 in the lane-travel worktree is a link into..."
- [20261127-005134] oversight, DUPLICATE of O17: "Shared build folders get deleted mid-run: D:\dev\DoomDaggerfall-build\verify-agility vanished between..."
- [20261127-005134] question, DROP-ANSWERED: "Shop ammo: please end the leftover processes UZDoom pid..." - Stale request; leftover games now closed by ed520f6c.
- [20261127-005245] question, DUPLICATE of G10: "Automatics: the card leaves these open. At which skill..."
- [20261127-005245] question, DROP-ANSWERED: "Automatics: DRLA's Uzi carries the pistol token, so under..." - Uzi ruled Automatic (a594d521).
- [20261127-005245] review, DROP-ANSWERED: "Architecture: the rule for 'which gun caused this hit'..." - Shared shot tag built (shotsource 01); questions.md [20261127-005245] is now stale.
- [20261127-023449] question, DROP-ANSWERED: "Choosing a spell in the spellbook works as it..." - Spell choice held on every route (bc917972, CHANGELOG magicmenu).
- [20261127-023449] question, DROP-ANSWERED: "There was no way to open the character sheet..." - Keys merged after owner answers (3b05139d, CHANGELOG magicmenu).
- [20261127-023449] question, DROP-ANSWERED: "The character sheet couldn't be opened in Doom except..." - Same as above (magicmenu).
- [20261127-023449] question, DROP-ANSWERED: "Until spell casting from Doom is built (backlog magic-casting-and-self-spells),..." - Spell choice held on every route (bc917972).
- [20261127-023449] question, DROP-ANSWERED: "May the character sheet have its own Doom key?..." - Keys merged (magicmenu).
- [20261127-023449] oversight, DROP-ANSWERED: "Existing routes to the spellbook already let the player..." - Casting held on every route (bc917972).
- [20261127-024745] question, DROP-ANSWERED: "The Explosives lane ran out of its $10 budget..." - Lane continued (todo skillperks note).
- [20261127-025856] question, DROP-ANSWERED: "During a door-press loading wait (5-45 s while a..." - Loading holds pause Daggerfall (89f39a38, CHANGELOG loadscreen).
- [20261127-032016] question, DROP-ANSWERED: "Shotgun ammo is now named "Shells" ("Silver Shells"), as..." - Plain names merged (bb699f46, CHANGELOG ammoname).
- [20261127-033005] review, DROP-ANSWERED: "Performance: crossing a chunk line causes repeated heavy render-thread..." - Documented in CHANGELOG distantlod (performance risks unmeasured).
- [20261127-033005] review, DROP-ANSWERED: "Performance: the near-flat buffer is rebuilt on the render..." - Same.
- [20261127-033005] review, DROP-ANSWERED: "Performance: the ring submits up to about 150k extra..." - Same.
- [20261127-033904] oversight, DUPLICATE of O14: "Character sheet indices will collide between perk lanes: Automatics..."
- [20261127-033904] question, DUPLICATE of G18: "Shotguns 75/100 collision damage: when a knocked enemy hits..."
- [20261127-033904] question, DUPLICATE of G19: "Shotguns knockback 'slower shotguns push harder': how should slowness..."
- [20261127-034545] question, DROP-ANSWERED: "Luck's extra ammo (attributes 04) is built as you..." - Owner replaced the Luck rule (todo killdrops 01); questions.md [20261127-034545] is now stale.
- [20261127-034855] oversight, DUPLICATE of O15: "tools/new_game/run_new_game.py 'create' stalls at a DaggerfallMessageBox right after CreateCharRaceSelect..."
- [20261127-035402] question, DUPLICATE of E2: "Dungeon collision (Privateer's Hold): after this run's fix, the..."
- [20261127-035402] oversight, DUPLICATE of O15: "The paired Daggerfall+Doom New Game driver (tools/new_game, used by..."
- [20261127-041725] question, DROP-ANSWERED: "Speed attribute and climbing: today Speed scales walking and..." - Owner: Speed scales climbing (decisions 20261127-speed-scales-climbing-owner).
- [20261127-043610] oversight, DROP-ANSWERED: "Town meshes (and the distant LOD view of a..." - Town reloads in the new season (53ab0c1c).
- [20261127-043610] oversight, DUPLICATE of O17: "Recent demo overworld packages lack the DDNATURE lump (e.g...."
- [20261127-043610] oversight, DROP-ANSWERED: "Town meshes and the distant LOD view of a..." - Fixed (53ab0c1c).
- [20261127-043610] oversight, DUPLICATE of O17: "Recent demo overworld packages lack the DDNATURE lump (e.g...."
- [20261127-043610] question, DROP-ANSWERED: "The weather-seam goal ran out of its $10 budget..." - Weather seam merged with the season reload (CHANGELOG 2026-11-27).
- [20261127-044701] oversight, DUPLICATE of O17: "`tools/map_keys/mapkeys.py` pointed at build folders that no longer exist..."
- [20261127-044701] oversight, DUPLICATE of O15: "Daggerfall message-box buttons may not answer their keyboard shortcuts..."
- [20261127-044701] oversight, DUPLICATE of O16: "Test-only mouse positions appear doubled in paired tests. With..."
- [20261127-045928] question, DROP-MINOR: "A Doom that has stopped publishing (crashed or hung)..." - Ordinary engineering call (60 s release built, CHANGELOG loadscreen).
- [20261127-045928] oversight, DUPLICATE of O15: "The scripted New Game driver (`tools/new_game/run_new_game.py create`) now always..."
- [20261127-045928] review, DROP-ANSWERED: "Performance (existing spawn path that this run measured; the..." - Loading screen covers the spawn block (CHANGELOG loadscreen 01).
- [20261127-051951] question, DUPLICATE of G24: "Snow ground now matches Daggerfall Unity (paired ratios 0.93-1.09),..."
- [20261127-051951] question, DROP-ANSWERED: "In a paired game, both engines start together, so..." - Owner holds the first-town season item (todo "Held by the owner").
- [20261127-051951] review, DUPLICATE of E8: "Performance (waiting at doors): RefreshTownSeason requests the current town..."
- [20261127-051951] review, DUPLICATE of G24: "Architecture (two lighting models outdoors): DD_ExteriorGroundLight (UZDoom/src/rendering/hwrenderer/scene/hw_flats.cpp:308-317, called at..."
- [20261127-051951] review, DUPLICATE of E8: "Architecture (partial live reload of a loaded town): RefreshTownSeason..."
- [20261127-052057] question, DROP-ANSWERED: "Doomerfall draws every Daggerfall window over solid black, while..." - Small menus show Doom, full-screen menus stay black (15fb2a4c, d289f22e).
- [20261127-052057] question, DROP-ANSWERED: "May one Daggerfall Unity menu capture run on the..." - Run done (d9346633).
- [20261127-052057] oversight, DUPLICATE of O16: "UZDoom's screenshot command produces an all-black image while a..."
- [20261127-054419] question, DROP-ANSWERED: "A shield already in a save is kept in..." - Built as described and merged (CHANGELOG noshields).
- [20261127-054419] oversight, DUPLICATE of O15: "The paired New Game driver (tools/new_game/run_new_game.py, used through tools/fixed_drops/paired.py)..."
- [20261127-054419] oversight, DUPLICATE of O15: "The paired New Game driver (tools/new_game/run_new_game.py, used through tools/fixed_drops/paired.py)..."
- [20261127-054419] question, DUPLICATE of G25: "Two quest rewards are shields: Auriel's Shield (quest B0B71Y03)..."
- [20261127-055226] oversight, DUPLICATE of O17: "A paired review folder is not self-consistent if you..."
- [20261127-055226] oversight, DUPLICATE of O17: "Paired review folders don't work if you mix parts..."
- [20261127-055226] oversight, DROP-MINOR: "In paired runs Daggerfall Unity reports the player at..." - Seen only under -dfsynctest; no real-play evidence.
- [20261127-055457] oversight, DUPLICATE of O16: "Doomerfall tests that check Daggerfall menus may be checking..."
- [20261127-055457] question, DROP-ANSWERED: "Visual parity menu pass: the Doom starting pistol shows..." - Accepted as an expected difference (66d686bd).
- [20261127-061016] question, DROP-ANSWERED: "Daggerfall menus in Doom are now rendered at Doom's..." - Owner kept the 1920x1200 cap (CHANGELOG menures).
- [20261127-061016] oversight, DUPLICATE of O16: "The existing Daggerfall test -dfhotkeyshots (DoomerfallHotkeyShotsTest.cs) throws ArgumentOutOfRangeException in..."
- [20261127-061016] oversight, DUPLICATE of O16: "Under quiet_run, the launcher's own nested private desktop (its..."
- [20261127-075528] oversight, DUPLICATE of O17: "The shared build folders D:\dev\DoomDaggerfall-build\uzdoom-quiet, bridge-quiet and launcher-quiet are..."
- [20261127-080929] oversight, DUPLICATE of O17: "UZDoom builds in D:\dev\DoomDaggerfall-build (uzdoom-quiet, and probably other lane..."
- [20261127-080929] review, DUPLICATE of E4: "Performance: tagging cost grows roughly with the square of..."
- [20261127-081218] oversight, DUPLICATE of O15: "The shared New Game test driver (tools/fixed_drops/paired.py "fresh" run)..."
- [20261127-081504] question, DUPLICATE of G4: "Uzi variants (owner ruled the Uzi an Automatic, 2026-11-27):..."
- [20261127-081504] question, DUPLICATE of G5: "Borderline DRLA pistols I left as Pistols: (a) The..."
- [20261127-081504] question, DUPLICATE of G4: "Plasma Uzi (cell-fed Uzi variant): you ruled the Uzi..."
- [20261127-082629] review, DROP-MINOR: "Performance, unmeasured (from the earlier fix this run verifies):..." - Unmeasured menu-only cost.
- [20261127-084059] question, DROP-ANSWERED: "Look labels no longer show a pickup on another..." - World logic, follows clearly (decisions 20261127-use-through-3d-floor).
- [20261127-084059] review, DROP-ANSWERED: "The look label and Use can now pick different..." - Same.
- [20261127-084126] question, DROP-ANSWERED: "Guards outdoors: when the player shoots a guard townsperson,..." - Deferred, owner's held guard item (decisions 20261127-outdoor-watchman-vanishes).
- [20261127-084126] oversight, DROP-ANSWERED: "Outdoor city guards never reach Doom: dd_guards.cpp drops any..." - Known and deferred (decisions 20261124-outdoor-guards; backlog guard-behavior-and-pathfinding "do not raise").
- [20261127-084126] question, DROP-ANSWERED: "Guard townspeople on the streets: in Daggerfall, shooting a..." - Same as decisions 20261127-outdoor-watchman-vanishes.
- [20261127-084126] oversight, DROP-ANSWERED: "Outdoor city guards never reach Doom: dd_guards.cpp drops any..." - Same as decisions 20261124-outdoor-guards.
- [20261127-091125] question, DROP-ANSWERED: "Full-screen Daggerfall menus (inventory, automap) are 16:10, so on..." - Full-screen menus back on black (d289f22e).
- [20261127-091125] question, DROP-ANSWERED: "When a Daggerfall popup opens with the HUD as..." - Daggerfall's HUD restored (d289f22e).
- [20261127-091125] review, DROP-MINOR: "Performance: `DDUiTexture::SetFrame` (UZDoom/src/dd_bridge.cpp:390-427) replaces a single memcpy with a..." - Unmeasured menu-only cost.
- [20261127-091736] question, DUPLICATE of G27: "Pickup lean strength: today about 1 dungeon in 5..."
- [20261127-091736] review, DROP-MINOR: "Old converted places can keep the old pickups. UZDoom/src/playsim/dd_towncache.cpp:104-153..." - A fresh install replaces the cache (scripts/play/install.py:144); dev folders only.
- [20261127-091736] review, DROP-MINOR: "Doom powerups are now reachable in Daggerfall dungeons, but..." - Unverified, no fault seen; play-test it.
- [20261127-093608] question, DROP-ANSWERED: "Regional favourite stand-in: 'cannot be purchased' now means even..." - Superseded by the round 3 threshold (b96bed91; decisions 20261127-favourite-affordable-threshold).
- [20261127-093608] question, DUPLICATE of G28: "Regional favourite stand-in threshold: the favourite counts as purchasable..."
- [20261127-093608] question, DUPLICATE of G29: "When a favourite gets a stand-in but the army's..."
- [20261127-093608] question, DROP-ANSWERED: "The regional guarantee (favourite or stand-in) is a 10%..." - Follows clearly (decisions 20261127-regional-favourite-guaranteed).
- [20261127-093608] review, DUPLICATE of G28: "Architecture: the planner has its own definition of 'affordable'..."
- [20261127-095003] question, DROP-MINOR: "DRLA's assembled weapons are not rarity tiers. I priced..." - Constrained judgment within the owner's tier rules (AGENTS.md example); show the BFG-as-common choice in review.
- [20261127-095003] oversight, DROP-MINOR: "In a paired -dfsynctest game, every shop price comes..." - Seen only under -dfsynctest; paired shop purchases priced correctly (CHANGELOG storeammo).
- [20261127-100440] question, DROP-ANSWERED: "Orchestrator: lane skillperks (agent/skillperks-20261127-100440) can't merge `integration`. The permission..." - todo: shotsource merged, continue 03 on it.
- [20261127-100612] question, DUPLICATE of G18: "Shotguns collision damage: the knockback collision and wall-slam damage..."
- [20261127-100612] question, DUPLICATE of G19: "Shotguns knockback 'best with slower shotguns': how should 'slower'..."
- [20261127-100612] question, DUPLICATE of G20: "Shotguns 100: should reloads get faster than the 35%..."
- [20261127-100612] question, DUPLICATE of G21: "Projectile shotguns (for example the DRLA Plasma Shotgun when..."
- [20261127-100612] oversight, DUPLICATE of O14: "The skillperks lane branches (agent/skillperks-20261127-100612 and -100440) are cut..."
- [20261127-100846] question, DROP-ANSWERED: "Town corpses: a walking town watchman killed outdoors leaves..." - Same as decisions 20261127-outdoor-watchman-vanishes.
- [20261127-100846] question, DROP-ANSWERED: "Town corpses: killing a guard leaves a corpse only..." - Same.
- [20261127-100846] question, DROP-ANSWERED: "Town corpses, outdoor watchman: a walking town watchman killed..." - Same.
- [20261127-101856] question, DUPLICATE of G16: "Explosives 50 perk (direct-hit bonus): how much extra damage..."
- [20261127-101856] oversight, DUPLICATE of O17: "Review demo folders link to each other's map data:..."
- [20261127-101856] oversight, DUPLICATE of O19: "Paired perk tests run with real Daggerfall HP and..."
- [20261127-101856] review, DROP-MINOR: "Performance: killing a big DRLA pack with Inpulsa's Broken..." - The notes blame DRLA deaths; comparison confounded.
- [20261127-101856] review, DROP-MINOR: "State lifetime: the pending blast queue (`DoomerfallExplosives.zs:73-75`) lives in..." - Short window, untested, predates the run.
- [20261127-103722] oversight, DROP-ANSWERED: "The spellbook commit f1b68be5 committed Unity Addressables build output:..." - Build output removed (68619dd0).
- [20261127-103953] review, DUPLICATE of G34: "Shop shelves and enemy drops use two different material..."
- [20261127-110242] review, DUPLICATE of O8: "Schism weapons taken from floor pickups are not treated..."
- [20261127-110332] question, DUPLICATE of G18: "Shotguns collision damage (an enemy knocked into another enemy,..."
- [20261127-110332] question, DUPLICATE of G19: "Shotguns knockback should be strongest with slow shotguns and..."
- [20261127-110332] question, DUPLICATE of G20: "Shotguns at 100: reloads stay 35% faster, the same..."
- [20261127-110332] question, DUPLICATE of G21: "Projectile shotguns such as DRLA's Plasma Shotgun (when Shotguns..."
- [20261127-110332] oversight, DUPLICATE of O17: "Review demos broken by cleanup: review/explosives-perks/data and review/shotguns-perks/data are..."
- [20261127-110956] question, DROP-ANSWERED: "Walking into a shop or an open house now..." - Owner: building messages as in Daggerfall Unity (todo buildingmessage 01).

## Game designer verdicts (challenge pass)

One entry per design question in section 2. Each block is the full text of one detail file for
`gamedesign/decisions/`. The index lines are already in `gamedesign/decisions.md`.

### FILE: 20261127-triage-q01-gun-skill-placeholders.md
## 2026-11-27: Gun skill placeholders: governing stats, advancement rate, Fighters Guild [triage G1]

- **Verdict:** Leans (stats, rate, trainer) / Not determined, one-line confirm (guild promotion list).
- **Answer:** Governing stats (Shotguns and Melee Strength, Automatics, Pistols and Rifles Agility, Explosives and
  Energy Weapons Intelligence) and advancement rate 2 probably stand as built; the owner sees them because they are
  numbers. The guild part is not settled: the build put Shotguns and Explosives into the Fighters Guild list in
  Orcish's and Giantish's places. One-line confirm for the owner: "Your two-step remap says removed skills first become
  other Daggerfall skills, then Daggerfall weapon skills reroute to Doom skills, and a gun skill never fills a language
  slot. Does that also cover guild skill lists (promotion and training)?" If yes, the guild lists should be redone that
  way (Orcish/Giantish to Daggerfall skills; Short Blade, Long Blade, Axe, Blunt, Archery rerouted), which also decides
  which guilds besides the Fighters Guild train gun skills.
- **Rests on:** Owner `20261126-use-main-source-owner.md`: "one flat skill multiplier (2, as for weapon skills)" (supports
  rate 2). Owner `20261126-two-step-skill-remap.md`: "Filling a language slot directly with a gun skill is rejected."
  Inference: the build's guild list does exactly what that rule rejects for class lists, but the rule was worded for
  class lists, so it needs a confirm, not a strike.
- **Challenge:** The answer pass leaned "approve as built". Stats and rate hold as a lean (numbers the player feels, so
  not minor). The guild slot choice contradicts the spirit of a quotable owner rule, so that part is downgraded to a
  confirm.

### FILE: 20261127-triage-q02-language-enchantments.md
## 2026-11-27: Enchantments for the removed monster languages; gun-skill Enhances in the item maker [triage G2]

- **Verdict:** Not determined (inert powers) / Leans (gun-skill Enhances).
- **Answer:** Keeping the old language powers inert, dropping them from items and souls (changes item-maker cost and
  capacity, and the forced Daedric power on Fire and Frost Daedra souls), or replacing them is the owner's choice. The
  item maker probably should offer Enhances Skill for the gun skills, since gun skills are now ordinary skills in
  Daggerfall's systems; it needs a marker on new items (engineering).
- **Rests on:** `gamedesign.md` "Daggerfall's systems are all planned" and "Systemic cause and effect ... Systems ...
  are allowed to interact with each other." Owner (skills-in-doom.md:17): languages removed "for now".
- **Challenge:** Inert powers that cost capacity but do nothing sit badly with "World logic", which argues for (b) or
  (c), but none of a/b/c contradicts a settled fact, and they differ in item-maker economy. Gun-skill Enhances changes
  balance (enchanted gear feeds perk thresholds), so it stays a lean, not Follows clearly. Kept.

### FILE: 20261127-triage-q03-reroute-collision.md
## 2026-11-27: Custom class reroute collision: which slot takes the fallback [triage G3]

- **Verdict:** Not determined.
- **Answer:** None. Ask together with the reroute map ([20261126] in `work/questions.md`): keep the build (the rerouted
  slot takes the next free gun skill, the player's own pick stays) or the proposal (the lower slot takes the fallback).
- **Rests on:** Owner `20261126-weapon-skill-reroute-owner.md`: "You propose the mapping and I'll approve/deny it."
  `20261127-weapon-skill-reroute-map.md` (map not approved).
- **Challenge:** The build's way keeps the player's explicit choice, which is a reasonable lean, but the owner reserved
  the mapping and the outcome differs in what skills a character has. Kept Not determined.

### FILE: 20261127-triage-q04-energy-automatic.md
## 2026-11-27: Energy + Automatic pair; the Plasma Uzi [triage G4]

- **Verdict:** Follows clearly.
- **Answer:** Cell-fed or recharging automatic energy guns that do not explode are Energy + Automatic and use whichever
  skill is higher. The Plasma Uzi is Energy + Automatic, not Pistol + Energy and not Energy only. The owner labelled the
  rule "Future", so when to build it (a card) is his to schedule; what to build is settled.
- **Rests on:** Owner (skills-in-doom.md:92-93): "tag automatic weapons that do not cause explosions as also automatics
  and let them be treated by whichever skill is higher." Owner, 2026-11-27, on the Uzi (`work/notes/20261127-081504.md`):
  "It's an Automatic. That's miscategorized." Owner example: "Plasma Rifle. Types: Energy, Automatic".
- **Challenge:** The two-skill rule named only Pistol + Energy and Shotgun + Energy, but it never banned other pairs and
  allows "Tags may be reassigned", and the later "Future" rule adds Automatic explicitly. Automatics' ammo-saving perks on
  cells could undercut "Energy Cells expensive", but the owner already chose "treated by whichever skill is higher".
  Kept. Defect for the orchestrator: manual.md:162-163 still says "The Uzi is a Pistol, not an Automatic", which
  contradicts manual.md:80 and the merged Uzi change.

### FILE: 20261127-triage-q05-unclear-drla-guns.md
## 2026-11-27: DRLA guns with no clear skill [triage G5]

- **Verdict:** (c) Follows clearly; (a), (b), (d) Leans; (e) Leans (downgraded from "already decided").
- **Answer:** (c) The Rigelatin Assault Weapon is not a Rifle: it fires lasers and rockets and uses no ammo, so it is
  neither ballistic nor non-explosive. (a)/(b) Lightweaver, Nano-shrapnel Plasma Shotgun, Duke 2 Rifle and Mother-in-Law
  get skills per weapon by constrained judgment within the owner's definitions (energy = cells or self-charging energy
  guns; every gun should train some skill), shown to the owner in review. (d) The Nanomachic Armament Generator is
  probably Automatic only, by its default fire mode, without a runtime mode check. (e) The Shredder Pistol probably stays
  a Pistol only: one pull dumps a small clip, which is a burst rather than automatic fire.
- **Rests on:** Owner `20261126-rifles-skill.md`: Rifles covers "ballistic semi-automatic non-explosive guns". AGENTS.md:
  "given a drop table's tier and weapon-type rules, Claude can choose the individual weapon mappings." manual.md:214
  ("a pistol that fires shotgun shells is only a Pistol").
- **Challenge:** The answer pass treated (e) as already decided by manual.md:214. That line is agent-written merged text,
  not an owner quote, and the owner's "Future" automatic rule could reach a clip-dumping gun, so (e) is a lean. A
  runtime M14-mode check for (d) would be a small new mechanism, so avoid it. The Dragonslayer deals no damage at all;
  that is oversight O11, not a skill question.

### FILE: 20261127-triage-q06-player-body.md
## 2026-11-27: Look of the Doom character in bridged games [triage G6]

- **Verdict:** Not determined.
- **Answer:** None. Generic DRLA body and Scout voice with "No Doom class" on the PDA, or the Marine's sprites, voice and
  portrait with no perk, is an art and feel choice for the owner.
- **Rests on:** Owner (skills-in-doom.md:10-11): "No Doom class. The Doom player is a normal character with no class
  effects". That rule is about effects, not looks.
- **Challenge:** "No Doom class" could be read as "no class look either", but that stretches a rule about effects.
  Visible art, so never minor. Kept.

### FILE: 20261127-triage-q07-drlax-gizmos.md
## 2026-11-27: DRLA X gizmos on Daggerfall maps; Maestro class perk [triage G7]

- **Verdict:** Follows clearly (spawn rule, Maestro perk) / Deferred (whether the devices exist at all).
- **Answer:** The deployers, revisers, recyclers, extractors, dimensional box, demon statue and quest objects must not
  spawn on Daggerfall maps every 2 to 3 map loads: that ties the world's contents to the player's load history and
  makes things appear from nowhere. The Maestro's random temporary DRLA class perk must be off. Whether these devices
  return in another form (seeded placement, a shop service) changes the gear economy and goes to the owner.
- **Rests on:** `gamedesign.md` Randomness: "Randomness uses only fixed facts about the place and its area level. There
  is no ... pity timers based on the player's history". "In-engine object permanence": things "don't ... appear from
  nowhere". Owner (skills-in-doom.md:10-11): "No Doom class ... no class effects".
- **Challenge:** Turning the devices off removes DRLA X's mod-handling features, which is a real gameplay change; but the
  current spawn rule contradicts quotable principles, so off is what follows until the owner designs a replacement. Kept.

### FILE: 20261127-triage-q08-fall-damage-curve.md
## 2026-11-27: Fall damage reduction below Jumping 75 [triage G8]

- **Verdict:** Not determined.
- **Answer:** None. No reduction below 75 (as built, as the card asked) or a curve up to immunity at 75 is a balance
  number for the owner.
- **Rests on:** The skillperks 01 card (immunity at 75, nothing stated below).
- **Challenge:** Skills "have continuous scaling" besides perks (skills-in-doom.md:12) hints at a curve, but Jumping's
  continuous scaling is already jump height. Kept.

### FILE: 20261127-triage-q09-jumping-uses.md
## 2026-11-27: Jumping skill uses from Doom; double jump after walking off an edge [triage G9]

- **Verdict:** (a) Follows clearly for jumps from the ground, Leans for mid-air jumps; (b) Leans.
- **Answer:** (a) Each Doom jump from the ground counts as a Jumping skill use at Daggerfall's normal rate. Mid-air
  double and triple jumps probably count too (each is a jump), but Daggerfall has none, so the owner sees it. (b) The
  double jump after walking off an edge probably stays as built and documented in the manual.
- **Rests on:** `gamedesign.md` Progression row: "Combat, spellcasting, and traversal drive Daggerfall's use-based skill
  leveling ... Doom play reports skill uses to Daggerfall". Owner `20261126-use-main-source-owner.md`: "other skills
  tally at Daggerfall's normal rate".
- **Challenge:** `20261126-skill-uses-from-doom.md` deferred the event-to-skill mapping, but the owner's later "other
  skills tally at Daggerfall's normal rate" and "Most skill gains should come from use" settle the rate for non-weapon
  skills. Doom players jump far more than Daggerfall players, so the owner may want a slower rate (as he chose 1.5x for
  Running); that is an overrule, not an open fork. (b) is no less physical than a double jump after a jump. Kept.

### FILE: 20261127-triage-q10-automatics-bands.md
## 2026-11-27: Automatics fire-rate bands and suppression [triage G10]

- **Verdict:** Not determined.
- **Answer:** None. Band unlock levels, band boundaries in shots per second, the lowest band's splash radius and the 75
  suppression slow are numbers the card leaves open.
- **Rests on:** skillperks 02 card (open items).
- **Challenge:** Nothing in the documents gives these numbers. Kept.

### FILE: 20261127-triage-q11-imported-save-gun.md
## 2026-11-27: Starting gun when loading a plain Daggerfall save [triage G11]

- **Verdict:** Leans.
- **Answer:** Probably keep giving the pistol and its bullets (the owner's 2026-11-24 rule) to a plain Daggerfall save
  with no Doom gun.
- **Rests on:** Owner `20261126-light-carbine-starting-gun.md`: "A new character's starting gun ... follows the highest
  weapon skill" (worded for new characters). manual.md:95-96: an imported character "starts the weapon skills
  untrained", so all six would tie and the tie rule ("give all the tied guns") would hand out six guns.
- **Challenge:** The owner's "old and new characters follow the same rule" (`20261126-old-saves-endurance-owner.md`)
  points the other way, but it was about the Endurance bonus. Following the highest skill on imports gives an absurd
  six-gun start, which is why the lean stays with the pistol. Kept as Leans.

### FILE: 20261127-triage-q12-starting-gun-material.md
## 2026-11-27: Starting gun material [triage G12]

- **Verdict:** Not determined.
- **Answer:** None. All Iron, or the fixed per-gun roll (some Steel or Silver), changes starting damage, so it goes to the
  owner.
- **Rests on:** The material odds in `gamedesign.md` apply to loot drops; the starting gun is not loot. "Most basic gun"
  names the kind of gun, not its material.
- **Challenge:** Iron is the plain reading of "the weakest, most basic gun", but that phrase chooses the gun, and the
  fixed roll is deterministic (no rule broken). Kept.

### FILE: 20261127-triage-q13-dodge-feedback.md
## 2026-11-27: Feedback for a dodged hit [triage G13]

- **Verdict:** Not determined.
- **Answer:** None. A "Dodged" popup, a sound, or silence is a player-visible feel choice.
- **Rests on:** No document covers combat feedback for dodges.
- **Challenge:** Immersive-sim readability argues for a cue, but which cue (and whether any) is visible design. Kept.

### FILE: 20261127-triage-q14-picking-crime.md
## 2026-11-27: Crime for picking into a closed building [triage G14]

- **Verdict:** Follows clearly.
- **Answer:** A successful pick into a closed shop or house records Daggerfall's breaking-and-entering crime exactly as
  vanilla does. If vanilla then spawns outdoor guards, that response belongs to the owner's held guard item and is not
  raised here.
- **Rests on:** `gamedesign.md` Crime row: "Daggerfall governs reputation, bounties, surrender, and court/jail".
  Interactive World row: "Lock ratings, lockpicking ... follow Daggerfall's RPG checks." "Daggerfall's systems are all
  planned."
- **Challenge:** Recording the crime can trigger guard spawns, which on Daggerfall's streets touch the held outdoor-guard
  design (`20261124-outdoor-guards.md`, "do not raise"). The crime itself is Daggerfall's rule; only the enforcement is
  held. Kept.

### FILE: 20261127-triage-q15-ammo-tier-prices.md
## 2026-11-27: Ammo tier prices after Regular moved to 1x [triage G15]

- **Verdict:** Not determined.
- **Answer:** None. Keeping the old higher-tier prices (Steel now 5x Regular) or rescaling them is an economy number.
  Cells at 10 gold is settled.
- **Rests on:** Owner `20261126-energy-weapons-owner.md` (cells 10 gold); the earlier tier table (Regular 3x).
- **Challenge:** Keeping the old tier-to-tier ratios is a natural lean, but prices are economy, never minor. Kept.

### FILE: 20261127-triage-q16-explosives-direct-hit.md
## 2026-11-27: Explosives 50 direct-hit bonus [triage G16]

- **Verdict:** Not determined.
- **Answer:** None. Percentage of impact damage or a flat amount, and its size, go to the owner (the card says "amount is
  open: ask").
- **Rests on:** skillperks 03 card.
- **Challenge:** The owner explicitly reserved the amount. Kept.

### FILE: 20261127-triage-q17-inpulsa-details.md
## 2026-11-27: Inpulsa's Broken Heart details [triage G17]

- **Verdict:** Follows clearly (bystanders) / Leans (radius 128, Doom falloff) / Not determined (chain bonus).
- **Answer:** Townspeople and guards caught in a chain blast take damage; only the player is spared. Radius 128 (a
  rocket's) with ordinary Doom falloff probably stands. Whether chain blasts get the +0-60% Explosives bonus is open.
- **Rests on:** skillperks 03 card (owner): enemies "explode for about 25% of their maximum health around them, chaining,
  each generation at half effect, never damaging the player". `gamedesign.md` "World logic" and "Systemic cause and
  effect". The approved Energy Weapons 100 explosion also uses radius 128.
- **Challenge:** Hurting townspeople can start crime and hostility, a large consequence; but that is Daggerfall's
  existing rule acting on a real explosion, which is exactly the systemic interaction the owner favours, and the card
  names only the player as spared. Kept.

### FILE: 20261127-triage-q18-shotgun-collision.md
## 2026-11-27: Shotguns 75/100 collision damage [triage G18]

- **Verdict:** Leans (upgraded from Not determined).
- **Answer:** Probably the owner's own tentative numbers: 200 at 75 and 400 at 100, once per shot, scaled by impact speed.
- **Rests on:** The owner's tentative numbers quoted on the card ("200 at 75 and 400 at 100").
- **Challenge:** The owner called them tentative, so they need his yes, but the design does point at them; Not
  determined understated that. Changed to Leans.

### FILE: 20261127-triage-q19-shotgun-slowness.md
## 2026-11-27: How "slower shotguns push harder" is measured [triage G19]

- **Verdict:** Leans (measure) / Not determined (strength).
- **Answer:** Probably measure slowness by reload time, as the owner suggested. How strongly knockback scales with it is
  open.
- **Rests on:** The owner's suggestion of reload speed (quoted in the reports).
- **Challenge:** Cycle time fits "slower" better for pump guns, but the owner named reload. The scaling is a number.
  Kept.

### FILE: 20261127-triage-q20-shotgun-100-reload.md
## 2026-11-27: Shotguns 100 reload speed [triage G20]

- **Verdict:** Not determined.
- **Answer:** None. Whether reloads get faster than 35% at 100, and by how much, goes to the owner.
- **Rests on:** skillperks 04 card.
- **Challenge:** No document gives a number. Kept.

### FILE: 20261127-triage-q21-projectile-pellets.md
## 2026-11-27: Extra balls for projectile shotguns [triage G21]

- **Verdict:** Leans.
- **Answer:** Projectile shotguns probably also get the +50%/+100% balls per shot when Shotguns is their higher skill,
  with their own spread.
- **Rests on:** Owner `20261126-two-skill-weapons-owner.md`: a two-skill gun "uses whichever skill is higher", which
  implies that skill's perks in full.
- **Challenge:** More plasma balls also spend nothing extra while cells are meant to be expensive, and it needs a spread
  mechanism. Balance is visible, so lean only. Kept.

### FILE: 20261127-triage-q22-dungeon-brightness.md
## 2026-11-27: Dungeon brightness [triage G22]

- **Verdict:** Leans.
- **Answer:** Probably match Daggerfall Unity's darker dungeons and distance darkening. The owner checks combat
  visibility before it is relied on.
- **Rests on:** `gamedesign.md` Aesthetics row: "Environments, architecture ... look like Daggerfall". Maps: "Converted
  maps must look very close to Daggerfall".
- **Challenge:** Halving brightness changes how far the player can see Doom packs, which is combat, a Doom domain. That
  keeps it at Leans. Kept.

### FILE: 20261127-triage-q23-eye-height-fov.md
## 2026-11-27: Eye height and field of view [triage G23]

- **Verdict:** Not determined.
- **Answer:** None. Eye height leans toward Daggerfall Unity's 1.71 m (the world should look as it does in Daggerfall);
  field of view is a feel choice for the owner (and usually a player option).
- **Rests on:** `gamedesign.md` Aesthetics and Maps lines; Movement row: "Doom's fast, responsive FPS movement is the
  baseline".
- **Challenge:** Both values are directly visible and affect aim feel, so neither is minor. Kept.

### FILE: 20261127-triage-q24-outdoor-sprite-light.md
## 2026-11-27: Outdoor sprite and monster lighting [triage G24]

- **Verdict:** Leans (billboards) / Not determined (monsters).
- **Answer:** Trees and other billboards outdoors probably take Daggerfall's flat daylight like the ground. Monster
  lighting at range is combat visibility and goes to the owner. Summer and rain ground lighting still need a check
  (engineering).
- **Rests on:** `gamedesign.md` Aesthetics row: environments look like Daggerfall; "monsters, gore, and combat effects
  look like Doom/DRLX".
- **Challenge:** Billboards are environment, so the lean holds; monsters are Doom's domain and their visibility is
  gameplay. Kept.

### FILE: 20261127-triage-q25-auriels-shield.md
## 2026-11-27: Auriel's Shield as a quest reward [triage G25]

- **Verdict:** Not determined.
- **Answer:** None. Carry-only (an exception to "no shields anywhere"), swapping it for another artifact, or no artifact
  goes to the owner.
- **Rests on:** The no-shields goal; backlog `spellbreaker-ring` excludes Auriel's Shield.
- **Challenge:** All three options are visible and touch quest rewards. Kept.

### FILE: 20261127-triage-q26-corpse-decay.md
## 2026-11-27: Corpse decay [triage G26]

- **Verdict:** Follows clearly.
- **Answer:** Corpses never decay, in towns or anywhere else.
- **Rests on:** `gamedesign.md` World Persistence: "Every killed monster, corpse, dropped item ... stays permanent across
  revisits. Persistence is total and uncompromising: there are no dungeon resets, respawns, or area refreshes." AGENTS.md
  pillar: "What the player does stays done."
- **Challenge:** Save size in big towns could grow, but that is an engineering cost, and the owner's only exception
  (moving parts) does not cover corpses. Kept.

### FILE: 20261127-triage-q27-pickup-lean.md
## 2026-11-27: Dungeon pickup lean [triage G27]

- **Verdict:** Not determined.
- **Answer:** None. Whether health leans too, and how common hard leans are, go to the owner.
- **Rests on:** Owner `20261126-slope-climb-pickups-owner.md`: the mix "made uneven by the loot system". `gamedesign.md`
  Randomness: "Favor extremes" and "Leans, not bans".
- **Challenge:** "Favor extremes" argues for some hard leans, which the build has; the amount is a number. Kept.

### FILE: 20261127-triage-q28-favourite-threshold.md
## 2026-11-27: What "affordable" means for the regional favourite [triage G28]

- **Verdict:** Leans (unchanged; see `20261127-favourite-affordable-threshold.md`).
- **Answer:** As logged: purchasable when one usable class costs at most one ordinary encounter at the area level. The
  owner's yes is still needed. The planner-bound mismatch (EncounterPlanner.zs) is engineering for the orchestrator.
- **Rests on:** `20261127-favourite-affordable-threshold.md`.
- **Challenge:** No new fact changes the earlier lean. Kept.

### FILE: 20261127-triage-q29-dear-favourite.md
## 2026-11-27: Dear favourite left in the army [triage G29]

- **Verdict:** Leans (unchanged; see `20261127-giant-rooms-dear-favourites.md`).
- **Answer:** As logged: keep it as a spike (Favor extremes, pattern breaks); report how often and play-test it. The
  owner's yes is still needed.
- **Rests on:** `20261127-giant-rooms-dear-favourites.md`.
- **Challenge:** No new fact changes the earlier lean. Kept.

### FILE: 20261127-triage-q30-standin-ranking.md
## 2026-11-27: Stand-in ranking order [triage G30]

- **Verdict:** Follows clearly.
- **Answer:** Theme fit first (a requirement), then the favourite's colour or DRLA family, then the nearest kind, as
  built.
- **Rests on:** Owner `20261126-favourite-fallback-owner.md`: "picks an affordable stand-in that fits its theme and
  region, preferring the favourite's own colour or DRLA family, then the nearest kind"; owner's words "based on the theme
  and area ... I don't care too much". `20261127-story-themes-vs-favourite.md`.
- **Challenge:** "colour or family first" could be read as before theme, but in the decision "fits" is the constraint and
  "preferring" ranks inside it. A zombie standing in for a Spider Mastermind looks odd, but it is what the theme allows.
  Kept.

### FILE: 20261127-triage-q31-weapon-value-cap.md
## 2026-11-27: Cap on Doom weapon values [triage G31]

- **Verdict:** Not determined.
- **Answer:** None. Capping (for example at 76,800) or leaving values uncapped is an economy choice.
- **Rests on:** Owner shop decision (`20261126-shop-proposal-owner.md`); no document gives a cap.
- **Challenge:** Daggerfall's dearest weapon is a tempting anchor, but that is "Daggerfall did it this way", which strikes
  nothing. Kept.

### FILE: 20261127-triage-q32-weapon-weight-material.md
## 2026-11-27: Doom weapon weight by material [triage G32]

- **Verdict:** Not determined (one-line confirm).
- **Answer:** None. Confirm: "Your weight rule says kind of weapon and sprite size; does it mean material never changes
  weight?"
- **Rests on:** The owner's weight rule as quoted in the report.
- **Challenge:** Weight feeds encumbrance, which the player feels. Kept.

### FILE: 20261127-triage-q33-df-creatures.md
## 2026-11-27: Daggerfall creatures in Doom [triage G33]

- **Verdict:** Deferred.
- **Answer:** None. Which Daggerfall creatures replace Doom monsters, and how they fight, would create a new system and
  change the encounter design.
- **Rests on:** `gamedesign.md` Monsters row: "Daggerfall's monsters are replaced by packs of Doom/DRLX monsters".
- **Challenge:** It even sits against the Monsters row, so only the owner can open it. Kept.

### FILE: 20261127-triage-q34-shelf-material-odds.md
## 2026-11-27: Material odds on shop shelves [triage G34]

- **Verdict:** Follows clearly.
- **Answer:** Shop shelves must roll material from the approved tier odds for the shop's level, not Daggerfall's classic
  curve. This is a defect in the unmerged shoplevels lane for the orchestrator. Seeding follows the owner's seeded-restock
  direction (engineering).
- **Rests on:** `gamedesign.md` Material tiers: "Daedric is the best tier, and its own check is the only way to get it. It
  reaches 1 in 40 at area level 20 and 1 in 20 at area level 30." Loot & Economy row: "The material tier comes from the
  approved odds for the area level." Randomness: "Randomness never bends approved rules."
- **Challenge:** The approved odds were written for drops, and the owner wants Daedric "rather feasible" at shops. But 50%
  of level 30 shelves holding Daedric is already feasible, and the material principles are written for every category.
  Kept.

### FILE: 20261127-triage-q35-shared-map-town-levels.md
## 2026-11-27: Several towns on one Doom map [triage G35]

- **Verdict:** Follows clearly (upgraded from Leans).
- **Answer:** Each town keeps its own town level (Daggerfall 20, Ripwych Commons 5), even on a shared Doom map.
- **Rests on:** Owner `20261126-shops-towns-restocks-owner.md`: "a town's danger level is the higher of its terrain level
  and its class level". AGENTS.md pillar: Daggerfall owns the world. `gamedesign.md`: levels are "facts about the world".
- **Challenge:** A shared map is a converter grouping, not a fact about the world; Daggerfall keeps the two as separate
  places. Using the group's maximum would let an engine artifact change a place's level. Upgraded.

### FILE: 20261127-triage-q36-ship-travel.md
## 2026-11-27: Ship in the transport menu [triage G36]

- **Verdict:** Leans (hold for now) / Deferred (how boarding works).
- **Answer:** Refusing Ship in paired runs is acceptable until it is built, since letting Daggerfall teleport alone would
  desync the engines. Ship travel must come eventually. How boarding works (Doom's travel path, a Doom map of the ship)
  goes to the owner.
- **Rests on:** `gamedesign.md` "Daggerfall's systems are all planned". AGENTS.md milestone hurdle 3 (no desync).
- **Challenge:** A ship map and travel route is new architecture, so Deferred fits. Kept.

### FILE: 20261127-triage-q37-riding.md
## 2026-11-27: Riding in Doom [triage G37]

- **Verdict:** Follows clearly (riding changes Doom movement) / Not determined (which effects, speeds) / Deferred
  (mounted combat).
- **Answer:** Riding must change Doom movement. Which of Daggerfall Unity's riding effects Doom gets (speed, jumping, no
  climbing, horse sprite, dismount at doors) and whether speeds come from Daggerfall or relative to Doom's run speed are
  open. Fighting while mounted, with Doom's weapon where the horse is drawn, changes how combat plays and goes to the
  owner.
- **Rests on:** `gamedesign.md` Movement row: "Doom's fast, responsive FPS movement is the baseline, modified by
  Daggerfall's encumbrance, swimming, climbing, levitation, and horses."
- **Challenge:** The answer pass deferred all details; speeds and which effects are design numbers, not architecture, so
  they are Not determined. Mounted combat stays Deferred.
