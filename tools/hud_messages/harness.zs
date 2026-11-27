version "4.14"

// HUD message shots (hud_messages.py). Keeps the player safe and still so the screenshots show only the messages, and
// logs each Daggerfall HUD line Doom receives with the time it arrived.
class HMHarness : StaticEventHandler
{
	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		players[0].mo.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
	}

	override void InterfaceProcess(ConsoleEvent e)
	{
		if (e.Name.Left(6) == "dfhud_") Console.PrintfEx(PRINT_LOG, "HM %d %s", MSTime(), e.Name);
	}
}
