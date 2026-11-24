# Dungeon actions: trap damage and poison (types 21-27)

**Waiting on:** owner approval to move to todo. Uses the shared trigger route (see `dungeon-action-text-and-riddles.md`).

Source: the record survey, `work/notes/20261124-104520-record-types.md` (branch `overnight/records`), and its proposed
card `work/notes/20261124-104520-record-cards/03.opus.action-harm-spells-and-sounds.md`.

- Types 21-25 (hurt): 21 models and 33 flats, in up to about 1,000 dungeons.
- Type 26 (poison): 1 flat. Type 27 (unknown): 6 flats.
- Today they only log `DFRULE` (`tools/dungeon_converter/action_objects.zs:283-290`).
- Daggerfall owns HP and status effects, so Daggerfall applies the effect with its own formulas, and the existing HP
  sync carries the result back. A trap fires as often as Daggerfall Unity lets it.
- Related gap, not an action type: movers play one stock Doom sound, though 813 action models name a Daggerfall sound
  (`SoundIndex`).
