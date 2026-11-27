// The Explosives skill in Doom (work/backlog/skills-in-doom.md, Explosives). Daggerfall decides the rules from the
// live skill and sends them in the character sheet (DFB_SHEET_EXPL_*, DoomerfallExplosivesRules.cs); Doom applies them
// to shots from a gun whose skill is Explosives (DoomerfallWeaponCategory.SkillSlotOf), such as stock Doom's or DRLA's
// rocket launcher. Without a Daggerfall character every rule reads off, so a Doom-only game is unchanged.
//
//   damage bonus   every hit from the gun's shots, direct or splash, does +x% to others (0 to 60%).
//   self cut       the player's own splash from the gun's shots is cut by x% (95% at 25, 99% at 75).
//   direct bonus   the enemy a shot hits directly takes +x% more from that impact (50; Daggerfall sends 0 until the
//                  owner sets the amount).
//   chain          Inpulsa's Broken Heart (100): a monster the gun's shots kill explodes for x% of its maximum health
//                  in a radius; monsters those blasts kill explode at half that, and so on. The blasts never hurt a
//                  player, and get no damage bonus. They wait in a queue and at most MaxBlastsPerTic go off in one tic,
//                  so a big pack chains over a few tics instead of stalling one.
//
// Which shots are the gun's: the shared shot tag says (DoomerfallShots.zs). A rocket and everything it spawns (its
// explosion actors, a cluster rocket's fragments) carry the gun that fired it, so a shot keeps its perks after a weapon
// switch, and a rocket that explodes point blank counts too; a bullet's puff counts for the held gun. Barrels, other
// guns' shots, the chain blasts and anything else get nothing. Fractional damage rounds with the chance of the fraction.
class DoomerfallExplosives : StaticEventHandler
{
	// DFB_SHEET_* indices; must match bridge/doomerfall_bridge.h.
	const SheetValid = 2;
	const SkillExplosives = 6;
	const ExplDamageBp = 162;
	const ExplSelfCutBp = 163;
	const ExplDirectBp = 164;
	const ExplChainBp = 165;
	const ExplChainRadius = 166;

	const MaxBlastsPerTic = 16;

	clearscope static int Rule(int index)
	{
		return max(0, Actor.DD_SheetValue(index));
	}

	// damage * factor, rounding the fraction up with its chance; at least minimum.
	static int Scale(int damage, double factor, int minimum = 1)
	{
		double x = damage * factor;
		int whole = int(x);
		if (frandom[DoomerfallExplosives](0, 1) < x - whole) whole++;
		return max(minimum, whole);
	}

	int logged;
	static void Log(String msg)
	{
		let h = Get();
		let all = CVar.FindCVar("dd_perklog");
		if (!h || (h.logged >= 200 && !(all && all.GetBool()))) return;
		h.logged++;
		DDLog.Debug(String.Format("explosives: %s", msg));
	}

	static DoomerfallExplosives Get()
	{
		return DoomerfallExplosives(StaticEventHandler.Find("DoomerfallExplosives"));
	}

	// Whether damage this player deals through this inflictor came from an Explosives gun: the shot's tag, or the held
	// gun for a bullet's puff (DoomerfallShots.Find). The chain blasts are not the gun's shots.
	static bool FromGun(Actor player, Actor inflictor)
	{
		if (!inflictor || inflictor is "DoomerfallChainBlast") return false;
		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		return DoomerfallShots.Find(player, inflictor, gun, skill, tag) && skill == SkillExplosives;
	}

	// Inpulsa's Broken Heart: blasts waiting to go off.
	Array<double> qx, qy, qz;
	Array<int> qDamage, qGen;
	Array<Actor> qSource;
	Array<Name> qVictim;
	double worstMs;
	int worstQueue, chainTic, chainBlasts;

	void QueueBlast(Actor victim, Actor source, int gen)
	{
		int bp = Rule(ExplChainBp), radius = Rule(ExplChainRadius);
		if (bp <= 0 || radius <= 0) return;
		int damage = int(victim.SpawnHealth() * (bp / 10000.) / (1 << min(gen, 30)));
		if (damage < 1) return;
		qx.Push(victim.pos.x); qy.Push(victim.pos.y); qz.Push(victim.pos.z + victim.height / 2);
		qDamage.Push(damage); qGen.Push(gen); qSource.Push(source); qVictim.Push(victim.GetClassName());
		if (qx.Size() > worstQueue) worstQueue = qx.Size();
	}

	void FireBlasts()
	{
		if (qx.Size() == 0) return;
		double start = MSTimeF();
		int n = min(qx.Size(), MaxBlastsPerTic);
		int radius = max(1, Rule(ExplChainRadius));
		for (int i = 0; i < n; i++)
		{
			let b = DoomerfallChainBlast(Actor.Spawn("DoomerfallChainBlast", (qx[i], qy[i], qz[i])));
			if (!b) continue;
			b.gen = qGen[i]; // no target: the blast is not a shot of the player's (DoomerfallShots leaves it untagged)
			int hit = b.RadiusAttack(qSource[i], qDamage[i], radius, 'None', 0); // no RADF_HURTSOURCE: never the player
			Log(String.Format("blast %s gen %d damage %d radius %d hit %d tic %d", qVictim[i], qGen[i], qDamage[i], radius, hit, level.maptime));
		}
		qx.Delete(0, n); qy.Delete(0, n); qz.Delete(0, n);
		qDamage.Delete(0, n); qGen.Delete(0, n); qSource.Delete(0, n); qVictim.Delete(0, n);
		double ms = MSTimeF() - start;
		worstMs = max(worstMs, ms);
		chainBlasts += n;
		if (chainTic == 0) chainTic = level.maptime;
		if (qx.Size() > 0) return;
		// The chain is over: one line with its cost, then start counting afresh for the next one.
		Log(String.Format("chain worst tic %.2f ms for %d blasts, queue peak %d, %d tics", worstMs, chainBlasts, worstQueue, level.maptime - chainTic + 1));
		worstMs = 0; worstQueue = 0; chainBlasts = 0; chainTic = 0;
	}

	override void WorldTick()
	{
		FireBlasts();
		if (Actor.DD_SheetValue(SheetValid) != 1) return; // Rules come from Daggerfall's character only.
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			let mo = playeringame[i] ? players[i].mo : null;
			if (mo && mo.health > 0 && !mo.FindInventory("DoomerfallExplosivesPerks")) mo.GiveInventory("DoomerfallExplosivesPerks", 1);
		}
	}

	// A monster killed by the gun's shots or by a chain blast explodes in turn.
	override void WorldThingDamaged(WorldEvent e)
	{
		let victim = e.Thing;
		let src = e.DamageSource;
		if (e.Damage <= 0 || !victim || victim.player || !victim.bIsMonster || victim.health > 0 || !src || !src.player || src.player.mo != src) return;
		let blast = DoomerfallChainBlast(e.Inflictor);
		if (blast) QueueBlast(victim, src, blast.gen + 1);
		else if (FromGun(src, e.Inflictor)) QueueBlast(victim, src, 0);
	}
}

// On the player while Daggerfall's character is loaded: the damage bonuses and the cut to their own splash.
class DoomerfallExplosivesPerks : Inventory
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
		if (damage <= 0 || !owner || !owner.player) return;
		if (passive) // The player is hit: their own splash from the gun's shots.
		{
			int cut = DoomerfallExplosives.Rule(DoomerfallExplosives.ExplSelfCutBp);
			if (cut <= 0 || source != owner || !(flags & DMG_EXPLOSION) || !DoomerfallExplosives.FromGun(owner, inflictor)) return;
			newdamage = DoomerfallExplosives.Scale(damage, 1 - min(cut, 10000) / 10000., 0);
			DoomerfallExplosives.Log(String.Format("self %d -> %d (cut %d bp) by %s tic %d", damage, newdamage, cut, inflictor.GetClassName(), level.maptime));
			return;
		}
		// Active: source is the actor being hit. The player's hits on others only.
		if (source == owner || !DoomerfallExplosives.FromGun(owner, inflictor)) return;
		bool direct = !(flags & DMG_EXPLOSION);
		double factor = 1 + DoomerfallExplosives.Rule(DoomerfallExplosives.ExplDamageBp) / 10000.;
		if (direct) factor *= 1 + DoomerfallExplosives.Rule(DoomerfallExplosives.ExplDirectBp) / 10000.;
		if (factor == 1) return;
		newdamage = DoomerfallExplosives.Scale(damage, factor);
		DoomerfallExplosives.Log(String.Format("hit %s %s: %d -> %d (x%.4f) tic %d by %s", source ? source.GetClassName() : 'None',
			direct ? "direct" : "splash", damage, newdamage, factor, level.maptime, inflictor.GetClassName()));
	}
}

// One Inpulsa's Broken Heart blast: the inflictor of its damage, so a kill by it chains at the next generation, and
// the explosion the player sees and hears.
class DoomerfallChainBlast : Actor
{
	int gen;

	Default
	{
		+NOBLOCKMAP
		+NOGRAVITY
		+NOINTERACTION
		RenderStyle "Add";
		Alpha 0.9;
	}

	override void PostBeginPlay()
	{
		Super.PostBeginPlay();
		A_StartSound("weapons/rocklx", CHAN_AUTO);
	}

	States
	{
	Spawn:
		MISL B 8 Bright;
		MISL C 6 Bright;
		MISL D 4 Bright;
		Stop;
	}
}
