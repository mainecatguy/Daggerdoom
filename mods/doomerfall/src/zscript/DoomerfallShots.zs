// Which gun fired a shot (owner, 2026-11-27): every projectile the player fires carries a tag naming the gun and its
// weapon type, and everything that shot spawns (its explosion actors, shrapnel, fragments, penetrating follow-up
// shots, and their own spawns in turn) carries a copy of the same tag. Gun perks read it to know which gun caused a
// hit, so a rocket fired before a weapon switch still counts for the launcher. Doom only: the tag is an item in the
// actor's inventory, so Doom's own saves keep it with the projectile. Daggerfall never sees it.
//
//   exact      first, the engine names the actor whose action or tick spawned the new actor (Actor.DD_SpawnedBy,
//              UZDoom/src/dd_shotsource.cpp). Spawned by a tagged shot or a carrier (live, or destroyed this tic): it
//              copies that tag, whatever its target is. Spawned by the player while the gun fires: a projectile is the
//              held gun's shot, and a puff becomes a carrier of the held gun. So in a fight with two guns, each shot's
//              fragments and their spawns take their own shot's gun, however close the other gun's shots are.
//   carrier    a puff, or any other non-projectile the player's own action spawns while the gun fires (DRLA's recoil
//              and reload effects, a launcher's spawner actor), gets a carrier tag: it is not a shot (Find and Tag
//              ignore it, as they ignored it untagged before), it only passes the gun on to its spawns. Something the
//              player's action spawns while the gun does not fire is no gun's: untagged (never a nearby shot's child).
//   Otherwise (spawned by a monster, a barrel or a script, or by nobody the engine knows) the old rules:
//   fired      a projectile (MISSILE flag, or by default if it already exploded at point blank) whose target is the player, spawned next to the player while the trigger is down or the gun
//              is mid-fire, is the held gun's shot (generation 0).
//   spawned    an actor whose target is the player (A_SpawnItemEx, A_CustomMissile and the like set it to the player
//              for anything a player's missile spawns), spawned near a tagged actor that is alive or was destroyed this
//              tic, is that actor's child: it copies the tag (generation + 1). When both rules fit, the nearer wins.
//   hitscan    bullets keep the simple rule: a puff's hit lands in the tic it is fired, so the held gun fired it
//              (DoomerfallShots.Find answers that for a puff). A puff holds only a carrier tag.
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
	bool burstSet;          // Automatics has decided autoBurst (at the spawn event, or at a point-blank hit before it)
	bool carrier;           // not a shot: a puff or a gun's helper actor that only passes the gun on to what it spawns
	transient int serial;   // the owner's spawn serial (Actor.DD_SpawnSerial), its key in DoomerfallShots' serial buckets

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
		burstSet = t.burstSet;
	}
}

class DoomerfallShotBucket play { Array<DoomerfallShotTag> tags; }

class DoomerfallShots : StaticEventHandler
{
	const SheetValid = 2; // DFB_SHEET_VALID (bridge/doomerfall_bridge.h)
	const ChildReach = 128; // how far from its parent a spawned child may appear

	// Tagged actors alive now, and tags of tagged actors destroyed this tic (detached from them so they outlive them;
	// their pos is where the actor died). Both rebuilt after a save loads.
	Array<Actor> tagged;
	Array<DoomerfallShotTag> fallen;
	// Every live and fallen tag, by its owner's spawn serial (BucketOf). ZScript 3.3 has no Map.
	const BucketCount = 256;
	Array<DoomerfallShotBucket> buckets;

	DoomerfallShotBucket BucketOf(int serial)
	{
		if (buckets.Size() != BucketCount)
		{
			buckets.Clear();
			for (int i = 0; i < BucketCount; i++) buckets.Push(new("DoomerfallShotBucket"));
		}
		return buckets[serial & (BucketCount - 1)];
	}

	DoomerfallShotTag BySerial(int serial)
	{
		let b = BucketOf(serial);
		for (int i = b.tags.Size() - 1; i >= 0; i--)
		{
			let t = b.tags[i];
			if (!t) b.tags.Delete(i);
			else if (t.serial == serial) return t;
		}
		return null;
	}

	void ClearSerials()
	{
		for (int i = 0; i < buckets.Size(); i++) buckets[i].tags.Clear();
	}

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
		if (!tag || tag.carrier || tag.shooter != player) { tag = null; return false; }
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
			if (t && !t.carrier && t.shooter == player) return t;
		}
		return null;
	}

	static bool Active()
	{
		return Actor.DD_SheetValue(SheetValid) == 1;
	}

	// The tag of a newly spawned actor, tagging it first if a rule above fits. Safe to call more than once. A carrier
	// (a puff, or a helper the firing gun made) is not a shot: null for it.
	static DoomerfallShotTag Tag(Actor m)
	{
		if (!m) return null;
		let have = DoomerfallShotTag.Of(m);
		if (have) return have.carrier ? null : have;
		if (m.bIsMonster || m.player || m is "Inventory" || !Active()) return null;
		let h = DoomerfallShots(StaticEventHandler.Find("DoomerfallShots"));
		if (!h) return null;
		let t = h.Classify(m);
		return t && !t.carrier ? t : null;
	}

	// The held gun is firing (trigger down, or the gun mid-fire).
	private static bool Firing(PlayerInfo p)
	{
		let w = p.ReadyWeapon;
		return w && (p.attackdown || ((p.cmd.buttons | p.oldbuttons) & (BT_ATTACK | BT_ALTATTACK)) || !(p.WeaponState & WF_WEAPONREADY));
	}

	private static bool IsPlayerBody(Actor a)
	{
		return a && a.player && a.player.mo == a;
	}

	// The body of the player with this spawn serial, or null.
	private static Actor PlayerBySerial(int serial)
	{
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || !players[i].mo) continue;
			if (players[i].mo.DD_SpawnSerial() == serial) return players[i].mo;
		}
		return null;
	}

	private DoomerfallShotTag Classify(Actor m)
	{
		// [Doomerfall engine hook] The exact spawner (dd_shotsource.cpp): the actor whose action or tick spawned m.
		// Spawned by a tagged shot or a carrier (live, or destroyed this tic): m is its child, whatever m's target is
		// (an actor a blast spawns without SXF_TRANSFERPOINTERS targets the blast, not the player). A puff stays a
		// carrier; anything else becomes a real shot.
		int from = m.DD_SpawnedBy();
		if (from)
		{
			let src = BySerial(from);
			if (src && src.shooter) return NewTag(m, src, m.bIsPuff, src.carrier ? "carried" : "child");
		}

		// The player who spawned it (a puff has no target unless PUFFGETSOWNER), else the player it targets.
		Actor spawner = from ? PlayerBySerial(from) : null;
		let pmo = spawner ? spawner : m.target;
		if (!IsPlayerBody(pmo)) return null;
		let p = pmo.player;
		bool firing = Firing(p);
		bool byPlayer = spawner != null;
		// Spawned by the player's own action while the gun fires: a projectile is the held gun's shot; a puff carries
		// the held gun for whatever it spawns.
		if (byPlayer && firing && !m.bIsPuff && (m.bMissile || m.default.bMissile)) return NewTag(m, null, false, "fired", 0, pmo);
		if (m.bIsPuff) return byPlayer && firing ? NewTag(m, null, true, "fired", 0, pmo) : null;
		// Anything else the player's own action spawned is never a nearby shot's child (that guess gave DRLA's
		// RLRocketLauncherRecoil the other gun's tag). While the gun fires it is the gun's helper (DRLA's recoil and
		// reload effects, a launcher's spawner actor): it carries the held gun, so whatever it fires is that gun's shot
		// (generation 0). With the gun not firing it is no gun's (an item's or a script's): untagged.
		if (byPlayer) return firing ? NewTag(m, null, true, "fired", -1, pmo) : null;

		// Spawned by something else (a monster, a barrel, a script) or by nobody known: the old rules.
		return Nearest(m, pmo, firing);
	}

	// The rules from before the engine hook: the nearest tagged shot of this player within ChildReach, or the held
	// gun's shot for a projectile next to the player while the gun fires.
	private DoomerfallShotTag Nearest(Actor m, Actor pmo, bool firing)
	{
		DoomerfallShotTag parent = null;
		double best = ChildReach;
		for (int i = 0; i < tagged.Size(); i++)
		{
			let a = tagged[i];
			if (!a || a == m) continue;
			let t = DoomerfallShotTag.Of(a);
			if (!t || t.carrier || t.shooter != pmo) continue;
			double d = a.Distance3D(m);
			if (d < best) { best = d; parent = t; }
		}
		for (int i = 0; i < fallen.Size(); i++)
		{
			let t = fallen[i];
			if (!t || t.carrier || t.shooter != pmo) continue;
			double d = (m.pos - t.pos).Length();
			if (d < best) { best = d; parent = t; }
		}

		double fromPlayer = m.Distance2D(pmo);
		// A sibling fired in the same tic (a spray of shrapnel or pellets) is not a parent.
		bool sibling = parent && parent.generation == 0 && parent.fireTic == level.maptime;
		// Only a projectile is fired by the gun (one that hit at point blank has already exploded and lost its MISSILE
		// flag, so its class default counts); its helper actors (DRLA's recoil and reload effects) are not shots.
		bool fired = (m.bMissile || m.default.bMissile) && firing && fromPlayer <= pmo.radius + m.radius + 64 && (!parent || sibling || fromPlayer <= best);

		if (!fired && !parent) return null;
		return NewTag(m, fired ? null : parent, false, "near");
	}

	// Tags m: a copy of parent's tag (generation + 1), or with no parent the held gun of shooter (default: m's target; generation gen).
	// A carrier tag only passes the gun on to m's own spawns.
	private DoomerfallShotTag NewTag(Actor m, DoomerfallShotTag parent, bool carrier, String how, int gen = 0, Actor shooter = null)
	{
		Weapon w = null;
		if (!shooter) shooter = m.target;
		if (!parent)
		{
			if (!IsPlayerBody(shooter)) return null;
			w = shooter.player.ReadyWeapon;
			if (!w) return null;
		}
		let tag = DoomerfallShotTag(Actor.Spawn("DoomerfallShotTag"));
		if (!tag) return null;
		if (!parent)
		{
			tag.shooter = shooter;
			tag.gun = w.GetClass();
			int first, second;
			[first, second] = DoomerfallWeaponCategory.Both(w);
			tag.category = first;
			tag.second = second;
			tag.skill = DoomerfallWeaponCategory.SkillSlotOf(w);
			tag.fireTic = level.maptime;
			tag.generation = gen;
		}
		else
		{
			tag.CopyFrom(parent);
			if (tag.generation == 0) tag.fireTic = level.maptime; // fired through a helper: fired now
		}
		tag.carrier = carrier;
		tag.AttachToOwner(m);
		tag.serial = m.DD_SpawnSerial();
		BucketOf(tag.serial).tags.Push(tag);
		tagged.Push(m);
		Log(String.Format("tag %s gun %s skill %d gen %d tic %d by %s%s", m.GetClassName(), tag.gun ? tag.gun.GetClassName() : 'None',
			tag.skill, tag.generation, level.maptime, how, carrier ? " carrier" : ""));
		return tag;
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		Tag(e.Thing);
	}

	override void WorldThingDestroyed(WorldEvent e)
	{
		let a = e.Thing;
		if (!a || a is "Inventory") return;
		let t = DoomerfallShotTag.Of(a);
		if (!t && a.GetAge() == 0 && Active()) // gone before its spawn event (point blank, or into a wall)
		{
			Tag(a);
			t = DoomerfallShotTag.Of(a);
		}
		if (!t) return;
		// Keep the tag (not the dying actor) until the next tic, for whatever the actor spawned as it died.
		a.RemoveInventory(t);
		t.SetXYZ(a.pos);
		fallen.Push(t);
	}

	override void WorldTick()
	{
		for (int i = 0; i < fallen.Size(); i++)
		{
			let t = fallen[i];
			if (!t) continue;
			let b = BucketOf(t.serial);
			int at = b.tags.Find(t);
			if (at < b.tags.Size()) b.tags.Delete(at);
			t.Destroy();
		}
		fallen.Clear();
		for (int i = tagged.Size() - 1; i >= 0; i--) if (!tagged[i]) tagged.Delete(i);
	}

	override void WorldLoaded(WorldEvent e)
	{
		tagged.Clear();
		fallen.Clear();
		ClearSerials();
		let it = ThinkerIterator.Create("DoomerfallShotTag", Thinker.STAT_INVENTORY);
		DoomerfallShotTag t;
		while (t = DoomerfallShotTag(it.Next()))
		{
			if (!t.owner) { t.Destroy(); continue; } // a dead shot's tag saved mid-tic
			tagged.Push(t.owner);
			t.serial = t.owner.DD_SpawnSerial(); // serials are not saved: a new one
			BucketOf(t.serial).tags.Push(t);
		}
		if (tagged.Size()) Log(String.Format("loaded %d tagged actors", tagged.Size()));
	}

	override void WorldUnloaded(WorldEvent e)
	{
		tagged.Clear();
		fallen.Clear();
		ClearSerials();
	}
}
