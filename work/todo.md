# Todo

Work that is ready to do automatically, in priority order. Every item here is approved by the owner, needs no owner input, and depends only on finished work or earlier items in this list. Anything else stays in `work/backlog.md`.

## Loop rules

- Take the first item only. Never take work from `work/backlog.md`.
- If an item turns out to need owner input or unfinished work, move it to the backlog, say what it is waiting on, add the question to `work/questions.md`, and continue with the next item that does not depend on it.
- When an item is verified, remove it from this file and record it in `CHANGELOG.md`.
- Stop if weekly plan usage reaches 95%, extra usage becomes enabled, two runs in a row fail to make verified progress, or the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Ready

The owner approved this work on 2026-11-23. Each item runs from its reviewed card in `work/queue`.

**Owner decisions on the research (2026-11-23):**

- Each Doomerfall save is one bundled UZDoom `.zds` file using Doom's save and load menus. It must still make a real Daggerfall save and carry it in the bundle.
- After death, show Doom's death view, then a screen offering Load Last Save, Load Game, and Main Menu.
- New Game temporarily uses one difficulty prompt after Daggerfall character creation and a fixed default Doom class. See "Full Daggerfall new game flow" in the backlog.
- Leave quick keys and quit behavior alone for now.
- Autosaves on Daggerfall maps use the bundled save. Their frequency can be revisited if they slow the game down a lot.
- Doom's Use button is the interaction button. It triggers Daggerfall's Grab action, or Steal while crouching, as well as Doom's normal use.
- Dungeons have a difficulty level (area level) from 0 to 30, and loot and encounter systems must be compatible with it.

### Make Doom guards better

Owner request (2026-11-23): after the first guards land, improve how they behave. Variety is a separate backlog item. No card yet.

### Doom ammo in Daggerfall's inventory, and arrow weight

Owner decisions (2026-11-24): weights and base prices per ammo type, arrows 0.01 kg. Card: `work/queue/ammo`. Starts when a lane is free, after `gunicons`, which also touches Doom items.

### Change ammo key

Owner request (2026-11-24), after the ammo item: a change ammo key. The type of ammo you're loading should appear on screen. The key changes ammo between the various quality tiers of ammo and shows an icon at the bottom of the screen with the one selected. Look at how Change Ammo works in Blood West as an example. No card yet.

Tiers (owner, 2026-11-24, working table, still being tuned with the owner). The tiers are Daggerfall's materials, and each tier's ammo gets that material's colour tint, as Daggerfall does for items. Tin was dropped so that ammo feels valuable. Iron is called "Regular". Elven, Dwarven and Orcish ammo are named Moonstone, Dwemer and Orichalcum, but still map to Daggerfall's material tiers. Price is a multiple of the owner's base prices (bullets 1, shells 3, rockets 10, cells 5), so plain (Regular) ammo costs 3x those. Weight is a multiple of the base weights. Stack is the number of rounds in one pickup or one vendor stack, relative to a base amount per ammo type, and pickups are big.

| Tier | Damage | Price | Weight | Stack | Where | Strength |
|---|---|---|---|---|---|---|
| Regular | 0% | 3x | 1x | 2x | Drops abundantly, and town | Commonplace baseline |
| Steel | +20% | 5x | 1x | 1.5x | Drops and town | Reliable all-rounder |
| Silver | +10% | 7x | 1x | 1x | Drops and town | Silver bonus against certain enemy types (backlog) |
| Moonstone | +35% | 14x | 0.5x | 0.75x | Town; rare 10x drop | Quiet (backlog `elven-ammo-quiet`) and light |
| Dwemer | +50% | 15x | 2x | 1x | Town; rare 10x drop | Mid-tier punch, heavy |
| Adamantium | +60% | 28x | 1x | 0.75x | Drops a bit more often than other rare ammo, and town (not common); only above a minimum level, not yet chosen | Most findable high tier |
| Orichalcum | +70% | 32x | 1x | 0.5x | Town, abundant mostly in Orsinium; rare 10x drop | Middle-of-the-road high damage |
| Mithril | +40% | 40x | 0.1x | 0.5x | Town; rare 10x drop | Quiet and nearly weightless |
| Ebony | +100% | 45x | 2x | 0.5x | Drops and town | Double damage, heavy |
| Daedric | +100% | 75x | 1x | 0.25x | Rare drop, and town | Top damage, light, plus the Silver bonus |

Only Regular, Steel, Silver, Adamantium, Ebony and Daedric drop normally in dungeons, so the inventory doesn't fill with odds and ends. Bonuses multiply with other bonuses (`gamedesign/damage.md`). Adamantium has no minimum level. Rarer ammo is rarer in lower-level dungeons.

**Ammo drop rule (owner approved 2026-11-24; Claude's numbers).** Ammo drops have their own rule, which replaces the weapons' "lower tiers are always more common" rule for ammo. It keeps the shape of the approved material odds in `work/notes/20261123-material-tier-proposal.md`:

1. Daedric gets its own roll, with the same formula as weapons: none at area level 1, 1 in 40 at level 20, 1 in 20 at level 30.
2. Otherwise, roll Regular, Steel, Silver, Adamantium and Ebony in that order. Each tier is `falloff` times as likely as the one before it. `falloff = 0.35 + 0.45 × (level - 1) / 19` for levels 1 to 20, and `0.80 + 0.10 × (level - 20) / 10` for levels 20 to 30. Levels are clamped to 1..30.

| Area level | Regular | Steel | Silver | Adamantium | Ebony | Daedric |
|---|---|---|---|---|---|---|
| 1 | 65.3% | 22.9% | 8.0% | 2.8% | 1.0% | none |
| 10 | 46.2% | 26.0% | 14.7% | 8.2% | 4.6% | 0.27% |
| 15 | 36.9% | 25.2% | 17.2% | 11.7% | 8.0% | 1.0% |
| 20 | 29.0% | 23.2% | 18.6% | 14.9% | 11.9% | 2.5% |
| 30 | 23.2% | 20.9% | 18.8% | 16.9% | 15.2% | 5.0% |

3. Town-only ammo (Moonstone, Dwemer, Orichalcum, Mithril) can also drop, from a separate rare check of about 4% of ammo drops (Claude's number). It is picked in that order with the same falloff. It drops as 10x a normal stack, and the owner prefers it as 10 separate pickups scattered around the spot ("10 copies of the item go everywhere").










