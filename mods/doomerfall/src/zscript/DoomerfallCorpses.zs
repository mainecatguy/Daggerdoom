// The corpse a Daggerfall person (townsperson, guard) leaves, and Daggerfall's blood splash at their death.
// UZDoom/src/dd_townsfolk.cpp places them and draws them with Daggerfall's own images; Daggerfall keeps the corpses.
// Both are inert scenery. They stay hidden until they have an image.
class DFCorpse : Actor
{
	Default { +NOINTERACTION +NOBLOCKMAP +NOGRAVITY +DONTSPLASH +NOTONAUTOMAP +INVISIBLE Radius 1; Height 1; }
	States { Spawn: PLAY A -1; Stop; }
}

class DFBloodSplash : Actor
{
	Default { +NOINTERACTION +NOBLOCKMAP +NOGRAVITY +DONTSPLASH +NOTONAUTOMAP +INVISIBLE Radius 1; Height 1; }
	States { Spawn: PLAY A -1; Stop; }
}
