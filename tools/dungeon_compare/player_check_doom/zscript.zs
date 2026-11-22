version "4.10"

// Prints the real player's collision and view values. Used by player_check.py.
class DFPlayerCheck : EventHandler
{
	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(8) != "dfcheck_") return;
		let mo = players[0].mo;
		Console.Printf("DFPLAYER %s map=%s class=%s radius=%.2f height=%.2f full=%.2f view=%.2f step=%.2f crouch=%.2f", e.Name.Mid(8), level.MapName, mo.GetClassName(), mo.Radius, mo.Height, mo.FullHeight, players[0].viewheight, mo.MaxStepHeight, players[0].crouchfactor);
	}
}
