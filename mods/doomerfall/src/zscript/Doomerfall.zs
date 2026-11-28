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
	// top of its 320x200 screen scaled to fit the window, each held for the time Daggerfall gave it (a second by default)
	// and then scrolled away (PopupText.cs), and mid-screen text centered at row 146 (DaggerfallHUD.cs). Daggerfall's yellow
	// text with its dark shadow down and right, in the font Daggerfall Unity draws by default: FONT0003's smooth SDF face
	// (fonts/dffont3sdf, which the converter rasterizes into ddruntime.pk3 from Daggerfall Unity's FONT0003-SDF asset at
	// several texels per Daggerfall pixel, with its advances and baseline; Daggerfall Unity offsets that face's shadow
	// 0.4 pixel, TextLabel.DrawLabel), else the classic pixel FONT0003 (fonts/dffont3, from the player's ARENA2, shadow one
	// pixel), else Doom's SmallFont.
	// Layout: Doomerfall's compass is planned for the top centre (owner, 2026-11-26), where Daggerfall Unity starts its
	// rows. The rows keep Daggerfall Unity's spacing and motion but start HudCompassBand pixels lower, and a row scrolling
	// away is cut off at the band's bottom edge as Daggerfall Unity's are cut off by the top of the screen, so no row ever
	// draws over the compass. Doom's own pickup messages stay top left.
	const HudPopDelay = 1.0;
	const HudMaxRows = 7;
	const HudGlyphHeight = 7; // FONT0003's classic glyph height; the SDF font's height is this times its texels per pixel
	const HudCompassBand = 26; // 320x200 pixels kept clear at the top: room for Daggerfall's 69x17 compass box, and below DRLA's top HUD key bar
	ui Array<String> hudRows;
	ui double hudTimer, hudNextDelay;
	ui int hudLastMs, midUntilMs;
	ui String midText;
	ui Font hudFont;
	ui bool hudSdf;
	ui bool hudFontChecked;

	override void InterfaceProcess(ConsoleEvent e)
	{
		bool mid = e.Name.Left(10) == "dfhud_mid:";
		if (!mid && e.Name.Left(10) != "dfhud_top:") return;
		// "<ms>:<text>": how long Daggerfall holds the line, 0 for its default.
		String body = e.Name.Mid(10);
		int colon = body.IndexOf(":");
		double hold = colon > 0 ? body.Left(colon).ToInt() / 1000.0 : 0;
		if (colon >= 0) body = body.Mid(colon + 1);
		Array<String> lines;
		body.Split(lines, "\n", TOK_SKIPEMPTY);
		if (mid)
		{
			if (lines.Size()) midText = lines[lines.Size() - 1];
			midUntilMs = MSTime() + int((hold > 0 ? hold : 1.5) * 1000);
			return;
		}
		if (hold <= 0) hold = HudPopDelay;
		for (int i = 0; i < lines.Size(); i++)
		{
			if (hudRows.Size() == 0) hudTimer = hold;
			else if (hudTimer >= 0) hudTimer = max(hudTimer, hold);
			else hudNextDelay = max(hudNextDelay, hold);
			hudRows.Push(lines[i]);
		}
	}

	// scale: screen pixels per Daggerfall pixel; texels: font texels per Daggerfall pixel.
	ui void DrawDaggerfallLine(Font f, String text, double y, double scale, double texels)
	{
		double s = scale / texels;
		double x = (Screen.GetWidth() - f.StringWidth(text) * s) / 2;
		double shadow = (hudSdf ? 0.4 : 1) * scale;
		// Daggerfall's glyphs are plain white, which a translation would darken: they are tinted untranslated.
		int tr = f == SmallFont ? Font.CR_WHITE : Font.CR_UNTRANSLATED;
		Screen.DrawText(f, tr, x + shadow, y + shadow, text, DTA_ScaleX, s, DTA_ScaleY, s, DTA_Color, Color(255, 93, 77, 12));
		Screen.DrawText(f, tr, x, y, text, DTA_ScaleX, s, DTA_ScaleY, s, DTA_Color, Color(255, 243, 239, 44));
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

		if (!hudFontChecked)
		{
			hudFontChecked = true;
			hudFont = Font.GetFont("dffont3sdf");
			hudSdf = hudFont != null;
			if (!hudFont) hudFont = Font.GetFont("dffont3");
		}
		Font f = hudFont ? hudFont : SmallFont;
		double texels = hudFont ? f.GetHeight() / double(HudGlyphHeight) : 1;
		// Daggerfall Unity's native panel: 320x200 scaled to fit and centered.
		double scale = min(Screen.GetWidth() / 320.0, Screen.GetHeight() / 200.0);
		double top = (Screen.GetHeight() - 200 * scale) / 2;
		double rowHeight = f.GetHeight() / texels + 1;
		double y = 4 + HudCompassBand;
		if (hudTimer < 0) y += rowHeight * hudTimer / HudPopDelay;
		if (hudRows.Size())
		{
			int clipTop = int(top + HudCompassBand * scale);
			Screen.SetClipRect(0, clipTop, Screen.GetWidth(), Screen.GetHeight() - clipTop);
			for (int i = 0; i < hudRows.Size() && i <= HudMaxRows; i++)
			{
				DrawDaggerfallLine(f, hudRows[i], top + y * scale, scale, texels);
				y += rowHeight;
			}
			Screen.ClearClipRect();
		}
		if (now < midUntilMs) DrawDaggerfallLine(f, midText, top + 146 * scale, scale, texels);
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
		else if (e.Name != "df_interact" && e.Name != "df_info" && e.Name != "df_change_ammo" && e.Name != "df_journal" && e.Name != "df_rest" && e.Name != "df_character" && e.Name != "df_spellbook" && e.Name != "df_status" && e.Name != "df_transport" && e.Name != "df_map" && e.Name != "df_skills") // The engine handles these in a bridge session (dd_items.cpp, dd_info.cpp, dd_bridge.cpp).
		{
			DDLog.Debug(String.Format("Doomerfall: unknown action %s", e.Name));
		}
	}
}
