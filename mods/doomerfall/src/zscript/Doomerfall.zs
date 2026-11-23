// Doomerfall event handler. Receives the actions bound in KEYCONF.
// Later tasks replace the log line in each case with a call into Daggerfall.
class Doomerfall_Events : StaticEventHandler
{
	override void OnRegister()
	{
		Console.Printf("Doomerfall: mod loaded");
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		// Only handle our own events; DRLA and others use different names.
		if (e.Name.Left(3) != "df_") return;

		if (e.Name == "df_fast_travel")
		{
			Console.Printf("Doomerfall: action fired: Open Fast Travel");
		}
		else if (e.Name == "df_inventory")
		{
			Console.Printf("Doomerfall: action fired: Open Inventory");
		}
		else
		{
			Console.Printf("Doomerfall: unknown action %s", e.Name);
		}
	}
}
