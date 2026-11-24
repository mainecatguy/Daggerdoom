// Encounter monster pool (encounter design, sections 5, 6 and 8: work/notes/20261123-205402-fractal-encounter-variety.md).
//
// Every monster class the running game can spawn, tagged for the encounter planner: kind (which of the 17 stock Doom
// monsters it descends from), tier, traits, points, size, cap and Civil War safety. Built once from the loaded classes
// and the rules in doomerfall_encounters.txt, which holds every tunable number, so tuning never needs a code change.
// Works with stock Doom alone (the 17 stock monsters), DRLA, and DRLA plus Colourful Hell.
//
// Use: let pool = DoomerfallEncounterPool.Get(); then pool.monsters, pool.data.

class DoomerfallMonster
{
	const T_HITSCAN = 1;
	const T_PROJECTILE = 2;
	const T_MELEE = 4;
	const T_FLIES = 8;
	const T_SUMMONS = 16;
	const T_STEALTHY = 32;
	const T_HOMING = 64;
	const T_EXPLOSIVE = 128;

	class<Actor> cls;
	int kind;            // index into DoomerfallEncounterData.kindName
	int tier;            // 1 to 8 (section 8.2)
	String group;        // colour, DRLA family, Stock, or the 'own' label for tier 8
	int traits;          // T_ bits
	double points;
	int health;
	double radius, height;
	bool capped;
	bool civilWarSafe;
	String unsafeWhy;    // why it is not Civil War safe, empty when safe

	static String TraitNames(int bits)
	{
		static const String names[] = { "hitscan", "projectile", "melee", "flies", "summons", "stealthy", "homing", "explosive" };
		String s = "";
		for (int i = 0; i < 8; i++)
			if (bits & (1 << i)) s = s .. (s.Length() ? "," : "") .. names[i];
		return s.Length() ? s : "-";
	}

	static int TraitBits(String list)
	{
		static const String names[] = { "hitscan", "projectile", "melee", "flies", "summons", "stealthy", "homing", "explosive" };
		Array<String> parts;
		list.MakeLower().Split(parts, ",", TOK_SKIPEMPTY);
		int bits = 0;
		for (int i = 0; i < parts.Size(); i++)
		{
			int j = 0;
			for (; j < 8; j++) if (parts[i] == names[j]) break;
			if (j < 8) bits |= 1 << j; else bits |= 1 << 30; // unknown trait: flagged as a data error
		}
		return bits;
	}
}

// The parsed data file. Field names follow its rule words.
class DoomerfallEncounterData
{
	const LumpName = "doomerfall_encounters.txt";

	Array<String> kindName, kindStock;
	Array<double> kindPoints;
	Array<int> kindTraits, kindHealth;
	Array<String> kindPat;   Array<int> kindPatKind;
	Array<String> kindClass; Array<int> kindClassKind;
	Array<String> excludePat, excludeWhy;
	Array<String> includePat;
	Array<String> groupName; Array<int> groupTier; Array<double> groupMult;
	Array<String> tierPat;   Array<int> tierGroup;
	Array<String> ownPat, ownLabel, ownMode; Array<double> ownA, ownB, ownC, ownD;
	Array<String> traitPat;  Array<int> traitBits;
	Array<String> cappedPat;
	Array<int> unsafeKind;   Array<String> unsafeKindWhy;
	Array<String> unsafePat, unsafeWhy;
	Array<int> levelAt;      Array<double> levelPoints;
	Array<int> titanAt;      Array<double> titanChance;
	Array<String> setKey;    Array<double> setValue;
	Array<String> themeName, themeKey, themeValue; // one row per theme key; themeName repeats
	Array<String> errors;

	static DoomerfallEncounterData Load()
	{
		let d = new("DoomerfallEncounterData");
		int lump = Wads.CheckNumForFullName(LumpName);
		if (lump < 0) { d.errors.Push(LumpName .. " is missing"); return d; }
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n", TOK_SKIPEMPTY);
		for (int i = 0; i < lines.Size(); i++) d.ParseLine(lines[i], i + 1);
		if (d.kindName.Size() != 17) d.errors.Push(String.Format("expected 17 kinds, found %d", d.kindName.Size()));
		return d;
	}

	int FindKind(String name)
	{
		for (int i = 0; i < kindName.Size(); i++) if (kindName[i] ~== name) return i;
		return -1;
	}

	int FindGroup(String name)
	{
		for (int i = 0; i < groupName.Size(); i++) if (groupName[i] ~== name) return i;
		return -1;
	}

	private void ParseLine(String line, int number)
	{
		int hash = line.IndexOf("#");
		if (hash >= 0) line = line.Left(hash);
		line.Replace("\t", " ");
		line.Replace("\r", " ");
		Array<String> w;
		line.Split(w, " ", TOK_SKIPEMPTY);
		if (!w.Size()) return;
		String rule = w[0].MakeLower();
		int n = w.Size();
		bool ok = true;
		if (rule == "kind" && n >= 4)
		{
			kindName.Push(w[1]); kindStock.Push(w[2]); kindPoints.Push(w[3].ToDouble());
			kindTraits.Push(n >= 5 ? DoomerfallMonster.TraitBits(w[4]) : 0);
			class<Actor> stock = w[2];
			kindHealth.Push(stock ? GetDefaultByType(stock).Health : 0);
			if (!stock) errors.Push(String.Format("line %d: stock class %s is not loaded", number, w[2]));
		}
		else if ((rule == "kindname" || rule == "kindclass") && n >= 3)
		{
			int k = FindKind(w[2]);
			if (k < 0) ok = false;
			else if (rule == "kindname") { kindPat.Push(w[1].MakeLower()); kindPatKind.Push(k); }
			else { kindClass.Push(w[1].MakeLower()); kindClassKind.Push(k); }
		}
		else if (rule == "include" && n >= 2) includePat.Push(w[1].MakeLower());
		else if (rule == "exclude" && n >= 2) { excludePat.Push(w[1].MakeLower()); excludeWhy.Push(n >= 3 ? w[2] : "excluded"); }
		else if (rule == "group" && n >= 4) { groupName.Push(w[1]); groupTier.Push(w[2].ToInt()); groupMult.Push(w[3].ToDouble()); }
		else if (rule == "tier" && n >= 3)
		{
			int g = FindGroup(w[2]);
			if (g < 0) ok = false; else { tierPat.Push(w[1].MakeLower()); tierGroup.Push(g); }
		}
		else if (rule == "own" && n >= 5)
		{
			String mode = w[3].MakeLower();
			if (mode == "fixed" || mode == "scale" || (mode == "lerp" && n >= 8))
			{
				ownPat.Push(w[1].MakeLower()); ownLabel.Push(w[2]); ownMode.Push(mode);
				ownA.Push(w[4].ToDouble());
				ownB.Push(n > 5 ? w[5].ToDouble() : 0); ownC.Push(n > 6 ? w[6].ToDouble() : 0); ownD.Push(n > 7 ? w[7].ToDouble() : 0);
			}
			else ok = false;
		}
		else if (rule == "trait" && n >= 3) { traitPat.Push(w[1].MakeLower()); traitBits.Push(DoomerfallMonster.TraitBits(w[2])); }
		else if (rule == "capped" && n >= 2) cappedPat.Push(w[1].MakeLower());
		else if (rule == "unsafekind" && n >= 2)
		{
			int k = FindKind(w[1]);
			if (k < 0) ok = false; else { unsafeKind.Push(k); unsafeKindWhy.Push(n >= 3 ? w[2] : "unsafe-kind"); }
		}
		else if (rule == "unsafe" && n >= 2) { unsafePat.Push(w[1].MakeLower()); unsafeWhy.Push(n >= 3 ? w[2] : "unsafe"); }
		else if (rule == "level" && n >= 3) { levelAt.Push(w[1].ToInt()); levelPoints.Push(w[2].ToDouble()); }
		else if (rule == "titanchance" && n >= 3) { titanAt.Push(w[1].ToInt()); titanChance.Push(w[2].ToDouble()); }
		else if (rule == "set" && n >= 3) { setKey.Push(w[1].MakeLower()); setValue.Push(w[2].ToDouble()); }
		else if (rule == "theme" && n >= 2)
		{
			themeName.Push(w[1]); themeKey.Push(""); themeValue.Push(""); // marks the theme even with no keys
			for (int i = 2; i < n; i++)
			{
				int eq = w[i].IndexOf("=");
				if (eq <= 0) { ok = false; continue; }
				themeName.Push(w[1]); themeKey.Push(w[i].Left(eq).MakeLower()); themeValue.Push(w[i].Mid(eq + 1));
			}
		}
		else ok = false;
		if (!ok) errors.Push(String.Format("line %d not understood: %s", number, line));
	}

	// A named number from a 'set' line.
	double Value(String key, double fallback = 0)
	{
		key = key.MakeLower();
		for (int i = 0; i < setKey.Size(); i++) if (setKey[i] == key) return setValue[i];
		return fallback;
	}

	// Average points per encounter at an area level (section 6.1): geometric between anchors.
	double AveragePoints(int level)
	{
		int n = levelAt.Size();
		if (!n) return 0;
		if (level <= levelAt[0]) return levelPoints[0];
		for (int i = 1; i < n; i++)
		{
			if (level > levelAt[i]) continue;
			double t = double(level - levelAt[i - 1]) / (levelAt[i] - levelAt[i - 1]);
			return levelPoints[i - 1] * (levelPoints[i] / levelPoints[i - 1]) ** t;
		}
		return levelPoints[n - 1];
	}

	// Chance a dungeon at this area level has a Black and White titan (section 6.3).
	double TitanChanceAt(int level)
	{
		int n = titanAt.Size();
		if (!n || level < titanAt[0]) return 0;
		for (int i = 1; i < n; i++)
		{
			if (level > titanAt[i]) continue;
			double t = double(level - titanAt[i - 1]) / (titanAt[i] - titanAt[i - 1]);
			return titanChance[i - 1] + (titanChance[i] - titanChance[i - 1]) * t;
		}
		return titanChance[n - 1];
	}

	int ThemeCount()
	{
		int count = 0;
		for (int i = 0; i < themeKey.Size(); i++) if (themeKey[i] == "") count++;
		return count;
	}

	// One theme value, such as ThemeGet("Crypt", "kinds"), or "" when absent.
	String ThemeGet(String theme, String key)
	{
		key = key.MakeLower();
		for (int i = 0; i < themeName.Size(); i++) if (themeName[i] ~== theme && themeKey[i] == key) return themeValue[i];
		return "";
	}

	// Glob match of a lower-case pattern against a lower-case name; '*' matches any run of characters.
	static bool Match(String pat, String name)
	{
		Array<String> parts;
		pat.Split(parts, "*", TOK_KEEPEMPTY);
		if (parts.Size() == 1) return pat == name;
		int at = 0;
		int last = parts.Size() - 1;
		if (name.Left(parts[0].Length()) != parts[0]) return false;
		at = parts[0].Length();
		for (int i = 1; i < last; i++)
		{
			if (!parts[i].Length()) continue;
			int found = name.IndexOf(parts[i], at);
			if (found < 0) return false;
			at = found + parts[i].Length();
		}
		int tail = parts[last].Length();
		return name.Length() - at >= tail && name.Mid(name.Length() - tail) == parts[last];
	}

	static int FirstMatch(Array<String> pats, String name)
	{
		for (int i = 0; i < pats.Size(); i++) if (Match(pats[i], name)) return i;
		return -1;
	}
}

class DoomerfallEncounterPool play
{
	DoomerfallEncounterData data;
	Array<DoomerfallMonster> monsters;
	// Classes that were monster-like but left out, for the test dump.
	Array<String> excludedName, excludedWhy;

	static play DoomerfallEncounterPool Get()
	{
		let h = DoomerfallEncounterPoolHolder(StaticEventHandler.Find("DoomerfallEncounterPoolHolder"));
		if (!h) return null;
		if (!h.pool) h.pool = Build();
		return h.pool;
	}

	static DoomerfallEncounterPool Build()
	{
		let p = new("DoomerfallEncounterPool");
		p.data = DoomerfallEncounterData.Load();
		for (int i = 0; i < AllActorClasses.Size(); i++) p.Consider(AllActorClasses[i]);
		return p;
	}

	private void Skip(String name, String why) { excludedName.Push(name); excludedWhy.Push(why); }

	private void Consider(class<Actor> cls)
	{
		let def = GetDefaultByType(cls);
		// Only hostile monsters that can act. This drops Colourful Hell's wrapper stubs (not monsters), spawners and
		// decorations. Monsters not counted as kills are mostly summoned helpers, so they need an 'include' rule.
		if (!def.bIsMonster || def.bFriendly || def.health <= 0 || !def.SeeState) return;
		String name = cls.GetClassName();
		String low = name.MakeLower();
		if (!def.bCountKill && data.FirstMatch(data.includePat, low) < 0) { Skip(name, "not-counted"); return; }
		int ex = data.FirstMatch(data.excludePat, low);
		if (ex >= 0) { Skip(name, data.excludeWhy[ex]); return; }
		if (Actor.GetReplacement(cls) != cls) { Skip(name, "replaced-by-" .. Actor.GetReplacement(cls).GetClassName()); return; }
		// The engine defines every game's monsters (Heretic, Hexen, ID24 and so on). Keep those whose art is loaded.
		if (!HasArt(def.SpawnState) && !HasArt(def.SeeState)) { Skip(name, "no-sprites"); return; }

		int kind = KindOf(cls, low);
		if (kind < 0) { Skip(name, "no-kind"); return; }

		let m = new("DoomerfallMonster");
		m.cls = cls;
		m.kind = kind;
		m.health = def.health;
		m.radius = def.radius;
		m.height = def.height;

		// Traits: the kind's defaults, class flags, then the data file's additions.
		m.traits = data.kindTraits[kind];
		if (def.bFloat || def.bNoGravity) m.traits |= DoomerfallMonster.T_FLIES;
		int style = def.GetRenderStyle();
		if (def.bShadow || def.bStealth || style == STYLE_Fuzzy || style == STYLE_OptFuzzy) m.traits |= DoomerfallMonster.T_STEALTHY;
		for (int i = 0; i < data.traitPat.Size(); i++) if (data.Match(data.traitPat[i], low)) m.traits |= data.traitBits[i];

		// Tier and points: 'own' rules first (tier 8), then the colour or family ladder.
		double kindPoints = data.kindPoints[kind];
		int own = data.FirstMatch(data.ownPat, low);
		if (own >= 0)
		{
			m.tier = 8;
			m.group = data.ownLabel[own];
			String mode = data.ownMode[own];
			if (mode == "fixed") m.points = data.ownA[own];
			else if (mode == "scale")
			{
				int stockHealth = max(1, data.kindHealth[kind]);
				m.points = kindPoints * sqrt(double(m.health) / stockHealth) * data.ownA[own];
			}
			else
			{
				double t = clamp((m.health - data.ownA[own]) / max(1., data.ownC[own] - data.ownA[own]), 0., 1.);
				m.points = data.ownB[own] + (data.ownD[own] - data.ownB[own]) * t;
			}
		}
		else
		{
			int t = data.FirstMatch(data.tierPat, low);
			int g = t >= 0 ? data.tierGroup[t] : data.FindGroup("Stock");
			m.group = g >= 0 ? data.groupName[g] : "Stock";
			m.tier = g >= 0 ? data.groupTier[g] : 1;
			m.points = kindPoints * (g >= 0 ? data.groupMult[g] : 1);
		}

		m.capped = data.FirstMatch(data.cappedPat, low) >= 0;

		// Civil War safety (section 5.5).
		m.unsafeWhy = "";
		for (int i = 0; i < data.unsafeKind.Size(); i++) if (data.unsafeKind[i] == kind) m.unsafeWhy = data.unsafeKindWhy[i];
		if (m.unsafeWhy == "" && (m.traits & DoomerfallMonster.T_SUMMONS)) m.unsafeWhy = "summons";
		if (m.unsafeWhy == "")
		{
			int u = data.FirstMatch(data.unsafePat, low);
			if (u >= 0) m.unsafeWhy = data.unsafeWhy[u];
		}
		m.civilWarSafe = m.unsafeWhy == "";
		monsters.Push(m);
	}

	// Whether a state sequence shows a sprite frame that exists in the loaded data, within its first few states.
	private static bool HasArt(State s)
	{
		int none = Actor.GetSpriteIndex("TNT1");
		for (int i = 0; s && i < 16; i++, s = s.NextState)
			if (s.sprite != none && s.ValidateSpriteFrame()) return true;
		return false;
	}

	// The kind: a class-name rule, else the nearest ancestor that is a stock kind class or a 'kindclass' entry.
	private int KindOf(class<Actor> cls, String low)
	{
		int p = data.FirstMatch(data.kindPat, low);
		if (p >= 0) return data.kindPatKind[p];
		for (class<Object> c = cls; c; c = c.GetParentClass())
		{
			String a = c.GetClassName();
			for (int i = 0; i < data.kindStock.Size(); i++) if (data.kindStock[i] ~== a) return i;
			a = a.MakeLower();
			for (int i = 0; i < data.kindClass.Size(); i++) if (data.kindClass[i] == a) return data.kindClassKind[i];
		}
		return -1;
	}

	int CountKind(int kind)
	{
		int n = 0;
		for (int i = 0; i < monsters.Size(); i++) if (monsters[i].kind == kind) n++;
		return n;
	}
}

// Holds the pool for the session. The pool is built on first use, after skill replacements are known.
class DoomerfallEncounterPoolHolder : StaticEventHandler
{
	DoomerfallEncounterPool pool;
}
