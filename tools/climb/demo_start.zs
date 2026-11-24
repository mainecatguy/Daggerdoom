// Climbing demo start (demo only). Puts the player in town against the front wall of a general store, the wall
// the paired probe climbed onto the roof (probe-run2). Holding forward for over a second starts the climb.
// Not applied when a save is loaded.
class ClimbDemoStart : StaticEventHandler
{
	bool done;
	override void WorldLoaded(WorldEvent e) { if (e.IsSaveGame) done = true; }
	override void WorldTick()
	{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		let p = players[0].mo;
		Vector2 at = (3565.0, -13410.75);
		p.SetOrigin((at, p.GetZAt(at.x, at.y, 0, GZF_ABSOLUTEPOS)), false);
		p.angle = 180;
		p.vel = (0, 0, 0);
	}
}
