version "4.10"

// Test only, loaded by tools/attributes/attributes_rework_test.py (fake Daggerfall peer) and attributes_rework_paired.py
// (real Daggerfall Unity) as its own pk3, never part of doomerfall.pk3. The attribute rework (owner, 2026-11-27):
// Strength and Agility gun damage, no dodge, Luck super crit.
//
// Whenever Strength, Agility and Luck (DD_SheetStat 0, 3, 7) change and then stay put for SettleTics, measures over a
// few tics, then prints "ATTRRW measured str=.. agi=.. luck=..":
//   ATTRRW curve str agi luck weapon first second rifle hits=<median of Hits real 1000-point hitscan hits> boom=<median
//     blast damage of a tagged rocket fired by the weapon (explosives only, else -1)>
//     Each weapon is held for the measurement only (ReadyWeapon set, with DRLA's type tokens as its Select state
//     gives them, DoomerfallWeaponTokens), so no switch animation is needed.
//   ATTRRW luck str agi luck weapon hits=<n> crits=<n>     n real hitscan hits, a crit is above 3x the median
//   ATTRRW blast luck blasts=<n> allcrit=<n> nocrit=<n> mixed=<n> targets=<per blast>
//     real explosions (ExplodeMissile) of rockets tagged by DoomerfallShots as fired by the rocket launcher, each
//     reaching BlastTargets dummies; a blast crits all or none
//   ATTRRW burn luck ticks=<n> crits=<n> base=<median>   DoomerfallBurn's real burn ticks on dummies
//   ATTRRW dodge agi hits=<n> evaded=<n> modzero=<n>      real 1-point hits on the player (none with attrrw_nohits), and DodgeHits GetModifiedDamage calls
class AttrRwDummy : Actor
{
	Default
	{
		Health 1000000000;
		Radius 8;
		Height 128;
		+SHOOTABLE
		+ISMONSTER
		+NOGRAVITY
		+NOBLOOD
		+NOPAIN
		+DONTTHRUST
	}
}

class AttrRework : StaticEventHandler
{
	const SettleTics = 8;
	const Hits = 7;
	const LuckHits = 2500;
	const LuckChunk = 500;
	const Blasts = 400;
	const BlastChunk = 40;
	const BlastTargets = 3;
	const BurnerCount = 40;
	const BurnWaitTics = 130;
	const DodgeHits = 400;

	static const String Stock[] = { "Fist", "Chainsaw", "Shotgun", "RocketLauncher", "Chaingun", "Pistol" };
	static const String Drla[] = { "RLFist", "RLChainsaw", "RLCombatShotgun", "RLRocketLauncher", "RLChaingun", "RLPistol", "RLMarksmanRifle", "RLGrammatonClericBeretta" };

	int lastS, lastA, lastL, stable, step, sub;
	Array<Actor> burners;
	Array<int> burnLast;
	Array<int> burnTicks;
	int burnWait;

	override void OnRegister() { lastS = -2; }

	static class<Weapon> Cls(String n) { return (class<Weapon>)(n); }
	bool HaveDrla() { return Cls("RLPistol") != null; }
	int WeaponCount() { return HaveDrla() ? Drla.Size() : Stock.Size(); }
	class<Weapon> WeaponAt(int i) { return HaveDrla() ? (class<Weapon>)(Drla[i]) : (class<Weapon>)(Stock[i]); }

	static const String TokenNames[] = { "RLPistolTypeWeapon", "RLShotgunTypeWeapon", "RLSingleShotRifleTypeWeapon", "RLRapidfireTypeWeapon", "RLMeleeTypeWeapon" };

	// Holds a weapon of this class (with its DRLA tokens) until Release.
	Weapon prevWeapon;
	Weapon Hold(PlayerInfo p, class<Weapon> wc)
	{
		let mo = p.mo;
		let w = Weapon(mo.FindInventory(wc));
		if (!w) { mo.GiveInventory(wc, 1); w = Weapon(mo.FindInventory(wc)); }
		if (!w) return null;
		prevWeapon = p.ReadyWeapon;
		p.ReadyWeapon = w;
		int bits = DoomerfallWeaponTokens.Of(wc);
		for (int i = 0; i < TokenNames.Size(); i++)
		{
			class<Inventory> tc = TokenNames[i];
			if (tc) { if (bits & (1 << i)) mo.GiveInventory(tc, 1); else mo.TakeInventory(tc, 999); }
		}
		return w;
	}

	void Release(PlayerInfo p)
	{
		for (int i = 0; i < TokenNames.Size(); i++) { class<Inventory> tc = TokenNames[i]; if (tc) p.mo.TakeInventory(tc, 999); }
		p.ReadyWeapon = prevWeapon;
	}

	Actor Front(Actor mo, double dist = 0)
	{
		return Actor.Spawn("AttrRwDummy", mo.Vec3Angle(mo.radius + 20 + dist, mo.Angle), NO_REPLACE);
	}

	// Damage of one real 1000-point hitscan hit (a puff is the inflictor) at the dummy.
	int Shot(Actor mo, Actor dummy)
	{
		int before = dummy.Health;
		mo.LineAttack(mo.Angle, 128, 0, 1000, 'Hitscan', "BulletPuff");
		return before - dummy.Health;
	}

	static int Median(Array<int> v)
	{
		if (!v.Size()) return -1;
		Array<int> s;
		s.Copy(v);
		for (int i = 1; i < s.Size(); i++) for (int j = i; j > 0 && s[j - 1] > s[j]; j--) { int t = s[j]; s[j] = s[j - 1]; s[j - 1] = t; }
		return s[s.Size() / 2];
	}

	// A rocket the held launcher fires: spawned by the player with the trigger down, tagged by DoomerfallShots' real
	// rule, then parked out of the way.
	Actor FireRocket(PlayerInfo p)
	{
		let mo = p.mo;
		bool down = p.attackdown;
		p.attackdown = true;
		let r = Actor.Spawn("Rocket", mo.Vec3Angle(mo.radius + 8, mo.Angle, mo.Height / 2), NO_REPLACE);
		r.target = mo;
		DoomerfallShots.Tag(r);
		p.attackdown = down;
		r.SetOrigin(mo.Pos + (0, 0, -2000), false);
		r.bNoInteraction = true;
		r.Vel = (0, 0, 0);
		return r;
	}

	// Explodes a rocket among BlastTargets fresh dummies; returns each dummy's loss in out. The player is made
	// invulnerable meanwhile (the blast is next to them).
	void Blast(PlayerInfo p, Actor r, out Array<int> lost)
	{
		lost.Clear();
		let mo = p.mo;
		int cheats = p.cheats;
		p.cheats |= CF_GODMODE;
		Array<Actor> ds;
		Array<int> before;
		vector3 at = mo.Vec3Angle(mo.radius + 60, mo.Angle);
		for (int i = 0; i < BlastTargets; i++)
		{
			let d = Actor.Spawn("AttrRwDummy", at + ((i - 1) * 24, (i - 1) * 8, 0), NO_REPLACE);
			ds.Push(d);
			before.Push(d.Health);
		}
		r.bNoInteraction = false;
		r.SetOrigin(at + (0, 0, 40), false);
		r.ExplodeMissile();
		for (int i = 0; i < ds.Size(); i++) { lost.Push(before[i] - ds[i].Health); ds[i].Destroy(); }
		if (r) r.Destroy();
		p.cheats = cheats;
	}

	override void WorldTick()
	{
		let p = players[consoleplayer];
		let mo = p.mo;
		if (!mo) return;
		TickBurn(mo);
		int s = Actor.DD_SheetStat(0), a = Actor.DD_SheetStat(3), l = Actor.DD_SheetStat(7);
		if (s != lastS || a != lastA || l != lastL) { lastS = s; lastA = a; lastL = l; stable = 0; step = 0; sub = 0; return; }
		if (step < 0 || ++stable < SettleTics) return;
		mo.Vel = (0, 0, 0);
		int n = WeaponCount();
		if (step < n) { Curve(p, step, s, a, l); step++; return; }
		if (step == n) // Luck: hitscan crits with a pistol, then fists
		{
			class<Weapon> wc = Cls(HaveDrla() ? "RLPistol" : "Pistol");
			if (sub >= LuckHits / LuckChunk) wc = Cls(HaveDrla() ? "RLFist" : "Fist");
			LuckChunkHits(p, wc, s, a, l);
			if (++sub >= 2 * (LuckHits / LuckChunk)) { step++; sub = 0; }
			return;
		}
		if (step == n + 1) { BlastChunkRun(p, l); if (++sub >= Blasts / BlastChunk) { step++; sub = 0; } return; }
		if (step == n + 2) { Dodge(p, a); step++; return; }
		if (step == n + 3) { if (l > 50 || l == 50) StartBurn(mo); step++; return; }
		if (step == n + 4) { if (burners.Size() && ++burnWait < BurnWaitTics) return; EndBurn(l); step++; return; }
		Console.Printf("ATTRRW measured str=%d agi=%d luck=%d drla=%d item=%d", s, a, l, HaveDrla(), mo.FindInventory("DoomerfallAttributeEffects") ? 1 : 0);
		step = -1;
	}

	void Curve(PlayerInfo p, int i, int s, int a, int l)
	{
		let mo = p.mo;
		class<Weapon> wc = WeaponAt(i);
		if (!wc) return;
		let w = Hold(p, wc);
		if (!w) { Console.Printf("ATTRRW missing %s", wc.GetClassName()); return; }
		int first, second;
		[first, second] = DoomerfallWeaponCategory.Both(w);
		Array<int> v;
		let d = Front(mo);
		for (int k = 0; k < Hits; k++) v.Push(Shot(mo, d));
		d.Destroy();
		int boom = -1;
		if (first == DoomerfallWeaponCategory.Explosive || second == DoomerfallWeaponCategory.Explosive)
		{
			Array<int> b, lost;
			for (int k = 0; k < Hits; k++) { Blast(p, FireRocket(p), lost); if (lost.Size()) b.Push(lost[0]); }
			boom = Median(b);
		}
		Console.Printf("ATTRRW curve %d %d %d %s %s %s %d hits=%d boom=%d", s, a, l, wc.GetClassName(), DoomerfallWeaponCategory.Label(first),
			DoomerfallWeaponCategory.Label(second), DoomerfallRifleTag.IsRifleClass(wc), Median(v), boom);
		Release(p);
	}

	Array<int> luckVals;
	void LuckChunkHits(PlayerInfo p, class<Weapon> wc, int s, int a, int l)
	{
		let mo = p.mo;
		int part = sub % (LuckHits / LuckChunk);
		if (part == 0) luckVals.Clear();
		if (!Hold(p, wc)) return;
		let d = Front(mo);
		for (int k = 0; k < LuckChunk; k++) luckVals.Push(Shot(mo, d));
		d.Destroy();
		Release(p);
		if (part + 1 < LuckHits / LuckChunk) return;
		int m = Median(luckVals), crits = 0;
		for (int k = 0; k < luckVals.Size(); k++) if (luckVals[k] > 3 * m) crits++;
		Console.Printf("ATTRRW luck %d %d %d %s hits=%d crits=%d median=%d", s, a, l, wc.GetClassName(), luckVals.Size(), crits, m);
	}

	int bAll, bNone, bMixed, bCount;
	Array<int> blastFirst;
	void BlastChunkRun(PlayerInfo p, int l)
	{
		if (sub == 0) { bAll = 0; bNone = 0; bMixed = 0; bCount = 0; blastFirst.Clear(); }
		class<Weapon> wc = Cls(HaveDrla() ? "RLRocketLauncher" : "RocketLauncher");
		Array<int> rows; // flattened: BlastTargets values per blast
		if (Hold(p, wc))
		{
			Array<int> lost;
			for (int k = 0; k < BlastChunk; k++)
			{
				Blast(p, FireRocket(p), lost);
				for (int t = 0; t < lost.Size(); t++) rows.Push(lost[t]);
				if (lost.Size()) blastFirst.Push(lost[0]);
			}
			Release(p);
		}
		allRows.Append(rows);
		if (sub + 1 < Blasts / BlastChunk) return;
		// Each target's normal damage is the median over all blasts at its spot; a crit is above 3x that.
		Array<int> med;
		for (int t = 0; t < BlastTargets; t++)
		{
			Array<int> col;
			for (int k = t; k < allRows.Size(); k += BlastTargets) col.Push(allRows[k]);
			med.Push(Median(col));
		}
		for (int k = 0; k + BlastTargets <= allRows.Size(); k += BlastTargets)
		{
			int c = 0;
			for (int t = 0; t < BlastTargets; t++) if (allRows[k + t] > 3 * med[t]) c++;
			bCount++;
			if (c == BlastTargets) bAll++; else if (c == 0) bNone++; else bMixed++;
		}
		Console.Printf("ATTRRW blast %d blasts=%d allcrit=%d nocrit=%d mixed=%d targets=%d base=%d,%d,%d", l, bCount, bAll, bNone, bMixed,
			BlastTargets, med[0], med[1], med[2]);
		allRows.Clear();
	}
	Array<int> allRows;

	void Dodge(PlayerInfo p, int a)
	{
		let mo = p.mo;
		int evaded = 0, zero = 0;
		for (int k = 0; k < DodgeHits; k++)
		{
			if (mo.GetModifiedDamage('None', 10, true) <= 0) zero++;
		}
		// Real hits on the player: 1 point each, health put back after each, so the player never dies. What DamageMobj
		// reports dealt is the measure (0 or less: evaded).
		// Skipped in a paired game (attrrw_nohits), where the hits would cost Daggerfall's real HP.
		int hp = mo.health;
		let nohits = CVar.FindCVar("attrrw_nohits");
		int realHits = nohits && nohits.GetBool() ? 0 : DodgeHits;
		for (int k = 0; k < realHits; k++)
		{
			if (mo.DamageMobj(null, null, 1, 'None') <= 0) evaded++;
			mo.health = hp;
			p.health = hp;
		}
		Console.Printf("ATTRRW dodge %d hits=%d evaded=%d modzero=%d agiitem=%d", a, realHits, evaded, zero, mo.FindInventory("DoomerfallAgilityEffects") ? 1 : 0);
	}

	void StartBurn(Actor mo)
	{
		burners.Clear();
		burnLast.Clear();
		burnTicks.Clear();
		burnWait = 0;
		for (int i = 0; i < BurnerCount; i++)
		{
			let d = Actor.Spawn("AttrRwDummy", mo.Pos + ((i % 8) * 20 - 80, (i / 8) * 20 + 200, -2000), NO_REPLACE);
			d.bNoInteraction = true;
			burners.Push(d);
			burnLast.Push(d.Health);
			DoomerfallBurn.Apply(d, 15000, mo); // 1000 per 0.2 s step
		}
	}

	void TickBurn(Actor mo)
	{
		for (int i = 0; i < burners.Size(); i++)
		{
			let d = burners[i];
			if (!d) continue;
			int lost = burnLast[i] - d.Health;
			burnLast[i] = d.Health;
			if (lost > 0) burnTicks.Push(lost);
		}
	}

	void EndBurn(int l)
	{
		int m = Median(burnTicks), crits = 0;
		for (int k = 0; k < burnTicks.Size(); k++) if (burnTicks[k] > 3 * m) crits++;
		if (burners.Size()) Console.Printf("ATTRRW burn %d ticks=%d crits=%d base=%d", l, burnTicks.Size(), crits, m);
		for (int i = 0; i < burners.Size(); i++) if (burners[i]) burners[i].Destroy();
		burners.Clear();
		burnTicks.Clear();
	}
}
