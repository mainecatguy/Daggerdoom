# Moonstone and Mithril ammo are quiet

**Waiting on:** the ammo tiers (`work/queue/ammotiers`).

The owner (2026-11-24): Elven ammo (now named Moonstone) is quiet, and Mithril gets the quiet tag too. It can't be completely silent, but:

1. A shot is silent if it kills an enemy in one hit.
2. It has the `reduced_noise` tag, which halves volume for Doom purposes. This is aggro, not sound, but to the
   player it should also reduce the volume of the guns.

The tag shows as player state while the ammo is loaded (`gamedesign/damage.md`).
