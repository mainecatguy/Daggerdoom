version "4.10"

// Holds the camera at a point for screenshots. netevent dftyaw angle, then netevent dftshot x y z.
class DFTextureShot : EventHandler
{
	Vector3 at;
	double yaw, pitch;
	bool ready;

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "dftyaw") { yaw = e.Args[0]; return; }
		if (e.Name != "dftshot") return;
		at = (e.Args[0], e.Args[1], e.Args[2]);
		ready = true;
	}

	override void WorldTick()
	{
		if (!ready) return;
		let mo = players[0].mo;
		mo.SetOrigin(at, false);
		mo.vel = (0, 0, 0);
		mo.A_SetAngle(yaw);
		mo.A_SetPitch(pitch);
		mo.bNOGRAVITY = true;
		mo.bINVULNERABLE = true;
	}
}
