// Encounters, cards 4 and 5: the bridge between UZDoom's placer (dd_encounter_placer.cpp) and the planner. UZDoom
// collects a converted dungeon's encounter markers, measures each one (walking distance from the entrance, nearest
// treasure, what fits at the origin), and with Daggerfall's area facts (bridge kinds 55 and 56) builds a text request.
// PlanObject plans it and hands the plan object back; the placer then reads each placement's mooks and calls the
// planner's hooks (leader, promote, drop, move) while it finds spots. Nothing here spawns.
//
// Request, one record per line, fields separated by tabs:
//   area      dungeonIndex locationId regionIndex worldX worldY dungeonType areaLevel seedOffset
//   location  name
//   region    name
//   p         idHi idLo x y z dfEnemyType quest walk treasure fitRadius fitHeight   (one per placement, in order)
// Mooks answer: the placement's role, then one line per mook in member order, separated by spaces:
//   member className idHi idLo cost

class DoomerfallEncounterLeaders play
{
	static DoomerfallEncounterPlan PlanObject(String text)
	{
		let req = new("DoomerfallEncounterRequest");
		Array<String> lines;
		text.Split(lines, "\n", TOK_SKIPEMPTY);
		for (int i = 0; i < lines.Size(); i++)
		{
			Array<String> f;
			lines[i].Split(f, "\t");
			if (f.Size() < 2) continue;
			if (f[0] == "area" && f.Size() >= 9)
			{
				req.dungeonIndex = f[1].ToInt();
				req.locationId = f[2].ToInt();
				req.regionIndex = f[3].ToInt();
				req.worldX = f[4].ToDouble();
				req.worldY = f[5].ToDouble();
				req.dungeonType = f[6];
				req.areaLevel = f[7].ToInt();
				req.seedOffset = f[8].ToInt();
			}
			else if (f[0] == "location") req.locationName = f[1];
			else if (f[0] == "region") req.regionName = f[1];
			else if (f[0] == "p" && f.Size() >= 8)
			{
				let p = new("DoomerfallEncounterPlacement");
				p.idHi = f[1].ToInt();
				p.idLo = f[2].ToInt();
				p.x = f[3].ToDouble();
				p.y = f[4].ToDouble();
				p.z = f[5].ToDouble();
				p.dfEnemyType = f[6].ToInt();
				p.quest = f[7].ToInt() != 0;
				p.walk = f.Size() > 8 ? f[8].ToDouble() : -1;
				p.treasure = f.Size() > 9 ? f[9].ToDouble() : -1;
				p.fitRadius = f.Size() > 10 ? f[10].ToDouble() : 0;
				p.fitHeight = f.Size() > 11 ? f[11].ToDouble() : 0;
				req.placements.Push(p);
			}
		}
		return DoomerfallEncounterPlanner.Plan(req);
	}

	static String Summary(DoomerfallEncounterPlan plan)
	{
		String bosses = "";
		for (int i = 0; i < plan.bosses.Size(); i++) bosses = bosses .. (i ? "," : "") .. plan.bosses[i];
		String s = String.Format("plan genes %d theme %s civilwar %d pool %d spent %d mooks %d moved-dropped %d bosses %s titan %d leftover %d titanclass %s",
			plan.order, plan.theme, plan.civilWar ? 1 : 0, plan.poolPoints, plan.spentPoints, plan.MookCount(), plan.movedDropped,
			bosses == "" ? "-" : bosses, plan.titanPlacement, plan.leftoverPoints, plan.titan ? plan.titan.cls.GetClassName() : 'none');
		for (int i = 0; i < plan.warnings.Size(); i++) s = s .. "\nwarning " .. plan.warnings[i];
		return s;
	}

	static int PlacementCount(DoomerfallEncounterPlan plan) { return plan.placements.Size(); }

	static String Mooks(DoomerfallEncounterPlan plan, int index)
	{
		if (index < 0 || index >= plan.placements.Size()) return "";
		let p = plan.placements[index];
		String s = p.role .. "\n";
		for (int i = 0; i < p.mooks.Size(); i++)
		{
			let k = p.mooks[i];
			s = s .. String.Format("%d %s %d %d %d\n", k.member, k.m.cls.GetClassName(), k.idHi, k.idLo, k.cost);
		}
		return s;
	}

	// Card 6: -1 in a united dungeon, else the placement's army (0 or 1) | Thing_Hate stance toward the player << 4.
	// A local war surprise room (side 2) is only in united dungeons and stays unrigged.
	static int Faction(DoomerfallEncounterPlan plan, int index)
	{
		if (!plan.civilWar || !plan.b || index < 0 || index >= plan.placements.Size()) return -1;
		int side = plan.placements[index].side;
		if (side != 0 && side != 1) return -1;
		return side | (DoomerfallCivilWar.StanceOf(side ? plan.b.stance : plan.a.stance) << 4);
	}

	static void MakeLeader(DoomerfallEncounterPlan plan, int index, int which) { DoomerfallEncounterPlanner.MakeLeader(plan, index, which); }
	static int CheapestLeader(DoomerfallEncounterPlan plan, int index) { return DoomerfallEncounterPlanner.CheapestLeader(plan, index); }
	static int Promote(DoomerfallEncounterPlan plan, int index, int maxCount) { return DoomerfallEncounterPlanner.Promote(plan, index, maxCount); }
	static int Drop(DoomerfallEncounterPlan plan, int index, int keep) { return DoomerfallEncounterPlanner.Drop(plan, index, keep); }

	// full: one character per placement, '1' for a placement that has no room left.
	static int Move(DoomerfallEncounterPlan plan, int from, int points, String full)
	{
		Array<bool> f;
		for (int i = 0; i < full.Length(); i++) f.Push(full.ByteAt(i) == 0x31);
		return DoomerfallEncounterPlanner.Move(plan, from, points, f);
	}
}
