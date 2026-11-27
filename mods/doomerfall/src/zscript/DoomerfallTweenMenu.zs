// The Tab menu: Skyrim's tween menu (skyrimui/tweenmenu.swf, converted at pk3 build time), whose four choices open
// Daggerfall's windows. In a Daggerfall area of a paired game the engine opens it for Doom's Automap control (Tab)
// (UZDoom/src/dd_bridge.cpp, DD_BridgeToggleMap). A choice runs the same command as its own control, so the bridge
// opens the window as it does for that key; Doom stays paused until the window closes.
// Arrow keys or WASD pick a direction, and the same direction again, Enter, or a click opens it. Tab or Escape closes.
// This file holds the behaviour the SWF's ActionScript had; the drawing is DDSwfMovie's.

class DoomerfallTweenMenu : GenericMenu
{
	enum EChoice { None = -1, Skills, Magic, Items, Map, NumChoices }

	DDSwfMovie movie;
	int selected;
	bool closing;
	int openFrom, openTo, closeFrom, closeTo;

	static const String Labels[] = { "Skills", "Magic", "Inventory", "Map" };
	static const String HitRects[] = { "SkillsInputRect", "MagicInputRect", "ItemsInputRect", "MapInputRect" };
	static const String Commands[] = { "netevent df_character", "netevent df_spellbook", "netevent df_inventory", "netevent df_map" };

	override void Init(Menu parent)
	{
		Super.Init(parent);
		DontDim = true;
		selected = None;
		movie = DDSwfMovie.Load("tweenmenu");
		if (!movie)
		{
			DDLog.Debug("Doomerfall: tween menu resources missing");
			return;
		}
		// TweenMenu.as: showMenu plays the expand, the bottom bar slides in, and nothing is selected.
		openFrom = movie.LabelFrame(movie.root, "startExpand");
		closeFrom = movie.LabelFrame(movie.root, "endExpand");
		openTo = closeFrom - 1;
		closeTo = movie.GetSprite(movie.root).frameCount - 1;
		movie.PlayFrames("", openFrom, openTo);
		movie.PlayFrames("BottomBarTweener_mc", 1, 9);
		movie.GotoFrame("Selections_mc", 0);
		// Daggerfall's world clock is not shown here yet, and Doom has no level progress to show.
		movie.SetHidden("DateText");
		movie.SetHidden("LevelProgressBar");
		int level = Actor.DD_SheetValue(3); // DFB_SHEET_LEVEL
		movie.SetText("LevelNumberLabel", level > 0 ? String.Format("%d", level) : "");
		DDLog.Debug("Doomerfall: tween menu opened");
	}

	override void Drawer()
	{
		if (!movie)
		{
			Close();
			return;
		}
		if (closing && !movie.Playing())
		{
			Close();
			return;
		}
		Screen.Dim(0, 0.35, 0, 0, Screen.GetWidth(), Screen.GetHeight());
		movie.Draw();
		Super.Drawer();
	}

	void Select(int choice)
	{
		if (choice == selected || !movie) return;
		selected = choice;
		// Selections_mc's frames are labelled with the choices' names.
		int f = choice == None ? 0 : movie.LabelFrame(SelectionsSprite(), Labels[choice]);
		movie.GotoFrame("Selections_mc", max(f, 0));
		MenuSound("menu/cursor");
	}

	int SelectionsSprite()
	{
		let s = movie.GetSprite(movie.root);
		for (int i = 0; i < s.places.Size(); i++) if (s.places[i].name == "Selections_mc") return s.places[i].chr;
		return -1;
	}

	void Choose(int choice)
	{
		if (choice == None || closing) return;
		DDLog.Debug(String.Format("Doomerfall: tween menu chose %s", Labels[choice]));
		Close();
		// Menus may run console commands only from a command item (OptionMenuItemCommand.DoCommand is private);
		// the safe item runs its command when its confirmation is answered yes, which is done here directly.
		let run = new("OptionMenuItemSafeCommand");
		run.Init("", Commands[choice]);
		run.MenuEvent(MKEY_MBYes, false);
	}

	void StartClose()
	{
		if (closing || !movie) return;
		closing = true;
		DDLog.Debug("Doomerfall: tween menu closed");
		movie.PlayFrames("", closeFrom, closeTo);
		movie.PlayFrames("BottomBarTweener_mc", 10, 18);
		MenuSound("menu/backup");
	}

	int Direction(int mkey)
	{
		if (mkey == MKEY_Up) return Skills;
		if (mkey == MKEY_Left) return Magic;
		if (mkey == MKEY_Right) return Items;
		if (mkey == MKEY_Down) return Map;
		return None;
	}

	override bool MenuEvent(int mkey, bool fromcontroller)
	{
		int dir = Direction(mkey);
		if (dir != None)
		{
			if (dir == selected) Choose(dir);
			else Select(dir);
			return true;
		}
		if (mkey == MKEY_Enter)
		{
			Choose(selected);
			return true;
		}
		if (mkey == MKEY_Back)
		{
			StartClose();
			return true;
		}
		return false;
	}

	override bool OnUIEvent(UIEvent ev)
	{
		if (closing) return true;
		if (ev.Type == UIEvent.Type_KeyDown)
		{
			int ch = ev.KeyChar;
			if (ch == UIEvent.Key_Tab) StartClose();
			else if (ch == 0x77 || ch == 0x57) MenuEvent(MKEY_Up, false);     // W
			else if (ch == 0x61 || ch == 0x41) MenuEvent(MKEY_Left, false);   // A
			else if (ch == 0x73 || ch == 0x53) MenuEvent(MKEY_Down, false);   // S
			else if (ch == 0x64 || ch == 0x44) MenuEvent(MKEY_Right, false);  // D
			else if (ch == 0x65 || ch == 0x45) MenuEvent(MKEY_Enter, false);  // E, Doom's default Use key
			return true;
		}
		if (ev.Type == UIEvent.Type_MouseMove || ev.Type == UIEvent.Type_LButtonDown || ev.Type == UIEvent.Type_LButtonUp)
		{
			int hit = HitTest(ev.MouseX, ev.MouseY);
			if (hit != None) Select(hit);
			// On release, so the window that opens never gets half a click.
			if (ev.Type == UIEvent.Type_LButtonUp && hit != None) Choose(hit);
			return true;
		}
		return Super.OnUIEvent(ev);
	}

	int HitTest(int mx, int my)
	{
		if (!movie) return None;
		for (int i = 0; i < NumChoices; i++)
		{
			bool shown;
			double x0, y0, x1, y1;
			[shown, x0, y0, x1, y1] = movie.InstanceRect(HitRects[i]);
			if (shown && mx >= x0 && mx < x1 && my >= y0 && my < y1) return i;
		}
		return None;
	}
}
