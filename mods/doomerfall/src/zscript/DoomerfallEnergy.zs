// The Energy Weapons skill in Doom (work/backlog/skills-in-doom.md, Energy Weapons; perks cards 06 and 08).
// Daggerfall decides the rules from the live skill and sends them in the character sheet (DFB_SHEET_ENERGY_*,
// DoomerfallEnergyRules.cs); Doom applies them to shots from a gun whose skill is Energy Weapons
// (DoomerfallWeaponCategory.SkillSlotOf), such as stock Doom's Plasma Rifle and BFG9000 or DRLA's plasma and laser guns.
// Without a Daggerfall character every rule reads off, so a Doom-only game is unchanged.
//
//   damage bonus   every hit from the gun's shots does +x% to others (0 to 50%).
//   splash         25: a hit that is not an explosion (no DMG_EXPLOSION: a plasma ball's impact, a laser's bullet, a BFG
//                  ray) also deals x% of the damage it did to every other live, unfriendly monster within the radius
//                  that the hit enemy can see. Never the player or the hit enemy. Splash damage gets no damage bonus and
//                  never splashes again (its inflictor is a DoomerfallEnergySplash, which is not the gun's shot).
//   speed          25/50/75/100: the gun's projectiles (generation 0 of the shared shot tag, still flying when their spawn
//                  event runs) fly x% faster. Hitscan guns have no projectiles, so it does nothing for them.
//   burn           a direct hit (any hit of the gun's shots that is not an explosion, so a BFG ray too, but not the
//                  perk's splash or a blast) sets the enemy burning for x% of the damage it did, over 3 s
//                  (DoomerfallBurn, card 07). Stacks without limit.
//   convert        50/75/100: before its own burn is added, a direct hit takes x% of the enemy's remaining burn and
//                  deals it at once (inflictor DoomerfallEnergyBurst: no damage bonus, splash, burn or convert from it).
//   burst          100: the converted damage also bursts out: every other live, unfriendly monster within the radius
//                  that the hit enemy can see starts burning for x% of it. That burn is ordinary burn, so only a later
//                  direct hit converts it (no chain). Never the player.
//
// Which shots are the gun's: the shared shot tag (DoomerfallShots.zs), as for Explosives. Fractional damage rounds with
// the chance of the fraction.
class DoomerfallEnergy : StaticEventHandler
{
	// DFB_SHEET_* indices; must match bridge/doomerfall_bridge.h.
	const SheetValid = 2;
	const SkillEnergy = 9;
	const EnergyDamageBp = 173;
	const EnergySplashBp = 174;
	const EnergySplashRadius = 175;
	const EnergySpeedBp = 176;

	clearscope static int Rule(int index)
	{
		return max(0, Actor.DD_SheetValue(index));
	}

	// damage * factor, rounding the fraction up with its chance; at least minimum.
	static int Scale(int damage, double factor, int minimum = 1)
	{
		double x = damage * factor;
		int whole = int(x);
		if (frandom[DoomerfallEnergy](0, 1) < x - whole) whole++;
		return max(minimum, whole);
	}

	int logged;
	static void Log(String msg)
	{
		let h = Get();
		let all = CVar.FindCVar("dd_perklog");
		if (!h || (h.logged >= 200 && !(all && all.GetBool()))) return;
		h.logged++;
		DDLog.Debug(String.Format("energy: %s", msg));
	}

	static DoomerfallEnergy Get()
	{
		return DoomerfallEnergy(StaticEventHandler.Find("DoomerfallEnergy"));
	}

	// Whether damage this player deals through this inflictor came from an Energy Weapons gun: the shot's tag, or the
	// held gun for a bullet's puff (DoomerfallShots.Find). Splash is not the gun's shot.
	static bool FromGun(Actor player, Actor inflictor)
	{
		if (!inflictor || inflictor is "DoomerfallEnergySplash" || inflictor is "DoomerfallEnergyBurst") return false;
		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		return DoomerfallShots.Find(player, inflictor, gun, skill, tag) && skill == SkillEnergy;
	}

	override void WorldTick()
	{
		if (Actor.DD_SheetValue(SheetValid) != 1) return; // Rules come from Daggerfall's character only.
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = playeringame[i] ? players[i].mo : null;
			if (mo && mo.health > 0 && !mo.FindInventory("DoomerfallEnergyPerks")) mo.GiveInventory("DoomerfallEnergyPerks", 1);
		}
	}

	// Projectile speed: the gun's own projectiles, as they start flying.
	override void WorldThingSpawned(WorldEvent e)
	{
		let m = e.Thing;
		if (!m || !m.bMissile || !m.target || !m.target.player) return;
		int bp = Rule(EnergySpeedBp);
		if (bp <= 0) return;
		let tag = DoomerfallShots.Tag(m); // tags it now if DoomerfallShots has not yet; safe to repeat
		if (!tag || tag.generation != 0 || tag.skill != SkillEnergy || tag.shooter != m.target) return;
		double f = 1 + bp / 10000.;
		double before = m.vel.Length();
		m.vel *= f;
		m.Speed *= f;
		Log(String.Format("speed %s x%.4f %.2f -> %.2f tic %d", m.GetClassName(), f, before, m.vel.Length(), level.maptime));
	}

	// Splash and burn: a hit from the gun's shots that is not an explosion.
	override void WorldThingDamaged(WorldEvent e)
	{
		let victim = e.Thing;
		let src = e.DamageSource;
		if (e.Damage <= 0 || !victim || victim.player || !src || !src.player || src.player.mo != src) return;
		if (e.DamageFlags & DMG_EXPLOSION) return;
		if (!FromGun(src, e.Inflictor)) return;
		Splash(e, victim, src);
		DoomerfallEnergyBurn.Hit(victim, src, e.Damage);
	}

	void Splash(WorldEvent e, Actor victim, Actor src)
	{
		int bp = Rule(EnergySplashBp), radius = Rule(EnergySplashRadius);
		if (bp <= 0 || radius <= 0) return;

		Vector3 centre = victim.pos + (0, 0, victim.height / 2);
		Array<Actor> near;
		let it = BlockThingsIterator.CreateFromPos(centre.x, centre.y, centre.z - radius, victim.height + 2 * radius, radius, false);
		while (it.Next())
		{
			let mo = it.thing;
			if (!mo || mo == victim || mo.player || !mo.bIsMonster || !mo.bShootable || mo.health <= 0 || mo.bFriendly) continue;
			Vector3 d = mo.pos + (0, 0, mo.height / 2) - centre;
			if (d.xy.Length() - mo.radius > radius || abs(d.z) - mo.height / 2 > radius) continue;
			if (!victim.CheckSight(mo, SF_IGNOREVISIBILITY)) continue;
			near.Push(mo);
		}
		if (near.Size() == 0) return;

		let splash = Actor.Spawn("DoomerfallEnergySplash", centre); // no target: not a shot of the player's (untagged)
		int total = 0;
		for (int i = 0; i < near.Size(); i++)
		{
			if (!near[i] || near[i].health <= 0) continue;
			int amount = Scale(e.Damage, bp / 10000., 0);
			if (amount <= 0) continue;
			total += near[i].DamageMobj(splash, src, amount, e.DamageType, DMG_THRUSTLESS);
		}
		Log(String.Format("splash from %s hit %d by %s: %d enemies within %d took %d (%d bp each) tic %d", victim.GetClassName(), e.Damage,
			e.Inflictor ? e.Inflictor.GetClassName() : 'None', near.Size(), radius, total, bp, level.maptime));
	}
}

// On the player while Daggerfall's character is loaded: the damage bonus.
class DoomerfallEnergyPerks : Inventory
{
	Default
	{
		Inventory.MaxAmount 1;
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
	}

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		// Active: source is the actor being hit. The player's hits on others only.
		if (passive || damage <= 0 || !owner || !owner.player || source == owner) return;
		int bp = DoomerfallEnergy.Rule(DoomerfallEnergy.EnergyDamageBp);
		if (bp <= 0 || !DoomerfallEnergy.FromGun(owner, inflictor)) return;
		double factor = 1 + bp / 10000.;
		newdamage = DoomerfallEnergy.Scale(damage, factor);
		DoomerfallEnergy.Log(String.Format("hit %s %s: %d -> %d (x%.4f) tic %d by %s", source ? source.GetClassName() : 'None',
			(flags & DMG_EXPLOSION) ? "explosion" : "direct", damage, newdamage, factor, level.maptime, inflictor.GetClassName()));
	}
}

// The inflictor of one splash: so splash damage is told apart from the gun's own hits. Invisible, gone in a moment.
class DoomerfallEnergySplash : Actor
{
	Default
	{
		+NOBLOCKMAP
		+NOGRAVITY
		+NOINTERACTION
		+NOTONAUTOMAP
	}
	States { Spawn: TNT1 A 2; Stop; }
}
