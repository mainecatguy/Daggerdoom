// What Daggerfall's item description says about a Doom gun (todo: weapontypes 01): the weapon skills it counts as and a
// brief description. Doom sends both with the gun's sprite and name (dd_items.cpp, SendArt), so this runs only when
// Daggerfall asks.
class DoomerfallWeaponTypes abstract
{
	// The gun's types, for example "Energy, Shotgun", or "" for a gun in no skill (or not a gun). The same tags the skill
	// code uses: DoomerfallWeaponCategory's two categories (first, then second), named only where they have a skill,
	// then Rifle where DoomerfallRifleTag tags the gun.
	clearscope static String Types(class<Actor> c)
	{
		class<Weapon> wc = (class<Weapon>)(c);
		if (!wc) return "";
		int first, second;
		[first, second] = DoomerfallWeaponCategory.BothOfClass(wc);
		String res = TypeName(first);
		String two = TypeName(second);
		if (two != "") res = res == "" ? two : res .. ", " .. two;
		if (DoomerfallRifleTag.IsRifleClass(wc)) res = res == "" ? "Rifle" : res .. ", Rifle";
		return res;
	}

	// A category's player-facing type name, or "" for a category with no skill (Other, Precision).
	clearscope static String TypeName(int category)
	{
		if (DoomerfallWeaponCategory.SkillSlot(category) < 0) return "";
		switch (category)
		{
			case DoomerfallWeaponCategory.Unarmed: return "Hand-to-Hand";
			case DoomerfallWeaponCategory.Melee: return "Melee";
			case DoomerfallWeaponCategory.Pistol: return "Pistol";
			case DoomerfallWeaponCategory.Shotgun: return "Shotgun";
			case DoomerfallWeaponCategory.Automatic: return "Automatic";
			case DoomerfallWeaponCategory.Explosive: return "Explosive";
			case DoomerfallWeaponCategory.Energy: return "Energy";
		}
		return "";
	}

	// A brief description from the gun's own mod data, or "". DRLA describes each gun in its PDA text
	// (PDA_WEAPON_<class without RL>_DESC in language.weapons); the brief is that text's quoted one-line summary where it
	// has one, for example "Your trusty 10mm pistol. It may be nice, but better find something stronger.", else its first
	// sentence. Stock Doom has no weapon descriptions.
	clearscope static String Brief(class<Actor> c)
	{
		if (!(class<Weapon>)(c)) return "";
		String cls = c.GetClassName();
		if (cls.Left(2) ~== "RL") cls = cls.Mid(2);
		cls = cls.MakeUpper();
		String key = "PDA_WEAPON_" .. cls .. "_DESC";
		String text = StringTable.Localize("$" .. key);
		if (text == key || text == "") return "";
		String esc = String.Format("%c", 0x1C); // Doom's color escape, which DRLA's "\c" becomes
		// Most basic guns have a quoted summary in DRLA's quote color: \cu"..."\c-.
		int quote = text.IndexOf(esc .. "u\"");
		if (quote >= 0)
		{
			int close = text.IndexOf("\"", quote + 3);
			if (close > quote + 3) return Plain(text.Mid(quote + 3, close - quote - 3));
		}
		// Otherwise the first sentence of the first line that is not a stat line ("\c[Orange]Fire rate\c-: 19 tics").
		Array<String> lines;
		text.Split(lines, "\n");
		for (int i = 0; i < lines.Size(); i++)
		{
			if (lines[i].IndexOf(esc .. "-:") >= 0) continue;
			String line = Plain(lines[i]);
			if (line != "") return FirstSentence(line);
		}
		return "";
	}

	// Up to and including the first ". ", "! " or "? ", or the whole line; cut at a word with "..." past MaxBrief bytes.
	const MaxBrief = 200;
	private clearscope static String FirstSentence(String s)
	{
		int cut = s.Length();
		static const String ends[] = { ". ", "! ", "? " };
		for (int i = 0; i < ends.Size(); i++)
		{
			int at = s.IndexOf(ends[i]);
			if (at >= 0 && at + 1 < cut) cut = at + 1;
		}
		String res = s.Left(cut);
		if (res.Length() > MaxBrief)
		{
			int space = res.RightIndexOf(" ", MaxBrief);
			res = res.Left(space > 0 ? space : MaxBrief) .. "...";
		}
		return res;
	}

	// Text without Doom's color codes (\c followed by one letter or a [Name]) or line breaks.
	private clearscope static String Plain(String s)
	{
		String res = "";
		int i = 0;
		while (i < s.Length())
		{
			int ch, next;
			[ch, next] = s.GetNextCodePoint(i);
			if (ch == 0x1C) // Doom's color escape
			{
				if (next < s.Length() && s.ByteAt(next) == 0x5B) // '[': a named color, up to ']'
				{
					int end = s.IndexOf("]", next);
					i = end < 0 ? s.Length() : end + 1;
				}
				else i = next + 1; // one color letter
				continue;
			}
			if (ch == 0x0A || ch == 0x0D) ch = 0x20;
			res.AppendCharacter(ch);
			i = next;
		}
		res.StripLeftRight();
		return res;
	}
}
