## 2026-11-27: Which building types take their own quality level, and may the town level reach indoor rolls?

- **Verdict:** Follows clearly / Leans / Not determined.
- **Answer:** Follows clearly: no indoor wealth roll (treasure piles, containers, shelves, guild stock) may use the town's
  class level. Card 03's town level must not reach ForCurrentPlace through the ForCurrentDanger fallback
  (DoomerfallAreaLevels.cs:213-217) for any building. Leans: taverns, temples, banks, libraries and palaces in towns also
  take their own quality through the shop bands, like houses and guild halls. Not determined (one-line confirm):
  whether buildings outside towns (castles, farms, manors) are covered too, or keep the area level.
- **Rests on:** owner, 2026-11-26 (`20261126-shops-towns-restocks-owner.md`): a town's class level "is a danger level for
  guards and night spawns", "wealth (shop stock, house and guild loot) comes from each building's own quality through the
  shop bands, not from town size", and the danger level "never influences shop quality". Inference for the lean: the
  owner's complaint was "people in big cities are magically way richer or poorer based on town size". A tavern's
  treasure pile is wealth in the same sense, so the same rule plausibly covers it, but the owner listed only shops,
  houses and guilds.
- **Challenge:** Is the "Follows clearly" part a stretch, since the owner's words name shops, houses and guilds and not
  taverns? No. The struck option is "town class level drives an indoor wealth roll". The owner called the class level
  "danger" only and said wealth is "not from town size". That holds for every building whatever its type. Which level
  taverns use instead (own quality or terrain area level) is still open, so that part stays a lean. Outside towns there
  is no town size, and the area level there is a fixed fact of the region, so the owner's rule plainly was not about that
  case. It goes to a confirm and is not struck. Kept.
- **Owner confirm:** Your rule says a building's wealth comes from its own quality, not town size. Does it also cover
  taverns, temples, banks, libraries and palaces, and buildings outside towns (castles, farms, manors)?
