// Test-only (tools/tween_menu): presses the tween menu's key for the test driver. Posted key messages reach Doom only
// while a menu is open, so this runs Doom's real togglemap command (bound to Tab) whenever the game has run for
// 3 seconds with no menu open, once Daggerfall has a character: the first time, and again after each window closes.
// It logs Doom's screen size for the driver's clicks, and how many times play resumed.
class TweenTest_Events : StaticEventHandler
{
	ui int lastMaptime, runningSince, presses;
	ui bool wasOpen;

	override void UiTick()
	{
		if (level == null || gamestate != GS_LEVEL) return;
		bool open = Menu.GetCurrentMenu() != null;
		if (open != wasOpen && open) Console.Printf("TWEENTEST menu %s screen %dx%d", Menu.GetCurrentMenu().GetClassName(), Screen.GetWidth(), Screen.GetHeight());
		wasOpen = open;
		if (open || level.maptime == lastMaptime)
		{
			runningSince = -1;
			lastMaptime = level.maptime;
			return;
		}
		lastMaptime = level.maptime;
		if (runningSince < 0)
		{
			runningSince = level.maptime;
			if (presses > 0) Console.Printf("TWEENTEST doom resumed %d", presses);
		}
		if (Actor.DD_SheetValue(2) != 1 || level.maptime - runningSince < 105 || presses >= 8) return;
		presses++;
		runningSince = level.maptime;
		Console.Printf("TWEENTEST press %d", presses);
		Menu.SetMenu('TweenTestKey');
	}
}

// Runs togglemap from menu code, the only place a ZScript may run a console command, and closes at once.
class TweenTestKey : GenericMenu
{
	override void Drawer() // Not Ticker: the engine lets only menu event and draw calls run commands.
	{
		Close();
		let run = new("OptionMenuItemSafeCommand");
		run.Init("", "togglemap");
		run.MenuEvent(MKEY_MBYes, false);
	}
}
