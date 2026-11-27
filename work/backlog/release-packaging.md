# Make a release: package everything

Waiting on: the initial release (owner, 2026-11-27: "let's backlog it for initial release along with installation
guide"). Card ready; goes with `player-install-guide`.

Owner (2026-11-27), replacing the idea of committing the built pk3: "what we would want really is to have the ability
to create a release item and part of that process of creating a release item is then packaging everything including
the PK3 ... like a release item for everything."

One command that makes a release: builds and collects everything Doomerfall ships (the Doomerfall pk3s, UZDoom, the
Daggerfall Unity build, the launcher, the converter, bundled resources such as the Tab menu art, and the play scripts)
into one versioned release folder or archive, ready to hand to a player. Game data and third-party Doom mods the player
installs themselves are not included (see the deferred player installation guide). `scripts/play/install.py`, which
already assembles a play folder, is a natural starting point.

Done when: running the command on a clean checkout produces a versioned release; unpacking it beside Daggerfall's data,
the IWAD and the Doom mods starts the game; the notes list what the release contains and how to make the next one.
