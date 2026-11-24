# NPC damage and death

**Waiting on:** owner approval to move to todo, "Show stationary NPCs in Doom", and the monster ID and death report task.

Owner decisions (2026-11-23):

- NPCs follow Daggerfall's rules on whether they can be killed.
- Flat NPCs that cannot be killed in Daggerfall are invincible in Doom. They take no damage.
- NPCs that Daggerfall allows the player to kill can be killed before self defense exists. They do not fight back yet.
- Quest-critical NPCs do whatever Daggerfall did with them.
- Daggerfall defines which NPCs are stationary and ignore damage, and which can be attacked and fight back.

This task must establish Daggerfall's real rules for each NPC type. Report each permitted death to Daggerfall by the NPC's stable ID. Daggerfall sets NPC HP, as `gamedesign.md` allows for its non-Doom entities.
