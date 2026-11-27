// Test hook: with +set dd_encounter_budgettest 1, plans fake dungeons on the first map loaded and prints the budget,
// bosses, titan, squads and every placement's monsters as "ENCBUD" lines, ending with "ENCBUD done".
// tools/encounter_planner/run_budget_test.py runs it and checks the output.
class DoomerfallEncounterBudgetTest : StaticEventHandler
{
	bool done;

	override void WorldLoaded(WorldEvent e)
	{
		if (done) return;
		let flag = CVar.FindCVar("dd_encounter_budgettest");
		if (!flag || !flag.GetBool()) return;
		done = true;
		let pool = DoomerfallEncounterPool.Get();
		if (!pool) { Console.Printf("ENCBUD error no-pool"); Console.Printf("ENCBUD done"); return; }
		Console.Printf("ENCBUD begin pool=%d", pool.monsters.Size());
		int t0 = MSTime();

		// The showcase: full detail. index, type, level, placements, walk known.
		Run(101, "Crypt", 1, 20, true, true);
		Run(102, "Mine", 10, 40, true, true);
		Run(103, "Prison", 10, 30, false, true);
		Run(104, "Coven", 20, 60, true, true);
		Run(105, "HumanStronghold", 30, 100, true, true);
		Run(106, "DragonsDen", 27, 50, true, true);
		Run(107, "DragonsDen", 30, 80, true, true);
		Run(108, "SpiderNest", 30, 8, true, true);
		Run(109, "Laboratory", 0, 3, true, true);
		Run(110, "VampireHaunt", 5, 1, true, true);
		// Titan and boss rates: summaries only.
		for (int k = 0; k < 100; k++)
		{
			Run(1000 + k * 13, "RuinedCastle", 19, 16, true, false);
			Run(1001 + k * 13, "RuinedCastle", 25, 16, true, false);
			Run(1002 + k * 13, "RuinedCastle", 30, 16, true, false);
			Run(1003 + k * 13, "DragonsDen", 25 + k % 6, 24, true, false);
			Run(1004 + k * 13, "Crypt", k % 31, 5 + k % 60, k % 7 != 0, false);
		}
		// The hooks (6.6) on a copy of the level 30 plan.
		Hooks();
		StartRoom();
		Console.Printf("ENCBUD time ms=%d", MSTime() - t0);
		Console.Printf("ENCBUD done");
	}

	static DoomerfallEncounterRequest Fake(int index, String type, int level, int count, bool walk)
	{
		let req = new("DoomerfallEncounterRequest");
		req.dungeonIndex = index;
		req.locationId = 70000 + index * 3;
		req.locationName = "Fake " .. index;
		req.regionIndex = (index * 7) % 62;
		req.regionName = "Region " .. req.regionIndex;
		req.worldX = (index * 53) % 1000;
		req.worldY = (index * 29) % 500;
		req.dungeonType = type;
		req.areaLevel = level;
		// A winding fake dungeon: placements along a path that doubles back, two or three treasure piles.
		int piles = 2 + index % 2;
		Array<double> tx, ty;
		for (int t = 0; t < piles; t++)
		{
			int at = (count - 1) * (t + 2) / (piles + 1);
			tx.Push((at % 10) * 512.0);
			ty.Push((at / 10) * 512.0 + 128);
		}
		for (int i = 0; i < count; i++)
		{
			let p = new("DoomerfallEncounterPlacement");
			int h = DoomerfallEncounterRng.Combine(index * 977, i);
			p.idHi = h & 0x1FFFFF;
			p.idLo = DoomerfallEncounterRng.Mix(h + 12345);
			p.x = (i % 10) * 512.0 + (h & 63);
			p.y = (i / 10) * 512.0 + ((h >>> 8) & 63);
			p.z = 0;
			p.dfEnemyType = i % 40;
			p.quest = i == 3;
			p.walk = walk ? i * 400.0 + ((h >>> 16) & 255) : -1;
			p.treasure = -1;
			for (int t = 0; t < piles; t++)
			{
				double d = sqrt((p.x - tx[t]) ** 2 + (p.y - ty[t]) ** 2);
				if (p.treasure < 0 || d < p.treasure) p.treasure = d;
			}
			// One placement in seven is a narrow spot where only small monsters fit.
			p.fitRadius = i % 7 == 5 ? 24 : 0;
			p.fitHeight = i % 7 == 5 ? 60 : 0;
			req.placements.Push(p);
		}
		return req;
	}

	// The PlainHumanoid start room: Privateer's Hold's facts with placement 0 in the room the cave opens into, 1 on the
	// floor below (its real neighbour, outside the radius) and 2 just outside the radius. Prints each placement's role and
	// classes, then a Move with every placement but the start room full (it must not land there).
	static void StartRoom()
	{
		for (int s = 0; s < 13; s++)
		{
			let req = Fake(1506, "PlainHumanoid", 1, 42, true);
			req.locationId = 50050;
			req.regionIndex = 17;
			req.seedOffset = s;
			req.placements[0].x = 563; req.placements[0].y = 1419; req.placements[0].z = 960;
			req.placements[1].x = 458; req.placements[1].y = 1292; req.placements[1].z = 576;
			req.placements[2].x = 510; req.placements[2].y = 1672 - 420; req.placements[2].z = 960;
			let p = DoomerfallEncounterPlanner.Plan(req);
			for (int i = 0; p && i < p.placements.Size(); i++)
			{
				String cls = "";
				for (int k = 0; k < p.placements[i].mooks.Size(); k++) cls = cls .. (k ? "," : "") .. p.placements[i].mooks[k].m.cls.GetClassName();
				Console.Printf("ENCBUD startroom seed=%d p=%d role=%s classes=%s", s, i, p.placements[i].role, cls);
			}
			Array<bool> full;
			for (int i = 0; p && i < p.placements.Size(); i++) full.Push(i != 0);
			if (p) Console.Printf("ENCBUD startmove seed=%d to=%d", s, DoomerfallEncounterPlanner.Move(p, 1, 500, full));
		}
	}

	static String Hex(int hi, int lo) { return String.Format("%08x%08x", hi, lo); }

	// A digest of every mook (class, member, ID) to compare runs.
	static int Digest(DoomerfallEncounterPlan p)
	{
		int h = 17;
		for (int i = 0; i < p.placements.Size(); i++)
		{
			let pl = p.placements[i];
			for (int k = 0; k < pl.mooks.Size(); k++)
			{
				let m = pl.mooks[k];
				h = DoomerfallEncounterRng.Combine(h, DoomerfallEncounterRng.StringHash(m.m.cls.GetClassName()));
				h = DoomerfallEncounterRng.Combine(h, m.idHi);
				h = DoomerfallEncounterRng.Combine(h, m.idLo);
			}
			h = DoomerfallEncounterRng.Combine(h, pl.budget);
		}
		return h;
	}

	private void Run(int index, String type, int level, int count, bool walk, bool detail)
	{
		let req = Fake(index, type, level, count, walk);
		let p = DoomerfallEncounterPlanner.Plan(req);
		if (!p) { Console.Printf("ENCBUD error no-plan idx=%d", index); return; }
		let again = DoomerfallEncounterPlanner.Plan(Fake(index, type, level, count, walk));
		int digest = Digest(p), digest2 = again ? Digest(again) : 0;
		let d = DoomerfallEncounterPool.Get().data;
		String bosses = "";
		for (int i = 0; i < p.bosses.Size(); i++) bosses = bosses .. (i ? "," : "") .. p.bosses[i];
		int cheapest = 0;
		for (int i = 0; i < DoomerfallEncounterPool.Get().monsters.Size(); i++)
		{
			let m = DoomerfallEncounterPool.Get().monsters[i];
			if (m.capped || DoomerfallEncounterPlanner.Cost(m) <= 0) continue;
			if (!cheapest || DoomerfallEncounterPlanner.Cost(m) < cheapest) cheapest = DoomerfallEncounterPlanner.Cost(m);
		}
		int maxPack = 0, lone = 0;
		String why = p.titanWhy;
		why.Replace(" ", "_");
		for (int i = 0; i < p.placements.Size(); i++) { maxPack = max(maxPack, p.placements[i].mooks.Size()); lone += p.placements[i].mooks.Size() == 1; }
		Console.Printf("ENCBUD plan idx=%d type=%s level=%d n=%d walk=%d detail=%d civilwar=%d size=%d swing=%d novelty=%d exceptions=%d tierlean=%d avg=%d pool=%d reserve=%d boss=%d titan=%d split=%d spent=%d leftover=%d cheapest=%d normalpack=%d lonerate=%d giantrate=%d jitter=%d bossstyle=%s bosses=%s titanat=%d titanclass=%s titanwhy=%s emptywing=%d squads=%d mooks=%d maxpack=%d lone=%d digest=%d digest2=%d",
			index, p.theme, level, count, walk, detail, p.civilWar, p.sizePermille, p.genes[7], p.genes[8], p.genes[9], p.tierLean,
			p.avgPoints, p.poolPoints, p.reservePoints, p.bossPoints, p.titanPoints, p.splitPoints, p.spentPoints, p.leftoverPoints,
			cheapest, p.normalPack, p.loneRate, p.giantRate, p.jitter, p.bossStyle, bosses == "" ? "-" : bosses, p.titanPlacement,
			p.titan ? "" .. p.titan.cls.GetClassName() : "none", why, p.emptyWing, p.squads.Size(), p.MookCount(), maxPack, lone, digest, digest2);
		for (int i = 0; i < p.warnings.Size(); i++) Console.Printf("ENCBUD warn idx=%d %s", index, p.warnings[i]);
		if (!detail) return;
		for (int i = 0; i < p.squads.Size(); i++)
		{
			let s = p.squads[i];
			String list = "";
			for (int k = 0; k < s.members.Size(); k++) list = list .. (k ? "|" : "") .. s.members[k].cls.GetClassName() .. ":" .. s.weights[k];
			Console.Printf("ENCBUD squad idx=%d k=%d side=%d uses=%d note=%s members=%s", index, i, s.side, s.uses, s.note == "" ? "-" : s.note, list);
		}
		for (int i = 0; i < p.placements.Size(); i++)
		{
			let pl = p.placements[i];
			let at = req.placements[i];
			// Monsters as class x count in first-seen order, members checked to run 0..n-1.
			Array<String> names;
			Array<int> counts;
			bool membersOk = true, fitsOk = pl.mooks.Size() > 0 && DoomerfallEncounterPlanner.Fits(pl.mooks[0].m, at);
			for (int k = 0; k < pl.mooks.Size(); k++)
			{
				let m = pl.mooks[k];
				if (m.member != k) membersOk = false;
				String n = m.m.cls.GetClassName();
				int f = names.Find(n);
				if (f == names.Size()) { names.Push(n); counts.Push(1); } else counts[f]++;
			}
			String list = "";
			for (int k = 0; k < names.Size(); k++)
			{
				class<Actor> c = names[k];
				int cost = 0;
				for (int q = 0; q < pl.mooks.Size(); q++) if (pl.mooks[q].m.cls == c) { cost = pl.mooks[q].cost; break; }
				list = list .. (k ? "|" : "") .. names[k] .. "x" .. counts[k] .. "@" .. cost;
			}
			int last = pl.mooks.Size() - 1;
			Console.Printf("ENCBUD place idx=%d p=%d role=%s surprise=%s side=%d awake=%d ambush=%d squad=%d squad2=%d reserve=%d reservecls=%s budget=%d spent=%d n=%d walk=%d treasure=%d fit=%d members=%d leaderfits=%d hash=%s id0=%s idlast=%s mooks=%s",
				index, i, pl.role, pl.surprise == "" ? "-" : pl.surprise, pl.side, pl.awake, pl.ambush, pl.squad, pl.squad2, pl.reserve,
				pl.reserveMonster ? "" .. pl.reserveMonster.cls.GetClassName() : "none", pl.budget, pl.spent, pl.mooks.Size(), int(at.walk),
				int(at.treasure), int(at.fitRadius), membersOk, fitsOk, Hex(at.idHi, at.idLo),
				last >= 0 ? Hex(pl.mooks[0].idHi, pl.mooks[0].idLo) : "-", last >= 0 ? Hex(pl.mooks[last].idHi, pl.mooks[last].idLo) : "-", list);
		}
	}

	// Promote the biggest pack of the level 30 plan to 5 monsters and Move what does not fit; then Move with every
	// placement full, which must drop and report the points.
	private void Hooks()
	{
		let p = DoomerfallEncounterPlanner.Plan(Fake(105, "HumanStronghold", 30, 100, true));
		if (!p) return;
		int big = 0;
		for (int i = 0; i < p.placements.Size(); i++) if (p.placements[i].mooks.Size() > p.placements[big].mooks.Size()) big = i;
		let pl = p.placements[big];
		int before = pl.mooks.Size(), spentBefore = pl.spent, totalBefore = p.spentPoints;
		int left = DoomerfallEncounterPlanner.Promote(p, big, 5);
		int after = pl.mooks.Size();
		Array<bool> full;
		for (int i = 0; i < p.placements.Size(); i++) full.Push(false);
		full[big] = true;
		int to = DoomerfallEncounterPlanner.Move(p, big, left, full);
		int sum = 0;
		for (int i = 0; i < p.placements.Size(); i++) sum += p.placements[i].spent;
		Console.Printf("ENCBUD promote p=%d before=%d after=%d spentbefore=%d spentafter=%d returned=%d moveto=%d totalbefore=%d totalafter=%d sum=%d pool=%d leftover=%d",
			big, before, after, spentBefore, pl.spent, left, to, totalBefore, p.spentPoints, sum, p.poolPoints, p.leftoverPoints);
		for (int i = 0; i < full.Size(); i++) full[i] = true;
		int dropped = DoomerfallEncounterPlanner.Move(p, 0, 500, full);
		Console.Printf("ENCBUD movefull to=%d dropped=%d", dropped, p.movedDropped);
	}
}
