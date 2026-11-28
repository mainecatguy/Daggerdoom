// Debug find-NPC (dd_dev only): the text box and the pick list. The engine does the rest (UZDoom/src/dd_findnpc.cpp):
// it opens this menu for `dd_findnpc` with no name, sends the typed name to Daggerfall, draws the marker, and sends
// "dffind:clear", "dffind:item:<label>" (one per match), "dffind:list", "dffind:done" and "dffind:none" here.
// This menu sends "ddfindlist:<text>" (the live list: empty lists the active quests' NPCs, typing filters it and then
// everyone), "ddfind:<name>" and "ddfindpick:<n>" back as network events.
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
	const FilterDelay = 180; // ms after the last key before the list is asked for again

	DoomerfallFindNpcEvents events;
	TextEnterMenu entry;
	bool wantEntry, waiting, focusList, focusWhenReady;
	int selected, top;
	String sentText, lastText;
	int changedAt, openedAt;
	bool sentOnce, opening;

	override void Init(Menu parent)
	{
		Super.Init(parent);
		events = DoomerfallFindNpcEvents(StaticEventHandler.Find("DoomerfallFindNpcEvents"));
		if (events && events.listReady) { focusList = true; return; } // the engine opened this to pick from a list
		if (events) { events.answered = false; events.listReady = false; events.labels.Clear(); }
		// Opens on the list of the active quests' NPCs (arrows, Enter, mouse); typing a letter opens the text box with it.
		// Doom's text box ignores Enter while empty, so the list cannot be reached from an empty box.
		focusList = true;
		opening = true;
		openedAt = MSTime();
		AskList("");
	}

	override bool OnUIEvent(UIEvent ev)
	{
		// The key that opened this menu may still send its character: ignore characters for a moment after opening.
		if (!entry && ev.Type == UIEvent.Type_Char && ev.KeyChar > 32 && MSTime() - openedAt > 250)
		{
			OpenEntry(String.Format("%c", ev.KeyChar));
			return true;
		}
		return Super.OnUIEvent(ev);
	}

	void OpenEntry(String text)
	{
		focusList = false;
		opening = false;
		entry = TextEnterMenu.OpenTextEnter(self, NewSmallFont, text, -1, false);
		entry.ActivateMenu();
	}

	void AskList(String text)
	{
		sentText = text;
		sentOnce = true;
		if (events) events.listReady = false; // until this answer: Enter must not pick from the old list
		EventHandler.SendNetworkEvent("ddfindlist:" .. text);
	}

	bool HaveList() { return events && events.listReady && events.labels.Size() > 0; }

	override bool MenuEvent(int mkey, bool fromcontroller)
	{
		if (mkey == MKEY_Input && entry)
		{
			String name = entry.GetText();
			entry = null;
			if (name != sentText) AskList(name);
			if (events && !events.listReady) { focusWhenReady = true; return true; } // pick from the list it gets
			if (HaveList() && events.labels.Size() == 1 && name.Length() > 0) { Pick(0); return true; }
			if (HaveList()) { focusList = true; selected = 0; return true; }
			if (name.Length() == 0) { Close(); return true; }
			waiting = true; // nothing listed: search as typed, which says "no one by that name"
			EventHandler.SendNetworkEvent("ddfind:" .. name);
			return true;
		}
		if (mkey == MKEY_Abort && entry) { entry = null; Close(); return true; }
		if (!focusList || !HaveList()) return Super.MenuEvent(mkey, fromcontroller);
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
		if (!focusList || !HaveList()) return Super.MouseEvent(type, x, y);
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
	int ListTop() { return Screen.GetHeight() / 5 + 4 * LineHeight(); }
	int RowAt(int y) { int r = (y - ListTop()) / LineHeight(); return y < ListTop() ? -1 : r + top; }

	override void Ticker()
	{
		Super.Ticker();
		if (opening && events && events.listReady)
		{
			opening = false;
			if (events.labels.Size() == 0) wantEntry = true; // no quest names anyone: straight to typing
		}
		if (wantEntry)
		{
			wantEntry = false; // opened from the ticker: this menu is activated after Init, which would bury it
			OpenEntry("");
			return;
		}
		if (focusWhenReady && events && events.listReady)
		{
			focusWhenReady = false;
			if (events.labels.Size() == 1 && sentText.Length() > 0) Pick(0);
			else if (events.labels.Size() > 0) { focusList = true; selected = 0; }
			else if (sentText.Length() > 0) { waiting = true; EventHandler.SendNetworkEvent("ddfind:" .. sentText); }
			else Close();
		}
		if (waiting && events && (events.answered || (events.listReady && !focusList)))
		{
			waiting = false;
			if (!events.listReady) Close();
			else focusList = true;
		}
	}

	// Live filtering: ask again once typing pauses. From the drawer, which the text box calls each frame; this menu's
	// ticker does not run while the text box is open.
	void Filter()
	{
		if (!entry || !sentOnce) return;
		String text = entry.GetText();
		int now = MSTime();
		if (text != lastText) { lastText = text; changedAt = now; }
		if (text != sentText && now - changedAt >= FilterDelay) AskList(text);
	}

	override void Drawer()
	{
		Filter();
		int s = Scale();
		int x = Screen.GetWidth() / 6, y = Screen.GetHeight() / 5;
		Screen.Dim(0, 0.6, 0, 0, Screen.GetWidth(), Screen.GetHeight());
		String title = focusList ? "Find NPC: pick one (arrows + Enter, or click), or type part of a name; Esc to cancel"
			: "Find NPC: type part of a name to filter, Enter to pick from the list";
		Screen.DrawText(NewSmallFont, Font.CR_GOLD, x, y, title, DTA_ScaleX, s, DTA_ScaleY, s);
		if (!focusList)
		{
			String text = entry ? entry.GetText() .. NewSmallFont.GetCursor() : waiting || focusWhenReady ? "Searching..." : "";
			Screen.DrawText(NewSmallFont, Font.CR_WHITE, x, y + 2 * LineHeight(), text, DTA_ScaleX, s, DTA_ScaleY, s);
		}
		if (!events) return;
		if (!events.listReady || events.labels.Size() == 0)
		{
			String note = !events.listReady ? "" : sentText.Length() == 0 ? "(no active quest names anyone; type a name)" : "(no matches)";
			Screen.DrawText(NewSmallFont, Font.CR_DARKGRAY, x, ListTop(), note, DTA_ScaleX, s, DTA_ScaleY, s);
			return;
		}
		if (!focusList && sentText.Length() == 0)
			Screen.DrawText(NewSmallFont, Font.CR_DARKGRAY, x, ListTop() - LineHeight(), "Your active quests name:", DTA_ScaleX, s, DTA_ScaleY, s);
		int rows = max(1, (Screen.GetHeight() - ListTop()) / LineHeight() - 1);
		if (selected < top) top = selected;
		if (selected >= top + rows) top = selected - rows + 1;
		for (int i = top; i < events.labels.Size() && i < top + rows; i++)
		{
			int colour = focusList ? (i == selected ? Font.CR_WHITE : Font.CR_GRAY) : Font.CR_GRAY;
			Screen.DrawText(NewSmallFont, colour, x, ListTop() + (i - top) * LineHeight(), events.labels[i], DTA_ScaleX, s, DTA_ScaleY, s);
		}
	}
}
