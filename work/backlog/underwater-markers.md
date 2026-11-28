# Underwater enemy markers spawn only underwater-capable monsters

Waiting on: the owner. On hold, low priority (owner, 2026-11-27). Card ready.

Daggerfall uses a separate underwater table (slaughterfish, dreugh, lamia) for enemy markers below a block's water
line. Doomerfall ignores it, so land Doom monsters spawn underwater.

Owner (2026-11-27): "I think we'll have to do enemies tagged as allowed to spawn underwater. Enemies allowed to spawn
underwater would be those that are flying, or that perhaps have some nautical theme, but I don't know if there are any
of those, I suppose."

Tag monsters in the pool as allowed underwater: flying monsters, plus any with a water or nautical theme (list any found
in stock Doom, DRLA and Colourful Hell). Underwater markers draw only from tagged monsters, through the normal planner,
seeded as usual.

Done when: a dungeon with underwater markers spawns only tagged monsters there, in a planner test and a paired run;
the notes list the tagged monsters.
