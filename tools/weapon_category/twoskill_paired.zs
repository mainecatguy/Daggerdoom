version "3.3"

// Test only, loaded by tools/weapon_category/twoskill_paired.py as its own pk3 (never part of doomerfall.pk3).
// In a paired launch with DRLA, holds an energy shotgun (Energy + Shotgun) and an energy pistol (Pistol + Energy) in
// turn, and prints a line whenever what the held gun reads changes:
//   TWOSKILL <class> first=<category>:<slot>:<live skill> second=<category>:<slot>:<live skill> uses=<slot>
// The live skills are Daggerfall's character sheet as Doom reads it (Actor.DD_SheetSkill, -1 without a character).
class TwoSkillPaired : StaticEventHandler
{
	static const String guns[] = { "RLPlasmaShotgun", "RLPlasmaPistol" };
	const SettleTics = 20;
	const HoldTics = 70;

	int gun, timer;
	String last[2];

	override void WorldTick()
	{
		let p = players[consoleplayer];
		if (!p.mo) return;
		class<Weapon> c = guns[gun];
		if (!c)
		{
			if (timer++ == 0) Console.Printf("TWOSKILL absent %s", guns[gun]);
			return;
		}
		let w = Weapon(p.mo.FindInventory(c));
		if (!w)
		{
			p.mo.GiveInventory(c, 1);
			w = Weapon(p.mo.FindInventory(c));
			if (!w) return;
		}
		if (p.ReadyWeapon != w)
		{
			if (p.PendingWeapon != w) p.PendingWeapon = w;
			timer = 0;
			return;
		}
		if (p.PendingWeapon != WP_NOCHANGE) return;
		timer++;
		if (timer > SettleTics) Report(w); // DRLA's Select state has given its type tokens by now.
		if (timer > HoldTics)
		{
			gun = (gun + 1) % guns.Size();
			timer = 0;
		}
	}

	void Report(Weapon w)
	{
		int a, b;
		[a, b] = DoomerfallWeaponCategory.Both(w);
		int sa = DoomerfallWeaponCategory.SkillSlot(a), sb = DoomerfallWeaponCategory.SkillSlot(b);
		String line = String.Format("TWOSKILL %s first=%s:%d:%d second=%s:%d:%d uses=%d", w.GetClassName(),
			DoomerfallWeaponCategory.Label(a), sa, Actor.DD_SheetSkill(sa), DoomerfallWeaponCategory.Label(b), sb,
			Actor.DD_SheetSkill(sb), DoomerfallWeaponCategory.SkillSlotOf(w));
		if (line == last[gun]) return;
		last[gun] = line;
		Console.Printf("%s", line);
	}
}
