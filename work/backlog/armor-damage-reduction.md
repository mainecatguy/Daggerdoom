# Armor as damage reduction (card ready)

Waiting on: the owner moving it to todo (owner, 2026-11-27: "write cards to get it in the backlog"). After
`noshields` 01.

Daggerfall armor has no effect in bridged play today. Doomerfall reads each body part's live armor from Daggerfall and
applies it as damage reduction on physical hits. Formula and table approved (owner, 2026-11-27: "Very good let's run
with this proposal for damage"): `work/notes/20261127-armor-dr-table.md`.

- A = live armor points, body-part weighted (Leather 15 to Daedric 105). L = area level.
- Armor DR = D(L) x (A / 105)^p(L). D(L): Daedric 80% at L1, 78% at L5, 76.5% at L15, 75% at L25, 72% at L30, linear
  between. p(L) = 0.35 + 0.055 x L (cheap armor strong at low levels, near useless at high).
- Physical hits only. Total damage taken = (1 - armor DR) x (1 - physical resistance) x Willpower factor, all
  multiplicative (owner: "MULTIPLICATIVE not ADDITIVE"; "This is an RPG, being able to break the game a little is fun").
- Wear: every physical hit wears armor at 1/30 of Daggerfall's rate, on one part chosen by hit weight, fractions carried;
  a broken piece stops counting.
- Carry fractional damage so small hits average out.

Done when: a test shows armor DR matching the table for several sets at several area levels, physical hits reduced and
others not, wear at the expected rate; a paired run shows armor working. Manual: a short Armor entry.
