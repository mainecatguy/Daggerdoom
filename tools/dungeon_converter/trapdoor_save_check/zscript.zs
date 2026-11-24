version "4.10"

// Save and load with one action 18 and one action 8 trapdoor open. First launch opens them and autosaves.
// Second launch loads, checks that they stayed open with their cells in place, and that a body over each hole falls.
// Static, because the engine does not send WorldLoaded to ordinary handlers restored from a save.
class DFTrapdoorSaveCheck : StaticEventHandler
{
	bool loaded, finished, dropping;
	int startTic, stage;
	double top;

	static bool IsTile(DFAction a)
	{
		double w = a.boxMax.x - a.boxMin.x, d = a.boxMax.y - a.boxMin.y;
		return a.kind == 1 && (a.flag == 18 || a.flag == 8) && w >= 90 && w <= 100 && d >= 90 && d <= 100 && a.boxMax.z - a.boxMin.z <= 8;
	}

	DFAction Tile(DFActionHandler sys, int flag)
	{
		foreach (a : sys.actions) if (a.flag == flag && IsTile(a)) return a;
		return null;
	}

	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame) { loaded = true; startTic = level.time; }
	}

	override void WorldTick()
	{
		let sys = DFActionHandler(EventHandler.Find("DFActionHandler"));
		if (!sys || finished || sys.actions.Size() == 0) return;
		let swung = Tile(sys, 18), hinged = Tile(sys, 8);
		if (!swung || !hinged) return;
		let p = players[consoleplayer].mo;
		if (!loaded)
		{
			if (level.time == 20) { swung.Receive(p, DFAction.FROM_ACTION); hinged.Receive(p, DFAction.FROM_ACTION); }
			if (level.time == 20 + 2 + int(max(1 / swung.rate, 1 / hinged.rate)))
			{
				Console.Printf("TSBEFORE swung %d %.2f hinged %d %.2f", swung.phase, swung.fraction, hinged.phase, hinged.fraction);
				LevelLocals.MakeAutoSave();
			}
			return;
		}
		int s = level.time - startTic;
		if (s == 2)
		{
			double drift = 0;
			foreach (a : sys.actions)
				if (a == swung || a == hinged)
					foreach (c : a.cells)
					{
						vector3 want = a.ToWorld((c.lx, c.ly, c.lz), a.fraction);
						drift = max(drift, (c.pos - (want.x, want.y, want.z - c.height / 2)).Length());
					}
			bool kept = swung.phase == DFAction.AT_END && hinged.phase == DFAction.AT_END && swung.fraction == 1 && hinged.fraction == 1;
			Console.Printf("TSLOADED kept %d drift %.2f free %d", kept, drift, hinged.freeSwing);
			if (!kept || drift > 0.01 || !hinged.freeSwing) { finished = true; Console.Printf("TSFAILED state not preserved"); return; }
		}
		// Body over each open hole, at the closed tile's height.
		for (int k = 0; k < 2; k++)
		{
			let a = k == 0 ? swung : hinged;
			int at = 4 + k * 60;
			double fx = a.fraction;
			a.fraction = 0;
			vector3 m = a.ToWorld(((a.boxMin.x + a.boxMax.x) / 2, (a.boxMin.y + a.boxMax.y) / 2, a.boxMax.z), 0);
			a.fraction = fx;
			if (s == at) { top = m.z; p.SetOrigin((m.x, m.y, m.z + 1), false); p.vel = (0, 0, 0); p.FindFloorCeiling(); }
			if (s == at + 50)
			{
				Console.Printf("TSDROP tile %d fell %.1f", a.id, top - p.pos.z);
				if (top - p.pos.z < 48) { finished = true; Console.Printf("TSFAILED body did not fall"); return; }
				if (k == 1) { finished = true; Console.Printf("TSDONE"); }
			}
		}
	}
}
