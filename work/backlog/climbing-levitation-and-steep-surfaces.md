# Climbing, levitation, and steep surfaces

**Waiting on:** owner design input after the research step.

Owner decision (2026-11-23): town roofs keep Daggerfall's original pitch.

The climb function itself moved to `work/todo.md` as an initial release target. This item keeps levitation and steep surface rules.

Climbing and levitation will eventually be in the game. Doom currently lets the player walk up very steep hills and surfaces without limit. The player should be blocked, slide, or need Daggerfall's climbing wherever Daggerfall would require it.

When this starts, research Daggerfall Unity's real behavior first: which surfaces the player can walk up, when they slide or get blocked, and when climbing starts, continues, or fails, including skill checks. Start with `FrictionMotor.cs`, `ClimbingMotor.cs`, and the player's slope limit. Then design the Doom behavior with the owner.

Game designer, 2026-11-24 (follows clearly): climbing should charge Daggerfall's climbing fatigue. Exhaustion still never kills (`exhaustion-rework.md`).
