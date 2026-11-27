version "4.14"

// Steep-stairs climbing demo (demo only, no Daggerfall). On Privateer's Hold's converted map, it sends the rule and
// chance events a bridge session would send (a new character's real chances, 76/48/57/29) and puts the player at the
// foot of the cliff, facing it. Holding forward for over a second starts the climb. Not applied when a save is loaded.
class CliffDemoStart : StaticEventHandler
{
	bool done;
	override void WorldLoaded(WorldEvent e) { if (e.IsSaveGame) done = true; }
	override void WorldTick()
	{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		EventHandler.SendNetworkEvent("dfi_rules:1");
		EventHandler.SendNetworkEvent("dfi_climb:76:48:57:29:0");
		let p = players[0].mo;
		p.SetOrigin((942, -96, 384), false);
		p.angle = 180;
		p.vel = (0, 0, 0);
	}
}
