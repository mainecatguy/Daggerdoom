// Test hook: with +set dd_rifletag_test 1, prints "RIFLETAG weapons <n>" for the number of loaded weapon classes,
// "RIFLETAG tagged <class>" for each one DoomerfallRifleTag tags, then gives the player each tagged gun in turn, waits
// until it is held (DRLA gives its type tokens only then), and prints "RIFLETAG held <class> <category> <second>",
// ending with "RIFLETAG done". tools/rifle_tag/run_rifletag_test.py runs it with and without DRLA and checks it.
class DoomerfallRifleTagTest : StaticEventHandler
{
	const WaitTics = 70;

	Array<String> tagged;
	int next, wait;
	bool active, listed, finished;

	override void WorldLoaded(WorldEvent e)
	{
		let flag = CVar.FindCVar("dd_rifletag_test");
		active = flag && flag.GetBool() && !finished;
		next = 0;
		wait = 0;
	}

	override void WorldTick()
	{
		if (!active || finished) return;
		let p = players[consoleplayer];
		if (!p.mo) return;
		if (!listed) List();
		if (wait > 0)
		{
			wait--;
			if (wait > 0 && p.ReadyWeapon && p.ReadyWeapon.GetClassName() == tagged[next] && p.PendingWeapon == WP_NOCHANGE && wait < WaitTics - 35)
				wait = 0; // Held and settled: DRLA's Select state has given its tokens.
			if (wait > 0) return;
			int first, second;
			[first, second] = DoomerfallWeaponCategory.Both(p.ReadyWeapon);
			String heldName = p.ReadyWeapon ? String.Format("%s", p.ReadyWeapon.GetClassName()) : "none";
			Console.Printf("RIFLETAG held %s %s %s heldclass=%s", tagged[next], DoomerfallWeaponCategory.Label(first), DoomerfallWeaponCategory.Label(second), heldName);
			next++;
		}
		while (next < tagged.Size())
		{
			class<Weapon> c = tagged[next];
			p.mo.GiveInventory(c, 1);
			let w = Weapon(p.mo.FindInventory(c));
			if (!w) { Console.Printf("RIFLETAG held %s not-given", tagged[next]); next++; continue; }
			p.PendingWeapon = w;
			wait = WaitTics;
			return;
		}
		finished = true;
		Console.Printf("RIFLETAG done");
	}

	void List()
	{
		listed = true;
		int weapons = 0;
		for (int i = 0; i < AllActorClasses.Size(); i++)
		{
			class<Weapon> c = (class<Weapon>)(AllActorClasses[i]);
			if (!c) continue;
			weapons++;
			if (DoomerfallRifleTag.IsRifleClass(c)) tagged.Push(c.GetClassName());
		}
		Console.Printf("RIFLETAG weapons %d", weapons);
		for (int i = 0; i < tagged.Size(); i++)
			Console.Printf("RIFLETAG tagged %s", tagged[i]);
	}
}
