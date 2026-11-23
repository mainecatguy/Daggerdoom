# Grid inventory (shelved by owner, 2026-11-22)

**Waiting on:** the owner deciding to revisit it. The existing inventory stays for now.

A Diablo-style grid replacing Daggerfall's inventory, chest, and trade item lists, matching Daggerfall's UI. Ideas so far:

- Small but not tiny cells, around 8 Daggerfall UI units, with items at normal sprite size.
- An item occupies every cell its non-transparent sprite pixels intersect. No rotation, a stack takes the space of one item, and gold stays outside the grid.
- Keep Daggerfall's item collections underneath, with grid positions as a layer on top, and never lose items.
- Start with unlimited scrolling, with weight as the only limit. A later limit could be around 4 pages for the player. Scripts and quests could still force items in past it, and containers stay unlimited.
- Reference only, do not copy code: https://github.com/SinlessDevil/TetrisInventorySystem
