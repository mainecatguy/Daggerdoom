// Which gun fired a shot (owner, 2026-11-27): every projectile the player fires carries a tag naming the gun and its
// weapon type, and everything that shot spawns (its explosion actors, shrapnel, fragments, penetrating follow-up
// shots, and their own spawns in turn) carries a copy of the same tag. Gun perks read it to know which gun caused a
// hit, so a rocket fired before a weapon switch still counts for the launcher. Doom only: the tag is an item in the
// actor's inventory, so Doom's own saves keep it with the projectile. Daggerfall never sees it.
//
//   fired      a projectile (MISSILE flag, or by default if it already exploded at point blank) whose target is the player, spawned next to the player while the trigger is down or the gun
//              is mid-fire, is the held gun's shot (generation 0).
//   spawned    an actor whose target is the player (A_SpawnItemEx, A_CustomMissile and the like set it to the player
//              for anything a player's missile spawns), spawned near a tagged actor that is alive or was destroyed this
//              tic, is that actor's child: it copies the tag (generation + 1). When both rules fit, the nearer wins.
//   hitscan    bullets keep the simple rule: a puff's hit lands in the tic it is fired, so the held gun fired it
//              (DoomerfallShots.Find answers that for a puff). Puffs are not tagged.
// Items, monsters and players are never tagged. Without a Daggerfall character nothing is tagged, so a Doom-only game
// is unchanged.
class DoomerfallShotTag : Inventory
{
	Actor shooter;          // the player's body
	class<Weapon> gun;      // the gun that fired the shot
	int category, second;   // DoomerfallWeaponCategory.Both of the gun when it fired
	int skill;              // DoomerfallWeaponCategory.SkillSlotOf of the gun when it fired (-1: none)
	int fireTic;            // level.maptime of the shot
	int generation;         // 0: fired by the gun; 1: spawned by that shot; and so on
	bool autoBurst;         // Automatics: the shot was one of a burst's first shots (DoomerfallAutomatics)

	Default
	{
		Inventory.MaxAmount 1;
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
	}
	States { Spawn: TNT1 A -1; Stop; }

	clearscope static DoomerfallShotTag Of(Actor a)
	{
		return a ? DoomerfallShotTag(a.FindInventory("DoomerfallShotTag")) : null;
	}

	void CopyFrom(DoomerfallShotTag t)
	{
		shooter = t.shooter;
		gun = t.gun;
		category = t.category;
		second = t.second;
		skill = t.skill;
		fireTic = t.fireTic;
		generation = t.generation + 1;
		autoBurst = t.autoBurst;
	}
}

class DoomerfallShots : StaticEventHandler
{
	const SheetValid = 2; // DFB_SHEET_VALID (bridge/doomerfall_bridge.h)
	const ChildReach = 128; // how far from its parent a spawned child may appear

	// Tagged actors alive now, and tags of tagged actors destroyed this tic (detached from them so they outlive them;
	// their pos is where the actor died). Both rebuilt after a save loads.
	Array<Actor> tagged;
	Array<DoomerfallShotTag> fallen;

	int logged;
	static void Log(String msg)
	{
		let h = DoomerfallShots(StaticEventHandler.Find("DoomerfallShots"));
		let all = CVar.FindCVar("dd_perklog");
		if (!h || (h.logged >= 200 && !(all && all.GetBool()))) return;
		h.logged++;
		DDLog.Debug(String.Format("shots: %s", msg));
	}

	// The gun behind damage this player deals through this inflictor: the inflictor's tag, or for a bullet's puff the
	// held gun. Null tag and false when neither applies (a barrel, a monster's shot, a projectile from nowhere).
	static bool Find(Actor player, Actor inflictor, out class<Weapon> gun, out int skill, out DoomerfallShotTag tag)
	{
		gun = null;
		skill = -1;
		tag = null;
		if (!player || !player.player || !inflictor) return false;
		if (inflictor.bIsPuff)
		{
			let w = player.player.ReadyWeapon;
			if (!w) return false;
			gun = w.GetClass();
			skill = DoomerfallWeaponCategory.SkillSlotOf(w);
			return true;
		}
		if (inflictor == player) tag = Exploding(player); // a BFG ball's spray hits with the player as inflictor
		else
		{
			tag = DoomerfallShotTag.Of(inflictor);
			// A shot that hit at point blank deals its damage inside the firing action, before its spawn event.
			if (!tag && inflictor.GetAge() == 0) tag = Tag(inflictor);
		}
		if (!tag || tag.shooter != player) { tag = null; return false; }
		gun = tag.gun;
		skill = tag.skill;
		return true;
	}

	// A_BFGSpray (and mods' sprays like it) damages with the player's body as the inflictor, from inside the ball's
	// death frame. The ball is the player's tagged projectile that has exploded (no longer a missile) and entered its
	// current frame this tic.
	private static DoomerfallShotTag Exploding(Actor player)
	{
		let h = DoomerfallShots(StaticEventHandler.Find("DoomerfallShots"));
		if (!h) return null;
		for (int i = 0; i < h.tagged.Size(); i++)
		{
			let a = h.tagged[i];
			if (!a || a.bMissile || !a.default.bMissile || !a.CurState || a.tics != a.CurState.Tics) continue;
			let t = DoomerfallShotTag.Of(a);
			if (t && t.shooter == player) return t;
		}
		return null;
	}

	static bool Active()
	{
		return Actor.DD_SheetValue(SheetValid) == 1;
	}

	// The tag of a newly spawned actor, tagging it first if a rule above fits. Safe to call more than once.
	static DoomerfallShotTag Tag(Actor m)
	{
		if (!m || !m.target || !m.target.player || m.target.player.mo != m.target) return null;
		let have = DoomerfallShotTag.Of(m);
		if (have) return have;
		if (m.bIsPuff || m.bIsMonster || m.player || m is "Inventory" || !Active()) return null;
		let h = DoomerfallShots(StaticEventHandler.Find("DoomerfallShots"));
		return h ? h.Classify(m) : null;
	}

	private DoomerfallShotTag Classify(Actor m)
	{
		let pmo = m.target;
		let p = pmo.player;

		// The nearest tagged actor of this player: a possible parent.
		DoomerfallShotTag parent = null;
		double best = ChildReach;
		for (int i = 0; i < tagged.Size(); i++)
		{
			let a = tagged[i];
			if (!a || a == m) continue;
			let t = DoomerfallShotTag.Of(a);
			if (!t || t.shooter != pmo) continue;
			double d = a.Distance3D(m);
			if (d < best) { best = d; parent = t; }
		}
		for (int i = 0; i < fallen.Size(); i++)
		{
			let t = fallen[i];
			if (!t || t.shooter != pmo) continue;
			double d = (m.pos - t.pos).Length();
			if (d < best) { best = d; parent = t; }
		}

		// The held gun firing it.
		let w = p.ReadyWeapon;
		bool firing = w && (p.attackdown || ((p.cmd.buttons | p.oldbuttons) & (BT_ATTACK | BT_ALTATTACK)) || !(p.WeaponState & WF_WEAPONREADY));
		double fromPlayer = m.Distance2D(pmo);
		// A sibling fired in the same tic (a spray of shrapnel or pellets) is not a parent.
		bool sibling = parent && parent.generation == 0 && parent.fireTic == level.maptime;
		// Only a projectile is fired by the gun (one that hit at point blank has already exploded and lost its MISSILE
		// flag, so its class default counts); its helper actors (DRLA's recoil and reload effects) are not shots.
		bool fired = (m.bMissile || m.default.bMissile) && firing && fromPlayer <= pmo.radius + m.radius + 64 && (!parent || sibling || fromPlayer <= best);

		if (!fired && !parent) return null;
		let tag = DoomerfallShotTag(Actor.Spawn("DoomerfallShotTag"));
		if (!tag) return null;
		if (fired)
		{
			tag.shooter = pmo;
			tag.gun = w.GetClass();
			int first, second;
			[first, second] = DoomerfallWeaponCategory.Both(w);
			tag.category = first;
			tag.second = second;
			tag.skill = DoomerfallWeaponCategory.SkillSlotOf(w);
			tag.fireTic = level.maptime;
		}
		else tag.CopyFrom(parent);
		tag.AttachToOwner(m);
		tagged.Push(m);
		Log(String.Format("tag %s gun %s skill %d gen %d tic %d", m.GetClassName(), tag.gun ? tag.gun.GetClassName() : 'None',
			tag.skill, tag.generation, level.maptime));
		return tag;
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		Tag(e.Thing);
	}

	override void WorldThingDestroyed(WorldEvent e)
	{
		let a = e.Thing;
		if (!a || !a.target || !a.target.player) return;
		let t = DoomerfallShotTag.Of(a);
		if (!t && a.GetAge() == 0) t = Tag(a); // gone before its spawn event (point blank, or into a wall)
		if (!t) return;
		// Keep the tag (not the dying actor) until the next tic, for whatever the actor spawned as it died.
		a.RemoveInventory(t);
		t.SetXYZ(a.pos);
		fallen.Push(t);
	}

	override void WorldTick()
	{
		for (int i = 0; i < fallen.Size(); i++) if (fallen[i]) fallen[i].Destroy();
		fallen.Clear();
		for (int i = tagged.Size() - 1; i >= 0; i--) if (!tagged[i]) tagged.Delete(i);
	}

	override void WorldLoaded(WorldEvent e)
	{
		tagged.Clear();
		fallen.Clear();
		let it = ThinkerIterator.Create("DoomerfallShotTag", Thinker.STAT_INVENTORY);
		DoomerfallShotTag t;
		while (t = DoomerfallShotTag(it.Next()))
		{
			if (t.owner) tagged.Push(t.owner);
			else t.Destroy(); // a dead shot's tag saved mid-tic
		}
		if (tagged.Size()) Log(String.Format("loaded %d tagged actors", tagged.Size()));
	}

	override void WorldUnloaded(WorldEvent e)
	{
		tagged.Clear();
		fallen.Clear();
	}
}
