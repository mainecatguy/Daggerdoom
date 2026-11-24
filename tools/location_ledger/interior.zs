version "4.14"

// Location ledger interior test (tools/location_ledger/interior.py). "first": enter a town building, take a map pickup,
// move another, drop a clip, kill an imp, leave and re-enter, then leave and autosave in the town. "load": from that
// save, enter the building again. Each visit prints a sorted signature of every monster, corpse and loose item.
class LLState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer;
}

class LLHarness : StaticEventHandler	// Static, so "started" survives the map changes of a loaded run.
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 12;
	bool done, loadMode, started;

	override void OnRegister() { loadMode = "@MODE@" ~== "load"; }
	void Finish(String why) { Console.Printf("LLDONE %s", why); done = true; }

	static void Signature(String when)
	{
		Array<String> rows;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (mo.player) continue;
			bool item = mo is "Inventory" && Inventory(mo).Owner == null;
			if (!mo.bISMONSTER && !item) continue;
			rows.Push(String.Format("%s %s %d,%d,%d hp %d%s", item ? "item" : mo.health > 0 ? "alive" : "dead", mo.GetClassName(),
				int(mo.pos.x / 8), int(mo.pos.y / 8), int(mo.pos.z / 8), mo.health, mo.bDROPPED ? " dropped" : ""));
		}
		for (int i = 1; i < rows.Size(); i++)
			for (int j = i; j > 0 && rows[j] < rows[j - 1]; j--) { String t = rows[j]; rows[j] = rows[j - 1]; rows[j - 1] = t; }
		Console.Printf("LLSIG %s begin %d", when, rows.Size());
		for (int i = 0; i < rows.Size(); i++) Console.Printf("LLSIG %s %s", when, rows[i]);
		Console.Printf("LLSIG %s end", when);
	}

	void MoveNear(PlayerPawn p, vector3 at, vector2 normal)
	{
		p.SetOrigin((at.xy + normal * 40, at.z), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
		p.pitch = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = LLState(p.FindInventory("LLState"));
		if (!st) st = LLState(p.GiveInventoryType("LLState"));
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 doorN = (DOORDATA[3], DOORDATA[4]);
		vector3 exit = (EXITDATA[0], EXITDATA[1], EXITDATA[2]);
		vector2 exitN = (EXITDATA[3], EXITDATA[4]);
		st.timer++;
		if (st.timer > LIMIT * 2) { Console.Printf("LLFAIL stuck in step %d on %s", st.phase, level.MapName); Finish("failed"); return; }
		if (loadMode && !started) { st.phase = 3; st.timer = 0; started = true; }	// The save was made in the town, after the first trip.
		switch (st.phase)
		{
		case 0: case 3: // In the town: use the building's door.
			if (inside || level.maptime < 20) break;
			MoveNear(p, door, doorN);
			if (st.timer < 50) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase++;
			st.timer = 0;
			break;
		case 1: case 4: // Inside.
			if (!inside || st.timer < 70) break;
			if (st.phase == 4) { Signature(loadMode ? "loaded" : "reentry"); if (loadMode) { Finish("passed"); break; } }
			else
			{
				Array<Inventory> loose;
				let it = ThinkerIterator.Create("Inventory");
				Inventory inv;
				while (inv = Inventory(it.Next())) if (inv.Owner == null) loose.Push(inv);
				Console.Printf("LLITEMS %d map items", loose.Size());
				if (loose.Size() > 0) { Console.Printf("LLTAKE %s", loose[0].GetClassName()); loose[0].CallTryPickup(p); }
				if (loose.Size() > 1) { loose[1].SetOrigin(loose[1].pos + (16, 0, 0), false); Console.Printf("LLMOVE %s", loose[1].GetClassName()); }
				let clip = p.Spawn("Clip", p.pos + p.AngleToVector(p.angle, 32));
				if (clip) { clip.bDROPPED = true; Console.Printf("LLDROP Clip"); }
				let imp = p.Spawn("DoomImp", p.pos + p.AngleToVector(p.angle, 64));
				if (imp) { imp.DamageMobj(p, p, imp.health + 100, 'None', DMG_FORCED); Console.Printf("LLKILL DoomImp"); }
				st.phase = 2;
				st.timer = 0;
				break;
			}
			st.phase = 5;
			st.timer = 0;
			break;
		case 2: case 5: // Leave the building.
			if (st.timer == 70 && st.phase == 2) Signature("leave");
			if (st.timer < 75) break;
			if (!inside) { st.phase = st.phase == 2 ? 3 : 6; st.timer = 0; break; }
			MoveNear(p, exit, exitN);
			if (st.timer == 80) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 6: // Back in the town: save there.
			if (st.timer == 60) { Console.Printf("LLSAVE"); level.MakeAutoSave(); }
			if (st.timer == 120) Finish("passed");
			break;
		}
	}
}
