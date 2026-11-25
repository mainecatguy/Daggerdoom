The verification is finished and its PASS stands. You are no longer the verifier. You are now a reviewer for the owner, using the reading you already did. Nothing you report here changes the PASS or sends the work back. It only tells the owner what to look at before merging.

List, in `owner_flags`, only these:

1. **Major architecture problems this change introduces.** For example: state owned in the wrong engine, a second copy of state, duplicating a system that already exists, going around the bridge contract, or a design that will be hard to undo. Subjective concerns are welcome here, if they are major.
2. **Specific performance risks.** Name the code path, why it runs often or at scale (every tic, per actor, per sector, every save), and the problem the player could see (a hitch, a freeze, a lower frame rate).

Anything you noticed during verification but set aside because it was not a reason to fail belongs here, if it fits one of the two kinds above.

Each flag is one self-contained item: what is wrong, the file and line, what it could cause, and your confidence. Skip style, small issues, and optional improvements. If there is nothing major, return an empty `owner_flags`. An empty list is a normal result.

Set `verdict` to `PASS` and `problems` to an empty string. Use only your existing reading and Read, Grep and Glob if you must check something. Do not change any file.
