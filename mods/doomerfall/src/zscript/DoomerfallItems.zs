// A Daggerfall loot pile in the Doom world. Daggerfall owns it: this actor only shows the latest list.
class DoomerfallWorldItem : Actor
{
	String dfId;
	int dfGeneration;
	int dfCount;

	Default
	{
		+NOINTERACTION
		+NOBLOCKMAP
		+NOGRAVITY
		+DONTSPLASH
		+NOTONAUTOMAP
		Radius 8;
		Height 16;
	}

	States
	{
	Spawn:
		BON1 A -1; // Shown only if the item sprite package is missing.
		Stop;
	}

	void Show(int archive, int record, double width, double height)
	{
		TextureID tex = TexMan.CheckForTexture(String.Format("DP%03d%03d", archive, record), TexMan.Type_Any);
		if (!tex.IsValid()) tex = TexMan.CheckForTexture("DPNOSPR", TexMan.Type_Any);
		if (!tex.IsValid()) return;
		int w, h;
		[w, h] = TexMan.GetSize(tex);
		if (w <= 0 || h <= 0) return;
		picnum = tex;
		scale = (width > 0 ? width / w : 1, height > 0 ? height / h : 1);
	}
}

// Shows Daggerfall's list and turns the Interact control into a pickup request.
class DoomerfallItems : EventHandler
{
	const Reach = 96.0;      // Daggerfall's 128-unit treasure reach at the 75% world scale.
	const MinAim = 0.90;     // About 25 degrees around the crosshair.

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "df_interact") Interact(e.Player);
		else if (e.Name == "dfi_clear") RemoveExcept(-1);
		else if (e.Name.Left(9) == "dfi_item:") AddItem(e.Name);
		else if (e.Name.Left(8) == "dfi_end:")
		{
			Array<String> f;
			e.Name.Split(f, ":");
			if (f.Size() >= 2) RemoveExcept(f[1].ToInt());
		}
	}

	void AddItem(String row)
	{
		Array<String> f;
		row.Split(f, ":");
		if (f.Size() < 11) return;
		String id = f[2];
		let item = Find(id);
		vector3 at = (f[6].ToDouble(), f[7].ToDouble(), f[8].ToDouble());
		if (item == null)
		{
			item = DoomerfallWorldItem(Actor.Spawn("DoomerfallWorldItem", at, NO_REPLACE));
			if (item == null) return;
			item.dfId = id;
		}
		else item.SetOrigin(at, false);
		item.dfGeneration = f[1].ToInt();
		item.dfCount = f[5].ToInt();
		item.Show(f[3].ToInt(), f[4].ToInt(), f[9].ToDouble(), f[10].ToDouble());
	}

	DoomerfallWorldItem Find(String id)
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
			if (item.dfId == id) return item;
		return null;
	}

	void RemoveExcept(int generation)
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
			if (item.dfGeneration != generation) item.Destroy();
	}

	void Interact(int playerNumber)
	{
		let mo = players[playerNumber].mo;
		if (mo == null || players[playerNumber].health <= 0) return;
		vector3 eye = mo.pos + (0, 0, players[playerNumber].viewheight);
		vector3 aim = (cos(mo.pitch) * cos(mo.angle), cos(mo.pitch) * sin(mo.angle), -sin(mo.pitch));
		DoomerfallWorldItem best = null;
		double bestAim = MinAim;
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		DoomerfallWorldItem item;
		while (item = DoomerfallWorldItem(it.Next()))
		{
			vector3 to = level.Vec3Diff(eye, item.pos);
			double distance = to.Length();
			if (distance > Reach) continue;
			double facing = distance > 1 ? (to / distance) dot aim : 1;
			if (facing > bestAim && mo.CheckSight(item, SF_IGNOREVISIBILITY))
			{
				bestAim = facing;
				best = item;
			}
		}
		if (best != null) EventHandler.SendNetworkEvent("dfi_take:" .. best.dfId);
	}
}
