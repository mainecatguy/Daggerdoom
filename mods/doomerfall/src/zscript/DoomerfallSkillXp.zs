// Skill XP and weapon skill use from damage (owner, 2026-11-26; work/backlog/skills-in-doom.md).
// Doom tallies the damage the player deals to monsters, townspeople and guards. Each hit counts at most the health it
// took, so overkill gives nothing and a monster gives at most its health per life. Every 100 HP in all is 1 Skill XP;
// every 250 HP dealt with one weapon skill's guns (DoomerfallShots.Find: the gun that fired the shot) is 1 use of that
// skill. About once a second the whole amounts go to the engine as "dfs_xp:<xp>:<skill>:<uses>" network events
// (dd_skillxp.cpp), which passes them to Daggerfall. Doom keeps the remainders and never saves them (owner: "We don't
// need to save/load the remainder"). Daggerfall owns the pool, the prices and the skills.
// Nothing is counted without a Daggerfall character, so a Doom-only game is unchanged.
class DoomerfallSkillXp : StaticEventHandler
{
	const HpPerXp = 100;
	const HpPerUse = 250;
	const FlushTics = 35;
	const MaxSkills = 64;

	int xpHp;                // damage not yet reported as Skill XP
	int useHp[MaxSkills];    // damage per weapon skill slot not yet reported as uses

	override void WorldThingDamaged(WorldEvent e)
	{
		let t = e.Thing;
		let src = e.DamageSource;
		if (!t || !src || !src.player || src.player.mo != src || t == src || e.Damage <= 0) return;
		if (!t.bIsMonster && !t.player && t.GetClassName() != 'DFTownsperson') return;
		if (!DoomerfallShots.Active()) return;
		int counted = e.Damage + min(0, t.health); // the health this hit took; overkill is not counted
		if (counted <= 0) return;
		xpHp = min(xpHp + counted, 0x3FFFFFFF);

		class<Weapon> gun;
		int skill;
		DoomerfallShotTag tag;
		if (!DoomerfallShots.Find(src, e.Inflictor, gun, skill, tag) && (!e.Inflictor || e.Inflictor == src) && src.player.ReadyWeapon)
			skill = DoomerfallWeaponCategory.SkillSlotOf(src.player.ReadyWeapon); // a melee hit with no puff
		if (skill >= 0 && skill < MaxSkills) useHp[skill] = min(useHp[skill] + counted, 0x3FFFFFFF);
	}

	override void WorldTick()
	{
		if (level.maptime % FlushTics) return;
		int xp = xpHp / HpPerXp;
		bool sent = false;
		for (int i = 0; i < MaxSkills; i++)
		{
			int uses = useHp[i] / HpPerUse;
			if (uses <= 0) continue;
			useHp[i] -= uses * HpPerUse;
			EventHandler.SendNetworkEvent(String.Format("dfs_xp:%d:%d:%d", sent ? 0 : xp, i, uses));
			sent = true;
		}
		if (!sent && xp > 0) EventHandler.SendNetworkEvent(String.Format("dfs_xp:%d:-1:0", xp));
		xpHp -= xp * HpPerXp;
	}
}
