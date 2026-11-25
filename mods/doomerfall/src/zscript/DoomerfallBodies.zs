// Monster movement width on generated Daggerfall maps (architecture.md, World Scale and Player Size).
// Doomguy is narrowed there from radius 16 to 10.5 so he fits Daggerfall's doorways and halls. Monsters keep their stock
// radius for everything (other actors, the player, open walls, and every hit test) and squeeze to the same proportion
// of it only to get through a gap in the level or past a door leaf that is narrower than they are. The engine owns the
// rule and the one "is this a Daggerfall map" test (UZDoom/src/dd_monsters.cpp, P_TryMove, AActor::SqueezeRadius).
// This class only names it for mod scripts.
class DoomerfallBodies play
{
	// The squeeze width's share of the radius: 10.5 / 16 on Daggerfall maps, otherwise 1.
	static double MonsterScale() { return Actor.DD_MonsterMoveScale(); }

	static bool OnDaggerfallMap() { return Actor.DD_OnDaggerfallMap(); }
}
