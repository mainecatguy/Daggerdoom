# Test that every weapon's damage gets the player's bonus (mod compatibility check)

**Waiting on:** owner approval to move to todo. Useful as soon as any damage bonus element is non-zero, and part of every mod compatibility check after that.

Owner request (2026-11-24): verify that gun attacks inherit Daggerfall's bonuses (material, ammo, and later skills),
including indirect damage such as splash, fire, or a thrown molotov.

- A harness gives the player a known multiplier (`DoomerfallDamageBonus.TestMultiplier`, for example x2), then fires
  every weapon in the loaded mods at a test target and compares the damage dealt with and without the bonus.
- It records each damage path separately: direct hit, projectile, splash, and anything the attack spawns (fire,
  puddles, bouncing grenades).
- Any weapon or path whose damage does not follow the multiplier is listed, with the reason, such as a spawned
  hazard with no owner. That list is the result. Fix only clear, small cases. Report the rest.
- Add this test to the checklist for adding or updating a Doom mod.
