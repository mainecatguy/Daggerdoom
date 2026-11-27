# Remaining collision mismatches

**Waiting on:** the parity test update, and an owner-approved target for how close is good enough.

Angled collision was a large improvement, but on Privateer's Hold the parity test still reports 803 standing false walls and 1,282 false openings. Some straight walls have small bends where a vertex stayed on the grid.

The target question is now answered by the collision fidelity metric (`collision-fidelity-metric.md`): a change must improve it overall.
