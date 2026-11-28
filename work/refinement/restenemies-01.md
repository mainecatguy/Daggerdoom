# Resting says "enemies nearby" after the nearby Doom monsters are dead

Lane: `restenemies` (new). Model: Opus. Depends on nothing.

After killing the Doom monsters near the player, Daggerfall's rest still refuses with "there are enemies nearby".
Rest is Daggerfall's rest menu "exactly as in Daggerfall", which refuses while enemies are near
(`DaggerfallRestWindow.cs`, `AreEnemiesNearby`), and hostile guard bots also block it (owner rule).

Owner (2026-11-27): "we seem to have a bug where you get 'there are enemies nearby' when resting in daggerfall when you
have killed the enemies in doom that are nearby. it seems that maybe the enemies don't actually get killed in
daggerfall when they die in doom but they should for this reason."

Find what Daggerfall counts as a nearby enemy in a bridged game (hidden Daggerfall enemy entities, mook placements, or
something else) and make Doom deaths count, so rest is refused only while living hostile monsters or hostile guard bots
are actually near, measured in Doom.

Done when: in a paired run, rest is refused next to a living monster, allowed once the nearby monsters are dead, and
still refused near a living hostile guard bot; after a save and load the result is the same.
