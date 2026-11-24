// Doomerfall event handler. Receives the actions bound in KEYCONF.
// Later tasks replace the log line in each case with a call into Daggerfall.
class Doomerfall_Events : StaticEventHandler
{
	override void OnRegister()
	{
		Console.Printf("Doomerfall: mod loaded");
	}

	ui bool menuDone;

	// Put "Doomerfall Controls" right after the last submenu entry of the Controls menu.
	override void UiTick()
	{
		if (menuDone) return;
		let d = OptionMenuDescriptor(MenuDescriptor.GetDescriptor('CustomizeControls'));
		if (d == null) return;
		menuDone = true;
		int at = -1;
		for (int i = 0; i < d.mItems.Size(); i++)
		{
			let it = d.mItems[i];
			if (it.GetClassName() == "OptionMenuItemSubmenu") at = i + 1;
		}
		if (at < 0) at = d.mItems.Size();
		let item = new("OptionMenuItemSubmenu").Init("Doomerfall Controls", 'DoomerfallControlsMenu');
		d.mItems.Insert(at, item);
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
		else if (e.Name != "df_interact") // The engine handles Interact in a bridge session (dd_items.cpp).
		{
			Console.Printf("Doomerfall: unknown action %s", e.Name);
		}
	}
}
