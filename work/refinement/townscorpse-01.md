# Daggerfall people and creatures die and leave corpses in Doom

Lane: `townscorpse` (new). Model: Opus. Depends on nothing.

Killing a townsperson makes them vanish. They should die with Daggerfall Unity's death animation and leave a corpse in
Doom, the way they did in Daggerfall. This breaks object permanence and total persistence today.

Owner's words (2026-11-26): "killing townspeople causes them to just disappear. They should get a corpse in doom engine.
This is where this gets a little weird - we need to import the townsperson corpse and death animations from DFU into
Doom and make them work the way they used to." Then: "Same for guards and other stuff that has a corpse and is a monster. It
needs to work right in doom." So this covers every Daggerfall entity shown in Doom that has a death animation or
corpse in Daggerfall Unity: townspeople, guards and other NPCs. Daggerfall creatures are generally replaced by Doom
monsters, but there may be exceptions, so Doom should be able to show them too (owner: "Daggerfall Creatures are
generally replaced. But there may be exceptions. I suppose, Doom should have the ability to show them.").

How the art gets to Doom (owner, 2026-11-26): "We should do this without asset ripping as we would like to maintain
compatibility with Daggerfall texture packs. It would be ideal if we can instead read Daggerfall's files directly. If
this isn't possible report back." So read the sprites from Daggerfall's own files (and texture pack replacements) at
run time rather than extracting copies; if that is not possible, stop and report why.

Done when: in a paired run, killing a townsperson, a guard and each other such entity plays Daggerfall's death
animation for it and leaves its corpse, which is still there after leaving and returning and after a save and load; Daggerfall's crime and
reputation effects still happen. The art is read from Daggerfall's files at run time (no extracted copies), and a
Daggerfall texture pack replacement for one of these sprites shows up in Doom.
