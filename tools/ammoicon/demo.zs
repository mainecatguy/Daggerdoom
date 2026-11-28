version "4.14"

// Demo only (review folder's demo.pk3, never the game): once Daggerfall's rules arrive and a gun's ammo is loaded, drops
// a Silver and a Daedric pickup of that gun's ammo type in front of the player, once per map, so the Change Ammo
// control has tiers to cycle through.
class AIDemo : EventHandler
{
	static const String TYPENAMES[] = { "Clip", "Shell", "Rocket", "Cell" };
	bool given;

	override void WorldTick()
	{
		let tiers = DoomerfallAmmoTiers.Get();
		if (given || !tiers || !tiers.rules || tiers.loadedTier < 0 || !players[consoleplayer].mo) return;
		given = true;
		let p = players[consoleplayer].mo;
		for (int i = 0; i < 2; i++)
			Actor.Spawn(String.Format("DFAmmo_%s_%d", TYPENAMES[tiers.loadedType], i == 0 ? 2 : 9), p.Vec3Angle(64, p.angle + (i == 0 ? 20 : -20)), NO_REPLACE);
	}
}
