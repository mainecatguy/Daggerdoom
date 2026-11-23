// Test-only helper: fires the Doomerfall actions as if bound keys were pressed, then reports.
class DoomerfallSmoke_Events : StaticEventHandler
{
	override void WorldTick()
	{
		if (level.maptime == 70)
		{
			EventHandler.SendNetworkEvent("df_fast_travel");
			EventHandler.SendNetworkEvent("df_inventory");
		}
		if (level.maptime == 80) Console.Printf("DoomerfallSmoke: done");
	}
}
