// Monster movement width on generated Daggerfall maps (architecture.md, World Scale and Player Size).
// Doomguy is narrowed there from radius 16 to 10.5 so he fits Daggerfall's doorways and halls. Monsters move and block
// at the same proportion of their radius, but keep their stock radius, so hitscan, projectiles, splash and melee hit
// them exactly as in stock Doom. The engine owns the rule and the one "is this a Daggerfall map" test
// (UZDoom/src/dd_monsters.cpp, AActor::MoveRadius). This class only names it for mod scripts such as the planner.
class DoomerfallBodies play
{
	// 10.5 / 16 on Daggerfall maps, otherwise 1.
	static double MonsterScale() { return Actor.DD_MonsterMoveScale(); }

	static bool OnDaggerfallMap() { return Actor.DD_OnDaggerfallMap(); }
}
