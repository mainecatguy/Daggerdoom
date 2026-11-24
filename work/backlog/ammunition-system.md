# Ammunition system

**Waiting on:** owner answers below and owner approval to move to todo. Depends on Daggerfall item pickup and the one-gun slice in "Doom weapon equipping and hotkeys".

Owner decisions (2026-11-23):

- It is time to implement ammunition as a real system.
- Ammo is tiered by Daggerfall's weapon material types.
- Ammo uses the same material tiers as weapons (owner, 2026-11-24).
- Tier odds follow the approved design in `work/notes/20261123-material-tier-proposal.md`.
- Swapping guns does not alter the player's ammo.

`gamedesign.md` already says ammo is an inventory object with different qualities, the player can change the type loaded in a gun, and Daggerfall can tell Doom the player holds more than Doom's maximum.

## Daggerfall's real data

Iron is Daggerfall's lowest material. **Arrows have no material at all** (`ItemBuilder.cs:359-364`, `398`), so there are no arrow rarities to copy. The closest real source is the weapon material roll, `FormulaHelper.RandomMaterial`, which uses `ItemBuilder.materialsByModifier`. Odds below were computed by enumerating all 256 rolls.

| Player level | Iron | Steel | Silver | Elven | Dwarven | Mithril | Adamantium | Ebony | Orcish | Daedric |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 39.5% | 50.0% | 3.9% | 6.6% | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | 33.2% | 50.0% | 3.9% | 8.2% | 4.7% | 0 | 0 | 0 | 0 | 0 |
| 10 | 25.4% | 50.0% | 3.9% | 8.2% | 5.1% | 3.1% | 2.0% | 1.2% | 0.8% | 0.4% |
| 20 | 17.6% | 50.0% | 3.9% | 8.2% | 5.1% | 3.1% | 2.0% | 1.2% | 0.8% | 8.2% |
| 30 | 9.8% | 50.0% | 3.9% | 8.2% | 5.1% | 3.1% | 2.0% | 1.2% | 0.8% | 16.0% |

This stock table is reference only. The approved Doomerfall odds replace it. Above level 10, the stock table moves all the extra chance to Daedric.

Daggerfall's material damage and to-hit modifier (`DaggerfallUnityItem.cs:979`): Iron -1, Steel and Silver 0, Elven +1, Dwarven +2, Mithril and Adamantium +3, Ebony +4, Orcish +5, Daedric +6. Arrow reference: weight 0.25, price 2, and loot stacks of 1 to 20.

## DRLA facts that affect this

- Each DRLA weapon has its own loaded magazine item, such as `RLAutoshotgunClip`, separate from reserve ammo.
- Reserve ammo is shared by ammo class, so tiers need either new ammo classes or a damage multiplier applied to the loaded tier.

## Open questions for the owner

1. What damage does each tier deal? It could be derived from Daggerfall's modifiers.
2. Does ammo have weight and price, and do stacks follow arrows?
