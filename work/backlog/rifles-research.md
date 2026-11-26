# Research: which rifles are in DRLA and DRLAX

**Waiting on:** owner moving it to todo. Research only.

Owner (2026-11-25): rifles probably can't share the pistol skill group ("Rifles and Pistols"), because some rifles are
very strong and the pistol perks would break the game. Pistol skill balance is tuned for DRLAX, so check what rifles
DRLAX actually has.

Find every rifle in DRLA 1.1.5 and DRLAX 1.2b (`GameMods/ExtractedData/`, read-only): name, fire mode (semi-auto,
single-shot, automatic, burst), damage per shot, fire cycle in tics, magazine, and which DRLA type tokens it carries
(`SingleShotRifle`, `RLRapidfireTypeWeapon`, others in `actors/base/ArsenalTokens.txt`). Note which come from
assemblies or DRLAX additions. Use damage per second to show which rifles would be unsafe under the pistol perks
(`skills-in-doom.md`, Rifles and Pistols). Report; don't decide the skill split.

Known so far: about 12 DRLA weapons carry `SingleShotRifle` (Marksman Rifle, High Power Marksman Rifle, Elephant Gun,
Anti-Materiel Rifle, Gauss Rifle, Railgun, Steel Beast, some assemblies). Earlier token searches found no DRLAX
weapons, possibly because DRLAX defines them differently (check ZScript and other formats). A rough per-weapon
fire-rate survey script was written in an earlier session (DECORATE only, default fire path).
