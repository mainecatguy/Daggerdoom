version "4.10"

// Location record card 1 probe: prints the terrain under and around the player, so a save made before the terrain
// planes were dropped from the snapshot and a load after it can be compared.
class LRCard1 : EventHandler
{
	override void WorldTick()
	{
		bool loading = CVar.FindCVar("lrc1_load").GetBool();
		let pl = players[consoleplayer].mo;
		// Move far enough that the treadmill shifts its window, so the save is not at the starting origin.
		if (level.maptime == 5 && !loading && pl) pl.SetOrigin(pl.pos + (9000, -6000, 3000), false);
		if (level.maptime == 105 && !loading) level.MakeAutoSave();
		if (level.maptime == 140) Console.Printf("LRC1DONE");
		if (level.maptime != 100 && level.maptime != 110) return;
		let p = players[consoleplayer].mo;
		if (!p) return;
		double sum = 0;
		for (int dx = -2; dx <= 2; dx++)
			for (int dy = -2; dy <= 2; dy++)
			{
				vector2 at = p.pos.xy + (dx * 512, dy * 512);
				sum += level.PointInSector(at).floorplane.ZatPoint(at);
			}
		Console.Printf("LRC1 tic %d map %s pos %.1f %.1f %.1f floorz %.1f ceilingz %.1f gridsum %.1f", level.maptime, level.MapName,
			p.pos.x, p.pos.y, p.pos.z, p.floorz, p.ceilingz, sum);
	}
}
