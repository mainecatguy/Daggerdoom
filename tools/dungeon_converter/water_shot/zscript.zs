version "4.10"

// Holds the camera at the deepest water for screenshots. netevent dfwatershot 0: above, 1: under, 2: under, looking up.
class DFWaterShot : EventHandler
{
	double x, y, top;
	int view;
	bool ready;

	override void WorldLoaded(WorldEvent e)
	{
		int lump = Wads.CheckNumForFullName("DFWPROBE.txt");
		if (lump < 0) lump = Wads.CheckNumForName("DFWPROBE", Wads.ns_global);
		if (lump < 0) return;
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n");
		foreach (text : lines)
		{
			Array<String> f;
			text.Split(f, " ");
			if (f.Size() != 5 || f[0] != "S") continue;
			x = f[1].ToDouble(); y = f[2].ToDouble(); top = f[4].ToDouble();
			ready = true;
		}
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "dfwatershot") view = e.Args[0];
	}

	override void WorldTick()
	{
		if (!ready) return;
		let mo = players[0].mo;
		mo.SetOrigin((x, y, view == 0 ? top + 4 : top - 90), false);
		mo.vel = (0, 0, 0);
		mo.A_SetPitch(view == 0 ? 25 : view == 1 ? 0 : -35);
		if (level.maptime % 35 == 0) Console.Printf("DFSHOT view=%d z=%.0f water=%d", view, mo.pos.z, mo.waterlevel);
	}
}
