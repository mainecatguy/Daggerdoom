# Dungeon actions: show text and riddles (types 11, 12)

**Waiting on:** owner approval to move to todo. Shares the trigger route described below with the other dungeon action items.

Source: the record survey, `work/notes/20261124-104520-record-types.md` (branch `overnight/records`), and its proposed
card `work/notes/20261124-104520-record-cards/02.opus.action-messages-and-quest-state.md`.

- Type 11 shows text: 3 models and 3 flats (Sentinel, Mantellan Crux).
- Type 12 asks for typed input: 2 models and 4 flats. These are the riddles in Shedungent, Daggerfall and Mantellan
  Crux. `AnswerAccepted` (`tools/dungeon_converter/action_objects.zs:18`) has no caller.
- Today both reach `DFActionRules.Request` (`action_objects.zs:10-15`), print `DFRULE`, and stop.

**Trigger route (shared):** Doom reports the trigger with the record's identity, and Daggerfall runs its own
`DaggerfallAction` for that record, with its windows shown through Doom as shops and talk already are.
