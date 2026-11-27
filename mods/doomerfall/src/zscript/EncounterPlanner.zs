// Encounter planner, part 1: the genome and the army (encounter design sections 4, 5, 9 and appendix A:
// work/notes/20261123-205402-fractal-encounter-variety.md). Pure: it reads the pool and the request and spawns nothing.
//
// Determinism: every decision uses DoomerfallEncounterRng, an integer hash of the place's facts, a purpose and an
// index. Never Doom's shared random(), the save, the player, the time or a new-game roll, so two players who enter the
// same dungeon with the same mods get the same plan. Floating point only reads inputs (data file numbers, the world
// position); every choice is made with integers.
//
// Use: let plan = DoomerfallEncounterPlanner.Plan(request);   (play scope; null when the pool is missing)

class DoomerfallEncounterRequest
{
	int dungeonIndex;        // fixed index of the dungeon among Daggerfall's dungeons; seeds the genome
	int locationId;
	String locationName;
	int regionIndex;
	String regionName;
	double worldX, worldY;   // world map position in map pixels (0-1000, 0-500), for the regional leaning
	String dungeonType;      // DFRegion.DungeonTypes name, such as VampireHaunt or DragonsDen
	int areaLevel;           // 0 to 30
	int seedOffset;          // 0 means fixed dungeons

	Array<DoomerfallEncounterPlacement> placements;
}

// The private random source. Value(purpose, index) depends only on the key (the place) and its arguments.
class DoomerfallEncounterRng
{
	const P_ANCHOR = 1;
	const P_CORE = 2;
	const P_SUPPORT = 3;
	const P_WILDCARD = 4;
	const P_SPREAD = 5;
	const P_THEME = 6;
	const P_REGION = 7;
	const P_CIVILWAR = 8;
	const P_THEMESET = 9;
	const P_REGIONPICK = 10;
	const P_SIDE_B = 100;     // added to a purpose for Civil War side B

	const P_TITAN = 20;
	const P_BOSS = 21;
	const P_SPLIT = 22;
	const P_SQUAD = 23;
	const P_FILL = 24;
	const P_SURPRISE = 25;
	const P_AWARE = 26;
	const P_SIDE = 27;
	const P_MOVE = 28;
	const P_START = 29;

	int key, purpose, index;

	// lowbias32 (Chris Wellons). Integer wraparound and logical shifts only.
	static int Mix(int x)
	{
		x ^= x >>> 16;
		x *= 2146121005;      // 0x7feb352d
		x ^= x >>> 15;
		x *= -2073254261;     // 0x846ca68b
		x ^= x >>> 16;
		return x;
	}

	static int Combine(int h, int v) { return Mix(h ^ Mix(v - 1640531527)); }

	static int StringHash(String s)
	{
		int h = 5381;
		for (int i = 0; i < s.Length(); i++) h = Combine(h, s.ByteAt(i));
		return h;
	}

	static DoomerfallEncounterRng Make(int key, int purpose)
	{
		let r = new("DoomerfallEncounterRng");
		r.key = key;
		r.purpose = purpose;
		r.index = 0;
		return r;
	}

	// The next number in 0 .. n-1 of this purpose's stream.
	int Next(int n)
	{
		int h = Combine(Combine(key, purpose), index);
		index++;
		if (n <= 1) return 0;
		return (h >>> 1) % n;
	}

	// An index chosen in proportion to integer weights, or -1 when every weight is 0.
	int Pick(Array<int> weights)
	{
		int total = 0;
		for (int i = 0; i < weights.Size(); i++) total += weights[i];
		if (total <= 0) { index++; return -1; }
		int r = Next(total);
		for (int i = 0; i < weights.Size(); i++)
		{
			if (r < weights[i]) return i;
			r -= weights[i];
		}
		return -1;
	}
}

// One row of the data file's theme table (section 4.1).
class DoomerfallEncounterTheme
{
	String name;
	String seedName;         // seedas=<row>: whose fitting gene settings this row uses (FitRank); default its own name
	bool known;
	Array<int> kinds;
	Array<String> classes;   // lower-case patterns
	int traits;
	String size, placement, awareness, tierlean, titan;
	bool only;               // only=1: every monster must match strictly, not just lean (story themes)

	// Favoured by kind or class name: what an anchor or a guaranteed theme monster must be.
	bool MatchesStrict(DoomerfallMonster m)
	{
		if (kinds.Find(m.kind) != kinds.Size()) return true;
		String low = m.cls.GetClassName();
		low = low.MakeLower();
		return DoomerfallEncounterData.FirstMatch(classes, low) >= 0;
	}

	// Strict match, or one of the favoured traits.
	bool Matches(DoomerfallMonster m) { return MatchesStrict(m) || (m.traits & traits) != 0; }

	bool HasMonsters() { return kinds.Size() || classes.Size(); }
}

class DoomerfallArmyEntry
{
	DoomerfallMonster m;
	String role;     // anchor, core, support, wildcard, theme, region
	int parent;      // entry this is a DRLA family variant of (section 5.4), or -1
	int share;       // thousandths of the army's points
}

class DoomerfallArmy
{
	Array<DoomerfallArmyEntry> entries;
	int coherence;          // raw setting 0 (Oops All One) to 12 (wild horde)
	int tierLean;           // tier 1 to 7
	int anchorKind;
	bool anchorThemed;
	String stance;          // toward the player in a Civil War: hunt, untilshot, ignore; "hunt" when united
	String themeHow;        // where the theme shows: anchor, core, support, wildcard, theme (added), unmet, none
	String regionHow;       // the same for the regional favourite kind
	Array<String> colour;   // per kind: the locked Colourful Hell colour, "" when none
	Array<int> spread;      // per kind: DRLA families allowed, 0 when the kind has no DRLA entry

	DoomerfallMonster Anchor() { return entries.Size() ? entries[0].m : null; }
}

class DoomerfallEncounterPlan
{
	DoomerfallEncounterRequest request;
	int order;              // the dungeon's shuffled number, 0 to 4231 (appendix A)
	Array<int> genes;       // raw settings 0 to 12, seedOffset applied
	Array<bool> themed;     // per gene: the setting fell among the theme's fitting settings
	String theme;
	int tierLean;
	int sizePermille;       // 4 (huge swarm) to 996 (lone titan)
	String placement, awareness;
	bool civilWar;
	int regionCellX, regionCellY;
	int regionKind;         // the region's favourite kind, -1 when none
	DoomerfallArmy a, b;    // b only in a Civil War
	Array<String> warnings;

	// The budget (EncounterBudget.zs, section 6 and 7).
	int avgPoints;           // centipoints per encounter at this area level (6.1)
	int poolPoints;          // avg x placements
	int reservePoints, bossPoints, titanPoints, splitPoints;
	int spentPoints;         // sum of every mook's cost
	int leftoverPoints;      // pool - spent: less than the pool's cheapest monster
	int movedDropped;        // points a Move could not place anywhere (the dungeon is full)
	int normalPack;          // centipoints of this dungeon's normal pack (6.2)
	int loneRate, giantRate, jitter;   // per mille, from the swing gene
	String bossStyle;        // strong, minis, both
	Array<int> bosses;       // placement indices, deepest first
	int titanPlacement;      // -1 when none
	DoomerfallMonster titan;
	String titanWhy;         // why there is or is not a titan
	bool emptyWing;
	Array<int> startRoom;    // placements the theme's start room rule replaced (StartRoom), nearest the player start
	Array<DoomerfallSquad> squads;
	Array<DoomerfallPlannedPlacement> placements;

	int MookCount()
	{
		int n = 0;
		for (int i = 0; i < placements.Size(); i++) n += placements[i].mooks.Size();
		return n;
	}
}

class DoomerfallEncounterPlanner play
{
	const DUNGEONS = 4232;
	const HALF = 2197;
	const SETTINGS = 13;
	const G_ANCHOR = 0;
	const G_COHERENCE = 1;
	const G_TIERLEAN = 2;
	const G_SIZE = 3;
	const G_FACTIONS = 4;
	const G_PLACEMENT = 5;
	const G_AWARENESS = 6;
	const G_SWING = 7;
	const G_NOVELTY = 8;
	const G_EXCEPTIONS = 9;
	// Traits that describe how a monster looks and fights, for resemblance.
	// hitscan 1, projectile 2, melee 4, flies 8, stealthy 32, homing 64, explosive 128 (DoomerfallMonster.T_*); not summons.
	const LOOK = 239;

	DoomerfallEncounterPool pool;
	DoomerfallEncounterData data;
	DoomerfallEncounterRequest req;
	DoomerfallEncounterPlan result;
	DoomerfallEncounterTheme theme;
	int placeKey;
	Array<int> ringPos;     // per kind: position on the anchor ring
	Array<String> families, titanGroups;

	static DoomerfallEncounterPlan Plan(DoomerfallEncounterRequest req)
	{
		let pool = DoomerfallEncounterPool.Get();
		if (!pool || !req) return null;
		let p = new("DoomerfallEncounterPlanner");
		return p.Run(pool, req);
	}

	// Appendix A: a fixed shuffle of the dungeon numbers (2897 is coprime with 4232, so this is a permutation).
	static int ShuffledOrder(int dungeonIndex)
	{
		int i = dungeonIndex % DUNGEONS;
		if (i < 0) i += DUNGEONS;
		return (i * 2897 + 1013) % DUNGEONS;
	}

	// Appendix A: gene[j] = (a + b*j + c*j^2 + s*j^3) mod 13. Two dungeons share at most 3 of the 10 genes.
	static void Genome(int dungeonIndex, int seedOffset, out Array<int> genes)
	{
		genes.Clear();
		int i = ShuffledOrder(dungeonIndex);
		int s = i < HALF ? 0 : 1;
		int n = i % HALF;
		int a = n % 13, b = (n / 13) % 13, c = n / 169;
		int off = seedOffset % 13;
		if (off < 0) off += 13;
		for (int j = 0; j < 10; j++) genes.Push((a + b * j + c * j * j + s * j * j * j + off) % 13);
	}

	private DoomerfallEncounterPlan Run(DoomerfallEncounterPool pool, DoomerfallEncounterRequest req)
	{
		self.pool = pool;
		data = pool.data;
		self.req = req;
		result = new("DoomerfallEncounterPlan");
		result.request = req;
		// The place's facts only.
		placeKey = DoomerfallEncounterRng.Combine(1013, req.dungeonIndex);
		placeKey = DoomerfallEncounterRng.Combine(placeKey, req.locationId);
		placeKey = DoomerfallEncounterRng.Combine(placeKey, req.regionIndex);
		placeKey = DoomerfallEncounterRng.Combine(placeKey, req.seedOffset);
		LoadLists();
		LoadTheme(req.dungeonType);
		result.theme = theme.name;
		result.order = ShuffledOrder(req.dungeonIndex);
		Genome(req.dungeonIndex, req.seedOffset, result.genes);
		for (int g = 0; g < 10; g++) result.themed.Push(false);
		ReadGenes();
		Region();

		result.a = BuildArmy(false, result.genes[G_COHERENCE], result.tierLean, result.genes[G_ANCHOR], result.themed[G_ANCHOR],
			FitRank(G_ANCHOR, result.genes[G_ANCHOR]), result.civilWar, null);
		if (result.civilWar)
		{
			// Section 5.5: a second, independently generated army from the next seed, which must differ visibly.
			let r = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_CIVILWAR);
			int coherence = r.Next(SETTINGS);
			Array<String> leans;
			data.GetList("tierlean_settings", leans);
			int lean = leans.Size() == SETTINGS ? leans[r.Next(SETTINGS)].ToInt() : 1 + r.Next(7);
			result.b = BuildArmy(true, coherence, lean, r.Next(SETTINGS), false, -1, true, result.a);
		}
		Array<String> stances;
		data.GetList("civilwar_stances", stances);
		result.a.stance = "hunt";
		if (result.civilWar && stances.Size())
		{
			int cw = int(data.Value("civil_war_settings", 5));
			int at = clamp(result.genes[G_FACTIONS] - (SETTINGS - cw), 0, stances.Size() - 1);
			Array<String> pair;
			stances[at].Split(pair, "/");
			result.a.stance = pair.Size() > 0 ? pair[0] : "hunt";
			if (result.b) result.b.stance = pair.Size() > 1 ? pair[1] : "hunt";
		}
		Budget();
		return result;
	}

	private void LoadLists()
	{
		data.GetList("families", families);
		data.GetList("titangroups", titanGroups);
		Array<String> ring;
		data.GetList("kind_ring", ring);
		for (int k = 0; k < data.kindName.Size(); k++) ringPos.Push(-1);
		for (int i = 0; i < ring.Size(); i++)
		{
			int k = data.FindKind(ring[i]);
			if (k >= 0) ringPos[k] = i;
		}
		for (int k = 0; k < ringPos.Size(); k++)
			if (ringPos[k] < 0) { result.warnings.Push("kind_ring lacks " .. data.kindName[k]); ringPos[k] = k; }
	}

	private void LoadTheme(String type)
	{
		theme = new("DoomerfallEncounterTheme");
		String tname = type;
		tname.Replace(" ", "");
		tname.Replace("'", "");
		theme.name = tname;
		theme.known = false;
		for (int i = 0; i < data.themeName.Size(); i++)
			if (data.themeName[i] ~== tname) { theme.known = true; theme.name = data.themeName[i]; break; }
		if (!theme.known) { result.warnings.Push("no theme row for dungeon type '" .. type .. "'"); return; }
		Array<String> parts;
		String kindList = data.ThemeGet(theme.name, "kinds");
		kindList.Split(parts, ",", TOK_SKIPEMPTY);
		for (int i = 0; i < parts.Size(); i++)
		{
			int k = data.FindKind(parts[i]);
			if (k >= 0) theme.kinds.Push(k); else result.warnings.Push("theme kind " .. parts[i] .. " unknown");
		}
		String classes = data.ThemeGet(theme.name, "classes");
		classes = classes.MakeLower();
		classes.Split(theme.classes, ",", TOK_SKIPEMPTY);
		theme.traits = DoomerfallMonster.TraitBits(data.ThemeGet(theme.name, "traits"));
		theme.size = data.ThemeGet(theme.name, "size");
		theme.placement = data.ThemeGet(theme.name, "placement");
		theme.awareness = data.ThemeGet(theme.name, "awareness");
		theme.tierlean = data.ThemeGet(theme.name, "tierlean");
		theme.titan = data.ThemeGet(theme.name, "titan");
		theme.only = data.ThemeGet(theme.name, "only") == "1" && theme.HasMonsters();
		theme.seedName = data.ThemeGet(theme.name, "seedas");
		if (theme.seedName == "") theme.seedName = theme.name;
	}

	// Section 4.1: for each theme and gene a fixed set of about 9 of the 13 settings is "fitting". Returns the
	// setting's rank in that set, or -1 when it is one of the deliberate exceptions. Depends on the theme only.
	int FitRank(int gene, int setting)
	{
		if (!theme.known) return -1;
		int fit = clamp(int(data.Value("theme_fitting_settings", 9)), 0, SETTINGS);
		Array<int> perm;
		for (int k = 0; k < SETTINGS; k++) perm.Push(k);
		let r = DoomerfallEncounterRng.Make(DoomerfallEncounterRng.StringHash(theme.seedName.MakeLower()), DoomerfallEncounterRng.P_THEMESET * 16 + gene);
		for (int k = SETTINGS - 1; k > 0; k--)
		{
			int j = r.Next(k + 1);
			int t = perm[k]; perm[k] = perm[j]; perm[j] = t;
		}
		for (int k = 0; k < fit; k++) if (perm[k] == setting) return k;
		return -1;
	}

	// What each raw setting means, with the theme's leanings applied (section 4.1).
	private void ReadGenes()
	{
		Array<String> list;
		data.GetList("tierlean_settings", list);
		int g = result.genes[G_TIERLEAN];
		result.tierLean = list.Size() == SETTINGS ? list[g].ToInt() : 1 + g * 7 / SETTINGS;
		if (theme.tierlean != "" && FitRank(G_TIERLEAN, g) >= 0)
		{
			int grp = data.FindGroup(theme.tierlean);
			result.tierLean = grp >= 0 ? data.groupTier[grp] : theme.tierlean.ToInt();
			result.themed[G_TIERLEAN] = true;
		}

		data.GetList("size_settings", list);
		g = result.genes[G_SIZE];
		result.sizePermille = list.Size() == SETTINGS ? list[g].ToInt() : 500;
		int rank = FitRank(G_SIZE, g);
		if (list.Size() == SETTINGS && rank >= 0 && (theme.size ~== "titan" || theme.size ~== "swarm"))
		{
			// The theme's end of the U: one of the three most extreme settings at that end.
			result.sizePermille = theme.size ~== "titan" ? list[SETTINGS - 1 - rank % 3].ToInt() : list[rank % 3].ToInt();
			result.themed[G_SIZE] = true;
		}

		data.GetList("placement_settings", list);
		g = result.genes[G_PLACEMENT];
		result.placement = list.Size() == SETTINGS ? list[g] : "scattered";
		if (theme.placement != "" && FitRank(G_PLACEMENT, g) >= 0) { result.placement = theme.placement; result.themed[G_PLACEMENT] = true; }

		data.GetList("awareness_settings", list);
		g = result.genes[G_AWARENESS];
		result.awareness = list.Size() == SETTINGS ? list[g] : "mixed";
		if (theme.awareness != "" && FitRank(G_AWARENESS, g) >= 0) { result.awareness = theme.awareness; result.themed[G_AWARENESS] = true; }

		result.themed[G_ANCHOR] = theme.HasMonsters() && FitRank(G_ANCHOR, result.genes[G_ANCHOR]) >= 0;
		result.civilWar = result.genes[G_FACTIONS] >= SETTINGS - int(data.Value("civil_war_settings", 5));
	}

	// Section 4.1: dungeons in the same world map cell share a favourite kind. It is chosen from the kinds that have a
	// Civil War safe monster, so a Civil War army can always honour it.
	private void Region()
	{
		double cell = max(1., data.Value("region_cell", 48));
		result.regionCellX = int(floor(req.worldX / cell));
		result.regionCellY = int(floor(req.worldY / cell));
		Array<int> kinds;
		for (int k = 0; k < data.kindName.Size(); k++)
		{
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				if (m.kind == k && m.civilWarSafe && !m.capped && !IsTitan(m)) { kinds.Push(k); break; }
			}
		}
		result.regionKind = -1;
		if (!kinds.Size()) return;
		int key = DoomerfallEncounterRng.Combine(DoomerfallEncounterRng.Combine(77, result.regionCellX), result.regionCellY);
		let r = DoomerfallEncounterRng.Make(key, DoomerfallEncounterRng.P_REGION);
		result.regionKind = kinds[r.Next(kinds.Size())];
	}

	// ---- Monster tests ----

	bool IsTitan(DoomerfallMonster m)
	{
		for (int i = 0; i < titanGroups.Size(); i++) if (m.group ~== titanGroups[i]) return true;
		return false;
	}

	bool IsFamily(DoomerfallMonster m)
	{
		for (int i = 0; i < families.Size(); i++) if (m.group ~== families[i]) return true;
		return false;
	}

	// A Colourful Hell colour, which the colour lock applies to (section 5.4).
	bool IsColour(DoomerfallMonster m) { return m.tier < 8 && !(m.group ~== "Stock") && !IsFamily(m) && !IsTitan(m); }

	bool Usable(DoomerfallMonster m, bool civil) { return !IsTitan(m) && (!civil || m.civilWarSafe) && ThemeAllows(m); }

	// An only=1 theme admits nothing outside it.
	bool ThemeAllows(DoomerfallMonster m) { return !theme || !theme.only || theme.MatchesStrict(m); }

	bool InArmy(DoomerfallArmy army, DoomerfallMonster m)
	{
		for (int i = 0; i < army.entries.Size(); i++) if (army.entries[i].m == m) return true;
		return false;
	}

	bool KindInArmy(DoomerfallArmy army, int kind)
	{
		for (int i = 0; i < army.entries.Size(); i++) if (army.entries[i].m.kind == kind) return true;
		return false;
	}

	bool ColourOk(DoomerfallArmy army, DoomerfallMonster m)
	{
		if (!IsColour(m)) return true;
		String c = army.colour[m.kind];
		return c == "" || c ~== m.group;
	}

	// The kind already has a DRLA family entry: further families come only from the variant spread.
	bool FamilyTaken(DoomerfallArmy army, DoomerfallMonster m)
	{
		if (!IsFamily(m)) return false;
		for (int i = 0; i < army.entries.Size(); i++)
		{
			let e = army.entries[i].m;
			if (e.kind == m.kind && IsFamily(e)) return true;
		}
		return false;
	}

	static int TierWeight(int tier, int lean)
	{
		static const int w[] = { 16, 8, 3 };
		int d = abs(tier - lean);
		return d < 3 ? w[d] : 1;
	}

	static int Bits(int x)
	{
		int n = 0;
		for (; x; x &= x - 1) n++;
		return n;
	}

	static int Power(int b, int e)
	{
		int r = 1;
		for (int i = 0; i < e; i++) r *= b;
		return r;
	}

	private int RingDistance(int kind, int from, int to)
	{
		int n = ringPos.Size();
		int p = ringPos[kind];
		int best = n;
		for (int q = from; q < to; q++)
		{
			int d = abs(p - q % n);
			best = min(best, min(d, n - d));
		}
		return best;
	}

	private void Add(DoomerfallArmy army, DoomerfallMonster m, String role, int parent = -1)
	{
		let e = new("DoomerfallArmyEntry");
		e.m = m;
		e.role = role;
		e.parent = parent;
		e.share = 0;
		army.entries.Push(e);
		if (IsColour(m) && role != "wildcard" && army.colour[m.kind] == "") army.colour[m.kind] = m.group;
	}

	// ---- Army building (section 5.2) ----

	private DoomerfallMonster PickAnchor(DoomerfallArmy army, int setting, bool themed, int fitRank, bool civil, DoomerfallEncounterRng r)
	{
		Array<int> w;
		if (themed)
		{
			// A theme monster, the preferred theme kind turning with the setting, near the tier lean.
			int pref = theme.kinds.Size() ? theme.kinds[max(0, fitRank) % theme.kinds.Size()] : -1;
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				bool ok = Usable(m, civil) && !m.capped && theme.MatchesStrict(m);
				w.Push(ok ? TierWeight(m.tier, army.tierLean) * (m.kind == pref ? 4 : 1) : 0);
			}
			int pick = r.Pick(w);
			if (pick >= 0) return pool.monsters[pick];
			army.anchorThemed = false;   // no theme monster loaded (or none is Civil War safe): use the plain meaning
		}

		// Plain meaning: the setting covers a slice of the kind ring. Widen to the nearest kinds that exist.
		int n = ringPos.Size();
		int from = setting * n / SETTINGS, to = max(from + 1, (setting + 1) * n / SETTINGS);
		Array<int> dist;
		int best = n;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			int d = Usable(m, civil) && !m.capped ? RingDistance(m.kind, from, to) : n + 1;
			dist.Push(d);
			best = min(best, d);
		}
		if (best >= n) return null;
		// Each nearest kind is equally likely, then the class within it leans to the tier lean.
		Array<int> kinds;
		for (int k = 0; k < n; k++)
		{
			for (int i = 0; i < dist.Size(); i++)
				if (dist[i] == best && pool.monsters[i].kind == k) { kinds.Push(k); break; }
		}
		int kind = kinds[r.Next(kinds.Size())];
		w.Clear();
		for (int i = 0; i < pool.monsters.Size(); i++)
			w.Push(dist[i] == best && pool.monsters[i].kind == kind ? TierWeight(pool.monsters[i].tier, army.tierLean) : 0);
		int pick = r.Pick(w);
		return pick >= 0 ? pool.monsters[pick] : null;
	}

	private DoomerfallArmy BuildArmy(bool sideB, int coherence, int tierLean, int anchorSetting, bool themed, int fitRank,
		bool civil, DoomerfallArmy other)
	{
		int side = sideB ? DoomerfallEncounterRng.P_SIDE_B : 0;
		let army = new("DoomerfallArmy");
		army.coherence = coherence;
		army.tierLean = clamp(tierLean, 1, 7);
		army.anchorThemed = themed;
		army.themeHow = "none";
		army.regionHow = "none";
		for (int k = 0; k < data.kindName.Size(); k++) { army.colour.Push(""); army.spread.Push(0); }

		let r = DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_ANCHOR + side);
		DoomerfallMonster anchor = null;
		if (other && other.Anchor())
		{
			// Side B: the first setting from anchorSetting on whose anchor differs by kind or by enough tiers.
			int gap = int(data.Value("civil_war_min_tier_gap", 2));
			let oa = other.Anchor();
			for (int t = 0; t < SETTINGS && !anchor; t++)
			{
				let m = PickAnchor(army, (anchorSetting + t) % SETTINGS, false, -1, civil, r);
				if (m && (m.kind != oa.kind || abs(m.tier - oa.tier) >= gap)) anchor = m;
			}
			if (!anchor) result.warnings.Push("civil war: no side B anchor differs visibly from side A");
		}
		if (!anchor) anchor = PickAnchor(army, anchorSetting, themed, fitRank, civil, r);
		if (!anchor) { result.warnings.Push("no anchor: the pool has no usable monster"); return army; }
		army.anchorKind = anchor.kind;
		Add(army, anchor, "anchor");

		bool follow = army.anchorThemed && !sideB;
		AddCore(army, civil, follow, DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_CORE + side));
		AddSupport(army, civil, follow, DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_SUPPORT + side));
		AddWildcard(army, civil, DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_WILDCARD + side));
		if (!sideB)
		{
			GuaranteeTheme(army, civil, DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_THEME));
			GuaranteeRegion(army, civil, DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_REGIONPICK));
		}
		Spread(army, civil, DoomerfallEncounterRng.Make(placeKey, DoomerfallEncounterRng.P_SPREAD + side));
		Shares(army);
		return army;
	}

	// Core: 1 to 3 more monsters that resemble the anchor, as strictly as the coherence says. None at coherence 0.
	private void AddCore(DoomerfallArmy army, bool civil, bool follow, DoomerfallEncounterRng r)
	{
		int c = army.coherence;
		if (c <= 0) return;
		int lo = int(data.Value("army_core_min", 1)), hi = int(data.Value("army_core_max", 3));
		int count = lo + r.Next(1 + c * (hi - lo) / 12);
		int p = clamp((12 - c) / 3, 0, 3) + 1;   // resemblance power: 4 when tight, 1 when loose
		let a = army.Anchor();
		for (int n = 0; n < count; n++)
		{
			Array<int> w;
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				if (!Usable(m, civil) || m.capped || InArmy(army, m) || !ColourOk(army, m) || FamilyTaken(army, m)) { w.Push(0); continue; }
				int sim = 1 + (m.kind == a.kind ? 6 : 0) + 2 * Bits(m.traits & a.traits & LOOK) + max(0, 3 - abs(m.tier - a.tier))
					+ (follow && theme.Matches(m) ? 4 : 0);
				w.Push(Power(sim, p));
			}
			int pick = r.Pick(w);
			if (pick < 0) break;
			Add(army, pool.monsters[pick], "core");
		}
	}

	// Support: 1 to 3 monsters that only loosely resemble the core, favouring what the core lacks.
	private void AddSupport(DoomerfallArmy army, bool civil, bool follow, DoomerfallEncounterRng r)
	{
		int c = army.coherence;
		if (c <= 0) return;
		int lo = int(data.Value("army_support_min", 1)), hi = int(data.Value("army_support_max", 3));
		int count = lo + r.Next(1 + c * (hi - lo) / 12);
		for (int n = 0; n < count; n++)
		{
			int have = 0;
			for (int i = 0; i < army.entries.Size(); i++) have |= army.entries[i].m.traits;
			Array<int> w;
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				if (!Usable(m, civil) || InArmy(army, m) || !ColourOk(army, m) || FamilyTaken(army, m)) { w.Push(0); continue; }
				int base = 1 + 3 * Bits(m.traits & ~have & LOOK) + (follow && theme.Matches(m) ? 3 : 0);
				w.Push(base * (KindInArmy(army, m.kind) ? 1 : 3) * TierWeight(m.tier, army.tierLean));
			}
			int pick = r.Pick(w);
			if (pick < 0) break;
			Add(army, pool.monsters[pick], "support");
		}
	}

	// Wildcard: sometimes one monster from anywhere, more often in loose armies. The colour lock does not bind it.
	private void AddWildcard(DoomerfallArmy army, bool civil, DoomerfallEncounterRng r)
	{
		int c = army.coherence;
		if (c <= 0 || r.Next(16) >= c) return;
		Array<int> w;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			w.Push(Usable(m, civil) && !InArmy(army, m) ? 1 : 0);
		}
		int pick = r.Pick(w);
		if (pick >= 0) Add(army, pool.monsters[pick], "wildcard");
	}

	private String FirstRoleWhere(DoomerfallArmy army, int kind)
	{
		for (int i = 0; i < army.entries.Size(); i++)
		{
			let m = army.entries[i].m;
			if (kind >= 0 ? m.kind == kind : theme.Matches(m)) return army.entries[i].role;
		}
		return "";
	}

	// Something from the theme is guaranteed (section 4.1).
	private void GuaranteeTheme(DoomerfallArmy army, bool civil, DoomerfallEncounterRng r)
	{
		if (!theme.known) return;
		String how = FirstRoleWhere(army, -1);
		if (how != "") { army.themeHow = how; return; }
		// Strict matches (kind or class) first, then trait matches.
		for (int pass = 0; pass < 2; pass++)
		{
			Array<int> w;
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				bool ok = Usable(m, civil) && !InArmy(army, m) && ColourOk(army, m) && !FamilyTaken(army, m)
					&& (pass == 0 ? theme.MatchesStrict(m) : theme.Matches(m));
				w.Push(ok ? TierWeight(m.tier, army.tierLean) * (m.capped ? 1 : 8) : 0);
			}
			int pick = r.Pick(w);
			if (pick >= 0) { Add(army, pool.monsters[pick], "theme"); army.themeHow = "theme"; return; }
		}
		army.themeHow = "unmet";
		result.warnings.Push(String.Format("theme %s: no %smonster from the theme is in the pool", theme.name, civil ? "Civil War safe " : ""));
	}

	// The region's favourite kind is guaranteed.
	private void GuaranteeRegion(DoomerfallArmy army, bool civil, DoomerfallEncounterRng r)
	{
		if (result.regionKind < 0) return;
		String how = FirstRoleWhere(army, result.regionKind);
		if (how != "") { army.regionHow = how; return; }
		Array<int> w;
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			bool ok = m.kind == result.regionKind && Usable(m, civil) && !m.capped && ColourOk(army, m) && !FamilyTaken(army, m);
			w.Push(ok ? TierWeight(m.tier, army.tierLean) : 0);
		}
		int pick = r.Pick(w);
		if (pick >= 0) { Add(army, pool.monsters[pick], "region"); army.regionHow = "region"; }
		else if (theme.only && theme.kinds.Find(result.regionKind) == theme.kinds.Size())
			army.regionHow = "excluded";   // a story theme outranks a regional favourite outside it
		else { army.regionHow = "unmet"; result.warnings.Push("region kind " .. data.kindName[result.regionKind] .. " has no usable monster"); }
	}

	// Section 5.4: each kind with a DRLA family entry rolls how many families it uses, U-shaped, nudged by coherence.
	private void Spread(DoomerfallArmy army, bool civil, DoomerfallEncounterRng r)
	{
		Array<String> row;
		data.GetList(army.coherence <= 4 ? "spread_tight" : army.coherence <= 8 ? "spread_middle" : "spread_loose", row);
		Array<int> weights;
		for (int i = 0; i < row.Size(); i++) weights.Push(row[i].ToInt());
		int count = army.entries.Size();
		for (int e = 0; e < count; e++)
		{
			let base = army.entries[e];
			if (base.role == "wildcard" || !IsFamily(base.m) || army.spread[base.m.kind]) continue;
			int kind = base.m.kind;
			int want = 1 + max(0, r.Pick(weights));
			army.spread[kind] = want;
			Array<String> used;
			used.Push(base.m.group);
			bool coreish = base.role == "anchor" || base.role == "core";
			for (int f = 1; f < want; f++)
			{
				// One more family, chosen evenly among those the pool has for this kind, then one of its classes.
				Array<String> open;
				for (int i = 0; i < families.Size(); i++)
				{
					if (used.Find(families[i]) != used.Size()) continue;
					for (int j = 0; j < pool.monsters.Size(); j++)
					{
						let m = pool.monsters[j];
						if (m.kind == kind && m.group ~== families[i] && Usable(m, civil) && !(coreish && m.capped) && !InArmy(army, m))
						{ open.Push(families[i]); break; }
					}
				}
				if (!open.Size()) break;
				String fam = open[r.Next(open.Size())];
				used.Push(fam);
				Array<int> w;
				for (int j = 0; j < pool.monsters.Size(); j++)
				{
					let m = pool.monsters[j];
					w.Push(m.kind == kind && m.group ~== fam && Usable(m, civil) && !(coreish && m.capped) && !InArmy(army, m) ? 1 : 0);
				}
				int pick = r.Pick(w);
				if (pick >= 0) Add(army, pool.monsters[pick], base.role, e);
			}
		}
	}

	// Section 5.2 shares, in thousandths: guarantees first, then core 75%, support 20%, wildcard 5% of the rest.
	// Missing roles hand their share to the core. Within the core the anchor counts twice. A family variant splits
	// its parent's share. A capped class keeps at most capped_share; the excess goes to the anchor.
	private void Shares(DoomerfallArmy army)
	{
		int n = army.entries.Size();
		if (!n) return;
		int gshare = int(data.Value("guarantee_share", 100));
		int coreUnits = 0, support = 0, wild = 0, guarantees = 0;
		for (int i = 0; i < n; i++)
		{
			let e = army.entries[i];
			if (e.parent >= 0) continue;
			if (e.role == "anchor") coreUnits += 2;
			else if (e.role == "core") coreUnits++;
			else if (e.role == "support") support++;
			else if (e.role == "wildcard") wild++;
			else guarantees++;
		}
		int rest = 1000 - min(guarantees * gshare, 500);
		int each = guarantees ? (1000 - rest) / guarantees : 0;
		int ws = wild ? int(rest * data.Value("army_wildcard_share", 0.05) + 0.5) : 0;
		int ss = support ? int(rest * data.Value("army_support_share", 0.20) + 0.5) : 0;
		int cs = rest - ws - ss;
		// First pass: each top-level entry's share.
		Array<int> top;
		int given = 0;
		for (int i = 0; i < n; i++)
		{
			let e = army.entries[i];
			int s = 0;
			if (e.parent < 0)
			{
				if (e.role == "anchor") s = cs * 2 / coreUnits;
				else if (e.role == "core") s = cs / coreUnits;
				else if (e.role == "support") s = ss / support;
				else if (e.role == "wildcard") s = ws / wild;
				else s = each;
			}
			top.Push(s);
			given += s;
		}
		top[0] += 1000 - given;   // rounding to the anchor
		// Second pass: split each parent's share among it and its variants.
		for (int i = 0; i < n; i++)
		{
			if (army.entries[i].parent >= 0) continue;
			int kids = 1;
			for (int j = 0; j < n; j++) if (army.entries[j].parent == i) kids++;
			int part = top[i] / kids;
			army.entries[i].share = top[i] - part * (kids - 1);
			for (int j = 0; j < n; j++) if (army.entries[j].parent == i) army.entries[j].share = part;
		}
		int cap = int(data.Value("capped_share", 0.10) * 1000 + 0.5);
		for (int i = 1; i < n; i++)
		{
			let e = army.entries[i];
			if (e.m.capped && e.share > cap) { army.entries[0].share += e.share - cap; e.share = cap; }
		}
	}
}
