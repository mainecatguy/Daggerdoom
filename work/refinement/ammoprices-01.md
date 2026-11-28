# Ammo prices: Regular is 3x base, other tiers by their table multiples

Lane: `ammoprices` (new). Model: Opus. DRAFT: the cell base price waits on the owner.

Regular ammo was dropped to 1x base price (bullets 1, shells 3, rockets 10, cells 10), while higher tiers kept their
old prices, so Steel became 5x Regular instead of 5/3x. Owner (2026-11-27, Q&A sheet item 36): "This was handled wrong.
Normal Ammo should be 3x base price. Ammo is not the 'base price' it's just a reference the other ammos multiply by.
Nothing is 1x base." So prices follow the approved tier table (`work/queue/ammotiers/done/04.opus.ammo-material-tiers.md`):
Regular 3x, Steel 5x, Silver 7x, Moonstone 14x, Dwemer 15x, Adamantium 28x, Orichalcum 32x, Mithril 40x, Ebony 45x,
Daedric 75x the base reference. Base references: bullets 1, shells 3, rockets 10, cells [5 or 10: pending owner].

Done when: shop prices for each ammo type and tier match the table, Regular = 3x the base reference.
