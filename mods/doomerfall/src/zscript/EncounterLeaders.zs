// Encounters, card 4: the bridge's entry point to the planner. UZDoom's dd_monsters.cpp collects a converted
// dungeon's encounter markers and Daggerfall's area facts (bridge kinds 55 and 56) into a text request, calls
// PlanText, and spawns what it returns. Until the placer (card 5) lands, only each placement's leader is spawned.
//
// Request, one record per line, fields separated by tabs:
//   area      dungeonIndex locationId regionIndex worldX worldY dungeonType areaLevel seedOffset
//   location  name
//   region    name
//   p         idHi idLo x y z dfEnemyType quest       (one per placement, in placement hash order)
// Answer: a summary line starting "plan", then one line per request placement in request order, separated by spaces:
//   index className idHi idLo role mooks
// className is "-" when the plan gave the placement no monster. An empty answer means no plan (no pool loaded).

class DoomerfallEncounterLeaders play
{
	static String PlanText(String text)
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
				// Card 5 measures these. Unknown for now.
				p.walk = -1;
				p.treasure = -1;
				p.fitRadius = 0;
				p.fitHeight = 0;
				req.placements.Push(p);
			}
		}
		let plan = DoomerfallEncounterPlanner.Plan(req);
		if (!plan) return "";

		Array<String> rows;
		for (int i = 0; i < req.placements.Size(); i++) rows.Push(String.Format("%d - 0 0 none 0", i));
		for (int i = 0; i < plan.placements.Size(); i++)
		{
			let pp = plan.placements[i];
			if (pp.index < 0 || pp.index >= rows.Size() || !pp.mooks.Size()) continue;
			let leader = pp.mooks[0];
			rows[pp.index] = String.Format("%d %s %d %d %s %d", pp.index, leader.m.cls.GetClassName(), leader.idHi, leader.idLo, pp.role, pp.mooks.Size());
		}
		String answer = String.Format("plan genes %d theme %s civilwar %d pool %d mooks %d\n", plan.order, plan.theme, plan.civilWar ? 1 : 0, plan.poolPoints, plan.MookCount());
		for (int i = 0; i < rows.Size(); i++) answer = answer .. rows[i] .. "\n";
		return answer;
	}
}
