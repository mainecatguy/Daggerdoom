# Hostile NPC sprites

**Waiting on:** owner decision on the approach.

Owner concern (2026-11-23): Daggerfall NPCs may have no self defense or angry sprites.

Code findings, not yet checked visually:

- Stationary NPCs store one billboard archive and record (`StaticNPC.cs:106-107`), so they appear to have no combat animation.
- Wandering NPCs have walking and idle animations in 8 directions, and guards have an idle set (`MobilePersonBillboard.cs:135-147`).
- Daggerfall's human enemy classes and city watch have separate male and female sprite archives in `EnemyBasics.cs`, for example 481/482, 487/488, and 399.

Likely option to evaluate: when an NPC turns hostile, swap to the closest human enemy class sprite set. The visible change of appearance is an owner call. Check the real frames before recommending it.
