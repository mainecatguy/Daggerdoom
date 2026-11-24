# Doom weapons have a Daggerfall material

**Waiting on:** owner approval to move to todo, and *Doom items replace most weapon loot* (where most of these weapons come from).

Owner decisions (2026-11-24): a Doom weapon can be made of a Daggerfall material, and Daggerfall respects it. It is
material metadata, not just a label.

- The `DoomerfallDoomItem` carries real material data, the way Daggerfall weapons do, so Daggerfall's own rules can
  read it: damage bonus, price, and any material effects. It is saved with the item and shown in its name and info,
  for example "Ebony Plasma Rifle". Doom items have no material today (`DoomerfallDoomItems.cs`).
- It is rolled with the approved material odds at the area level, like any other loot.
- The material gives the weapon a damage modifier (*Weapon material damage bonus*). It does not change which Doom
  weapon it is.
