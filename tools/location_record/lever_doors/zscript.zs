version "4.14"

// Card 5's lever-driven door check (tools/location_record/lever_doors.py), standalone on a converted dungeon with door
// links (Wayrest castle; Privateer's Hold has none). Visit 1 opens every door an action opens (flag 18) through that
// action and keeps DFDoorHandler.Distill(). The map is then entered fresh, so doors and actions reset, and visit 2
// restores the record, prints the doors and the actions' state, and runs each action again (the lever pulled again).
class DFLeverDoorCheck : StaticEventHandler
{
	String record;
	int visit;
	Array<int> leverDoors;

	static void Doors(String when, Array<int> watch)
	{
		Array<DFDoor> doors;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while (d = DFDoor(it.Next())) doors.Push(d);
		String text = "";
		int open = 0, bad = 0;
		foreach (i : watch)
		{
			d = doors[i];
			text.AppendFormat(" %d:%d/%d", i, int(d.swung), d.moving);
			bool solid = d.links.Size() > 0 && d.links[0].bSOLID;
			if (d.moving == 0 && (d.sightOpen != (d.swung > 0) || solid != (d.swung <= 0))) bad++;
		}
		for (int i = 0; i < doors.Size(); i++) if (doors[i].swung > 0) open++;
		Console.Printf("LVDOORS %s: doors %d, open %d; lever doors index:swung/moving%s; sight or collision wrong %d", when, doors.Size(), open, text, bad);
	}

	override void WorldTick()
	{
		let p = players[consoleplayer].mo;
		if (level.maptime == 35)
		{
			Array<DFDoor> doors;
			let di = ThinkerIterator.Create("DFDoor");
			DFDoor d;
			while (d = DFDoor(di.Next())) doors.Push(d);
			let it = ThinkerIterator.Create("DFAction");
			DFAction a;
			int pulled = 0, used = 0;
			while (a = DFAction(it.Next()))
			{
				if (a.flag != 18 || !a.door) continue;
				if (visit == 0) { a.Perform(p); pulled++; leverDoors.Push(doors.Find(a.door)); }
				else used += a.activationCount;
			}
			if (visit == 0) { Console.Printf("LVPULL %d actions with flag 18 opened their doors", pulled); return; }
			Console.Printf("LVRESTORE %d doors open; the actions' activation counts after the fresh entry: %d", DFDoorHandler.Restore(record), used);
			Doors("restored", leverDoors);
			it = ThinkerIterator.Create("DFAction");
			while (a = DFAction(it.Next())) if (a.flag == 18 && a.door) a.Perform(p);
			Doors("pulled again", leverDoors);
		}
		if (level.maptime != 35 * 4) return;
		if (visit == 0)
		{
			Doors("opened", leverDoors);
			record = DFDoorHandler.Distill();
			Console.Printf("LVRECORD %s", record);
			visit = 1;
			level.ChangeLevel("MAP01", 0, CHANGELEVEL_NOINTERMISSION | CHANGELEVEL_RESETINVENTORY);
			return;
		}
		Doors("after", leverDoors);
		Console.Printf("LVSAME %d", DFDoorHandler.Distill() == record);
		Console.Printf("ACDONE");
	}
}
