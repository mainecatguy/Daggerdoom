# Passive guards and friendly entities become passive Doom guard bots

Lane: `passiveguards` (new). Model: Opus. Depends on nothing; builds on the town guard bots.

Daggerfall has 70 enemy markers flagged passive (Action 99), mostly Knights in the Daggerfall, Wayrest, Sentinel and
Orsinium castles and 3 in Scourg Barrow. Daggerfall Unity makes them attack only when provoked. Doomerfall spawns a
normal hostile Doom monster at each, so royal courts start fights.

Owner (2026-11-26): "For passive guards and friendly entities, I think we want to give the passive guard which is a
doom bot, yes. It can be fast moving, jump up and down and fire projectile weapons if attacked and it becomes hostile.
THis is important potentially."

They still look like Daggerfall's guard. Owner: "passive guards should still look like the daggerfall guard entity
though. Pull the sprite in to doom and scale it appropriately to the new world scale, figure it out". Read the sprite
from Daggerfall's files as the other Daggerfall art is (texture packs apply), scaled to Doomerfall's world scale.

Done when: in a paired run the castle courts and Scourg Barrow's passive markers hold passive guard bots that ignore
the player until attacked, then turn hostile: fast, jumping, firing projectile weapons, looking like Daggerfall's guard at the right size; Daggerfall's crime and
reputation effects follow as for town guards; the notes list which other friendly entities now use the same bot.
