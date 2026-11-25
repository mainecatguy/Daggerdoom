// Doomerfall diagnostics. They always reach stdout and the -logfile/+logfile log, which tests read, and reach the console
// and the on-screen messages only with dd_debugmessages on (launch with +dd_debugmessages 1). Same rule as the engine's
// DD_DebugPrintf (UZDoom/src/playsim/dd_log.h), so a normal launch shows the player only messages meant for the player.
class DDLog
{
	clearscope static void Debug(String msg)
	{
		let on = CVar.FindCVar("dd_debugmessages");
		int level = (on && on.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE;
		Console.PrintfEx(level, "%s", msg);
	}
}
