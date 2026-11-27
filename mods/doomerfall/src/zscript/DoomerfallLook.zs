// The label under the crosshair: a short name for what the player looks at, if it is close enough to interact with
// (owner, 2026-11-24). The engine picks the target and its name (UZDoom/src/dd_look.cpp) and sends "dflook:<label>"
// only when the label changes, so it is empty off Daggerfall maps and outside bridge sessions. Drawn like Doomerfall's
// other labels (Sneaking, the loaded ammo): SmallFont at DoomerfallText.Scale(), centred, just below the crosshair.
class DoomerfallLook : StaticEventHandler
{
	ui String label;

	override void InterfaceProcess(ConsoleEvent e)
	{
		if (e.Name.Left(7) == "dflook:") label = e.Name.Mid(7);
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (label.Length() == 0 || automapactive || consoleplayer < 0) return;
		let p = players[consoleplayer];
		if (p.mo == null || p.health <= 0 || p.camera != p.mo) return;

		int scale = DoomerfallText.Scale();
		int w = SmallFont.StringWidth(label) * scale;
		// The crosshair sits at the centre of the 3D view, drawn at crosshairscale * screen height / 200 (about 16
		// pixels tall at 1x), so the label starts below its lower edge with a small gap.
		int vx, vy, vw, vh;
		[vx, vy, vw, vh] = Screen.GetViewWindow();
		let cs = CVar.FindCVar("crosshairscale");
		double crossScale = max(1.0, Screen.GetHeight() * (cs ? cs.GetFloat() : 0.5) / 200.0);
		int top = vy + vh / 2 + int(8 * crossScale) + 4 * scale;
		Screen.DrawText(SmallFont, Font.CR_GOLD, vx + (vw - w) / 2, top, label, DTA_ScaleX, scale, DTA_ScaleY, scale);
	}
}

// A Doom item's name for the look label and Daggerfall's inventory (UZDoom/src/dd_items.cpp ItemName calls Of; the
// engine then removes color codes and DRLA's " [Pickup]"). DRLA gives most of its pickups no Tag, only a pickup message
// ("Picked up a stimpack."), so a missing Tag is filled in, in this order: the Tag of the stock item the class replaces
// (RLStimpack replaces Stimpack: "Stimpack"), the pickup message cut down to its noun ("Stimpack"), the class name
// ("RLMarathonStimpack": "Marathon Stimpack"). Inventory's default message ("You got a pickup") never names anything.
// A Tag that is an untranslated string id (DRLA's RLSoulsphere has "TAG_MEGASPHERE") counts as none, and a trailing
// "Pickup" word is dropped (DRLA's RLClip is "Clip Pickup").
class DoomerfallItemName play
{
	static String Of(Actor mo)
	{
		if (mo == null) return "";
		String tag = TagOf(mo.GetTag(NoTag));
		if (tag.Length() > 0) return tag;
		class<Actor> replaced = Actor.GetReplacee(mo.GetClass());
		if (replaced && replaced != mo.GetClass())
		{
			tag = TagOf(GetDefaultByType(replaced).GetTag(NoTag));
			if (tag.Length() > 0) return tag;
		}
		let inv = Inventory(mo);
		if (inv)
		{
			tag = FromMessage(StringTable.Localize(inv.PickupMsg));
			if (tag.Length() > 0) return tag;
		}
		return FromClassName(mo.GetClassName());
	}

	// GetTag("") would answer the class name for an actor without a Tag, so a mark that is never a Tag stands in.
	const NoTag = "@@doomerfall-no-tag@@";

	// The tag without a trailing "Pickup" word, or "" for none or a string id.
	static String TagOf(String tag)
	{
		if (tag == NoTag) return "";
		bool id = tag.IndexOf("_") >= 0;
		for (int i = 0; id && i < tag.Length(); i++)
		{
			int c = tag.ByteAt(i);
			id = c == 95 || (c >= 65 && c <= 90) || (c >= 48 && c <= 57);
		}
		if (id) return "";
		static const String trail[] = { " [Pickup]", " Pickups", " Pickup" };
		for (int i = 0; i < trail.Size(); i++)
		{
			int n = trail[i].Length();
			if (tag.Length() > n && tag.Mid(tag.Length() - n) ~== trail[i]) tag.Truncate(tag.Length() - n);
		}
		return tag;
	}

	// "Picked up a small health canister." -> "Small Health Canister". Empty for a message that does not say what it is.
	static String FromMessage(String msg)
	{
		if (msg.Length() == 0 || msg ~== StringTable.Localize("$TXT_DEFAULTPICKUPMSG") || msg.IndexOf("%") >= 0) return "";
		msg.StripRight();
		while (msg.Length() > 0 && (msg.ByteAt(msg.Length() - 1) == 46 || msg.ByteAt(msg.Length() - 1) == 33)) msg.Truncate(msg.Length() - 1); // . !
		static const String lead[] = { "you picked up ", "you pick up ", "picked up ", "pick up ", "you got ", "you found ", "found ", "got ", "a ", "an ", "the ", "some " };
		for (bool cut = true; cut; )
		{
			cut = false;
			for (int i = 0; i < lead.Size(); i++)
			{
				int n = lead[i].Length();
				if (msg.Length() > n && msg.Left(n) ~== lead[i])
				{
					msg = msg.Mid(n);
					cut = true;
				}
			}
		}
		// A leading count ("10 Bullets") is how many, not what.
		int digits = 0;
		while (digits < msg.Length() && msg.ByteAt(digits) >= 48 && msg.ByteAt(digits) <= 57) digits++;
		if (digits > 0 && digits < msg.Length() && msg.ByteAt(digits) == 32) msg = msg.Mid(digits + 1);
		if (msg.Length() == 0) return "";
		Array<String> words;
		msg.Split(words, " ");
		// A sentence ("This laser can fire through anything", "Cloaking device activated") does not name the item.
		static const String sentence[] = { "you", "your", "this", "these", "there", "it", "its", "is", "are", "was", "has", "have", "had", "been", "will", "now", "activated" }; // Not "can": "Fuel Can".
		for (int i = 0; i < words.Size(); i++)
		{
			String w = words[i].MakeLower();
			for (int j = 0; j < sentence.Size(); j++)
				if (w == sentence[j]) return "";
		}
		// Title case like the stock tags ("Armor Bonus"), small words after the first kept low ("Sixpack of Soda").
		String title = "";
		for (int i = 0; i < words.Size(); i++)
		{
			String w = words[i];
			bool lower = i > 0 && (w == "of" || w == "the" || w == "a" || w == "an" || w == "and" || w == "for" || w == "with" || w == "to" || w == "in");
			if (!lower && w.Length() > 0) w = w.Left(1).MakeUpper() .. w.Mid(1);
			title = i > 0 ? title .. " " .. w : w;
		}
		return TagOf(title);
	}

	// "RLMarathonStimpack" -> "Marathon Stimpack": DRLA's RL prefix and a Pickup suffix dropped, words split.
	static String FromClassName(String cls)
	{
		if (cls.Length() > 2 && cls.Left(2) == "RL" && cls.ByteAt(2) >= 65 && cls.ByteAt(2) <= 90) cls = cls.Mid(2);
		if (cls.Length() > 6 && cls.Mid(cls.Length() - 6) ~== "Pickup") cls.Truncate(cls.Length() - 6);
		String words = "";
		for (int i = 0; i < cls.Length(); i++)
		{
			int c = cls.ByteAt(i), prev = i > 0 ? cls.ByteAt(i - 1) : 0;
			if (c == 95) c = 32; // _
			bool upper = c >= 65 && c <= 90, prevLower = prev >= 97 && prev <= 122, prevDigit = prev >= 48 && prev <= 57;
			if (upper && (prevLower || prevDigit)) words = words .. " ";
			words.AppendFormat("%c", c);
		}
		return words;
	}
}
