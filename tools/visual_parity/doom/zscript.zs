version "4.10"

// Visual parity test only (tools/visual_parity). Loaded only by those scripts, never by the game.
// 1. Removes every monster and every NPC each tic, so the scenes show the place alone.
// 2. "netevent vp_pos x y z" (tenths of a map unit) and "netevent vp_look angle pitch fov" (hundredths of a degree) put a
//    camera at an exact eye point, so Doom's view can match Daggerfall Unity's eye height and field of view.
//    "netevent vp_player" gives the view back to the player.

class VPCamera : Actor
{
	Default { Radius 1; Height 1; CameraHeight 0; +NOGRAVITY; +NOBLOCKMAP; +NOINTERACTION; }
	States { Spawn: TNT1 A -1; Stop; }
}

class VPHarness : EventHandler
{
	Actor cam;
	int removed;

	static bool IsPerson(Actor a)
	{
		if (a.player) return false;
		if (a.bIsMonster || a.bCountKill) return true;
		String cls = a.GetClassName();
		cls = cls.MakeLower();
		return a is "DFDungeonNpc" || cls.IndexOf("npc") >= 0 || cls.IndexOf("townsperson") >= 0 || cls.IndexOf("ddguard") >= 0;
	}

	override void WorldTick()
	{
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (IsPerson(a))
			{
				if (removed < 400) Console.Printf("VPREMOVE %s at %.0f %.0f %.0f", a.GetClassName(), a.pos.x, a.pos.y, a.pos.z);
				removed++;
				a.Destroy();
			}
		}
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		let p = players[e.Player];
		if (!p.mo) return;
		if (!cam) cam = Actor.Spawn("VPCamera", p.mo.pos);
		if (e.Name == "vp_pos")
		{
			cam.SetOrigin((e.Args[0] / 10., e.Args[1] / 10., e.Args[2] / 10.), false);
			p.camera = cam;
		}
		else if (e.Name == "vp_look")
		{
			cam.angle = e.Args[0] / 100.;
			cam.pitch = e.Args[1] / 100.;
			cam.CameraFOV = e.Args[2] / 100.;
			p.camera = cam;
			Console.Printf("VPCAM %.1f %.1f %.1f angle %.2f pitch %.2f fov %.2f removed %d", cam.pos.x, cam.pos.y, cam.pos.z, cam.angle, cam.pitch, cam.CameraFOV, removed);
		}
		else if (e.Name == "vp_player")
		{
			p.camera = p.mo;
			Console.Printf("VPPLAYER %.1f %.1f %.1f view %.1f angle %.2f fov %.2f", p.mo.pos.x, p.mo.pos.y, p.mo.pos.z, p.viewz - p.mo.pos.z, p.mo.angle, p.fov);
		}
	}
}
