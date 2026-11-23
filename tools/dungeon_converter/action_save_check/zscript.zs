version "4.10"

// Save and load check for action objects, run by action_regress.py on Scourg Barrow.
// First launch: moves two moving records, then autosaves. Second launch: loads and checks they stayed done.
// Static, because the engine does not send WorldLoaded to ordinary handlers restored from a save.
class DFActionSaveCheck : StaticEventHandler
{
	bool loaded, reported, reversing, finished;
	int startTic;

	DFAction Mover(DFActionHandler sys, int skip)
	{
		foreach (a : sys.actions)
			if (a.kind == 1 && a.cells.Size() > 0 && skip-- == 0) return a;
		return null;
	}

	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame) { loaded = true; reported = false; startTic = level.time; }
	}

	override void WorldTick()
	{
		let sys = DFActionHandler(EventHandler.Find("DFActionHandler"));
		if (!sys || finished || sys.actions.Size() == 0) return;
		let first = Mover(sys, 0), second = Mover(sys, 1);
		if (!first || !second) return;
		let p = players[consoleplayer].mo;
		if (!loaded)
		{
			if (level.time == 20) { first.Receive(p, DFAction.FROM_ACTION); second.Receive(p, DFAction.FROM_ACTION); }
			if (level.time == 20 + 2 + int(max(1 / first.rate, 1 / second.rate)))
			{
				Console.Printf("ASBEFORE first phase %d fraction %.2f second phase %d fraction %.2f", first.phase, first.fraction, second.phase, second.fraction);
				LevelLocals.MakeAutoSave();
			}
			return;
		}
		if (level.time < startTic + 2) return;
		if (!reported)
		{
			reported = true;
			double drift = 0;
			foreach (c : second.cells)
			{
				vector3 want = second.ToWorld((c.lx, c.ly, c.lz), second.fraction);
				drift = max(drift, (c.pos - (want.x, want.y, want.z - second.cellHalf)).Length());
			}
			bool linked = first.visual != null;
			foreach (a : sys.actions) if (a.door && a.door.listener != a) linked = false;
			bool kept = first.phase == DFAction.AT_END && second.phase == DFAction.AT_END && first.fraction == 1 && second.fraction == 1;
			Console.Printf("ASLOADED records %d kept %d cell drift %.2f links %d", sys.actions.Size(), kept, drift, linked);
			if (!kept || drift > 0.01 || !linked) { finished = true; Console.Printf("ASFAILED state not preserved"); return; }
			second.Receive(p, DFAction.FROM_ACTION);
			reversing = true;
			return;
		}
		if (reversing && second.phase == DFAction.AT_START)
		{
			finished = true;
			Console.Printf("ASDONE object reversed after load");
		}
	}
}
