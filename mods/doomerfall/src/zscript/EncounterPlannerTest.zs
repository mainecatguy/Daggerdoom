// Test hook: with +set dd_encounter_plantest 1, runs the encounter planner on a fixed list of fake area facts on the
// first map loaded and prints genes and armies as "ENCPLAN" lines, ending with "ENCPLAN done".
// tools/encounter_planner/run_test.py runs it and checks the output.
class DoomerfallEncounterPlanTest : StaticEventHandler
{
	bool done;

	override void WorldLoaded(WorldEvent e)
	{
		if (done) return;
		let flag = CVar.FindCVar("dd_encounter_plantest");
		if (!flag || !flag.GetBool()) return;
		done = true;
		let pool = DoomerfallEncounterPool.Get();
		if (!pool) { Console.Printf("ENCPLAN error no-pool"); Console.Printf("ENCPLAN done"); return; }
		Console.Printf("ENCPLAN begin pool=%d", pool.monsters.Size());

		// Every dungeon's genome (appendix A).
		Array<int> genes;
		for (int i = 0; i < DoomerfallEncounterPlanner.DUNGEONS; i++)
		{
			DoomerfallEncounterPlanner.Genome(i, 0, genes);
			Console.Printf("ENCPLAN genes %d %d %d %d %d %d %d %d %d %d %d", i, genes[0], genes[1], genes[2], genes[3], genes[4],
				genes[5], genes[6], genes[7], genes[8], genes[9]);
		}

		// Fake area facts: 120 Dragon's Dens, 120 Vampire Haunts, 6 of every other type, spread over the map,
		// and a cluster of 10 neighbours in one region cell.
		static const String types[] = { "Crypt", "OrcStronghold", "HumanStronghold", "Prison", "DesecratedTemple", "Mine",
			"NaturalCave", "Coven", "VampireHaunt", "Laboratory", "HarpyNest", "RuinedCastle", "SpiderNest", "GiantStronghold",
			"DragonsDen", "BarbarianStronghold", "VolcanicCaves", "ScorpionNest", "Cemetery" };
		int made = 0;
		for (int k = 0; k < 120; k++)
		{
			Run(k * 31 + 5, "DragonsDen", (k * 53) % 1000, (k * 29) % 500, k % 31);
			Run(k * 31 + 17, "VampireHaunt", (k * 71 + 300) % 1000, (k * 37 + 100) % 500, (k * 7) % 31);
			made += 2;
		}
		for (int t = 0; t < types.Size(); t++)
		{
			if (types[t] == "DragonsDen" || types[t] == "VampireHaunt") continue;
			for (int k = 0; k < 6; k++)
			{
				Run(3900 + t * 17 + k * 3, types[t], (t * 97 + k * 151) % 1000, (t * 41 + k * 67) % 500, (t * 5 + k * 6) % 31);
				made++;
			}
		}
		for (int k = 0; k < 10; k++)
		{
			Run(3720 + k * 7,types[(k * 5) % types.Size()], 490 + k * 3, 245 + k * 4, 10 + k);
			made++;
		}
		made += Ladder();
		Console.Printf("ENCPLAN summary plans=%d", made);
		Console.Printf("ENCPLAN done");
	}

	// A level ladder in the region cell whose favourite kind is dearest (its cheapest class): out of reach at low
	// levels, purchasable at high ones. Types every setup has theme monsters for, so any warning here is the region
	// rule's; no Dragon's Den or Vampire Haunt (they are counted at 120 each).
	private int Ladder()
	{
		let pool = DoomerfallEncounterPool.Get();
		int bestX = 0, bestY = 0, bestCost = -1;
		for (int cy = 0; cy < 10; cy++)
		{
			for (int cx = 0; cx < 20; cx++)
			{
				let req = new("DoomerfallEncounterRequest");
				req.dungeonIndex = 4231;
				req.worldX = cx * 48 + 24;
				req.worldY = cy * 48 + 24;
				req.dungeonType = "Crypt";
				let p = DoomerfallEncounterPlanner.Plan(req);
				if (!p || p.regionKind < 0) continue;
				int cheapest = 0x7FFFFFFF;
				for (int i = 0; i < pool.monsters.Size(); i++)
				{
					let m = pool.monsters[i];
					if (m.kind == p.regionKind && !m.capped) cheapest = min(cheapest, DoomerfallEncounterPlanner.Cost(m));
				}
				if (cheapest > bestCost) { bestCost = cheapest; bestX = cx; bestY = cy; }
			}
		}
		Console.Printf("ENCPLAN ladder cell=%d,%d", bestX, bestY);
		static const String types[] = { "OrcStronghold", "Prison", "Mine", "NaturalCave", "DesecratedTemple", "RuinedCastle",
			"SpiderNest", "GiantStronghold", "Cemetery", "BarbarianStronghold", "Crypt" };
		static const int levels[] = { 0, 1, 2, 3, 4, 5, 7, 10, 15, 20, 30 };
		for (int k = 0; k < 11; k++) Run(3790 + k * 7, types[k], bestX * 48 + 2 + k * 4, bestY * 48 + 2 + k * 4, levels[k]);
		return 11;
	}

	private void Run(int index, String type, double x, double y, int level)
	{
		let req = new("DoomerfallEncounterRequest");
		req.dungeonIndex = index;
		req.locationId = 50000 + index * 3;
		req.locationName = "Fake " .. index;
		req.regionIndex = (index * 7) % 62;
		req.regionName = "Region " .. req.regionIndex;
		req.worldX = x;
		req.worldY = y;
		req.dungeonType = type;
		req.areaLevel = level;
		req.seedOffset = 0;
		let p = DoomerfallEncounterPlanner.Plan(req);
		if (!p) { Console.Printf("ENCPLAN error no-plan idx=%d", index); return; }
		let d = DoomerfallEncounterPool.Get().data;
		String g = "", th = "";
		for (int i = 0; i < p.genes.Size(); i++) { g = g .. (i ? "," : "") .. p.genes[i]; th = th .. (p.themed[i] ? "1" : "0"); }
		Console.Printf("ENCPLAN plan idx=%d type=%s level=%d order=%d genes=%s themed=%s civilwar=%d tierlean=%d size=%d placement=%s awareness=%s cell=%d,%d regionkind=%s regionafford=%d",
			index, p.theme, level, p.order, g, th, p.civilWar, p.tierLean, p.sizePermille, p.placement, p.awareness,
			p.regionCellX, p.regionCellY, p.regionKind >= 0 ? d.kindName[p.regionKind] : "-", p.regionAfford);
		Army(index, "A", p.a, d);
		if (p.b) Army(index, "B", p.b, d);
		for (int i = 0; i < p.warnings.Size(); i++) Console.Printf("ENCPLAN warn idx=%d %s", index, p.warnings[i]);
	}

	private void Army(int index, String side, DoomerfallArmy a, DoomerfallEncounterData d)
	{
		String list = "";
		for (int i = 0; i < a.entries.Size(); i++)
		{
			let e = a.entries[i];
			list = list .. (i ? "|" : "") .. String.Format("%s:%s:%s:%s:%d:%d:%s", e.role, e.m.cls.GetClassName(), d.kindName[e.m.kind],
				e.m.group, e.m.tier, e.share, e.parent >= 0 ? "v" .. e.parent : "-");
		}
		Console.Printf("ENCPLAN army idx=%d side=%s anchorkind=%s anchorthemed=%d coherence=%d tierlean=%d stance=%s theme=%s region=%s regionref=%s entries=%s",
			index, side, a.entries.Size() ? d.kindName[a.anchorKind] : "-", a.anchorThemed, a.coherence, a.tierLean, a.stance,
			a.themeHow, a.regionHow, a.regionRef ? String.Format("%s", a.regionRef.cls.GetClassName()) : "-", list);
	}
}
