## 2026-11-27: Levitate speed, narrowed hitboxes, quest gold, converting Daggerfall saves

- **Verdict:** Owner decided.
- **Answer:** Levitate becomes Doom flight at the same percent of player speed as in Daggerfall, using the Doom
  player's current speed (after Running/Athletics and Speed) as the base; the QA bot may fly without it. Narrowed
  monsters use the smaller radius only to squeeze through tight spaces and keep their full-size box for everything
  else (to be verified). Quest rewards follow the area level instead of a fixed 20. A low-priority "Convert Daggerfall
  Save" entry loads a plain Daggerfall save, presented to the player as a conversion, with a pistol and some ammo.
- **Owner's words:** "we want the same PERCENT of player speed as daggerfall, but it should use the Doom engine
  player's current speed as the base after applying athletics skill and speed." "the bot should be permitted to fly
  without levitation". "we had it so only an enemy that needed to squeeze through a small space would get treated as
  smaller hitbox otherwise it got a full size box for all other purposes". "Quest Gold: Agree, use Area Level now."
  "Convert Daggerfall Save ... It does nothing but load the daggerfall save without a doom save".
