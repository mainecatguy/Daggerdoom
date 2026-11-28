> **Sent back (2026-11-28):** waiting on owner choices. The dungeon part is built and verified (branch
> agent/randomencounters-20261128-072945, rest_ambush 9/9, demo review\rest-ambush\play.bat, notes
> work/notes/20261128-072945.md) and goes to the next merge.

# Random encounter packs: what is left

1. **Outdoor random encounters** (town at night, wilderness): Daggerfall still rolls these, but Doom has no outdoor
   pack system, so they stay suppressed. The monster list, planner request and dead-id tracking are all dungeon-only.
   An outdoor pack's ids would have to survive the treadmill window, which is the same open design as outdoor guard
   bots (gamedesign/decisions/20261124-outdoor-guards.md).
   - (a) Their own card: an outdoor monster registry in the treadmill, packs placed near the player, deaths kept per map
     pixel.
   - (b) Wait for the outdoor guard design; they stay suppressed until then.
2. **Reputation and banishment guards** (Daggerfall's 5%/10% per-minute guard rolls for a low-reputation or banished
   player): the card listed them as mook packs, but earlier decisions make angry guards Doom guard bots. Today they run
   as guard bots inside buildings and stay suppressed outdoors.
   - (a) Stay guard bots.
   - (b) Become DRLA mook packs planned by the encounter system.
