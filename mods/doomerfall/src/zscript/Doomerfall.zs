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

	// True on a generated Daggerfall map in a bridge session. The engine sends it when the map context changes (dd_items.cpp).
	bool daggerfallRules;

	// Crouching is Daggerfall's Sneaking, and Use then acts in Daggerfall's Steal mode (dd_items.cpp).
	// The same test as the engine's, so the message shows exactly when Use would steal.
	override void RenderOverlay(RenderEvent e)
	{
		if (!daggerfallRules || automapactive || consoleplayer < 0) return;
		let p = players[consoleplayer];
		if (p.mo == null || p.health <= 0 || p.camera != p.mo) return;
		if (!(p.cmd.buttons & BT_CROUCH) && p.crouchfactor >= 1) return;

		String text = "Sneaking";
		int scale = max(1, CleanXfac_1);
		int w = SmallFont.StringWidth(text) * scale;
		int h = SmallFont.GetHeight() * scale;
		int bottom = min(StatusBar.GetTopOfStatusBar(), int(Screen.GetHeight() * 0.85));
		Screen.DrawText(SmallFont, Font.CR_GOLD, (Screen.GetWidth() - w) / 2, bottom - h * 2, text, DTA_ScaleX, scale, DTA_ScaleY, scale);
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) == "dfi_rules:")
		{
			daggerfallRules = e.Name.Mid(10) == "1";
			return;
		}
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
