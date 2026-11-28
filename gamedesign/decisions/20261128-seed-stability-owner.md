## 2026-11-28: Seeded results may change between versions until release

- **Verdict:** Owner decided.
- **Answer:** Everything seeded must use a fixed seed, so entering and leaving the same area in any playthrough of the
  same version gives the same items and placement. Between versions that contract may break (for example when
  geometry or the route graph changes and pickups move) until the game is released. Keeping seeded results stable
  across versions is a post-release item; the project is pre-alpha.
- **Settles:** `collisionshape` 01's route fix may change the default 12-unit output (875 pickups moved on 23 maps).
  Future cards need not keep converter or loot output byte-identical across versions, but must stay deterministic
  within a version.
- **Owner's words:** "Changing the result of the deterministic seed during development is acceptable. When geometry
  changes, it's not crazy for that to change. The seed being stable is a post-release item." "things SHOULD and MUST be
  programmed using a fixed seed such that entering and leaving the same area in any playthrough in THAT VERSION gets the
  same items, but BETWEEN VERSIONS that contract is allowed to break until we are POST RELEASE".
