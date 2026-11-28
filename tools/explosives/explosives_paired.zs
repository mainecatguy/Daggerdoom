version "4.10"

// Paired-run harness for the Explosives perks (tools/explosives/explosives_paired.py). Not part of the game.
// Holds DRLA's Rocket Launcher (the stock one without DRLA) and fires one rocket per cycle at a fresh target. The first
// cycle after the skill changes puts the target 100 units ahead, so the splash reaches the player (the own-splash cut);
// later cycles put it 240 ahead, out of splash reach, to spare Daggerfall's hit points. Once the chain rule arrives
// (skill 100) it spawns a pack three times (the first warms up the monsters' art and sounds; the third is a control,
// killed at once from nowhere by 'Explosion' damage (DRLA's rocket deaths) with no rocket and no chain, to compare the
// cost of the deaths themselves): a Baron of Hell among imps
// (DRLA replaces both), the one nearest the centre left 1 health and the rest 20, fires at it, and logs each tic's
// wall time and playsim time (WorldTick to a thinker that ticks after every actor) until the chain is over.

class ExpPairTarget : Actor
{
	Default { Health 1000000; Radius 40; Height 64; +SHOOTABLE +SOLID +NOBLOOD +DONTTHRUST +NOGRAVITY }
	States { Spawn: PLAY A -1; Stop; }
}

class ExpPairProbe : Actor
{
	Default { Radius 24; Height 64; +SOLID +NOGRAVITY }
	States { Spawn: TNT1 A -1; Stop; }
}

// Ticks after every actor (statnum 101, after STAT_DEFAULT), so the harness can time each whole playsim tic.
class ExpPairTicEnd : Thinker
{
	ExpPairHarness h;
	override void Tick() { if (h) h.TicEnd(); }
}

class ExpPairHarness : EventHandler
{
	int t, cycle, lastSkill, phase, packTic, packs;
	bool near, packDone, aimed;
	int roomLogs;
	double ticStart;
	Vector3 packCentre;
	ExpPairTicEnd ender;
	Actor target;
	Array<Actor> pack;
	double lastMs;

	override void WorldThingDamaged(WorldEvent e)
	{
		if (e.Thing && e.Thing.player)
			Console.Printf("PAIRED player hurt %d by %s tic %d", e.Damage, e.Inflictor ? e.Inflictor.GetClassName() : 'None', level.maptime);
		else if (e.Thing && e.Thing.health <= 0 && pack.Find(e.Thing) < pack.Size())
			Console.Printf("PAIRED killed %s by %s tic %d", e.Thing.GetClassName(), e.Inflictor ? e.Inflictor.GetClassName() : 'None', level.maptime);
	}

	bool Ready(PlayerInfo p)
	{
		let mo = p.mo;
		class<Weapon> k = "RLRocketLauncher";
		if (!k) k = "RocketLauncher";
		let w = p.ReadyWeapon;
		if (!w || !(w is k))
		{
			if (!mo.FindInventory(k)) mo.GiveInventory(k, 1);
			p.PendingWeapon = Weapon(mo.FindInventory(k));
			return false;
		}
		if (!(p.WeaponState & WF_WEAPONREADY)) return false;
		if (w.AmmoType2) { mo.GiveInventory(w.AmmoType2, 1); mo.FindInventory(w.AmmoType2).Amount = 50; }
		let m = mo.FindInventory(w.AmmoType1);
		if (!m) { mo.GiveInventory(w.AmmoType1, 1); m = mo.FindInventory(w.AmmoType1); }
		m.Amount = max(1, w.AmmoType2 ? m.MaxAmount : 50);
		return true;
	}

	// Whether a monster-sized probe fits at pos and sees the player.
	bool Room(Actor mo, Vector3 pos)
	{
		let probe = Actor.Spawn("ExpPairProbe", pos);
		if (probe) probe.SetZ(probe.floorz); // terrain slopes: stand on the ground there
		bool ok = probe && probe.TestMobjLocation() && probe.CheckSight(mo) && abs(probe.floorz - mo.floorz) < 40;
		if (probe && !ok && roomLogs++ < 8)
			Console.Printf("PAIRED room no at %.0f,%.0f,%.0f fit=%d sight=%d floor %.0f vs %.0f", pos.x, pos.y, pos.z, probe.TestMobjLocation(), probe.CheckSight(mo), probe.floorz, mo.floorz);
		if (probe) probe.Destroy();
		return ok;
	}

	// Once, before the first shot: face the direction with the most room, so the shots and the pack have open ground
	// (the city start differs between runs). Counts the shot spot, the far target spot and the pack's grid spots.
	void Aim(Actor mo)
	{
		int best = 0, bestCount = -1;
		for (int a = 0; a < 8; a++)
		{
			double ang = mo.angle + a * 45;
			int n = 0;
			if (!Room(mo, mo.Vec3Angle(100, ang)) || !Room(mo, mo.Vec3Angle(240, ang))) n = -1;
			else
			{
				Vector3 c = mo.Vec3Angle(260, ang);
				for (int i = -3; i <= 3; i++) for (int j = -3; j <= 3; j++) if (Room(mo, c + (i * 36, j * 36, 0))) n++;
			}
			if (n > bestCount) { bestCount = n; best = a; }
		}
		mo.angle += best * 45;
		Console.Printf("PAIRED aim %d room %d", best * 45, bestCount);
	}

	void SpawnPack(PlayerInfo p)
	{
		let mo = p.mo;
		Vector3 c = mo.Vec3Angle(260, mo.angle);
		let baron = Actor.Spawn("BaronOfHell", c, ALLOW_REPLACE);
		baron.SetZ(baron.floorz); baron.angle = mo.angle; // terrain slopes: stand on the ground there
		for (int i = -3; i <= 3; i++)
			for (int j = -3; j <= 3; j++)
			{
				if (i == 0 && j == 0) continue;
				let m = Actor.Spawn("DoomImp", baron.Vec3Offset(i * 36, j * 36, 0), ALLOW_REPLACE);
				if (!m) continue;
				m.SetZ(m.floorz);
				if (!m.TestMobjLocation() || !m.CheckSight(baron)) { m.Destroy(); continue; }
				m.health = 20; m.angle = mo.angle; pack.Push(m);
			}
		mo.pitch = 0;
		packCentre = c;
		pack.Clear(); // DRLA spawns its monsters through spawner actors: the real ones are collected a few tics later
	}

	// The monsters that came out of the spawners: the one nearest the centre is left 1 health, the rest 20.
	void CollectPack()
	{
		let it = ThinkerIterator.Create("Actor");
		Actor a, nearest;
		while (a = Actor(it.Next()))
		{
			if (!a.bIsMonster || a.player || a.health <= 0 || (a.pos.xy - packCentre.xy).Length() > 300) continue;
			a.health = 20;
			pack.Push(a);
			if (!nearest || (a.pos.xy - packCentre.xy).Length() < (nearest.pos.xy - packCentre.xy).Length()) nearest = a;
		}
		if (nearest) { nearest.health = 1; pack.Delete(pack.Find(nearest)); pack.Insert(0, nearest); }
		Console.Printf("PAIRED pack start %d size %d first %s second %s tic %d", packs, pack.Size(), nearest ? nearest.GetClassName() : 'None',
			pack.Size() > 1 ? pack[1].GetClassName() : 'None', level.maptime);
	}

	// The city's own encounters attack the player and Daggerfall's hit points are real here (no buddha): monsters
	// that target the player and are not the test pack leave quietly, so the run lives to skill 100.
	void RemoveHostiles(Actor mo)
	{
		Array<Actor> gone;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (!a.bIsMonster || a.player || a.health <= 0 || a.target != mo || pack.Find(a) < pack.Size()) continue;
			if (phase >= 10 && (a.pos.xy - packCentre.xy).Length() <= 320) continue;
			gone.Push(a);
		}
		for (int i = 0; i < gone.Size(); i++) { Console.Printf("PAIRED removed hostile %s tic %d", gone[i].GetClassName(), level.maptime); gone[i].Destroy(); }
	}

	// What the player's own protection does to a 100-point fire explosion before the perk sees it, and what they carry.
	void LogProtection(Actor mo)
	{
		String inv = "";
		for (let i = mo.Inv; i; i = i.Inv) if (!(i is "Weapon") && !(i is "Ammo")) inv = inv .. " " .. i.GetClassName() .. (i.Amount != 1 ? String.Format("x%d", i.Amount) : "");
		Console.Printf("PAIRED protection modified=%d factor=%d health %d inv%s", mo.GetModifiedDamage('Fire', 100, true, null, mo, DMG_EXPLOSION),
			mo.ApplyDamageFactor('Fire', 100), mo.health, inv);
	}

	void TicEnd()
	{
		if (phase >= 10) Console.Printf("PAIRED cost tic %d %.2f", level.maptime, MSTimeF() - ticStart);
	}

	override void WorldTick()
	{
		PlayerInfo p = players[consoleplayer];
		let mo = p.mo;
		double now = MSTimeF();
		if (phase >= 10 && lastMs > 0) Console.Printf("PAIRED tic %d gap %.1f", level.maptime, now - lastMs);
		lastMs = now;
		ticStart = now;
		if (!ender) { ender = new("ExpPairTicEnd"); ender.ChangeStatNum(101); ender.h = self; }
		if (!mo || mo.health <= 0 || level.maptime < 140 || Actor.DD_SheetValue(2) != 1) return;
		int skill = Actor.DD_SheetSkill(6);
		// DRLA's random class can be the Demolitionist (RadiusDamageFactor 0: immune to its own splash), which would
		// hide the own-splash cut. Give it the normal factor.
		if (mo.RadiusDamageFactor != 1) { Console.Printf("PAIRED radius factor %.2f -> 1", mo.RadiusDamageFactor); mo.RadiusDamageFactor = 1; }
		if (level.maptime % 5 == 0) RemoveHostiles(mo);
		if (phase >= 10) { PackTick(p); return; }
		if (!target)
		{
			if (!Ready(p)) return;
			if (!aimed) { Aim(mo); aimed = true; }
			if (DoomerfallRules.Get(10) > 0 && packs < 3) { phase = 10; packTic = level.maptime; SpawnPack(p); return; }
			near = skill != lastSkill && DoomerfallRules.Get(8) > 0;
			lastSkill = skill;
			mo.pitch = 0;
			target = Actor.Spawn("ExpPairTarget", mo.Vec3Angle(near ? 100 : 240, mo.angle, 0));
			t = 0; cycle++;
			Console.Printf("PAIRED start %d skill=%d dmg=%d cut=%d direct=%d chain=%d radius=%d near=%d", cycle, skill,
				DoomerfallRules.Get(7), DoomerfallRules.Get(8), DoomerfallRules.Get(9), DoomerfallRules.Get(10), DoomerfallRules.Get(11), near);
			if (near) LogProtection(mo);
			return;
		}
		if (t == 0) { p.attackdown = true; if (p.WeaponState & WF_WEAPONREADY) { mo.FireWeapon(null); t = 1; } return; }
		p.attackdown = false;
		if (++t == 50)
		{
			Console.Printf("PAIRED end %d skill=%d", cycle, skill);
			target.Destroy();
			target = null;
		}
	}

	// Pack: wait a second (baseline frame times), fire at the baron, then watch until the chain has been quiet a while.
	void PackTick(PlayerInfo p)
	{
		let mo = p.mo;
		int age = level.maptime - packTic;
		if (phase == 10 && age == 8) CollectPack();
		if (phase == 10 && age >= 35)
		{
			if (packs == 2) // control: the same pack killed at once from nowhere, no rocket and no chain
			{
				Console.Printf("PAIRED pack fire tic %d control", level.maptime);
				for (int i = 0; i < pack.Size(); i++) if (pack[i] && pack[i].health > 0) pack[i].DamageMobj(null, null, pack[i].health + 100, 'Explosion');
				phase = 11;
				return;
			}
			if (pack[0]) mo.angle = mo.AngleTo(pack[0]);
			p.attackdown = true;
			if (p.WeaponState & WF_WEAPONREADY) { Console.Printf("PAIRED pack fire tic %d", level.maptime); mo.FireWeapon(null); phase = 11; }
			return;
		}
		p.attackdown = false;
		if (phase == 11 && age >= 35 + 140)
		{
			int dead = 0;
			for (int i = 0; i < pack.Size(); i++) if (pack[i] && pack[i].health <= 0) dead++;
			Console.Printf("PAIRED pack end %d dead %d of %d tic %d", packs, dead, pack.Size(), level.maptime);
			packs++;
			for (int i = 0; i < pack.Size(); i++) if (pack[i] && pack[i].health > 0) pack[i].Destroy(); // survivors leave quietly
			pack.Clear();
			packDone = true;
			phase = 0;
		}
	}
}
