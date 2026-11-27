// Encounter planner, part 2: the budget, bosses, titans, the uneven split, squads and mook IDs (encounter design
// sections 6, 7 and 9.2: work/notes/20261123-205402-fractal-encounter-variety.md). Still pure: nothing spawns.
//
// Points are integers in hundredths ("centipoints") so every choice stays integer. Monsters cost their pool points.
// The walk distance, nearby treasure and what fits at each placement are inputs measured by the placer (card 5).

// One Daggerfall enemy placement, as the map and Daggerfall describe it.
class DoomerfallEncounterPlacement
{
	int idHi, idLo;          // the placement hash (EnemyRoster.Hash / DoomerfallMonsters.PlacementHash) as two 32-bit halves
	double x, y, z;          // Doom coordinates of the placement's origin
	int dfEnemyType;         // the Daggerfall enemy type it replaces
	bool quest;              // a quest uses it
	double walk;             // walking distance from the entrance, < 0 when unknown
	double treasure;         // distance to the nearest treasure pile, < 0 when there is none or it is unknown
	double fitRadius;        // largest monster radius that fits at the origin, 0 when not measured
	double fitHeight;        // largest monster height that fits at the origin, 0 when not measured
}

class DoomerfallPlannedMook
{
	DoomerfallMonster m;
	int member;              // number within the placement, 0 .. 4095
	int idHi, idLo;          // the 64-bit mook ID: tag 5 (3 bits) | placement hash (49) | member (12)
	int cost;                // centipoints
}

// A recurring squad recipe (section 7): army monsters and their relative weights.
class DoomerfallSquad
{
	int side;                // 0 army A, 1 army B
	Array<DoomerfallMonster> members;
	Array<int> weights;
	int uses;
	String note;             // "" for an ordinary squad, else the surprise it was made for
}

class DoomerfallPlannedPlacement
{
	int index;               // into request.placements
	String role;             // normal, lone, giant, boss, miniboss, titan, surprise
	String surprise;         // for role surprise: wrongtier, wrongarmy, lonebrute, swarm, sleepinghorde, localwar
	int side;                // 0 army A, 1 army B, 2 local war (both armies, hostile to each other)
	bool awake, ambush;
	int squad, squad2;       // squads used, -1 when none
	int reserve;             // centipoints set aside so the placement always keeps one monster
	DoomerfallMonster reserveMonster;
	int budget;              // centipoints given to the placement
	int spent;               // centipoints actually bought
	int nextMember;
	Array<DoomerfallPlannedMook> mooks;
}

extend class DoomerfallEncounterPlanner
{
	// Must match DFB_MONSTER_MEMBER_BITS in bridge/doomerfall_bridge.h.
	const MOOK_MEMBER_BITS = 12;
	const MOOK_MAX_MEMBERS = 4096;

	// The 64-bit mook ID as two halves: tag 5 | (hash & (2^49 - 1)) << 12 | member.
	static void MookId(int hashHi, int hashLo, int member, out int idHi, out int idLo)
	{
		idHi = (5 << 29) | ((hashHi & 0x1FFFF) << 12) | (hashLo >>> 20);
		idLo = (hashLo << 12) | (member & 0xFFF);
	}

	static int Cost(DoomerfallMonster m) { return max(1, int(m.points * 100 + 0.5)); }

	// Fits at a placement's origin by the placer's measurement (0 means not measured: everything fits).
	static bool Fits(DoomerfallMonster m, DoomerfallEncounterPlacement p)
	{
		return (p.fitRadius <= 0 || m.radius <= p.fitRadius) && (p.fitHeight <= 0 || m.height <= p.fitHeight);
	}

	DoomerfallArmy Side(int side) { return side == 1 && result.b ? result.b : result.a; }

	// ---- The budget (section 6) ----

	private void Budget()
	{
		int n = req.placements.Size();
		result.avgPoints = int(data.AveragePoints(clamp(req.areaLevel, 0, 30)) * 100 + 0.5);
		result.poolPoints = result.avgPoints * n;
		result.titanPlacement = -1;
		result.titanWhy = "none";
		result.bossStyle = "-";
		if (!n || !result.a || !result.a.entries.Size()) return;

		let sideRng = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_SIDE);
		let awareRng = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_AWARE);
		for (int i = 0; i < n; i++)
		{
			let p = new("DoomerfallPlannedPlacement");
			p.index = i;
			p.role = "normal";
			p.surprise = "";
			p.side = result.civilWar && result.b ? sideRng.Next(2) : 0;
			p.squad = -1;
			p.squad2 = -1;
			Awareness(p, awareRng);
			result.placements.Push(p);
		}
		Reserve();
		ChooseBosses();
		Titan();
		Split();
		Fill();
		StartRoom();
		Finish();
	}

	// The theme's start room (owner, 2026-11-26): start=<exact classes> startat=<x,y,z> startradius=<map units>.
	// Placements whose origin is within the radius of the story start point (Privateer's Hold: the cave a new character
	// wakes in; the placer's walk distances start at the exit door instead) keep their number of monsters, but each
	// becomes one of the start classes the pool has, so the game's first fight is easy (battle rifle Former Humans, who
	// drop battle rifles). The points this saves stay unspent (leftover). Bosses and titans there are replaced too.
	void StartMonsters(out Array<DoomerfallMonster> list)
	{
		list.Clear();
		if (!theme || !theme.known) return;
		Array<String> names;
		String s = data.ThemeGet(theme.name, "start");
		s.Split(names, ",", TOK_SKIPEMPTY);
		for (int n = 0; n < names.Size(); n++)
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				String cn = pool.monsters[i].cls.GetClassName();
				if (cn ~== names[n]) list.Push(pool.monsters[i]);
			}
	}

	private void StartRoom()
	{
		if (!theme.known) return;
		double reach = data.ThemeGet(theme.name, "startradius").ToDouble();
		Array<String> xyz;
		String s = data.ThemeGet(theme.name, "startat");
		s.Split(xyz, ",", TOK_SKIPEMPTY);
		if (reach <= 0 || xyz.Size() != 3) return;
		Vector3 from = (xyz[0].ToDouble(), xyz[1].ToDouble(), xyz[2].ToDouble());
		Array<DoomerfallMonster> start;
		StartMonsters(start);
		if (!start.Size()) { result.warnings.Push("start room: no start class in the pool"); return; }
		let r = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_START);
		for (int i = 0; i < result.placements.Size(); i++)
		{
			let at = req.placements[i];
			if (((at.x, at.y, at.z) - from).Length() > reach) continue;
			let p = result.placements[i];
			if (i == result.titanPlacement) { result.titanPlacement = -1; result.titan = null; result.titanWhy = "start room"; }
			int b = result.bosses.Find(i);
			if (b != result.bosses.Size()) result.bosses.Delete(b);
			p.role = "start";
			p.surprise = "";
			p.squad = -1;
			p.squad2 = -1;
			p.spent = 0;
			for (int k = 0; k < p.mooks.Size(); k++)
			{
				let mk = p.mooks[k];
				mk.m = start[r.Next(start.Size())];
				mk.cost = Cost(mk.m);
				p.spent += mk.cost;
			}
		}
	}

	// Section 9.2: whether a placement starts awake, from the awareness gene's meaning.
	private void Awareness(DoomerfallPlannedPlacement p, DoomerfallEncounterRng r)
	{
		String a = result.awareness;
		int awake = 500;
		if (a ~== "asleep") awake = 0;
		else if (a ~== "mostlyasleep") awake = 250;
		else if (a ~== "mostlyalert") awake = 750;
		else if (a ~== "alert") awake = 1000;
		else if (a ~== "sentries") awake = 400;
		int roll = r.Next(1000);
		p.ambush = a ~== "ambush";
		p.awake = !p.ambush && roll < awake;
	}

	// 6.2 step 1: every placement keeps one monster. The cheapest army monster that fits there, else the cheapest pool
	// monster that fits, else the cheapest pool monster (it becomes the leader, 9.3). If the reserve alone exceeds the
	// pool (an army of expensive monsters at a low level), the dearest reserves fall back to the pool's cheapest.
	private void Reserve()
	{
		int total = 0;
		for (int i = 0; i < result.placements.Size(); i++)
		{
			let p = result.placements[i];
			let at = req.placements[i];
			let m = Cheapest(Side(p.side), at, p.side == 1 || result.civilWar);
			if (!m) m = CheapestPool(at, result.civilWar);
			p.reserveMonster = m;
			p.reserve = m ? Cost(m) : 0;
			total += p.reserve;
		}
		result.reservePoints = total;
		ShrinkReserve(result.poolPoints, -1);
		total = result.reservePoints;
		if (total > result.poolPoints) result.warnings.Push("reserve exceeds the pool: every placement's cheapest monster costs more than the level's average");
		result.reservePoints = total;
	}

	// Downgrades the dearest reserves to the pool's cheapest monster until the reserve is at most `limit`.
	private void ShrinkReserve(int limit, int skip)
	{
		while (result.reservePoints > limit)
		{
			int worst = -1, gain = 0;
			for (int i = 0; i < result.placements.Size(); i++)
			{
				let p = result.placements[i];
				let c = CheapestPool(req.placements[i], result.civilWar);
				if (i != skip && c && p.reserve - Cost(c) > gain) { gain = p.reserve - Cost(c); worst = i; }
			}
			if (worst < 0) break;
			let p = result.placements[worst];
			p.reserveMonster = CheapestPool(req.placements[worst], result.civilWar);
			p.reserve = Cost(p.reserveMonster);
			result.reservePoints -= gain;
		}
	}

	DoomerfallMonster Cheapest(DoomerfallArmy army, DoomerfallEncounterPlacement at, bool civil)
	{
		DoomerfallMonster best = null;
		for (int i = 0; i < army.entries.Size(); i++)
		{
			let m = army.entries[i].m;
			if (Fits(m, at) && (!best || Cost(m) < Cost(best))) best = m;
		}
		return best;
	}

	DoomerfallMonster CheapestPool(DoomerfallEncounterPlacement at, bool civil)
	{
		DoomerfallMonster best = null, any = null;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			if (!Usable(m, civil) || m.capped) continue;
			if (!any || Cost(m) < Cost(any)) any = m;
			if ((!at || Fits(m, at)) && (!best || Cost(m) < Cost(best))) best = m;
		}
		return best ? best : any;
	}

	// ---- Bosses (6.4) ----

	private void ChooseBosses()
	{
		int n = result.placements.Size();
		let r = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_BOSS);
		int per = max(1, int(data.Value("boss_placements_per", 15)));
		int lo = int(data.Value("boss_min", 1)), hi = int(data.Value("boss_max", 4));
		int count = clamp((n + per / 2) / per + r.Next(3) - 1, lo, hi);
		// Style: one strong boss, several minibosses, or a strong deepest boss with minibosses.
		int style = r.Next(3);
		if (style == 0) { result.bossStyle = "strong"; count = 1; }
		else if (style == 1) { result.bossStyle = "minis"; count = clamp(max(count, n >= 4 ? 2 : 1), lo, hi); }
		else result.bossStyle = "both";
		count = min(count, n);

		// Where: the deepest boss at the far placement nearest treasure, others far-flung, near treasure, spaced apart.
		double maxWalk = -1;
		for (int i = 0; i < n; i++) maxWalk = max(maxWalk, req.placements[i].walk);
		Array<int> chosen;
		if (maxWalk > 0)
		{
			int deepest = -1;
			double bestT = 0;
			for (int i = 0; i < n; i++)
			{
				let at = req.placements[i];
				if (at.walk < maxWalk * 0.75 || at.treasure < 0) continue;
				if (deepest < 0 || at.treasure < bestT) { deepest = i; bestT = at.treasure; }
			}
			if (deepest < 0)
				for (int i = 0; i < n; i++) if (req.placements[i].walk == maxWalk) { deepest = i; break; }
			chosen.Push(deepest);
			while (chosen.Size() < count)
			{
				int best = -1, bestScore = -1;
				for (int i = 0; i < n; i++)
				{
					if (chosen.Find(i) != chosen.Size()) continue;
					let at = req.placements[i];
					int score = int(max(0., at.walk) / maxWalk * 1000);
					if (at.treasure >= 0) score += int(500 * (1 - min(at.treasure, 1024.) / 1024));
					score += min(1000, int(NearestChosen(chosen, i) / 2048 * 1000));
					if (score > bestScore) { bestScore = score; best = i; }
				}
				if (best < 0) break;
				chosen.Push(best);
			}
		}
		else
		{
			// No walking distance: random, spread-out placements.
			chosen.Push(r.Next(n));
			while (chosen.Size() < count)
			{
				int best = -1;
				double bestD = -1;
				for (int i = 0; i < n; i++)
				{
					if (chosen.Find(i) != chosen.Size()) continue;
					double d = NearestChosen(chosen, i);
					if (d > bestD) { bestD = d; best = i; }
				}
				if (best < 0) break;
				chosen.Push(best);
			}
			result.warnings.Push("no walking distances: bosses placed at random spread-out placements");
		}

		double smin = data.Value("boss_share_min", 4), smax = data.Value("boss_share_max", 8);
		double mmin = data.Value("miniboss_share_min", 2), mmax = data.Value("miniboss_share_max", 4);
		int total = 0;
		for (int k = 0; k < chosen.Size(); k++)
		{
			let p = result.placements[chosen[k]];
			bool strong = result.bossStyle == "strong" || (result.bossStyle == "both" && k == 0);
			p.role = strong ? "boss" : "miniboss";
			int lo10 = int((strong ? smin : mmin) * 10), hi10 = int((strong ? smax : mmax) * 10);
			int mult10 = lo10 + r.Next(hi10 - lo10 + 1);
			p.budget = max(p.reserve, result.avgPoints * mult10 / 10);
			total += p.budget - p.reserve;
			result.bosses.Push(chosen[k]);
		}
		// Bosses take at most half of the free points; scale down if a small dungeon cannot pay.
		int free = result.poolPoints - result.reservePoints;
		int cap = max(0, free / 2);
		if (total > cap && total > 0)
		{
			int given = 0;
			for (int k = 0; k < result.bosses.Size(); k++)
			{
				let p = result.placements[result.bosses[k]];
				int extra = int(double(p.budget - p.reserve) * cap / total);
				p.budget = p.reserve + extra;
				given += extra;
			}
			total = given;
		}
		result.bossPoints = total;
	}

	double NearestChosen(Array<int> chosen, int i)
	{
		double best = 1e9;
		let a = req.placements[i];
		for (int k = 0; k < chosen.Size(); k++)
		{
			let b = req.placements[chosen[k]];
			best = min(best, (a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
		}
		return best >= 1e9 ? 1e9 : sqrt(best);
	}

	// ---- Black and White titans (6.3) ----

	private void Titan()
	{
		let r = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_TITAN);
		int roll = r.Next(1000);
		int chance = int(data.TitanChanceAt(req.areaLevel) * 1000 + 0.5);
		bool den = theme.titan ~== "always" && req.areaLevel >= int(data.Value("titan_dragon_den_level", 25)) && result.bosses.Size();
		if (!den && roll >= chance) { result.titanWhy = chance ? String.Format("roll %d >= %d", roll, chance) : "below level"; return; }

		int limit = int(result.poolPoints * data.Value("titan_max_pool_share", 0.40));
		int free = result.poolPoints - result.reservePoints - result.bossPoints;
		// Where: a random non-boss placement it fits at, or the deepest boss in a Dragon's Den.
		int at = -1;
		if (den) at = result.bosses[0];
		Array<int> titans;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			if (!(m.group ~== "EX") || (result.civilWar && !m.civilWarSafe) || !ThemeAllows(m)) continue;
			titans.Push(i);
		}
		if (!titans.Size()) { result.titanWhy = result.civilWar ? "no Civil War safe titan loaded" : "no titan loaded"; return; }
		if (!den)
		{
			Array<int> spots;
			for (int i = 0; i < result.placements.Size(); i++)
				if (result.placements[i].role == "normal") spots.Push(i);
			if (!spots.Size()) { result.titanWhy = "no non-boss placement"; return; }
			// Start at a random spot and take the first one some titan fits at.
			int start = r.Next(spots.Size());
			for (int k = 0; k < spots.Size() && at < 0; k++)
			{
				int s = spots[(start + k) % spots.Size()];
				for (int t = 0; t < titans.Size(); t++)
					if (Fits(pool.monsters[titans[t]], req.placements[s])) { at = s; break; }
			}
			if (at < 0) { result.titanWhy = "no titan fits anywhere"; return; }
		}
		let p = result.placements[at];
		int refund = den ? 0 : p.reserve;
		if (den)
		{
			// A Dragon's Den always has its titan: if an expensive army's reserve leaves no room, the dearest reserves
			// fall back to the pool's cheapest monster until the cheapest titan that fits is affordable.
			int need = 0;
			for (int t = 0; t < titans.Size(); t++)
			{
				let m = pool.monsters[titans[t]];
				if (Fits(m, req.placements[at]) && Cost(m) <= limit && (!need || Cost(m) < need)) need = Cost(m);
			}
			if (need > free)
			{
				int before = result.reservePoints;
				ShrinkReserve(result.poolPoints - result.bossPoints - need, -1);
				free += before - result.reservePoints;
			}
		}
		Array<int> w;
		for (int t = 0; t < titans.Size(); t++)
		{
			let m = pool.monsters[titans[t]];
			int c = Cost(m);
			w.Push(Fits(m, req.placements[at]) && c <= limit && c <= free + refund ? 1 : 0);
		}
		int pick = r.Pick(w);
		if (pick < 0) { result.titanWhy = den ? "dragon's den cannot afford one within the pool share" : "cannot afford one within the pool share"; if (den) result.warnings.Push("dragon's den: no affordable titan"); return; }
		result.titan = pool.monsters[titans[pick]];
		result.titanPlacement = at;
		result.titanPoints = Cost(result.titan) - refund;
		result.titanWhy = den ? "dragon's den" : String.Format("roll %d < %d", roll, chance);
		if (!den) { p.role = "titan"; p.budget = Cost(result.titan); }
	}

	// ---- The uneven split (6.2 step 4) and surprise rooms (7.1) ----

	private void Split()
	{
		let r = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_SPLIT);
		let sr = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_SURPRISE);
		int swing = result.genes[G_SWING], exc = result.genes[G_EXCEPTIONS];
		result.loneRate = int(data.Value("split_lone_base", 20) + swing * data.Value("split_lone_step", 25));
		result.giantRate = int(data.Value("split_giant_base", 10) + swing * data.Value("split_giant_step", 5));
		result.jitter = int(data.Value("split_jitter_base", 100) + swing * data.Value("split_jitter_step", 40));
		int gmin = int(data.Value("split_giant_min", 5)), gmax = int(data.Value("split_giant_max", 10));
		int surpriseRate = int(exc * data.Value("surprise_step", 10));

		// Empty wing: a seed placement and its nearest neighbours keep only their one monster.
		int n = result.placements.Size();
		if (exc > 0 && n >= 10 && sr.Next(100) < exc * int(data.Value("empty_wing_step", 4)))
		{
			int seed = sr.Next(n);
			int want = max(2, n / 10);
			Array<int> wing;
			wing.Push(seed);
			while (wing.Size() < want)
			{
				int best = -1;
				double bestD = 1e18;
				let s = req.placements[seed];
				for (int i = 0; i < n; i++)
				{
					if (wing.Find(i) != wing.Size()) continue;
					let a = req.placements[i];
					double d = (a.x - s.x) * (a.x - s.x) + (a.y - s.y) * (a.y - s.y);
					if (d < bestD) { bestD = d; best = i; }
				}
				if (best < 0) break;
				wing.Push(best);
			}
			for (int k = 0; k < wing.Size(); k++)
				if (result.placements[wing[k]].role == "normal") { result.placements[wing[k]].role = "lone"; result.placements[wing[k]].surprise = "emptywing"; }
			result.emptyWing = true;
		}

		Array<int> weight;
		int sum = 0;
		for (int i = 0; i < n; i++)
		{
			let p = result.placements[i];
			int w = 0;
			if (p.role == "normal")
			{
				int roll = r.Next(1000);
				if (roll < result.loneRate) { p.role = "lone"; }
				else if (roll < result.loneRate + result.giantRate) { p.role = "giant"; w = 1000 * (gmin + r.Next(gmax - gmin + 1)); }
				else w = max(50, 1000 - result.jitter + r.Next(2 * result.jitter + 1));
				if (p.role != "lone" && sr.Next(1000) < surpriseRate) Surprise(p, sr, w);
			}
			weight.Push(w);
			sum += w;
		}
		int split = max(0, result.poolPoints - result.reservePoints - result.bossPoints - result.titanPoints);
		result.splitPoints = split;
		if (!sum)
		{
			// Nobody has split weight (every placement is a boss, the titan, or lone): the bosses take the split, or
			// failing that every placement but the titan's, evenly. Points are never lost.
			for (int pass = 0; pass < 2 && !sum; pass++)
			{
				for (int i = 0; i < n; i++)
				{
					let p = result.placements[i];
					bool take = pass == 0 ? (p.role == "boss" || p.role == "miniboss") : p.role != "titan";
					if (!take) continue;
					weight[i] = 1000;
					sum += 1000;
				}
			}
			for (int i = 0; i < n; i++)
			{
				let p = result.placements[i];
				if (weight[i] && (p.role == "boss" || p.role == "miniboss")) p.budget += int(double(split) * weight[i] / sum);
			}
		}
		int normals = 0, normalW = 0;
		for (int i = 0; i < n; i++)
		{
			let p = result.placements[i];
			if (p.role == "boss" || p.role == "miniboss" || p.role == "titan") continue;
			int extra = sum ? int(double(split) * weight[i] / sum) : 0;
			p.budget = p.reserve + extra;
			if (p.role == "normal") { normals++; normalW += weight[i]; }
		}
		result.normalPack = sum && normals ? int(double(split) * (normalW / normals) / sum) + result.reservePoints / n : 0;
	}

	// Section 7.1: a room that breaks the pattern, the opposite of the dungeon's own.
	private void Surprise(DoomerfallPlannedPlacement p, DoomerfallEncounterRng r, out int w)
	{
		Array<String> kinds;
		kinds.Push("wrongtier");
		kinds.Push("wrongarmy");
		kinds.Push(result.sizePermille < 500 ? "lonebrute" : "swarm");
		kinds.Push("sleepinghorde");
		if (!result.civilWar) kinds.Push("localwar");
		p.role = "surprise";
		p.surprise = kinds[r.Next(kinds.Size())];
		if (p.surprise == "sleepinghorde") { w = 1000 * int(data.Value("split_giant_min", 5)); p.awake = false; p.ambush = false; }
		if (p.surprise == "localwar") p.side = 2;
	}

	// ---- Filling placements with squads (6.5, section 7) ----

	private void Fill()
	{
		let sq = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_SQUAD);
		let fr = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_FILL);
		int carry = 0;
		// Bosses and the titan first, so the free carry flows into ordinary placements.
		for (int pass = 0; pass < 2; pass++)
		{
			for (int i = 0; i < result.placements.Size(); i++)
			{
				let p = result.placements[i];
				bool special = p.role == "boss" || p.role == "miniboss" || p.role == "titan" || i == result.titanPlacement;
				if (special != (pass == 0)) continue;
				int budget = p.budget + carry;
				if (i == result.titanPlacement)
				{
					AddMook(p, result.titan);
					if (p.role == "titan") { carry = budget - p.spent; continue; }
					budget = p.budget + carry;   // a Dragon's Den boss keeps its boss share for the escort
				}
				else if (p.role == "boss" || p.role == "miniboss")
				{
					let leader = BossLeader(p, budget);
					if (leader) AddMook(p, leader);
					budget -= p.spent;
				}
				carry = FillPlacement(p, budget, MOOK_MAX_MEMBERS, sq, fr);
			}
		}
		// The last carry: the pool's cheapest monsters on the last ordinary placements, so points are never lost.
		for (int i = result.placements.Size() - 1; i >= 0 && carry > 0; i--)
		{
			let p = result.placements[i];
			let c = CheapestPool(req.placements[i], result.civilWar || p.side == 1);
			if (!c) break;
			while (carry >= Cost(c) && p.nextMember < MOOK_MAX_MEMBERS) { AddMook(p, c); carry -= Cost(c); }
		}
		result.leftoverPoints = carry;
	}

	// 6.4: the leader is the strongest army monster that fits, one tier up from the army's usual.
	private DoomerfallMonster BossLeader(DoomerfallPlannedPlacement p, int budget)
	{
		let army = Side(p.side == 2 ? 0 : p.side);
		int want = clamp(army.tierLean + int(data.Value("boss_tier_up", 1)), 1, 8);
		int afford = budget * 3 / 4;
		bool civil = result.civilWar;
		DoomerfallMonster best = null;
		int bestD = 99;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			if (!Usable(m, civil) || m.capped || !KindInArmy(army, m.kind) || !Fits(m, req.placements[p.index]) || Cost(m) > afford) continue;
			int d = m.tier >= want ? m.tier - want : 2 * (want - m.tier);   // prefer the tier above, then higher, then lower
			if (d < bestD || (d == bestD && Cost(m) > Cost(best))) { best = m; bestD = d; }
		}
		if (best) return best;
		for (int i = 0; i < army.entries.Size(); i++)
		{
			let m = army.entries[i].m;
			if (Fits(m, req.placements[p.index]) && Cost(m) <= budget && (!best || Cost(m) > Cost(best))) best = m;
		}
		return best;
	}

	// Pitman-Yor: reuse squad k with weight (uses_k - d), or invent one with weight (theta + d * K). The squad novelty
	// gene scales theta from a quarter to four times squad_strength.
	private int ChooseSquad(int side, DoomerfallEncounterRng r)
	{
		int d = int(data.Value("squad_discount", 0.5) * 1000);
		int theta = int(data.Value("squad_strength", 1) * 1000);
		int nov = result.genes[G_NOVELTY];
		Array<String> scale;
		data.GetList("novelty_theta", scale);
		if (scale.Size() == SETTINGS) theta = theta * scale[nov].ToInt() / 1000;
		Array<int> w;
		int k = 0;
		for (int i = 0; i < result.squads.Size(); i++)
		{
			let s = result.squads[i];
			bool mine = s.side == side && s.note == "";
			w.Push(mine && s.uses > 0 ? max(1, s.uses * 1000 - d) : 0);
			if (mine) k++;
		}
		w.Push(theta + d * k);
		int pick = r.Pick(w);
		if (pick < 0 || pick == result.squads.Size()) return NewSquad(side, "", r);
		return pick;
	}

	private int NewSquad(int side, String note, DoomerfallEncounterRng r)
	{
		let s = new("DoomerfallSquad");
		s.side = side;
		s.note = note;
		let army = Side(side);
		bool civil = result.civilWar;
		if (note == "")
		{
			// 1 to 3 army monsters by share, with weights 1 to 4.
			int count = 1 + r.Next(3);
			Array<int> w;
			for (int i = 0; i < army.entries.Size(); i++) w.Push(army.entries[i].share);
			for (int c = 0; c < count; c++)
			{
				int pick = r.Pick(w);
				if (pick < 0) break;
				w[pick] = 0;
				s.members.Push(army.entries[pick].m);
				s.weights.Push(1 + r.Next(4));
			}
		}
		else if (note == "wrongtier")
		{
			// Army kinds at a tier far from the lean: elite in a standard dungeon, or the reverse.
			bool high = army.tierLean <= 4;
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				if (!Usable(m, civil) || m.capped || !KindInArmy(army, m.kind)) continue;
				if (high ? m.tier >= army.tierLean + 3 : m.tier <= army.tierLean - 3) { s.members.Push(m); s.weights.Push(1); }
			}
		}
		else if (note == "wrongarmy")
		{
			// A squad built around a kind the army does not have.
			Array<int> w;
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				w.Push(Usable(m, civil) && !m.capped && !KindInArmy(army, m.kind) && !KindInArmy(result.a, m.kind) ? 1 : 0);
			}
			int pick = r.Pick(w);
			if (pick >= 0)
			{
				int kind = pool.monsters[pick].kind;
				for (int i = 0; i < pool.monsters.Size(); i++)
					if (w[i] && pool.monsters[i].kind == kind && abs(pool.monsters[i].tier - pool.monsters[pick].tier) <= 1)
					{ s.members.Push(pool.monsters[i]); s.weights.Push(pool.monsters[i] == pool.monsters[pick] ? 3 : 1); }
			}
		}
		if (!s.members.Size())
		{
			// Nothing matched the surprise: fall back to the army's anchor.
			s.members.Push(army.entries[0].m);
			s.weights.Push(1);
		}
		result.squads.Push(s);
		return result.squads.Size() - 1;
	}

	// Buys monsters for one placement. Returns the points it could not spend (the carry).
	private int FillPlacement(DoomerfallPlannedPlacement p, int budget, int maxCount, DoomerfallEncounterRng sq, DoomerfallEncounterRng fr)
	{
		let at = req.placements[p.index];
		int remaining = budget;
		if (p.role == "surprise" && p.surprise != "sleepinghorde")
		{
			if (p.surprise == "lonebrute" || p.surprise == "swarm")
			{
				let m = p.surprise == "lonebrute" ? Dearest(Side(p.side), at, remaining) : null;
				if (m) { AddMook(p, m); remaining -= Cost(m); }
				else if (p.surprise == "swarm")
				{
					let c = CheapestPool(at, result.civilWar);
					while (c && remaining >= Cost(c) && p.nextMember < maxCount) { AddMook(p, c); remaining -= Cost(c); }
				}
				if (!p.mooks.Size()) { AddMook(p, p.reserveMonster); remaining -= p.reserve; }
				return remaining;
			}
			if (p.surprise == "localwar")
			{
				// Half from the army's squad, half from a squad of another army.
				p.squad = ChooseSquad(0, sq);
				result.squads[p.squad].uses++;
				p.squad2 = NewSquad(0, "wrongarmy", sq);
				int half = remaining / 2;
				int left = BuySquad(p, result.squads[p.squad], half, maxCount, fr, true);
				return BuySquad(p, result.squads[p.squad2], remaining - half + left, maxCount, fr, false);
			}
			p.squad = NewSquad(p.side, p.surprise, sq);
			return BuySquad(p, result.squads[p.squad], remaining, maxCount, fr, true);
		}
		p.squad = ChooseSquad(p.side, sq);
		result.squads[p.squad].uses++;
		return BuySquad(p, result.squads[p.squad], remaining, maxCount, fr, !p.mooks.Size());
	}

	// The dearest army (or pool) monster that fits and is affordable: the lone brute in a swarm dungeon.
	DoomerfallMonster Dearest(DoomerfallArmy army, DoomerfallEncounterPlacement at, int budget)
	{
		DoomerfallMonster best = null;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			if (!Usable(m, result.civilWar) || m.capped || m.tier < 5 || !Fits(m, at) || Cost(m) > budget) continue;
			if (!best || Cost(m) > Cost(best)) best = m;
		}
		return best;
	}

	// 6.5: buys squad members until no member is affordable. The size gene tilts picks toward cheap members (swarm) or
	// dear ones (titan), so a heavy encounter is a bigger swarm or a bigger monster. When `fitFirst`, the first monster
	// must fit at the origin (the leader); if none can, the reserve monster stands there.
	private int BuySquad(DoomerfallPlannedPlacement p, DoomerfallSquad s, int remaining, int maxCount, DoomerfallEncounterRng r, bool fitFirst)
	{
		let at = req.placements[p.index];
		int k = s.members.Size();
		// Rank members by cost for the size tilt.
		Array<int> rank;
		for (int i = 0; i < k; i++)
		{
			int rk = 0;
			for (int j = 0; j < k; j++) if (Cost(s.members[j]) < Cost(s.members[i]) || (Cost(s.members[j]) == Cost(s.members[i]) && j < i)) rk++;
			rank.Push(rk);
		}
		int tilt = result.sizePermille * 7 / 1000 - 3;   // -3 swarm .. +3 titan
		Array<int> cost, base, fits, w;
		for (int i = 0; i < k; i++)
		{
			cost.Push(Cost(s.members[i]));
			base.Push(s.weights[i] * (tilt >= 0 ? Power(1 + rank[i], tilt) : Power(k - rank[i], -tilt)));
			fits.Push(Fits(s.members[i], at));
			w.Push(0);
		}
		bool first = fitFirst;
		while (p.nextMember < maxCount)
		{
			int any = 0;
			for (int i = 0; i < k; i++)
			{
				bool ok = cost[i] <= remaining && (!first || fits[i]);
				w[i] = ok ? base[i] : 0;
				any += ok;
			}
			if (!any)
			{
				if (first && p.reserveMonster && remaining >= p.reserve) { AddMook(p, p.reserveMonster); remaining -= p.reserve; first = false; continue; }
				break;
			}
			int pick = r.Pick(w);
			AddMook(p, s.members[pick], cost[pick]);
			remaining -= cost[pick];
			first = false;
		}
		if (!p.mooks.Size() && p.reserveMonster) { AddMook(p, p.reserveMonster); remaining -= p.reserve; }
		return remaining;
	}

	private void AddMook(DoomerfallPlannedPlacement p, DoomerfallMonster m, int cost = -1)
	{
		if (!m || p.nextMember >= MOOK_MAX_MEMBERS) return;
		let k = new("DoomerfallPlannedMook");
		k.m = m;
		k.member = p.nextMember++;
		k.cost = cost >= 0 ? cost : Cost(m);
		let at = req.placements[p.index];
		MookId(at.idHi, at.idLo, k.member, k.idHi, k.idLo);
		p.mooks.Push(k);
		p.spent += k.cost;
	}

	private void Finish()
	{
		result.spentPoints = 0;
		for (int i = 0; i < result.placements.Size(); i++)
		{
			let p = result.placements[i];
			result.spentPoints += p.spent;
			if (!p.mooks.Size()) result.warnings.Push(String.Format("placement %d has no monster", i));
		}
		result.leftoverPoints = result.poolPoints - result.spentPoints;
	}

	// ---- Hooks for the placer (6.6) ----

	private static DoomerfallEncounterPlanner Resume(DoomerfallEncounterPlan plan)
	{
		let pool = DoomerfallEncounterPool.Get();
		if (!pool || !plan || !plan.request) return null;
		let p = new("DoomerfallEncounterPlanner");
		p.pool = pool;
		p.data = pool.data;
		p.req = plan.request;
		p.result = plan;
		p.placeKey = DoomerfallEncounterRng.Combine(1013, p.req.dungeonIndex);
		p.placeKey = DoomerfallEncounterRng.Combine(p.placeKey, p.req.locationId);
		p.placeKey = DoomerfallEncounterRng.Combine(p.placeKey, p.req.regionIndex);
		p.placeKey = DoomerfallEncounterRng.Combine(p.placeKey, p.req.seedOffset);
		p.LoadLists();
		p.LoadTheme(p.req.dungeonType);
		return p;
	}

	// Promote: swap the placement's monsters for at most maxCount stronger ones that fit, keeping the same points.
	// Returns the points that could not be bought within maxCount (centipoints), for the placer to Move.
	// Mooks are renumbered from 0, so the same calls give the same IDs.
	static int Promote(DoomerfallEncounterPlan plan, int placement, int maxCount)
	{
		let me = Resume(plan);
		if (!me || placement < 0 || placement >= plan.placements.Size()) return 0;
		let p = plan.placements[placement];
		maxCount = clamp(maxCount, 1, MOOK_MAX_MEMBERS);
		if (p.mooks.Size() <= maxCount) return 0;
		int budget = p.spent;
		// Candidates: the side's army monsters and their same-kind higher tiers, that fit.
		let army = me.Side(p.side == 2 ? 0 : p.side);
		let at = plan.request.placements[placement];
		Array<DoomerfallMonster> cand;
		if (p.role == "start") me.StartMonsters(cand);   // the start room stays easy
		else for (int i = 0; i < me.pool.monsters.Size(); i++)
		{
			let m = me.pool.monsters[i];
			if (me.Usable(m, plan.civilWar) && !m.capped && me.KindInArmy(army, m.kind) && Fits(m, at)) cand.Push(m);
		}
		let leader = p.mooks[0].m;   // the first mook is the one chosen to fit at the origin; it stays
		p.mooks.Clear();
		p.nextMember = 0;
		p.spent = 0;
		me.AddMook(p, leader);
		int remaining = budget - p.spent;
		// Greedy: the dearest affordable candidate whose cost leaves room for the rest within the count.
		while (p.nextMember < maxCount && remaining > 0)
		{
			int slots = maxCount - p.nextMember;
			int target = (remaining + slots - 1) / slots;   // average cost needed per remaining slot
			DoomerfallMonster best = null;
			for (int i = 0; i < cand.Size(); i++)
			{
				int c = Cost(cand[i]);
				if (c > remaining) continue;
				// The cheapest candidate that reaches the target, else the dearest affordable one.
				if (!best) { best = cand[i]; continue; }
				int bc = Cost(best);
				bool reach = c >= target, breach = bc >= target;
				if ((reach && !breach) || (reach && breach && c < bc) || (!reach && !breach && c > bc)) best = cand[i];
			}
			if (!best) break;
			me.AddMook(p, best);
			remaining -= Cost(best);
		}
		plan.spentPoints += p.spent - budget;
		return remaining;
	}

	// Move: give points to the nearest placement not marked full, as more of its own squad. Returns that placement,
	// or -1 when every placement is full (the points are dropped and counted in plan.movedDropped).
	static int Move(DoomerfallEncounterPlan plan, int from, int points, Array<bool> full)
	{
		let me = Resume(plan);
		if (!me || points <= 0) return -1;
		let src = plan.request.placements[from];
		int best = -1;
		double bestD = 0;
		for (int i = 0; i < plan.placements.Size(); i++)
		{
			if (i == from || (i < full.Size() && full[i]) || plan.placements[i].role == "start") continue;   // the start room stays easy
			let a = plan.request.placements[i];
			double d = (a.x - src.x) * (a.x - src.x) + (a.y - src.y) * (a.y - src.y);
			if (best < 0 || d < bestD) { best = i; bestD = d; }
		}
		if (best < 0) { plan.movedDropped += points; return -1; }
		let p = plan.placements[best];
		int before = p.spent;
		let r = DoomerfallEncounterRng.Make(DoomerfallEncounterRng.Combine(me.placeKey, from), DoomerfallEncounterRng.P_MOVE);
		DoomerfallSquad s = p.squad >= 0 ? plan.squads[p.squad] : null;
		int left = points;
		if (s) left = me.BuySquad(p, s, points, MOOK_MAX_MEMBERS, r, false);
		let c = me.CheapestPool(plan.request.placements[best], plan.civilWar);
		while (c && left >= Cost(c) && p.nextMember < MOOK_MAX_MEMBERS) { me.AddMook(p, c); left -= Cost(c); }
		plan.spentPoints += p.spent - before;
		plan.leftoverPoints += left;
		return best;
	}

	// Gives the placement's mooks member numbers and IDs by their order, so mooks[0] is the leader (member 0).
	static void Renumber(DoomerfallEncounterPlan plan, int placement)
	{
		let p = plan.placements[placement];
		let at = plan.request.placements[placement];
		for (int i = 0; i < p.mooks.Size(); i++)
		{
			let k = p.mooks[i];
			k.member = i;
			MookId(at.idHi, at.idLo, i, k.idHi, k.idLo);
		}
		p.nextMember = p.mooks.Size();
	}

	// The placer found mook `which` to be the highest-point monster that fits at the origin: it becomes the leader.
	// The others keep their order behind it.
	static void MakeLeader(DoomerfallEncounterPlan plan, int placement, int which)
	{
		if (placement < 0 || placement >= plan.placements.Size()) return;
		let p = plan.placements[placement];
		if (which <= 0 || which >= p.mooks.Size()) return;
		let k = p.mooks[which];
		p.mooks.Delete(which);
		p.mooks.Insert(0, k);
		Renumber(plan, placement);
	}

	// No mook fits at the origin: the pool's cheapest monster becomes the leader there (owner, 2026-11-24), in front of
	// the others. Returns its cost in centipoints (0 when there is no pool or the placement is at the member limit).
	static int CheapestLeader(DoomerfallEncounterPlan plan, int placement)
	{
		let me = Resume(plan);
		if (!me || placement < 0 || placement >= plan.placements.Size()) return 0;
		let p = plan.placements[placement];
		if (p.mooks.Size() >= MOOK_MAX_MEMBERS) return 0;
		let c = me.CheapestPool(plan.request.placements[placement], plan.civilWar || p.side == 1);
		if (!c) return 0;
		let k = new("DoomerfallPlannedMook");
		k.m = c;
		k.cost = Cost(c);
		p.mooks.Insert(0, k);
		p.spent += k.cost;
		plan.spentPoints += k.cost;
		Renumber(plan, placement);
		return k.cost;
	}

	// Removes the mooks from `keep` on (they found no spot) and returns their points, for Promote or Move.
	static int Drop(DoomerfallEncounterPlan plan, int placement, int keep)
	{
		if (placement < 0 || placement >= plan.placements.Size()) return 0;
		let p = plan.placements[placement];
		keep = max(1, keep);
		int points = 0;
		while (p.mooks.Size() > keep)
		{
			points += p.mooks[p.mooks.Size() - 1].cost;
			p.mooks.Pop();
		}
		p.spent -= points;
		plan.spentPoints -= points;
		p.nextMember = p.mooks.Size();
		return points;
	}
}
