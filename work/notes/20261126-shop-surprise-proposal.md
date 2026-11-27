# Shop levels 5: making shops and restocks surprising

Research and proposal only. No code changed. Card: `work/refinement/shoplevels-05.md`.

## 1. How shops work today

- **When a shelf stocks.** Opening a shelf stocks it if its stocked date is earlier than today
  (`PlayerActivate.cs:882`). Any wait, rest or travel of a day re-stocks it. Doomerfall's item ledger keeps the date
  and contents (`DoomerfallItems.cs:286, 425`), so the classic rule still applies.
- **Restocking deletes the old stock.** `DaggerfallLoot.StockShopShelf` starts with `items.Clear()`. Everything unsold
  vanishes overnight, along with anything the player sold to the shop.
- **Every shelf is a full shop.** Each shelf model rolls the shop type's whole table on its own (a weapon smith shelf
  makes about 13 weapon rolls). A shop's size comes from its shelf count, not from its wealth.
- **Quality barely matters.** Every weapon has rarity 1 and armor rarity 1 or 3, so quality mostly decides book counts
  and whether shops at quality 1-2 skip body armor. Material uses the terrain level, `WorldLevel.Current`
  (shoplevels card 02 changes this to the shop level).
- **Not seeded.** `PlayerActivate` calls `Random.InitState(Time.frameCount)` before stocking, so stock is new noise on
  every visit and differs between saves. This breaks "fixed seeds, not per-save randomness".
- **Doomerfall additions:** tiered ammo (`DoomerfallAmmoTiers.StockShop`: weapon smiths stock all tiers, general
  stores stock Regular) and lockpicks. Doom guns are never on shelves, and they cannot be sold until
  `weaponvalues/01` lands.
- **Material odds in practice** (`20261124-124736-shop-levels.md` section 3): a whole weapon smith shows a Daedric item
  on 67% of days at level 20 and 82% at level 25. One or two days of resting brings a 50% chance. Gold is the only
  brake.

## 2. Is it adequate?

No. Every shop of a type is the same shop with different noise. Players learn nothing about a particular shop, so
nothing can surprise them (the "every room is different in the same way" failure). Things that are broken, not just
dull:

- **Object permanence:** unsold goods and items the player sold disappear overnight.
- **Fixed seeds:** stock is per-visit noise, not a fact about the place.
- **Rarity is cheap:** high-level weapon smiths act as daily Daedric vendors, because resting re-rolls the shop.
- **Minor:** clothing follows the player's gender, so stock adapts to the player. This is classic Daggerfall
  behaviour, and it could stay as a convenience.

## 3. Proposal: every shop is a business with a supply chain

The idea: a shelf holds **lots**, and each lot came from somewhere. Players learn a shop's normal suppliers and
rhythm. Surprise comes when a lot breaks that pattern. All rolls are seeded by (building, delivery number), so every
player sees the same goods on the same date. Material odds per item never change; only which kinds of items arrive,
how many, and when.

**A. The shelf is a ledger (permanence).** A restock adds new lots and never clears the shelf. Items leave when
"sold to other customers": each period, every item has a fixed chance to go. Cheap goods sell fast and expensive
goods linger, so a Daedric sword you can't afford yet is often still there next week. Items the player sells go on
the shelf and later sell off the same way. Stock size is set by the shop's wealth (shop level), not by its shelf
count: the shelves share one stock.

**B. Fixed shop identity (the learnable pattern).** From the building seed, each shop gets:
- **Specialty lean:** which item kinds it favours, for example an axe smith, an archery outfitter, a general store
  that serves fishermen and miners. These are leans, not bans: other kinds still appear sometimes.
- **Breadth, U-shaped:** most shops are either deep specialists (many of a few kinds) or thin generalists (one of
  everything). Few sit in the middle.
- **Rhythm, U-shaped:** either a small trickle every few days, or a big delivery on a fixed weekday or date with
  sparse stock between deliveries. Rhythm sets throughput, and throughput is what tames Daedric without touching the
  odds. A level 25 smith getting 6 weapons a week sees one Daedric about every 5 weeks (1 in 27 per item). A big
  monthly smith getting 20 weapons sees one in about half of its months. Today it is most days.
- **Suppliers, Pitman-Yor style:** two or three regular suppliers ("the Sentinel caravan", "the local forge") supply
  most lots. A new supplier shows up now and then, and some later become regulars.

**C. Lots that tell a story.** A lot is a small, coherent bundle from a template, rolled with Daggerfall's normal
item and material code:
- *Regular supply:* the specialty goods. Most lots are this, and that is the baseline.
- *Estate sale:* one dead adventurer's kit: a weapon, armor that matches it, a few potions, a book, a ring. It reads
  like a person.
- *Salvage:* gear from the nearest dungeon. It leans to the item kinds its accepted encounter genome carries (orc
  lair, so axes and shields). Ammo types lean the same way (plasma troopers, so cells), at the approved tier odds.
- *Caravan:* goods from another region, by item kind only (Hammerfell blades in High Rock).
- *Bulk lot:* forty arrows, or a crate of the same mace. Many identical items read as an army being outfitted.
- *Pawn shops* take only estate, salvage and "townsfolk" lots (one odd item each: a wedding band, a lone helmet).
  This makes them the high-variance shop, where exceptions surface.

**D. Rare exceptions (the pattern breaks).** A small fixed share of deliveries, seeded, the same in every game, never
tied to the player:
- the archery outfitter's one shipment of plate;
- a pawn shop with a single Doom gun from an estate sale (needs `weaponvalues/01`; see question 2);
- a general store emptied by a siege lot (all weapons, no food);
- a village smith whose monthly crate is all one weapon kind.

These give the "the pawn shop in Ykalon had a plasma rifle on Morndas" story that players compare.

**E. Let players learn the pattern.** Surprise needs an expectation first. Make the identity visible: one line on
entry or from the shopkeeper ("The caravan from Sentinel comes on Turdas", "Mostly axes here"), and lot labels in
item names or tooltips ("from an estate", "salvage"). Without this the structure exists but players only see noise.

## 4. Cost and value

| Part | Rough cost | Worth it? |
|---|---|---|
| A. Ledger shelves, seeded restocks, items sell off, player-sold items appear, one stock per shop | 1 card, medium. Touches `StockShopShelf`, `PlayerActivate`, the ledger | Yes. It fixes two broken principles and is the base for everything else |
| B. Identity: lean, breadth, rhythm, suppliers (a table keyed by building seed that multiplies the existing chance mods) | 1 card, small to medium | Yes. Cheapest real surprise, and it tames Daedric |
| E. Visible pattern (entry or keeper line, lot labels) | 1 small card | Yes. B is mostly invisible without it |
| C. Lot templates (about 6 templates, data-driven) | 1-2 cards, medium | Yes. This is the "story told by the goods" |
| C. Salvage from the nearest dungeon's genome | 1 card, medium. Needs a nearest-dungeon lookup and the genome API | Later, after C |
| D. Rare exceptions | Small once C exists (exception templates at a low fixed share) | Yes, cheap after C |

Recommended order: A, B, E, then C, then D. Salvage last.

## Questions for the owner

1. **Throughput target:** is about one Daedric item a month at a top weapon smith (instead of most days) the right
   ballpark? This sets the rhythm numbers.
2. **Doom guns on shelves:** may a Doom gun ever be for sale (rare estate or salvage lots at pawn shops and weapon
   smiths), or can players only sell them?
3. **Visible pattern:** should shopkeepers tell the player the delivery day and specialty, or should players
   discover it themselves?
4. **Item condition as story:** may estate and salvage lots arrive worn and priced lower? This changes the economy
   a little.
