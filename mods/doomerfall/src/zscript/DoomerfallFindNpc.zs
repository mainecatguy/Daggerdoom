// Debug find-NPC (dd_dev only): the text box and the pick list. The engine does the rest (UZDoom/src/dd_findnpc.cpp):
// it opens this menu for `dd_findnpc` with no name, sends the typed name to Daggerfall, draws the marker, and sends
// "dffind:clear", "dffind:item:<label>" (one per match), "dffind:list", "dffind:done" and "dffind:none" here.
// This menu sends "ddfind:<name>" and "ddfindpick:<n>" back as network events.
class DoomerfallFindNpcEvents : StaticEventHandler
{
	ui Array<String> labels;
	ui bool listReady, answered;

	override void InterfaceProcess(ConsoleEvent e)
	{
		if (e.Name.Left(7) != "dffind:") return;
		String what = e.Name.Mid(7);
		if (what == "clear") { labels.Clear(); listReady = false; }
		else if (what.Left(5) == "item:") labels.Push(what.Mid(5));
		else if (what == "list") listReady = true;
		else if (what == "done" || what == "none") answered = true;
	}
}

class DoomerfallFindNpcMenu : GenericMenu
{
	DoomerfallFindNpcEvents events;
	TextEnterMenu entry;
	bool waiting;
	int selected, top;

	override void Init(Menu parent)
	{
		Super.Init(parent);
		events = DoomerfallFindNpcEvents(StaticEventHandler.Find("DoomerfallFindNpcEvents"));
		if (events && events.listReady) return; // the engine opened this to pick from a list
		if (events) { events.answered = false; events.labels.Clear(); }
		wantEntry = true; // opened on the first tick: this menu is activated after Init, which would bury it
	}

	bool wantEntry;

	override bool MenuEvent(int mkey, bool fromcontroller)
	{
		if (mkey == MKEY_Input && entry)
		{
			String name = entry.GetText();
			entry = null;
			if (name.Length() == 0) { Close(); return true; }
			waiting = true;
			EventHandler.SendNetworkEvent("ddfind:" .. name);
			return true;
		}
		if (mkey == MKEY_Abort && entry) { entry = null; Close(); return true; }
		if (!events || !events.listReady) return Super.MenuEvent(mkey, fromcontroller);
		int count = events.labels.Size();
		if (mkey == MKEY_Up) { selected = (selected + count - 1) % count; MenuSound("menu/cursor"); return true; }
		if (mkey == MKEY_Down) { selected = (selected + 1) % count; MenuSound("menu/cursor"); return true; }
		if (mkey == MKEY_Enter) { Pick(selected); return true; }
		if (mkey == MKEY_Back) { events.listReady = false; Close(); return true; }
		return Super.MenuEvent(mkey, fromcontroller);
	}

	void Pick(int index)
	{
		EventHandler.SendNetworkEvent("ddfindpick:" .. index);
		events.listReady = false;
		MenuSound("menu/choose");
		Close();
	}

	override bool MouseEvent(int type, int x, int y)
	{
		if (!events || !events.listReady) return Super.MouseEvent(type, x, y);
		int row = RowAt(y);
		if (row >= 0 && row < events.labels.Size())
		{
			selected = row;
			if (type == MOUSE_Release) Pick(row);
			return true;
		}
		return Super.MouseEvent(type, x, y);
	}

	int Scale() { return max(1, Screen.GetHeight() / 360); }
	int LineHeight() { return NewSmallFont.GetHeight() * Scale() + 2 * Scale(); }
	int ListTop() { return Screen.GetHeight() / 5 + 2 * LineHeight(); }
	int RowAt(int y) { int r = (y - ListTop()) / LineHeight(); return y < ListTop() ? -1 : r + top; }

	override void Ticker()
	{
		Super.Ticker();
		if (wantEntry)
		{
			wantEntry = false;
			entry = TextEnterMenu.OpenTextEnter(self, NewSmallFont, "", -1, false);
			entry.ActivateMenu();
			return;
		}
		if (waiting && events && (events.answered || events.listReady))
		{
			waiting = false;
			if (!events.listReady) Close();
		}
	}

	override void Drawer()
	{
		int s = Scale();
		int x = Screen.GetWidth() / 6, y = Screen.GetHeight() / 5;
		Screen.Dim(0, 0.6, 0, 0, Screen.GetWidth(), Screen.GetHeight());
		if (events && events.listReady)
		{
			Screen.DrawText(NewSmallFont, Font.CR_GOLD, x, y, "Find NPC: pick one (Enter), Esc to cancel", DTA_ScaleX, s, DTA_ScaleY, s);
			int rows = max(1, (Screen.GetHeight() - ListTop()) / LineHeight() - 1);
			if (selected < top) top = selected;
			if (selected >= top + rows) top = selected - rows + 1;
			for (int i = top; i < events.labels.Size() && i < top + rows; i++)
				Screen.DrawText(NewSmallFont, i == selected ? Font.CR_WHITE : Font.CR_GRAY, x, ListTop() + (i - top) * LineHeight(), events.labels[i], DTA_ScaleX, s, DTA_ScaleY, s);
			return;
		}
		Screen.DrawText(NewSmallFont, Font.CR_GOLD, x, y, "Find NPC: type a name (full or partial), Enter to search", DTA_ScaleX, s, DTA_ScaleY, s);
		String text = entry ? entry.GetText() .. NewSmallFont.GetCursor() : waiting ? "Searching..." : "";
		Screen.DrawText(NewSmallFont, Font.CR_WHITE, x, y + 2 * LineHeight(), text, DTA_ScaleX, s, DTA_ScaleY, s);
	}
}
