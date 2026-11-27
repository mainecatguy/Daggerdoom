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

	// A dropped pile of one ammo type (DoomerfallAmmoPileArt.cs): record is the type, plus 4 for a box's worth.
	const AmmoArchive = 9100;
	// Doom's own pickup sprites, which DRLA's ammo pickups also use: clip, shells, rocket, cell, then their boxes.
	static const String AmmoSprites[] = { "CLIPA0", "SHELA0", "ROCKA0", "CELLA0", "AMMOA0", "SBOXA0", "BROKA0", "CELPA0" };

	void Show(int archive, int record, double width, double height)
	{
		if (archive == AmmoArchive && ShowAmmo(record)) return;
		TextureID tex = TexMan.CheckForTexture(String.Format("DP%03d%03d", archive, record), TexMan.Type_Any);
		if (!tex.IsValid()) tex = TexMan.CheckForTexture("DPNOSPR", TexMan.Type_Any);
		if (!tex.IsValid()) return;
		int w, h;
		[w, h] = TexMan.GetSize(tex);
		if (w <= 0 || h <= 0) return;
		picnum = tex;
		scale = (width > 0 ? width / w : 1, height > 0 ? height / h : 1);
	}

	bool ShowAmmo(int record)
	{
		if (record < 0 || record >= AmmoSprites.Size()) return false;
		TextureID tex = TexMan.CheckForTexture(AmmoSprites[record], TexMan.Type_Sprite);
		if (!tex.IsValid()) return false;
		picnum = tex;
		scale = (1, 1);
		return true;
	}
}

// A Daggerfall furniture container, such as a shop shelf or a wardrobe. The furniture itself is map geometry, so this
// only holds the box that Use aims at (dd_items.cpp). It sits at the bottom center of the box.
class DoomerfallWorldContainer : Actor
{
	String dfId;
	int dfGeneration;
	double dfMinX, dfMinY, dfMinZ, dfMaxX, dfMaxY, dfMaxZ;

	Default
	{
		+NOINTERACTION
		+NOBLOCKMAP
		+NOGRAVITY
		+DONTSPLASH
		+NOTONAUTOMAP
		RenderStyle "None";
		Radius 8;
		Height 16;
	}

	States
	{
	Spawn:
		TNT1 A -1;
		Stop;
	}
}

// Shows Daggerfall's list. The engine's Use handling (dd_items.cpp) aims at these piles and asks Daggerfall.
class DoomerfallItems : EventHandler
{
	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "dfi_clear") RemoveExcept(-1);
		else if (e.Name.Left(9) == "dfi_item:") AddItem(e.Name);
		else if (e.Name.Left(8) == "dfi_box:") AddBox(e.Name);
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

	void AddBox(String row)
	{
		Array<String> f;
		row.Split(f, ":");
		if (f.Size() < 9) return;
		String id = f[2];
		DoomerfallWorldContainer box = null;
		let it = ThinkerIterator.Create("DoomerfallWorldContainer");
		DoomerfallWorldContainer each;
		while (each = DoomerfallWorldContainer(it.Next()))
			if (each.dfId == id) box = each;
		double x0 = f[3].ToDouble(), y0 = f[4].ToDouble(), z0 = f[5].ToDouble(), x1 = f[6].ToDouble(), y1 = f[7].ToDouble(), z1 = f[8].ToDouble();
		vector3 at = ((x0 + x1) / 2, (y0 + y1) / 2, z0);
		if (box == null)
		{
			box = DoomerfallWorldContainer(Actor.Spawn("DoomerfallWorldContainer", at, NO_REPLACE));
			if (box == null) return;
			box.dfId = id;
		}
		else box.SetOrigin(at, false);
		box.dfGeneration = f[1].ToInt();
		box.dfMinX = x0;
		box.dfMinY = y0;
		box.dfMinZ = z0;
		box.dfMaxX = x1;
		box.dfMaxY = y1;
		box.dfMaxZ = z1;
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
		let boxes = ThinkerIterator.Create("DoomerfallWorldContainer");
		DoomerfallWorldContainer box;
		while (box = DoomerfallWorldContainer(boxes.Next()))
			if (box.dfGeneration != generation) box.Destroy();
	}
}
