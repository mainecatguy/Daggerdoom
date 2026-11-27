# Mod compatibility research (specialist)

**Waiting on:** the owner moving it to todo ("a todo in the future", owner, 2026-11-25).

A specialist research task. Review the commit history (`git log` on `integration`, `CHANGELOG.md`, `work/notes/`) to
learn how DRLA, DRLA Monsters, DRLAX and Colourful Hell were made to work, then write the process for adding a new
Doom mod so nothing is forgotten.

Main goal: a new mod's weapons are recognized by and work with Daggerfall's inventory, RPG systems, skills, items on
the ground, materials, and so on. Also cover ammo, health, armor and powerups, damage types, monsters and encounter
prices, deterministic drops, the mod set locking a save, and running without the mod.

Deliverable: a guide for agents adding a mod, and where it should live and be referenced. Owner design questions it
raises go to the owner.

Required step (owner, 2026-11-26): the guide must include setting each new mod's weapon value and weight in the
Doomerfall mod's support file ("we need to update mod compatibility guidelines to indicate this needs to be a step is
setting value and weight"). See `weaponvalues` 01.

Required step (owner, 2026-11-26): for a mod without DRLAX tiers, determine each weapon's tier from its DPS ("if it is
not let's tier them off DPS"). The tier sets shop rarity and value.
