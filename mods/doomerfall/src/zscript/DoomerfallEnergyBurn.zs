// Plasma burn, the Energy Weapons skill's burn perks (work/backlog/skills-in-doom.md, Energy Weapons; perks card 08).
// Doom's shared rules turn the live skill from Daggerfall's character sheet into the numbers (DoomerfallRules.zs,
// EnergyBurn* ...); this applies them through the general burn system (DoomerfallBurn.zs, card 07). DoomerfallEnergy calls Hit for each
// direct hit of an Energy Weapons gun's shots (not an explosion, not the perk's splash, not this file's burst).
//
//   25+   the hit enemy burns for BurnBp of the hit's damage over 3 s, stacking without limit.
//   50+   first, ConvertBp of the enemy's remaining burn is taken and dealt at once (so a hit never converts its own burn).
//         Dealt with DMG_DD_DEALT: the hit that sized the burn already had the player's multipliers.
//   100   that converted amount also bursts out: other live, unfriendly monsters within BurstRadius that the hit enemy can
//         see start burning for BurstBp of it. Their burn is ordinary burn: a later direct hit converts it, so bursts
//         spread but never chain by themselves. Never the player.
class DoomerfallEnergyBurn play
{
	const EnergyBurnBp = DoomerfallRules.EnergyBurnBp;
	const EnergyConvertBp = DoomerfallRules.EnergyConvertBp;
	const EnergyBurstBp = DoomerfallRules.EnergyBurstBp;
	const EnergyBurstRadius = DoomerfallRules.EnergyBurstRadius;

	static void Hit(Actor victim, Actor src, int damage)
	{
		int burnBp = DoomerfallEnergy.Rule(EnergyBurnBp);
		if (burnBp <= 0 || !victim) return;
		int convertBp = DoomerfallEnergy.Rule(EnergyConvertBp);
		// A hit that kills still converts (its record lives until the next tick): nothing is dealt to the corpse, but at
		// 100 the converted burn still bursts.
		if (convertBp > 0)
		{
			double before = DoomerfallBurn.Pool(victim);
			double taken = before > 0 ? DoomerfallBurn.Take(victim, convertBp / 10000.) : 0;
			if (taken > 0)
			{
				int amount = Round(taken);
				int burstBp = DoomerfallEnergy.Rule(EnergyBurstBp), radius = DoomerfallEnergy.Rule(EnergyBurstRadius);
				let burst = Actor.Spawn("DoomerfallEnergyBurst", victim.pos + (0, 0, victim.height / 2));
				int dealt = amount > 0 && victim.health > 0 ? victim.DamageMobj(burst, src, amount, 'Fire', DMG_THRUSTLESS | DMG_DD_DEALT) : 0;
				int spread = 0;
				if (burstBp > 0 && radius > 0 && burst) spread = Burst(burst, victim, src, taken * burstBp / 10000., radius);
				DoomerfallEnergy.Log(String.Format("convert %s: took %.3f of its burn %.3f, dealt %d; burst %d enemies %.2f burn each tic %d",
					victim.GetClassName(), taken, before, dealt, spread, taken * burstBp / 10000., level.maptime));
			}
		}
		if (!victim || victim.health <= 0) return;
		double burn = damage * burnBp / 10000.;
		DoomerfallBurn.Apply(victim, burn, src);
		DoomerfallEnergy.Log(String.Format("burn %s hit %d: +%.2f burn, pool %.2f tic %d", victim.GetClassName(), damage, burn,
			DoomerfallBurn.Pool(victim), level.maptime));
	}

	// x rounded down, plus 1 with the chance of the fraction.
	static int Round(double x)
	{
		int whole = int(x);
		if (frandom[DoomerfallEnergy](0, 1) < x - whole) whole++;
		return whole;
	}

	// Sets the monsters around the victim burning for amount each; returns how many.
	static int Burst(Actor burst, Actor victim, Actor src, double amount, int radius)
	{
		DoomerfallEnergyBurst(burst).Show(radius);
		if (amount <= 0) return 0;
		Vector3 centre = burst.pos;
		int n = 0;
		let it = BlockThingsIterator.CreateFromPos(centre.x, centre.y, centre.z - radius, victim.height + 2 * radius, radius, false);
		while (it.Next())
		{
			let mo = it.thing;
			if (!mo || mo == victim || mo.player || !mo.bIsMonster || !mo.bShootable || mo.health <= 0 || mo.bFriendly) continue;
			Vector3 d = mo.pos + (0, 0, mo.height / 2) - centre;
			if (d.xy.Length() - mo.radius > radius || abs(d.z) - mo.height / 2 > radius) continue;
			if (!victim.CheckSight(mo, SF_IGNOREVISIBILITY)) continue;
			DoomerfallBurn.Apply(mo, amount, src);
			n++;
		}
		return n;
	}
}

// The inflictor of converted burn damage, and the burst's look: a puff of the burn flames (DoomerfallBurnFlame)
// thrown out to the burst's radius. No target, so it is never one of the player's shots: no damage bonus, splash,
// burn or conversion comes from it.
class DoomerfallEnergyBurst : Actor
{
	Default
	{
		+NOBLOCKMAP
		+NOGRAVITY
		+NOINTERACTION
		+NOTONAUTOMAP
	}
	States { Spawn: TNT1 A 2; Stop; }

	void Show(int radius)
	{
		if (!DoomerfallBurnLook.Enabled()) return;
		// 8 flames, 7 actors per burst after the centre: light enough for a BFG blast across a burning pack.
		let c = Actor.Spawn("DoomerfallBurnFlame", pos, NO_REPLACE);
		if (c) c.scale = (1.2, 1.2);
		double speed = radius / 24.0; // reaches the radius as the flames die
		for (int k = 0; k < 7; k++)
		{
			double a = k * (360.0 / 7) + FRandom[DoomerfallBurnLook](-20, 20);
			let f = Actor.Spawn("DoomerfallBurnFlame", pos, NO_REPLACE);
			if (!f) continue;
			f.scale = (0.8, 0.8);
			f.vel = (cos(a) * speed, sin(a) * speed, FRandom[DoomerfallBurnLook](0.5, 1.5));
		}
	}
}
