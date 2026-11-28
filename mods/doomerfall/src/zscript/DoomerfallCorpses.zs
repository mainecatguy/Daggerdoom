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

// A Daggerfall creature shown in Doom. UZDoom/src/dd_creatures.cpp draws it with Daggerfall's own images (args[0]: the
// mobile archive, args[1]: its Daggerfall MobileTypes value), picking idle, move, attack and hurt by its state. This
// base only stands; how a creature moves and fights is for a subclass to give. When it dies, Daggerfall's blood splash
// plays and Daggerfall's corpse takes its place.
class DFCreature : Actor
{
	Default { Monster; +DONTSPLASH Health 20; Radius 16; Height 40; }
	States
	{
	Spawn: PLAY A -1; Stop;
	Death: TNT1 A -1; Stop;
	}
}
