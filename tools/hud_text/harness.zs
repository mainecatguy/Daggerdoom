version "4.14"

// HUD text size shots. Prints HTREADY once Daggerfall is in the game and the loaded-ammo label has had time to arrive.
// hud_text.py then draws the test pistol Daggerfall's -dfchangeammotest put on key 4 (so the loaded ammo label shows),
// holds crouch through the QA channel (so "Sneaking" shows), sends 'netevent htpickup' (a stock
// Stimpack at the player's feet, so Doom's own pickup message shows), and takes a screenshot.
class HTHarness : StaticEventHandler
{
	bool ready;

	override void WorldTick()
	{
		if (ready || !playeringame[0] || !players[0].mo) return;
		players[0].mo.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		let phase = CVar.FindCVar("dd_sync_df_phase");
		if (level.maptime < 35 * 6 || !phase || phase.GetInt() != 3) return;
		ready = true;
		Console.PrintfEx(PRINT_LOG, "HTREADY");
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name != "htpickup" || !players[0].mo) return;
		let p = players[0].mo;
		p.health = p.player.health = 50;
		let item = Actor.Spawn("Stimpack", p.pos + (Actor.AngleToVector(p.angle, 24), 0));
		p.vel.xy = Actor.AngleToVector(p.angle, 4);
		Console.PrintfEx(PRINT_LOG, "HTPICKUP %s", item ? item.GetClassName() : 'none');
	}
}
