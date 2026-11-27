# Commit the Doomerfall pk3

Lane: `commitpk3` (new). Model: Opus. Depends on nothing.

Owner (2026-11-27): "we should be similarly committing our own pk3 we're making for Doomerfall." The built Doomerfall
mod (`doomerfall.pk3`, built from `mods/doomerfall/src`) is committed to git and kept current, so a checkout or a
distributed build has it without building it first.

Done when: the pk3 is committed in a sensible place, the build step that makes it updates the committed copy, and the
notes say how to keep it in step with `mods/doomerfall/src` (for example a check that fails when they differ).
