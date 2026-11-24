# Exhaustion rework

**Waiting on:** priority. Backlogged by the owner (2026-11-23).

Owner design (2026-11-23):

- Exhaustion never makes the player pass out from running or jumping, and never kills them.
- A fatigue-damaging attack can make the player collapse for 5 to 10 seconds. Tell the player: "You've collapsed from exhaustion."
- Otherwise, running or jumping with fatigue loss progressively slows the player, down to a maximum of 50% speed.
- While exhausted, the screen edges flash black. When this starts, look online for an effect to use as a template.

Implementation facts: `PlayerEntity_OnExhausted` (`PlayerEntity.cs:2380`) currently rests or kills the player. `GameManager.AreEnemiesNearby` cannot see Doom monsters. Daggerfall's running drain is 88 per game minute, which empties 100 fatigue in about 6 real minutes of nonstop running.
