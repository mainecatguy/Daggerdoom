# Game designer verdicts: shop levels and kill drops questions (2026-11-27)

Sources: work/agent-reports/20261127-120125-shoplevels.md, 20261127-123536-shoplevels.md, 20261127-112323-killdrops.md.

## Challenge pass

### FILE: 20261127-indoor-own-quality-buildings.md

## 2026-11-27: Which building types take their own quality level, and may the town level reach indoor rolls?

- **Verdict:** Follows clearly / Leans / Not determined.
- **Answer:** Follows clearly: no indoor wealth roll (treasure piles, containers, shelves, guild stock) may use the town's
  class level. Card 03's town level must not reach ForCurrentPlace through the ForCurrentDanger fallback
  (DoomerfallAreaLevels.cs:213-217) for any building. Leans: taverns, temples, banks, libraries and palaces in towns also
  take their own quality through the shop bands, like houses and guild halls. Not determined (one-line confirm):
  whether buildings outside towns (castles, farms, manors) are covered too, or keep the area level.
- **Rests on:** owner, 2026-11-26 (`20261126-shops-towns-restocks-owner.md`): a town's class level "is a danger level for
  guards and night spawns", "wealth (shop stock, house and guild loot) comes from each building's own quality through the
  shop bands, not from town size", and the danger level "never influences shop quality". Inference for the lean: the
  owner's complaint was "people in big cities are magically way richer or poorer based on town size". A tavern's
  treasure pile is wealth in the same sense, so the same rule plausibly covers it, but the owner listed only shops,
  houses and guilds.
- **Challenge:** Is the "Follows clearly" part a stretch, since the owner's words name shops, houses and guilds and not
  taverns? No. The struck option is "town class level drives an indoor wealth roll". The owner called the class level
  "danger" only and said wealth is "not from town size". That holds for every building whatever its type. Which level
  taverns use instead (own quality or terrain area level) is still open, so that part stays a lean. Outside towns there
  is no town size, and the area level there is a fixed fact of the region, so the owner's rule plainly was not about that
  case. It goes to a confirm and is not struck. Kept.
- **Owner confirm:** Your rule says a building's wealth comes from its own quality, not town size. Does it also cover
  taverns, temples, banks, libraries and palaces, and buildings outside towns (castles, farms, manors)?

### FILE: 20261127-indoor-enemy-level.md

## 2026-11-27: Which level do enemies inside buildings use?

- **Verdict:** Follows clearly / Leans / Not determined (was Follows clearly / Leans).
- **Answer:** Follows clearly: indoor enemies (quest foes, house and guild guards) never take their stats from the
  building's wealth level. Leans: their gear, gold and loot also come from the danger side, and only things the building
  itself rolls (containers, loot piles, shelves, Mages Guild stock) follow building wealth, as built. Not determined
  (one-line confirm): whether the indoor danger level includes the town's class level or uses the terrain area level
  only.
- **Rests on:** owner, 2026-11-26: level "is split in two", with the class level a "danger level for guards and night
  spawns" and wealth meaning "shop stock, house and guild loot". `gamedesign.md`, "The world does not scale to the
  player" and Monsters row: "Difficulty follows area level". A rich house holding level-30 guards in a level-1 region
  would make danger follow wealth, which the split rules out. The lean rests on World logic: what an enemy carries is
  its own, not the building's furniture. That is inference, because "house and guild loot" could be read to include a
  guild guard's purse.
- **Challenge:** The answer said "danger level for stats" was Follows clearly, but "danger level" inside a town is the
  higher of terrain and class level. The owner gave the class level to "guards and night spawns while friendly
  townspeople occupy it". That plainly covers outdoor town guards and night spawns. It does not plainly cover a quest
  foe inside a house. The agent's own review says "Indoor enemies would also need an explicit decision on whether they
  get the town level." So the Follows clearly part is narrowed to "not the building's wealth level", and whether the town
  class level applies indoors goes to a confirm. The loot lean is kept.
- **Owner confirm:** Your town class level is danger for guards and night spawns. Does it also set the level of enemies
  inside buildings (quest foes, house guards), or do they use the terrain level?

### FILE: 20261127-shop-daedric-frequency.md

## 2026-11-27: How often should a top shop hold a Daedric item?

- **Verdict:** Leans / Not determined.
- **Answer:** Struck: making Daedric goods sell off faster. Leans: fewer Daedric arrivals, so a top level-30 smith does
  not hold one on 100% of days. The exact target (for example about half of top smiths on a given day, or about one a
  month at a top smith) is a number for the owner.
- **Rests on:** owner, 2026-11-26 (`20261126-shop-proposal-owner.md`): "it should be rather feasible to find a Daedric item
  at a shop, i like the idea of rotating expensive stock less to make them feel more memorable or significant". This
  strikes faster sell-off. Owner, 2026-11-26 (`20261126-shops-towns-restocks-owner.md`): "how can we maximize principle of
  surprise that's the biggest important thing to me". `gamedesign.md` Randomness: "Surprise comes from fixed structure
  that the player can learn, which then breaks its own pattern." A Daedric item present every day is neither memorable
  nor surprising. Data: shoplevels 05 report, 100% of days at level 30 after 60 days, 91.9% at level 20.
- **Challenge:** "Rather feasible" could be read to bless near certainty at the very top shops, so keeping it as built
  is not struck. That keeps the verdict at Leans, not Follows clearly. Each shelf item already rolls the approved tier
  odds (triage q34), so fewer arrivals must mean fewer or rarer deliveries of expensive goods, never altered tier odds
  ("Randomness never bends approved rules"). The report says the figure came "before the round-1 fixes", so the current
  rate should be re-measured before the owner sees it. Kept.
- **Owner question:** A level-30 top weapon smith now has a Daedric item on 100% of days (91.9% at level 20). Fewer
  arrivals, keeping slow rotation: what target do you want, for example about half of top smiths on any day, or about
  one a month per top smith?

### FILE: 20261127-shop-stock-numbers.md

## 2026-11-27: Shop stock target, sell-off rate and ammo restock numbers

- **Verdict:** Not determined / Leans.
- **Answer:** The numbers (stock target 15 + 2 x shop level, daily sell-off chance clamp(0.5*sqrt(25/unit value), 1%,
  50%), daily ammo delivery with 50% daily sell-off) are not given by the design. They may ship as placeholders and go
  to the owner. Leans: Doom ammo stays outside the stock target, so frequent ammo restocks never crowd out other goods.
- **Rests on:** owner, 2026-11-26: shops are "the main place the player will get ammo ... restock often" and Daedric
  "rotating expensive stock less". The value-based sell-off follows that slow-rotation direction, but its curve and the
  target are numbers. The ammo lean is inference: counting ammo inside a fixed target would make ammo deliveries push
  goods off the shelves or the reverse, against both owner wishes.
- **Challenge:** Is ammo outside the target a hidden balance choice? Yes, it changes how much a smith holds (about 116
  items at a 75 target). The player sees it, so it is a lean the owner sees, not a minor detail. Nothing in the design
  strikes either option. Kept.
- **Owner question:** Shop numbers are placeholders: stock 15 + 2 x level, value-based daily sell-off (1% to 50%), ammo
  delivered daily outside the target and sold off at 50% a day. OK for now, and should ammo stay outside the target?

### FILE: 20261127-shop-per-shelf-trade.md

## 2026-11-27: Does each shelf open its own trade list, or the whole shop's stock?

- **Verdict:** Leans.
- **Answer:** Keep per-shelf trade lists, as built and as in Daggerfall. The shared stock target stays an off-screen
  bookkeeping fact.
- **Rests on:** `gamedesign.md` In-engine object permanence: "Things that exist in the world appear to the player as if
  they really exist in the world." World logic: "nothing happens that makes no physical sense". Items listed on the shelf
  the player uses are where they appear to be. AGENTS.md: Daggerfall owns UI. Inference: a whole-shop list from one shelf
  is not impossible (a shopkeeper can fetch goods), so the principles point one way without settling it.
- **Challenge:** Daggerfall's per-container trade window alone would not strike the other option (it is precedent, not an
  owner rule). Object permanence leans toward per shelf but does not forbid a shop-wide list. The choice changes what the
  player sees, so it is not a minor detail. Kept at Leans.

### FILE: 20261127-armor-material-split.md

## 2026-11-27: Armor material on shelves and in drops (leather/chain/plate split)

- **Verdict:** Leans / Not determined (was Follows clearly / Not determined).
- **Answer:** Leans: armor should reach the approved tier odds. Daggerfall's RandomArmorMaterial rolls leather 70%, chain
  20% and plate 10%, and only plate uses the approved odds, so Daedric armor is about 10x rarer than Daedric weapons (0.5%
  against 5% at level 30). That probably bends the approved odds, for shelves and enemy drops alike. Not determined: where
  leather and chain fit.
- **Rests on:** `work/notes/20261123-material-tier-proposal.md`, approved by the owner: the table is titled "Material
  odds for weapons, armor, and ammo" and runs Iron to Daedric, with no leather or chain. `gamedesign.md` Loot & Economy:
  "The material tier comes from the approved odds for the area level." Randomness: "Randomness never bends approved
  rules." Precedent: `20261127-triage-q34-shelf-material-odds.md`.
- **Challenge:** The same Loot & Economy line says Daggerfall "decides how much drops and in which category". Leather and
  chain can be read as armor kinds Daggerfall picks (light, medium and heavy armor), with the approved odds applying to
  plate. Under that reading the build follows the rules. Under the other reading they are materials below Iron, which is
  how Daggerfall's own data stores them, and 90% of armor misses the table. Both readings are honest. The q34 precedent
  was about the classic tier curve, not this split. The fix also changes what the player sees (how much leather and
  chain appears, and how common Daedric armor is). Downgraded to Leans, with the owner deciding.
- **Owner question:** Your approved tier table covers armor from Iron to Daedric. Should leather and chain count as armor
  kinds Daggerfall picks (Daedric armor then stays about 10x rarer than Daedric weapons), or should every armor piece roll
  the table, and if so where do leather and chain go?

### FILE: 20261127-luck-drop-ammo-type.md

## 2026-11-27: Which ammo does a Luck kill drop give?

- **Verdict:** Follows clearly / Not determined.
- **Answer:** Follows clearly: never ammo for the gun the player holds. Not determined: the mix. Options are (a) equal
  odds across the four types, as built; (b) the owner's dungeon pickup mix without health (clips 30, shells 25, rockets
  10, cells 3); (c) ammo for the dying monster's own weapon; (d) leaned by the area's loot identity.
- **Rests on:** `gamedesign.md` Randomness, Never adapt to the player: "There is no 'smart loot' tuned to the player's
  guns". Options b to d each have a footing: b is the owner's approved pickup mix
  (`20261126-slope-climb-pickups-owner.md`), c is World logic (a zombieman carries bullets), d is the Loot & Economy loot
  identity (still a proposal).
- **Challenge:** Does World logic strike (a) and (d), since an Imp dropping cells makes little physical sense? Not
  clearly. Monsters carrying loot they don't use is how Daggerfall loot already works, and the owner has not said drops
  must match the carrier. The struck part is solid: the quoted line names this exact case. Related open owner question
  20261127-034545 asks whether Luck's roll should cover non-ammo drops at all, so this mix may change with that answer.
  Kept.
- **Owner question:** Luck's extra ammo drop is equal odds across bullets, shells, rockets and cells for now. Keep that,
  use the dungeon pickup mix (30/25/10/3), give the dying monster's own ammo, or lean by area loot identity?

### FILE: 20261127-luck-drop-whose-kills.md

## 2026-11-27: Whose kills roll the Luck drop?

- **Verdict:** Follows clearly / Leans / Not determined.
- **Answer:** Follows clearly: summoned and revived monsters never roll. Leans: every placed-monster death rolls whoever
  killed it (player, infighting, faction fights, hazards), as built. Not determined: whether town guard kills roll. They
  stay "never" for now, because guards are bot players and not monsters.
- **Rests on:** `gamedesign.md` Loot & Economy: "Summoned and resurrected monsters drop nothing on Daggerfall maps", and
  `20261125-unplaced-monster-loot.md`. The lean rests on World logic and Systemic cause and effect: what a monster drops
  when it dies does not depend on who killed it, and infighting is a system interaction the design favors. That is
  inference, because Luck is the player's attribute and could be read as applying only to the player's own kills.
- **Challenge:** Is a player stat applying to kills the player did not make a stretch? A Luck bonus is arguably about the
  player's fortune, which a hazard kill elsewhere could still count for, so the build is not clearly wrong. But
  "player-only" is not struck either. Guard bots carry Daggerfall's own NPC loot, and adding Luck ammo to them is a new
  rule the design does not give. The performance concern in the killdrops report (up to about half of all kills leaving
  pickups at Luck 100) is engineering, not design. Kept.
- **Owner question:** Luck drops now roll on every placed-monster death, whoever killed it, and never on guards. Should
  only your own kills count, and should guard kills roll?
