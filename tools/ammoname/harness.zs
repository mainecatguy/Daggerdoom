version "4.10"
// Ammo name test (tools/ammoname/ammoname.py), Doom only. A new map spawns a Regular and a Silver clip in front of the
// player and prints every DFAmmo class's tag, the HUD name and the pickup message. A loaded save prints the tag and
// pickup message of each tiered pickup it holds, which shows whether pickups saved by an older mod get the new name.
class ANHarness : StaticEventHandler
{
	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame)
		{
			let it = ThinkerIterator.Create("DoomerfallAmmoPickup");
			DoomerfallAmmoPickup p;
			int n = 0;
			while (p = DoomerfallAmmoPickup(it.Next()))
			{
				Console.Printf("ANLOAD class=%s tag=%s message=%s", p.GetClassName(), p.GetTag(), p.PickupMessage());
				n++;
			}
			Console.Printf("ANLOAD count=%d", n);
			return;
		}
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		for (int type = 0; type < 4; type++)
			for (int tier = 0; tier < 10; tier++)
			{
				class<Actor> cls = String.Format("DFAmmo_%s_%d", TypeNames[type], tier);
				Console.Printf("ANTAG type=%d tier=%d tag=%s hud=%s", type, tier, GetDefaultByType(cls).GetTag(), /*NEW*/DoomerfallAmmoTiers.AmmoName(type, tier)/*NEW*/);
			}
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		Vector3 ahead = pmo.Vec3Angle(128, pmo.angle);
		for (int i = 0; i < 2; i++)
		{
			let p = DoomerfallAmmoPickup(Actor.Spawn(i == 0 ? "DFAmmo_Clip_0" : "DFAmmo_Clip_2", ahead + (0, i * 32 - 16, 0)));
			if (p) Console.Printf("ANSPAWN class=%s tag=%s message=%s", p.GetClassName(), p.GetTag(), p.PickupMessage());
		}
	}
}
