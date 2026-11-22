version "4.10"

// Comparison capture. Does nothing unless a DFVIEWS lump is loaded.

class DFCapCamera : Actor
{
	Default { Radius 1; Height 1; CameraHeight 0; +NOGRAVITY; +NOBLOCKMAP; +NOINTERACTION; }
	States { Spawn: TNT1 A -1; Stop; }
}

class DFCapture : EventHandler
{
	Array<String> ids;
	Array<double> xs, ys, zs, yaws, pitches;
	Actor cam;

	override void WorldLoaded(WorldEvent e)
	{
		int lump = Wads.CheckNumForName("DFVIEWS", Wads.ns_global);
		if (lump < 0) return;
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n");
		for (int i = 0; i < lines.Size(); i++)
		{
			Array<String> p;
			lines[i].Split(p, " ");
			if (p.Size() < 6) continue;
			ids.Push(p[0]);
			xs.Push(p[1].ToDouble());
			ys.Push(p[2].ToDouble());
			zs.Push(p[3].ToDouble());
			yaws.Push(p[4].ToDouble());
			pitches.Push(p[5].ToDouble());
		}
		cam = Actor.Spawn("DFCapCamera", (0, 0, 0));
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name != "dfview" || !cam || e.Args[0] >= ids.Size()) return;
		int i = e.Args[0];
		vector3 eye = (xs[i], ys[i], zs[i]);
		let mo = players[0].mo;
		mo.bNOGRAVITY = true;
		mo.A_SetRenderStyle(0, STYLE_None);
		mo.Vel = (0, 0, 0);
		mo.SetOrigin(eye, false);
		cam.SetOrigin(eye, false);
		cam.angle = yaws[i];
		cam.pitch = pitches[i];
		cam.ClearInterpolation();
		players[0].camera = cam;
		players[0].fixedlightlevel = 255;

		// Same order as the Daggerfall probe: down, up, east, north, west, south.
		String line = "DFPROBE " .. ids[i];
		line = line .. Probe(0, 90) .. Probe(0, -90) .. Probe(0, 0) .. Probe(90, 0) .. Probe(180, 0) .. Probe(270, 0);
		Console.Printf("%s", line);
	}

	String Probe(double angle, double pitch)
	{
		FLineTraceData data;
		bool hit = cam.LineTrace(angle, 4096, pitch, TRF_THRUACTORS, 0, 0, 0, data);
		return String.Format(" %.1f", hit ? data.Distance : -1.0);
	}
}
