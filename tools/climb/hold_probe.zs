// Demo-start check (test only). Holds forward from wherever the player stands, with no teleport, so it checks
// that the climbing demo's start (demo_start.zs) puts the player against a climbable wall. Prints CLIMBPROBE lines.
class ClimbProbe : StaticEventHandler
{
	int t, startT;
	double z0, zMax;
	override void OnRegister() { SetOrder(-100); startT = -1; }
	override void WorldTick()
	{
		let mo = players[0].mo;
		let c = DoomerfallClimb(StaticEventHandler.Find("DoomerfallClimb"));
		if (!mo || !c || !c.Active() || t > 400) return;
		t++;
		if (t < 105) return;
		if (t == 105) { z0 = zMax = mo.pos.z; Console.Printf("CLIMBPROBE hold from %.0f,%.0f z=%.0f angle %.0f", mo.pos.x, mo.pos.y, z0, mo.angle); }
		players[0].cmd.forwardmove = 6400;
		let s = c.st[0];
		if (startT < 0 && s && s.climbing) startT = t - 105;
		zMax = max(zMax, mo.pos.z);
		if (t == 400) { Console.Printf("CLIMBPROBE start=%d rose=%.0f", startT, zMax - z0); players[0].cmd.forwardmove = 0; }
	}
}
