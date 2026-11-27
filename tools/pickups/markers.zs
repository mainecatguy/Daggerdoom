version "4.14"

// Pickup marker test (mix_survey.py markers). Spawns each Doomerfall pickup marker in a row beside the player and,
// a few tics later, logs the item standing at each spot and how many markers are left (they must remove themselves).
class PMHarness : StaticEventHandler
{
	static const String MARKERS[] = {
		"DoomerfallPickupStimpack", "DoomerfallPickupClip", "DoomerfallPickupShells", "DoomerfallPickupRockets",
		"DoomerfallPickupCells", "DoomerfallPickupBerserk", "DoomerfallPickupBlur", "DoomerfallPickupVisor",
		"DoomerfallPickupSoulsphere", "DoomerfallPickupMegasphere", "DoomerfallPickupInvulnerability" };
	Array<double> xs, ys;
	bool done;

	override void WorldTick()
	{
		if (done || !players[0].mo) return;
		let p = players[0].mo;
		if (level.maptime == 10)
		{
			for (int i = 0; i < MARKERS.Size(); i++)
			{
				vector3 at = (p.Pos.X + 40 * (i - 5), p.Pos.Y + 96, p.Pos.Z);
				class<Actor> cls = MARKERS[i];
				if (!cls) { Console.Printf("PMARK %s missing class", MARKERS[i]); continue; }
				Actor.Spawn(cls, at);
				xs.Push(at.X);
				ys.Push(at.Y);
			}
		}
		if (level.maptime == 30)
		{
			int bad = 0;
			for (int i = 0; i < xs.Size(); i++)
			{
				String found = "";
				let it = ThinkerIterator.Create("Inventory");
				Inventory inv;
				while (inv = Inventory(it.Next()))
					if (!inv.Owner && abs(inv.Pos.X - xs[i]) < 4 && abs(inv.Pos.Y - ys[i]) < 4) found = found .. " " .. inv.GetClassName();
				if (found == "") bad++;
				Console.Printf("PMARK %s ->%s", MARKERS[i], found == "" ? " NOTHING" : found);
			}
			int markers = 0;
			let im = ThinkerIterator.Create("DoomerfallPickupMarker");
			while (im.Next()) markers++;
			Console.Printf("PMRESULT spots=%d empty=%d markers_left=%d", xs.Size(), bad, markers);
			Console.Printf("PMDONE");
			done = true;
		}
	}
}
