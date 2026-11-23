// A Daggerfall item shown in the Doom world. Display only: no pickup, loot, or inventory yet.
class DaggerfallItem : Actor
{
	int DFTemplateIndex;   // ItemTemplates index, or -1 for an artifact.
	int DFVariant;
	int DFArtifactIndex;   // ArtifactsSubTypes value, or -1.
	int DFItemGroup;       // ItemGroups value.
	int DFSpriteArchive;   // TEXTURE.xxx file number.
	int DFSpriteRecord;
	String DFItemName;

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
		PLAY A -1;
		Stop;
	}

	static DaggerfallItem Create(Vector3 where, int template, int variant, int artifact, int group, int archive, int record, double size, String texture, String itemName)
	{
		let item = DaggerfallItem(Actor.Spawn("DaggerfallItem", where));
		if (item == null) return null;
		item.DFTemplateIndex = template;
		item.DFVariant = variant;
		item.DFArtifactIndex = artifact;
		item.DFItemGroup = group;
		item.DFSpriteArchive = archive;
		item.DFSpriteRecord = record;
		item.DFItemName = itemName;
		item.picnum = TexMan.CheckForTexture(texture, TexMan.Type_Any);
		item.scale = (size, size);
		return item;
	}
}

// Fills the gallery map from the generated table. Does nothing on any other map.
class DaggerfallItemGallery : EventHandler
{
	DaggerfallItem nearest;

	clearscope static bool IsGallery() { return level.MapName ~== "DFGALLRY"; }

	override void WorldLoaded(WorldEvent e)
	{
		if (!IsGallery() || e.IsSaveGame || e.IsReopen) return;
		int lump = Wads.CheckNumForFullName("dfitems.txt");
		if (lump < 0) { Console.Printf("DFITEMS: table missing"); return; }
		Array<String> rows, f;
		Wads.ReadLump(lump).Split(rows, "\n", TOK_SKIPEMPTY);
		int shown = 0, broken = 0;
		for (int i = 0; i < rows.Size(); i++)
		{
			f.Clear();
			rows[i].Split(f, "\t");
			if (f.Size() < 11) { broken++; continue; }
			let item = DaggerfallItem.Create((f[6].ToDouble(), f[7].ToDouble(), 0), f[0].ToInt(), f[1].ToInt(), f[2].ToInt(), f[3].ToInt(), f[4].ToInt(), f[5].ToInt(), f[8].ToDouble(), f[9], f[10]);
			if (item == null || !item.picnum.IsValid()) { broken++; continue; }
			int w, h;
			[w, h] = TexMan.GetSize(item.picnum);
			if (w <= 0 || h <= 0) { broken++; continue; }
			shown++;
		}
		Console.Printf("DFITEMS: shown=%d total=%d broken=%d", shown, rows.Size(), broken);
	}

	override void WorldTick()
	{
		if (!IsGallery() || level.maptime % 5 || !players[consoleplayer].mo) return;
		let viewer = players[consoleplayer].mo;
		DaggerfallItem best = null;
		double bestDistance = 200;
		let it = ThinkerIterator.Create("DaggerfallItem");
		DaggerfallItem item;
		while (item = DaggerfallItem(it.Next()))
		{
			double d = viewer.Distance2D(item);
			if (d < bestDistance) { bestDistance = d; best = item; }
		}
		nearest = best;
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (!IsGallery() || nearest == null) return;
		String label;
		if (nearest.DFArtifactIndex >= 0) label = String.Format("Artifact %d", nearest.DFArtifactIndex);
		else label = String.Format("Template %d, variant %d", nearest.DFTemplateIndex, nearest.DFVariant);
		String text = String.Format("%s\n%s, group %d\nTEXTURE.%03d record %d", nearest.DFItemName, label, nearest.DFItemGroup, nearest.DFSpriteArchive, nearest.DFSpriteRecord);
		Screen.DrawText(SmallFont, Font.CR_GOLD, 16, 16, text, DTA_VirtualWidth, 640, DTA_VirtualHeight, 400, DTA_FullscreenScale, FSMode_ScaleToFit43);
	}
}
