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
		// The Humanoid story theme (only=1): Privateer's Hold's real facts at level 1 and at other levels, then 30
		// other dungeon indices across all levels. Every army member must be a Former Human kind.
		for (int lv = 1; lv <= 30; lv += 7)
		{
			RunAt(1506, 50050, 17, "Humanoid", 109.5, 158.5, lv);
			made++;
		}
		for (int k = 0; k < 30; k++)
		{
			Run(4100 + k * 13, "Humanoid", (k * 83 + 40) % 1000, (k * 47 + 20) % 500, 1 + k);
			made++;
		}
		Console.Printf("ENCPLAN summary plans=%d", made);
		Console.Printf("ENCPLAN done");
	}

	private void Run(int index, String type, double x, double y, int level)
	{
		RunAt(index, 50000 + index * 3, (index * 7) % 62, type, x, y, level);
	}

	private void RunAt(int index, int locationId, int region, String type, double x, double y, int level)
	{
		let req = new("DoomerfallEncounterRequest");
		req.dungeonIndex = index;
		req.locationId = locationId;
		req.locationName = "Fake " .. index;
		req.regionIndex = region;
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
		Console.Printf("ENCPLAN plan idx=%d type=%s level=%d order=%d genes=%s themed=%s civilwar=%d tierlean=%d size=%d placement=%s awareness=%s cell=%d,%d regionkind=%s",
			index, p.theme, level, p.order, g, th, p.civilWar, p.tierLean, p.sizePermille, p.placement, p.awareness,
			p.regionCellX, p.regionCellY, p.regionKind >= 0 ? d.kindName[p.regionKind] : "-");
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
		Console.Printf("ENCPLAN army idx=%d side=%s anchorkind=%s anchorthemed=%d coherence=%d tierlean=%d stance=%s theme=%s region=%s entries=%s",
			index, side, a.entries.Size() ? d.kindName[a.anchorKind] : "-", a.anchorThemed, a.coherence, a.tierLean, a.stance,
			a.themeHow, a.regionHow, list);
	}
}
