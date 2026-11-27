// Test hook: with +set dd_weapontypes_test 1, prints "WEAPTYPES class <class> types=<types> brief=<brief>" for every
// loaded weapon class (what Daggerfall's description would show), then gives the player each gun DRLA's tokens matter
// for (any class with a DoomerfallWeaponTokens entry, plus each stock gun), waits until it is held (DRLA gives its type
// tokens only then), and prints "WEAPTYPES held <class> <both> <bothofclass> heldclass=<class>", where both is
// DoomerfallWeaponCategory.Both of the held gun and bothofclass is BothOfClass of its class, as "first/second" labels.
// Ends with "WEAPTYPES done". tools/weapon_types/run_weapontypes_test.py runs it and checks the output.
class DoomerfallWeaponTypesTest : StaticEventHandler
{
	const WaitTics = 70;
	const SettleTics = 10;

	Array<String> guns;
	int next, wait, held;
	bool active, listed, finished;

	override void WorldLoaded(WorldEvent e)
	{
		let flag = CVar.FindCVar("dd_weapontypes_test");
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
			bool now = p.ReadyWeapon && p.ReadyWeapon.GetClassName() == guns[next] && p.PendingWeapon == WP_NOCHANGE;
			held = now ? held + 1 : 0;
			if (wait > 0 && held < SettleTics) return;
			Report(p, guns[next]);
			if (next >= 2) p.mo.TakeInventory((class<Inventory>)(guns[next - 2]), 1); // Long put away: keeps DRLA's carry limit clear.
			next++;
		}
		while (next < guns.Size())
		{
			class<Weapon> c = guns[next];
			p.mo.GiveInventory(c, 1);
			let w = Weapon(p.mo.FindInventory(c));
			if (!w) { Console.Printf("WEAPTYPES held %s not-given", guns[next]); next++; continue; }
			p.PendingWeapon = w;
			wait = WaitTics;
			held = 0;
			return;
		}
		finished = true;
		Console.Printf("WEAPTYPES done");
	}

	void Report(PlayerInfo p, String cls)
	{
		int a, b, c, d;
		[a, b] = DoomerfallWeaponCategory.Both(p.ReadyWeapon);
		[c, d] = DoomerfallWeaponCategory.BothOfClass((class<Weapon>)(cls));
		String heldName = p.ReadyWeapon ? String.Format("%s", p.ReadyWeapon.GetClassName()) : "none";
		Console.Printf("WEAPTYPES held %s %s/%s %s/%s heldclass=%s", cls,
			DoomerfallWeaponCategory.Label(a), DoomerfallWeaponCategory.Label(b),
			DoomerfallWeaponCategory.Label(c), DoomerfallWeaponCategory.Label(d), heldName);
	}

	void List()
	{
		listed = true;
		static const String stock[] = { "Fist", "Chainsaw", "Pistol", "Shotgun", "SuperShotgun", "Chaingun", "RocketLauncher", "PlasmaRifle", "BFG9000" };
		for (int i = 0; i < stock.Size(); i++) guns.Push(stock[i]);
		for (int i = 0; i < AllActorClasses.Size(); i++)
		{
			class<Weapon> c = (class<Weapon>)(AllActorClasses[i]);
			if (!c) continue;
			Console.Printf("WEAPTYPES class %s types=%s brief=%s", c.GetClassName(), DoomerfallWeaponTypes.Types(c), DoomerfallWeaponTypes.Brief(c));
			if (DoomerfallWeaponTokens.Of(c) != 0 && guns.Find(c.GetClassName()) == guns.Size()) guns.Push(c.GetClassName());
		}
	}
}
