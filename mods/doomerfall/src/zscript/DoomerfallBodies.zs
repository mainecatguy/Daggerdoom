// Monster collision width on generated Daggerfall maps (architecture.md, World Scale and Player Size).
// Doomguy is narrowed there from radius 16 to 10.5 so he fits Daggerfall's doorways and halls. Monsters get the same
// proportion: every monster's radius is its class default times 10.5 / 16. Height and everything else stay stock.
// Regular Doom maps are untouched. The encounter placer (dd_encounter_placer.cpp) and planner (EncounterBudget.zs) read
// MonsterScale() so they size spots for the bodies that will stand in them.
class DoomerfallBodies : EventHandler
{
	const PlayerRadius = 10.5;	// the player's Daggerfall-map radius (converter PlayerScale.Radius, ddruntime.pk3, overworld.pk3)
	const StockPlayerRadius = 16.0;

	// The same maps the player-width handlers narrow Doomguy on: generated locations (DDTnnnnn and DDSnnnnn, ddruntime.pk3),
	// the overworld (DDOVER01, overworld.pk3), and converted dungeons (MAP01 with the converter's DDDUNGN or DFPOINTS lump).
	static bool OnDaggerfallMap()
	{
		String map = level.MapName;
		String prefix = map.Left(3);
		if ((prefix ~== "DDT" || prefix ~== "DDS") && map.Length() == 8) return true;
		if (map.Left(6) ~== "DDOVER") return true;
		return map ~== "MAP01" && (Wads.CheckNumForName("DDDUNGN", Wads.ns_global) >= 0 || Wads.CheckNumForName("DFPOINTS", Wads.ns_global) >= 0);
	}

	// The factor applied to monster radii on the current map: 10.5 / 16 on Daggerfall maps, otherwise 1.
	static double MonsterScale()
	{
		return OnDaggerfallMap() ? PlayerRadius / StockPlayerRadius : 1.0;
	}

	// Only a body still at its class's default width is narrowed, so this is safe to repeat and leaves sizes that a mod's
	// own script chose alone. Narrowing never needs room, so it cannot fail or move anything.
	static void Narrow(Actor mo, double scale)
	{
		if (!mo || !mo.bIsMonster || mo.player || scale >= 1) return;
		double stock = mo.Default.radius;
		if (abs(mo.radius - stock) > 0.001) return;
		mo.A_SetSize(stock * scale, -1, false);
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		if (e.Thing && e.Thing.bIsMonster) Narrow(e.Thing, MonsterScale());
	}

	// Saves made before this rule, and anything spawned before the handler saw it.
	override void WorldLoaded(WorldEvent e)
	{
		double scale = MonsterScale();
		if (scale >= 1) return;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next())) if (mo.bIsMonster) Narrow(mo, scale);
	}
}
