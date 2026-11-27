version "4.10"

// Test only (tools/looklabel/looklabel.py): every pickup class that shows a sprite on the floor is spawned once on E1M1,
// named by the Doomerfall mod's rule (DoomerfallItemName.Of, what the look label and Daggerfall's inventory use), and
// removed. The old rule (tag, else pickup message) is logged beside it. Lines go to the log file only.
class LLHarness : EventHandler
{
	int tics;

	override void WorldTick()
	{
		if (++tics != 20) return;
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		Vector3 spot = pmo.Vec3Angle(64, pmo.angle);
		int tnt = Actor.GetSpriteIndex("TNT1");
		int count = 0;
		for (int i = 0; i < AllActorClasses.Size(); i++)
		{
			class<Actor> cls = AllActorClasses[i];
			if (!(cls is "Inventory") || cls.IsAbstract()) continue;
			let def = GetDefaultByType(cls);
			if (!def.bSPECIAL || !Visible(def.SpawnState, tnt)) continue;
			let mo = Actor.Spawn(cls, spot, NO_REPLACE);
			if (!mo) continue;
			String name = DoomerfallItemName.Of(mo);
			String old = mo.GetTag("@@none@@"); // The engine's old rule: the tag, else the pickup message.
			if (old == "@@none@@" || old.Length() == 0) old = StringTable.Localize(Inventory(mo).PickupMsg);
			Console.PrintfEx(PRINT_LOG, "LLNAME class=%s name=%s old=%s", cls.GetClassName(), name, old);
			mo.Destroy();
			count++;
		}
		Console.PrintfEx(PRINT_LOG, "LLDONE %d", count);
	}

	// A sprite other than TNT1 within the first few spawn states, as the engine's look label requires a visible pickup.
	static bool Visible(State st, int tnt)
	{
		for (int i = 0; st && i < 8; i++, st = st.NextState)
			if (st.sprite != tnt && st.sprite != 0) return true;
		return false;
	}
}
