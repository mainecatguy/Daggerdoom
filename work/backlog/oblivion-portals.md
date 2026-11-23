# Oblivion Portals

**Waiting on:** MVP, including HP sync, synchronized saving and loading, and item drops.

Owner design (2026-11-22):

- Oblivion Portals are styled after the portals in The Elder Scrolls: Oblivion.
- Entering one takes the player to a classic Doom map, or a map from a WAD in their custom WADs.
- A system may let the player buy an item that makes a portal lead to a specific Doom map, so players can visit any Doom map they choose.
- Some random dungeons may also lead to Doom maps.
- Daggerfall idles while the player is inside and keeps mediating damage dealt and taken. Portal maps have random drops.

**Likely approach, if we build see-through rifts (owner, 2026-11-22):** generate a map from the WAD map that also includes the surrounding Daggerfall exterior and the portal, joined by a UZDoom line portal. The overworld treadmill hands off to it the way it does to a town, because the treadmill itself cannot host linked portals. Generate this as a separate cached map and never modify the player's WAD. Start with a proof using one classic Doom map. Maps that cannot merge, such as heavily scripted ones, fall back to a normal load.

**To work out when this starts:**

- Most WADs are already supported. The risk is WADs that change core monsters or rules, because UZDoom mounts WADs at startup and those changes could reach Daggerfall maps. Map names such as MAP01 can also collide between WADs.
- How the player returns, including when a map's normal exit fires, and what happens on death inside a portal.
- Saving and loading while inside a portal map.
- Keeping the player's inventory through Doom map changes that normally reset it.
