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

// Test-only: prints the live labels of the main controls list and our submenu.
class DoomerfallSmoke_Menus : StaticEventHandler
{
	override void UiTick()
	{
		if (done || level == null || level.maptime < 40) return;
		done = true;
		DumpMenu('CustomizeControls');
		DumpMenu('DoomerfallControlsMenu');
	}
	ui bool done;

	ui void DumpMenu(Name n)
	{
		let d = OptionMenuDescriptor(MenuDescriptor.GetDescriptor(n));
		if (d == null) { Console.Printf("MENUDUMP %s: none", n); return; }
		for (int i = 0; i < d.mItems.Size(); i++)
		{
			let it = d.mItems[i];
			String keys = "";
			let ctl = OptionMenuItemControlBase(it);
			if (ctl != null)
			{
				int k1, k2, unused;
				Name cmd;
				[cmd, unused] = ctl.GetAction();
				[k1, k2] = ctl.mBindings.GetKeysForCommand(cmd);
				keys = String.Format(" {%s} keys=%s", cmd,KeyBindings.NameKeys(k1, k2, false));
			}
			Console.Printf("MENUDUMP %s: %d [%s] %s%s", n, i, it.GetClassName(), OptionMenuItem(it) ? OptionMenuItem(it).mLabel : "", keys);
		}
	}
}
