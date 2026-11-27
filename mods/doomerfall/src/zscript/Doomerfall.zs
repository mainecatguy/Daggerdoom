// Doomerfall event handler. Receives the actions bound in KEYCONF.
// Later tasks replace the log line in each case with a call into Daggerfall.
class Doomerfall_Events : StaticEventHandler
{
	override void OnRegister()
	{
		DDLog.Debug("Doomerfall: mod loaded");
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
		// Items leave only by Daggerfall's inventory window (d_net.cpp, DoomerfallGuns), so the drop keys are hidden.
		// The commands and bindings stay for other wads.
		HideControls('InventoryControlsMenu', 'weapdrop', 'invdrop');
		HideControls('DRLAControlsMenu', '+zoom', 'rl_specialitemdropper'); // DRLA's "Drop Item", "Remove Special Item"
	}

	static ui void HideControls(Name menu, Name a, Name b)
	{
		let d = OptionMenuDescriptor(MenuDescriptor.GetDescriptor(menu));
		for (int i = d ? d.mItems.Size() - 1 : -1; i >= 0; i--)
			if (d.mItems[i] is "OptionMenuItemControlBase" && (d.mItems[i].GetAction() == a || d.mItems[i].GetAction() == b)) d.mItems.Delete(i);
	}

	// True on a generated Daggerfall map in a bridge session. The engine sends it when the map context changes (dd_items.cpp).
	bool daggerfallRules;

	// Crouching is Daggerfall's Sneaking, and Use then acts in Daggerfall's Steal mode (dd_items.cpp).
	// The same test as the engine's, so the message shows exactly when Use would steal.
	override void RenderOverlay(RenderEvent e)
	{
		DrawDaggerfallText();
		if (!daggerfallRules || automapactive || consoleplayer < 0) return;
		let p = players[consoleplayer];
		if (p.mo == null || p.health <= 0 || p.camera != p.mo) return;
		if (!(p.cmd.buttons & BT_CROUCH) && p.crouchfactor >= 1) return;

		String text = "Sneaking";
		int scale = DoomerfallText.Scale();
		int w = SmallFont.StringWidth(text) * scale;
		int h = SmallFont.GetHeight() * scale;
		int bottom = min(StatusBar.GetTopOfStatusBar(), int(Screen.GetHeight() * 0.85));
		Screen.DrawText(SmallFont, Font.CR_GOLD, (Screen.GetWidth() - w) / 2, bottom - h * 2, text, DTA_ScaleX, scale, DTA_ScaleY, scale);
	}

	// Daggerfall's HUD text, sent by the engine (dd_info.cpp), drawn as Daggerfall Unity draws it: HUD rows centered from the
	// top of its 320x200 screen, each held a second then scrolled away (PopupText.cs), and mid-screen text centered at
	// row 146 for 1.5 seconds (DaggerfallHUD.cs). Daggerfall's yellow text with its dark shadow one pixel down and right.
	const HudPopDelay = 1.0;
	const HudMaxRows = 7;
	ui Array<String> hudRows;
	ui double hudTimer, hudNextDelay;
	ui int hudLastMs, midUntilMs;
	ui String midText;

	override void InterfaceProcess(ConsoleEvent e)
	{
		bool mid = e.Name.Left(10) == "dfhud_mid:";
		if (!mid && e.Name.Left(10) != "dfhud_top:") return;
		Array<String> lines;
		e.Name.Mid(10).Split(lines, "\n", TOK_SKIPEMPTY);
		if (mid)
		{
			if (lines.Size()) midText = lines[lines.Size() - 1];
			midUntilMs = MSTime() + 1500;
			return;
		}
		for (int i = 0; i < lines.Size(); i++)
		{
			if (hudRows.Size() == 0) hudTimer = HudPopDelay;
			else if (hudTimer >= 0) hudTimer = max(hudTimer, HudPopDelay);
			else hudNextDelay = max(hudNextDelay, HudPopDelay);
			hudRows.Push(lines[i]);
		}
	}

	ui void DrawDaggerfallLine(String text, double y, int scale)
	{
		int x = (Screen.GetWidth() - SmallFont.StringWidth(text) * scale) / 2;
		Screen.DrawText(SmallFont, Font.CR_WHITE, x + scale, y + scale, text, DTA_ScaleX, scale, DTA_ScaleY, scale, DTA_Color, Color(255, 93, 77, 12));
		Screen.DrawText(SmallFont, Font.CR_WHITE, x, y, text, DTA_ScaleX, scale, DTA_ScaleY, scale, DTA_Color, Color(255, 243, 239, 44));
	}

	ui void DrawDaggerfallText()
	{
		int now = MSTime();
		double dt = hudLastMs ? (now - hudLastMs) / 1000.0 : 0;
		hudLastMs = now;
		if (hudRows.Size())
		{
			int late = hudRows.Size() - HudMaxRows;
			hudTimer -= dt * (late > 0 ? 1 + 0.8 * late : 1);
			if (hudNextDelay <= 0) hudNextDelay = HudPopDelay;
			while (hudRows.Size() && hudTimer < -HudPopDelay)
			{
				hudTimer += hudNextDelay;
				hudRows.Delete(0);
				hudNextDelay = HudPopDelay;
			}
		}
		if (!hudRows.Size() && now >= midUntilMs) return;

		int scale = max(1, min(Screen.GetWidth() / 320, Screen.GetHeight() / 200));
		double top = (Screen.GetHeight() - 200 * scale) / 2;
		double rowHeight = SmallFont.GetHeight() + 1;
		double y = 4;
		if (hudTimer < 0) y += rowHeight * hudTimer / HudPopDelay;
		for (int i = 0; i < hudRows.Size() && i <= HudMaxRows; i++)
		{
			DrawDaggerfallLine(hudRows[i], top + y * scale, scale);
			y += rowHeight;
		}
		if (now < midUntilMs) DrawDaggerfallLine(midText, top + 146 * scale, scale);
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
			DDLog.Debug("Doomerfall: action fired: Open Fast Travel");
		}
		else if (e.Name == "df_inventory")
		{
			DDLog.Debug("Doomerfall: action fired: Open Inventory");
		}
		else if (e.Name != "df_interact" && e.Name != "df_info" && e.Name != "df_change_ammo" && e.Name != "df_journal" && e.Name != "df_rest" && e.Name != "df_character" && e.Name != "df_spellbook") // The engine handles these in a bridge session (dd_items.cpp, dd_info.cpp, dd_bridge.cpp).
		{
			DDLog.Debug(String.Format("Doomerfall: unknown action %s", e.Name));
		}
	}
}
