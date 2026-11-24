// Tiered Doom ammo (card ammotiers/04). On a generated Daggerfall map in a bridge session, every loose ammo pickup
// (stock or DRLA, placed by the converter or dropped by a monster) becomes one ammo drop: a pickup of one material
// tier, rolled with the area level Daggerfall answers for the player's map pixel (dd_items.cpp, dfa_level). Touching
// a tiered pickup sends its rounds to Daggerfall's inventory (dfa_take) instead of Doom's counter; Daggerfall then
// sends the loaded tier's rounds back. Outside a bridge session a tiered pickup gives plain Doom ammo.
//
// The odds are the owner's (2026-11-24): a 2% jackpot of 20 pickups (10 for rockets) of one random town tier, else
// a Daedric roll (none at level 1, 1 in 40 at 20, 1 in 20 at 30), else Regular, Silver, Adamantium, Ebony, each
// `falloff` times as likely as the one before. Each roll is a pure function of the map, the spot, and the ammo type,
// so a placed pickup rolls the same in every game. A rolled pickup is its own class (DFAmmo_<type>_<tier>), which
// the treadmill table and saves keep.
class DoomerfallAmmoTiers : StaticEventHandler
{
	const JackpotChance = 0.02;
	const WaitTics = 175; // A pickup spawned before Daggerfall's rules arrive is forgotten after this, outside Daggerfall maps.

	int areaLevel; // -1 while unknown
	bool rules;
	Array<Inventory> pending;
	Array<int> pendingTic;


	override void OnRegister()
	{
		areaLevel = -1;
	}

	static DoomerfallAmmoTiers Get()
	{
		return DoomerfallAmmoTiers(StaticEventHandler.Find("DoomerfallAmmoTiers"));
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) == "dfa_level:") areaLevel = e.Name.Mid(10).ToInt();
		else if (e.Name.Left(10) == "dfi_rules:") rules = e.Name.Mid(10) == "1";
	}

	override void WorldUnloaded(WorldEvent e)
	{
		pending.Clear();
		pendingTic.Clear();
	}

	// 0 bullets, 1 shells, 2 rockets, 3 cells, or -1 for anything that is not a loose ammo pickup.
	static int PlainType(Actor a)
	{
		for (class<Object> c = a.GetClass(); c != null; c = c.GetParentClass())
		{
			name n = c.GetClassName();
			if (n == 'DoomerfallAmmoPickup' || n == 'Inventory') return -1;
			if (n == 'Clip' || n == 'ClipBox' || n == 'RLClip' || n == 'RLClipBox') return 0;
			if (n == 'Shell' || n == 'ShellBox' || n == 'RLShell' || n == 'RLShellBox') return 1;
			if (n == 'RocketAmmo' || n == 'RocketBox' || n == 'RLRocketAmmo' || n == 'RLRocketBox') return 2;
			if (n == 'Cell' || n == 'CellPack' || n == 'RLCell' || n == 'RLCellPack') return 3;
		}
		return -1;
	}

	// A player's ammo is spawned and given in the same tic, so a pickup is judged a tic later, once it has no owner.
	override void WorldThingSpawned(WorldEvent e)
	{
		let inv = Inventory(e.Thing);
		if (inv == null || PlainType(inv) < 0) return;
		pending.Push(inv);
		pendingTic.Push(level.maptime);
	}

	override void WorldTick()
	{
		for (int i = pending.Size() - 1; i >= 0; i--)
		{
			let inv = pending[i];
			if (inv == null || inv.Owner != null)
			{
				Forget(i);
				continue;
			}
			if (!rules)
			{
				if (level.maptime - pendingTic[i] > WaitTics) Forget(i);
				continue;
			}
			if (areaLevel < 0) continue;
			Convert(inv, PlainType(inv));
			Forget(i);
		}
	}

	void Forget(int i)
	{
		pending.Delete(i);
		pendingTic.Delete(i);
	}

	// ---- The roll ----------------------------------------------------------------------------------------------

	static int Mix(int h, int v)
	{
		h ^= v;
		h *= 16777619;
		h ^= h >>> 15;
		return h;
	}

	static double Unit(int seed, int salt)
	{
		int x = Mix(Mix(seed, salt * 7919), 0x5bd1e995);
		x ^= x >>> 13;
		x *= 0x2c1b3c6d;
		x ^= x >>> 16;
		return (x & 0xFFFFFF) / 16777216.0;
	}

	static int Seed(Actor a, int type)
	{
		int h = 0x011c9dc5;
		String map = level.MapName;
		for (int i = 0; i < map.Length(); i++) h = Mix(h, map.ByteAt(i));
		h = Mix(h, int(floor(a.pos.x / 16)));
		h = Mix(h, int(floor(a.pos.y / 16)));
		h = Mix(h, int(floor(a.pos.z / 16)));
		return Mix(h, type + 1);
	}

	static double DaedricChance(int lvl)
	{
		lvl = clamp(lvl, 1, 30);
		if (lvl <= 20) return 0.025 * ((lvl - 1) / 19.0) ** 3;
		return 0.025 + 0.025 * (lvl - 20) / 10.0;
	}

	static double Falloff(int lvl)
	{
		lvl = clamp(lvl, 1, 30);
		if (lvl <= 20) return 0.35 + 0.45 * (lvl - 1) / 19.0;
		return 0.80 + 0.10 * (lvl - 20) / 10.0;
	}

	// The tier of one ordinary (not jackpot) drop.
	static int RollTier(int lvl, double daedricRoll, double tierRoll)
	{
		static const int RollTiers[] = { 0, 2, 5, 8 }; // Regular, Silver, Adamantium, Ebony
		if (daedricRoll < DaedricChance(lvl)) return 9;
		double f = Falloff(lvl), total = 0, w = 1;
		for (int i = 0; i < 4; i++)
		{
			total += w;
			w *= f;
		}
		double r = tierRoll * total;
		w = 1;
		for (int i = 0; i < 3; i++)
		{
			if (r < w) return RollTiers[i];
			r -= w;
			w *= f;
		}
		return RollTiers[3];
	}

	void Convert(Inventory plain, int type)
	{
		static const int TownTiers[] = { 1, 3, 4, 6, 7 }; // Steel, Moonstone, Dwemer, Orichalcum, Mithril
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		int seed = Seed(plain, type);
		if (Unit(seed, 1) < JackpotChance)
		{
			int tier = TownTiers[min(4, int(Unit(seed, 2) * 5))];
			int count = type == 2 ? 10 : 20;
			for (int i = 0; i < count; i++)
			{
				let p = SpawnTier(plain, type, tier);
				if (p == null) continue;
				double angle = Unit(seed, 10 + i) * 360, speed = 2 + Unit(seed, 40 + i) * 6;
				p.vel = (cos(angle) * speed, sin(angle) * speed, 4 + Unit(seed, 70 + i) * 5);
			}
			Console.Printf("DFAMMO jackpot %s tier %d x%d at %.0f %.0f level %d", TypeNames[type], tier, count, plain.pos.x, plain.pos.y, areaLevel);
		}
		else
		{
			int tier = RollTier(areaLevel, Unit(seed, 3), Unit(seed, 4));
			let p = SpawnTier(plain, type, tier);
			if (p != null) p.vel = plain.vel;
			Console.Printf("DFAMMO drop %s tier %d at %.0f %.0f level %d", TypeNames[type], tier, plain.pos.x, plain.pos.y, areaLevel);
		}
		plain.Destroy();
	}

	static Actor SpawnTier(Actor at, int type, int tier)
	{
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		class<Actor> cls = String.Format("DFAmmo_%s_%d", TypeNames[type], tier);
		if (cls == null) return null;
		return Actor.Spawn(cls, at.pos, NO_REPLACE);
	}
}

// One pickup of one ammo type and tier. Amount is its rounds.
class DoomerfallAmmoPickup : Inventory abstract
{
	meta int ammoType;
	meta int tier;
	property AmmoType: ammoType;
	property Tier: tier;

	Default
	{
		Inventory.PickupSound "misc/ammo_pkup";
		Inventory.Amount 1;
		Inventory.MaxAmount 0x7fffffff;
	}

	static int Rounds(int type, int tier)
	{
		// DoomerfallAmmoTiers.cs: rounds per pack at a 1x stack size, and each tier's stack size in quarters.
		static const int BaseStack[] = { 40, 10, 4, 50 };
		static const int StackQuarters[] = { 8, 6, 4, 3, 4, 3, 2, 2, 2, 1 };
		// Rounded half away from zero, at least one, as DoomerfallAmmoTiers.Stack does.
		return max(1, (BaseStack[type] * StackQuarters[tier] + 2) / 4);
	}

	override void BeginPlay()
	{
		Super.BeginPlay();
		Amount = Rounds(ammoType, tier);
		A_SetTranslation(String.Format("DFAmmoTier%d", tier));
	}

	override String PickupMessage()
	{
		static const String TypeNames[] = { "bullets", "shotgun shells", "rockets", "energy cells" };
		static const String TierNames[] = { "Regular", "Steel", "Silver", "Moonstone", "Dwemer", "Adamantium", "Orichalcum", "Mithril", "Ebony", "Daedric" };
		return String.Format("Picked up %d %s %s.", Amount, TierNames[tier], TypeNames[ammoType]);
	}

	override bool TryPickup(in out Actor toucher)
	{
		static const String ReserveClasses[] = { "Clip", "Shell", "RocketAmmo", "Cell" };
		if (toucher == null || toucher.player == null) return false;
		let tiers = DoomerfallAmmoTiers.Get();
		if (tiers != null && tiers.rules)
			EventHandler.SendNetworkEvent(String.Format("dfa_take:%d:%d:%s", tier, Amount, ReserveClasses[ammoType]));
		else
			toucher.A_GiveInventory(ReserveClasses[ammoType], Amount);
		GoAwayAndDie();
		return true;
	}
}

class DoomerfallAmmoClip : DoomerfallAmmoPickup abstract { Default { DoomerfallAmmoPickup.AmmoType 0; } States { Spawn: CLIP A -1; Stop; } }
class DoomerfallAmmoShell : DoomerfallAmmoPickup abstract { Default { DoomerfallAmmoPickup.AmmoType 1; } States { Spawn: SHEL A -1; Stop; } }
class DoomerfallAmmoRocket : DoomerfallAmmoPickup abstract { Default { DoomerfallAmmoPickup.AmmoType 2; } States { Spawn: ROCK A -1; Stop; } }
class DoomerfallAmmoCell : DoomerfallAmmoPickup abstract { Default { DoomerfallAmmoPickup.AmmoType 3; } States { Spawn: CELL A -1; Stop; } }

// One class per ammo type and tier, so the treadmill table and saves keep the tier.
class DFAmmo_Clip_0 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 0; } }
class DFAmmo_Clip_1 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 1; } }
class DFAmmo_Clip_2 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 2; } }
class DFAmmo_Clip_3 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 3; } }
class DFAmmo_Clip_4 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 4; } }
class DFAmmo_Clip_5 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 5; } }
class DFAmmo_Clip_6 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 6; } }
class DFAmmo_Clip_7 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 7; } }
class DFAmmo_Clip_8 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 8; } }
class DFAmmo_Clip_9 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 9; } }
class DFAmmo_Shell_0 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 0; } }
class DFAmmo_Shell_1 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 1; } }
class DFAmmo_Shell_2 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 2; } }
class DFAmmo_Shell_3 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 3; } }
class DFAmmo_Shell_4 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 4; } }
class DFAmmo_Shell_5 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 5; } }
class DFAmmo_Shell_6 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 6; } }
class DFAmmo_Shell_7 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 7; } }
class DFAmmo_Shell_8 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 8; } }
class DFAmmo_Shell_9 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 9; } }
class DFAmmo_Rocket_0 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 0; } }
class DFAmmo_Rocket_1 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 1; } }
class DFAmmo_Rocket_2 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 2; } }
class DFAmmo_Rocket_3 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 3; } }
class DFAmmo_Rocket_4 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 4; } }
class DFAmmo_Rocket_5 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 5; } }
class DFAmmo_Rocket_6 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 6; } }
class DFAmmo_Rocket_7 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 7; } }
class DFAmmo_Rocket_8 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 8; } }
class DFAmmo_Rocket_9 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 9; } }
class DFAmmo_Cell_0 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 0; } }
class DFAmmo_Cell_1 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 1; } }
class DFAmmo_Cell_2 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 2; } }
class DFAmmo_Cell_3 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 3; } }
class DFAmmo_Cell_4 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 4; } }
class DFAmmo_Cell_5 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 5; } }
class DFAmmo_Cell_6 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 6; } }
class DFAmmo_Cell_7 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 7; } }
class DFAmmo_Cell_8 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 8; } }
class DFAmmo_Cell_9 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 9; } }
