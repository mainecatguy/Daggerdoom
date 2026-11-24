# Rebuild load: a save survives a broken Doom snapshot

**Waiting on:** the location ledger (`work/queue/locationledger`, cards 1-3), and the player's Doom inventory (guns, ammo, armor) being restorable from Daggerfall. Ammo counts are live in Doom today (open question 20261124-075147).

Stage 4 of the approved location state plan (`work/notes/20261124-105104-location-state-research.md`). When Doom's
snapshot in a bundled save cannot load, because the mod list or order changed, a converted map changed, or the
snapshot is missing, Doom starts the map fresh at Daggerfall's position and applies Daggerfall's ledger. Today the
whole save is lost (`dd_bridge.cpp` `LoadBreak`). The research reproduced three such breaks.
