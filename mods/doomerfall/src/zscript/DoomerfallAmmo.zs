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
	Array<double> pendingX, pendingY, pendingZ; // Where each spawned: the roll uses this, not where it fell.
	Array<bool> pendingDropped; // Dropped by a monster (WasDropped), judged when it spawned, before it lands.
	Array<int> pendingSeed; // The engine's fixed loot seed (DD_LootSeed), 0 when it has none.


	override void OnRegister()
	{
		areaLevel = -1;
		loadedTier = -1;
	}

	static DoomerfallAmmoTiers Get()
	{
		return DoomerfallAmmoTiers(StaticEventHandler.Find("DoomerfallAmmoTiers"));
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) == "dfa_level:") areaLevel = e.Name.Mid(10).ToInt();
		else if (e.Name.Left(10) == "dfi_rules:") rules = e.Name.Mid(10) == "1";
		else if (e.Name.Left(11) == "dfa_loaded:")
		{
			// dfa_loaded:<tier or -1>:<type>:<tags>, from Daggerfall whenever the ready gun's loaded ammo changes (card ammotiers/05).
			Array<String> f;
			e.Name.Mid(11).Split(f, ":");
			loadedTier = f.Size() > 0 ? f[0].ToInt() : -1;
			loadedType = f.Size() > 1 ? f[1].ToInt() : -1;
			loadedTags = f.Size() > 2 ? f[2] : "";
			if (loadedTier < 0 || loadedTier >= TIERCOUNT || loadedType < 0 || loadedType >= AMMOICONS.Size()) loadedTier = -1;
			loadedName = loadedTier < 0 ? "" : AmmoName(loadedType, loadedTier);
			DDLog.Debug(String.Format("Doomerfall: loaded ammo %s", loadedTier < 0 ? "none" : loadedName));
		}
		else if (e.Name.Left(11) == "dfa_reload:" && consoleplayer >= 0)
		{
			// dfa_reload:<weapon class>, from dd_items.cpp UnloadMagazine after a change by the key emptied the ready
			// gun's magazine. Daggerfall had already swapped the reserve to the new tier.
			let w = players[consoleplayer].ReadyWeapon;
			if (w && w.GetClassName() == e.Name.Mid(11))
			{
				reloadGun = w;
				reloadTic = level.maptime;
			}
		}
	}

	// ---- The change ammo key is a reload (owner, 2026-11-24) ----------------------------------------------------
	// The engine starts a ready gun's reload itself (dd_items.cpp UnloadMagazine) and sends dfa_reload only when the
	// gun was busy (firing, raising). Here the wait ends once the magazine is empty and the gun is ready: the gun plays
	// its own Reload state, which fills the magazine from the reserve, now the new tier. A gun without a magazine or a
	// Reload state (stock Doom) is lowered and raised instead, so the new tier fires only after it is back up. A swap,
	// or the gun reloading by itself (DRLA's Fire state on an empty magazine), ends the wait; so does a gun that never
	// comes ready.
	const ReloadWait = 105;
	Weapon reloadGun;
	int reloadTic;

	static bool IsReserve(class<Inventory> c)
	{
		if (!c) return false;
		let d = GetDefaultByType(c);
		return d is "Clip" || d is "Shell" || d is "RocketAmmo" || d is "Cell";
	}

	void TickReload()
	{
		let p = players[consoleplayer];
		let gun = reloadGun;
		if (!p.mo || p.health <= 0 || p.ReadyWeapon != gun || p.PendingWeapon != WP_NOCHANGE || level.maptime - reloadTic > ReloadWait)
		{
			reloadGun = null;
			return;
		}
		let psp = p.FindPSprite(PSP_WEAPON);
		State reload = gun.FindState("Reload");
		bool magazine = gun.AmmoType1 && !IsReserve(gun.AmmoType1) && IsReserve(gun.AmmoType2);
		if (!psp) return;
		if (magazine && reload && Actor.InStateSequence(psp.CurState, reload))
		{
			reloadGun = null; // Already reloading.
			return;
		}
		if (magazine && p.mo.CountInv(gun.AmmoType1) > 0) return; // The engine has not emptied it yet.
		if (!(p.WeaponState & WF_WEAPONREADY)) return;
		reloadGun = null;
		if (magazine && reload)
		{
			p.SetPsprite(PSP_WEAPON, reload);
			Console.PrintfEx(PRINT_LOG, "DFAMMO reload %s", gun.GetClassName());
		}
		else
		{
			p.PendingWeapon = gun;
			p.SetPsprite(PSP_WEAPON, gun.GetDownState());
			Console.PrintfEx(PRINT_LOG, "DFAMMO redraw %s", gun.GetClassName());
		}
	}

	// The ammo loaded in the ready gun, shown at the bottom of the screen: the tier's tinted pickup sprite, its name, and
	// its tags (none exist yet: Silver's creature bonus and the quiet tag are backlog items). Daggerfall clears it with
	// the weapon (fists, or a gun with no reserve ammo).
	const TIERCOUNT = 10;
	static const String AMMOICONS[] = { "CLIPA0", "SHELA0", "ROCKA0", "CELLA0" };

	// The ammo's name, as Daggerfall's inventory gives it: the plain name for Regular ("Bullets"), else the material
	// first ("Silver Bullets") (owner, 2026-11-26). Each DFAmmo class's Tag holds it, so the look label, pickup message
	// and this HUD agree, and pickups in older saves get it from the class default.
	static clearscope String AmmoName(int type, int tier)
	{
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		class<Actor> cls = String.Format("DFAmmo_%s_%d", TypeNames[type], tier);
		return cls ? GetDefaultByType(cls).GetTag() : "";
	}
	int loadedTier, loadedType;
	String loadedTags, loadedName;

	override void RenderOverlay(RenderEvent e)
	{
		if (loadedTier < 0 || !rules || automapactive || consoleplayer < 0) return;
		let p = players[consoleplayer];
		if (p.mo == null || p.health <= 0 || p.camera != p.mo) return;
		int scale = DoomerfallText.Scale();
		int fh = SmallFont.GetHeight() * scale;
		int bottom = min(StatusBar.GetTopOfStatusBar(), int(Screen.GetHeight() * 0.85)) - fh * 3; // Above "Sneaking".
		String text = loadedName;
		int textW = SmallFont.StringWidth(text) * scale;
		int x = Screen.GetWidth() * 3 / 4;
		TextureID icon = TexMan.CheckForTexture(AMMOICONS[loadedType], TexMan.Type_Sprite);
		if (loadedTags != "")
		{
			Screen.DrawText(SmallFont, Font.CR_GREEN, x - SmallFont.StringWidth(loadedTags) * scale / 2, bottom - fh, loadedTags, DTA_ScaleX, scale, DTA_ScaleY, scale);
			bottom -= fh;
		}
		Screen.DrawText(SmallFont, Font.CR_GOLD, x - textW / 2, bottom - fh, text, DTA_ScaleX, scale, DTA_ScaleY, scale);
		if (icon.IsValid())
		{
			Vector2 size = TexMan.GetScaledSize(icon);
			double s = scale * 1.5;
			Screen.DrawTexture(icon, false, x - size.x * s / 2, bottom - fh - 2 * scale - size.y * s,
				DTA_DestWidthF, size.x * s, DTA_DestHeightF, size.y * s, DTA_TopOffset, 0, DTA_LeftOffset, 0,
				DTA_TranslationIndex, Translation.GetID(String.Format("DFAmmoTier%d", loadedTier)));
		}
	}

	override void WorldUnloaded(WorldEvent e)
	{
		reloadGun = null;
		pending.Clear();
		pendingTic.Clear();
		pendingX.Clear();
		pendingY.Clear();
		pendingZ.Clear();
		pendingDropped.Clear();
		pendingSeed.Clear();
	}

	// 0 bullets, 1 shells, 2 rockets, 3 cells, or -1 for anything that is not a loose ammo pickup.
	static int PlainType(Actor a)
	{
		bool box;
		return PlainKind(a, box);
	}

	// The ammo type, as PlainType, and whether the pickup is Doom's large one (box of bullets, box of shells, box of
	// rockets, cell pack). ClipBox inherits Clip, so each class is checked for a box name before its parent is.
	static int PlainKind(Actor a, out bool box)
	{
		box = false;
		for (class<Object> c = a.GetClass(); c != null; c = c.GetParentClass())
		{
			name n = c.GetClassName();
			if (n == 'DoomerfallAmmoPickup' || n == 'Inventory') return -1;
			if (n == 'ClipBox' || n == 'RLClipBox') { box = true; return 0; }
			if (n == 'ShellBox' || n == 'RLShellBox') { box = true; return 1; }
			if (n == 'RocketBox' || n == 'RLRocketBox') { box = true; return 2; }
			if (n == 'CellPack' || n == 'RLCellPack') { box = true; return 3; }
			if (n == 'Clip' || n == 'RLClip') return 0;
			if (n == 'Shell' || n == 'RLShell') return 1;
			if (n == 'RocketAmmo' || n == 'RLRocketAmmo') return 2;
			if (n == 'Cell' || n == 'RLCell') return 3;
		}
		return -1;
	}

	// Dropped by a monster. DROPPED cannot tell: every Inventory starts with it (inventory.zs BeginPlay), and only map
	// things clear it, so pickups the converter's markers spawn keep it. Doom's drop code (A_DropItem, inventory_util.zs)
	// marks the drop TOSSED and throws it. With DRLA the drop is a RandomSpawner, which passes neither flag on to the
	// pickup it spawns but copies its toss velocity and its spawn flags, which are empty for anything not placed by the
	// map. A placed pickup starts at rest.
	static bool WasDropped(Inventory inv)
	{
		return inv.bTOSSED || (inv.SpawnFlags == 0 && inv.vel != (0, 0, 0));
	}

	// A player's ammo is spawned and given in the same tic, so a pickup is judged a tic later, once it has no owner.
	override void WorldThingSpawned(WorldEvent e)
	{
		let inv = Inventory(e.Thing);
		if (inv == null || PlainType(inv) < 0) return;
		pending.Push(inv);
		pendingTic.Push(level.maptime);
		pendingX.Push(inv.pos.x);
		pendingY.Push(inv.pos.y);
		pendingZ.Push(inv.pos.z);
		pendingDropped.Push(WasDropped(inv));
		pendingSeed.Push(inv.DD_LootSeed());
	}

	override void WorldTick()
	{
		if (reloadGun) TickReload();
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
			bool box;
			int type = PlainKind(inv, box);
			Convert(inv, type, box, pendingDropped[i], (pendingX[i], pendingY[i], pendingZ[i]), pendingSeed[i]);
			Forget(i);
		}
	}

	void Forget(int i)
	{
		pending.Delete(i);
		pendingTic.Delete(i);
		pendingX.Delete(i);
		pendingY.Delete(i);
		pendingZ.Delete(i);
		pendingDropped.Delete(i);
		pendingSeed.Delete(i);
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

	static int Seed(vector3 at, int type)
	{
		int h = 0x011c9dc5;
		String map = level.MapName;
		for (int i = 0; i < map.Length(); i++) h = Mix(h, map.ByteAt(i));
		h = Mix(h, int(floor(at.x / 16)));
		h = Mix(h, int(floor(at.y / 16)));
		h = Mix(h, int(floor(at.z / 16)));
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

	// Each tiered pickup keeps the size of the pickup it replaces (small, large, or dropped), in Doom's amounts.
	void Convert(Inventory plain, int type, bool box, bool dropped, vector3 spawned, int lootSeed)
	{
		static const int TownTiers[] = { 1, 3, 4, 6, 7 }; // Steel, Moonstone, Dwemer, Orichalcum, Mithril
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		// A drop from a fixed loot roll (or a map thing) rolls from its engine seed, which does not depend on where the
		// monster happened to die; anything else from its map and spot.
		int seed = lootSeed != 0 ? Mix(Mix(0x011c9dc5, lootSeed), type + 1) : Seed(spawned, type);
		if (Unit(seed, 1) < JackpotChance)
		{
			int tier = TownTiers[min(4, int(Unit(seed, 2) * 5))];
			int count = type == 2 ? 10 : 20;
			for (int i = 0; i < count; i++)
			{
				let p = SpawnTier(plain, type, tier, box, dropped);
				if (p == null) continue;
				double angle = Unit(seed, 10 + i) * 360, speed = 2 + Unit(seed, 40 + i) * 6;
				p.vel = (cos(angle) * speed, sin(angle) * speed, 4 + Unit(seed, 70 + i) * 5);
			}
			DDLog.Debug(String.Format("DFAMMO jackpot %s tier %d x%d at %.0f %.0f level %d", TypeNames[type], tier, count, plain.pos.x, plain.pos.y, areaLevel));
		}
		else
		{
			int tier = RollTier(areaLevel, Unit(seed, 3), Unit(seed, 4));
			let p = SpawnTier(plain, type, tier, box, dropped);
			if (p != null) p.vel = plain.vel;
			DDLog.Debug(String.Format("DFAMMO drop %s tier %d at %.0f %.0f level %d", TypeNames[type], tier, plain.pos.x, plain.pos.y, areaLevel));
		}
		Console.PrintfEx(PRINT_LOG, "DFAMMO size %s%s %s -> %d rounds", box ? "large " : "small ", TypeNames[type], dropped ? "dropped" : "placed",
			DoomerfallAmmoPickup.Rounds(type, box, dropped));
		if (dropped && lootSeed != 0) LuckDrop(plain, type, box, seed);
		plain.Destroy();
	}

	// ---- Luck (card attributes/04, owner 2026-11-26) -------------------------------------------------------------
	// Daggerfall's live Luck makes monsters' ammo drops more frequent: each ammo drop from a monster's fixed loot roll
	// has a Luck in 100 chance (Luck above 100 counts as 100) to come with one more ordinary drop of the same ammo and
	// size, so +1% drops at Luck 1 and +100% at 100. Its own stream: a hash of the drop's seed with its own salt, so
	// it draws from no random stream and the fixed loot (what drops, its tier, any jackpot) is the same at every Luck.
	// The same drop gets the same number every game, so a luckier character gets every extra drop a less lucky one does.
	const LuckStat = 7; // DFCareer.Stats.Luck
	const LuckSalt = 0x4c75636b;

	void LuckDrop(Inventory plain, int type, bool box, int seed)
	{
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		int luck = Actor.DD_SheetStat(LuckStat);
		if (luck <= 0) return;
		int luckSeed = Mix(seed, LuckSalt);
		if (Unit(luckSeed, 1) * 100 >= min(luck, 100)) return;
		int tier = RollTier(areaLevel, Unit(luckSeed, 3), Unit(luckSeed, 4));
		let p = SpawnTier(plain, type, tier, box, true);
		if (p == null) return;
		double angle = Unit(luckSeed, 5) * 360;
		p.vel = plain.vel + (cos(angle) * 2, sin(angle) * 2, 2);
		DDLog.Debug(String.Format("DFAMMO luck drop %s tier %d at %.0f %.0f luck %d", TypeNames[type], tier, plain.pos.x, plain.pos.y, luck));
	}

	static Inventory SpawnTier(Actor at, int type, int tier, bool box, bool dropped)
	{
		static const String TypeNames[] = { "Clip", "Shell", "Rocket", "Cell" };
		class<Actor> cls = String.Format("DFAmmo_%s_%d", TypeNames[type], tier);
		if (cls == null) return null;
		let p = Inventory(Actor.Spawn(cls, at.pos, NO_REPLACE));
		if (p) p.Amount = DoomerfallAmmoPickup.Rounds(type, box, dropped);
		return p;
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

	// Rounds in one pickup: stock Doom's amounts, from id Software's p_inter.c (clipammo {10, 4, 20, 1}; a large pickup
	// is five of them; a dropped clip is half). A dropped pickup of any size is half, at least one, as UZDoom's
	// Ammo.ModifyDropAmount does. Every tier gives the same as Regular: higher tiers are rarer, not smaller (owner,
	// 2026-11-26). This is the only place pickup amounts are decided: Daggerfall receives the count with dfa_take.
	static int Rounds(int type, bool box = false, bool dropped = false)
	{
		static const int Small[] = { 10, 4, 1, 20 };  // Clip, 4 shotgun shells, rocket, energy cell.
		static const int Large[] = { 50, 20, 5, 100 }; // Box of bullets, box of shells, box of rockets, cell pack.
		int n = box ? Large[type] : Small[type];
		return dropped ? max(1, n / 2) : n;
	}

	override void BeginPlay()
	{
		Super.BeginPlay();
		Amount = Rounds(ammoType); // A small placed pickup; the converter (SpawnTier) and the treadmill set the real size.
		A_SetTranslation(String.Format("DFAmmoTier%d", tier));
	}

	override String PickupMessage()
	{
		return String.Format("Picked up %d %s.", Amount, GetTag());
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
class DFAmmo_Clip_0 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 0; Tag "Bullets"; } }
class DFAmmo_Clip_1 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 1; Tag "Steel Bullets"; } }
class DFAmmo_Clip_2 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 2; Tag "Silver Bullets"; } }
class DFAmmo_Clip_3 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 3; Tag "Moonstone Bullets"; } }
class DFAmmo_Clip_4 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 4; Tag "Dwemer Bullets"; } }
class DFAmmo_Clip_5 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 5; Tag "Adamantium Bullets"; } }
class DFAmmo_Clip_6 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 6; Tag "Orichalcum Bullets"; } }
class DFAmmo_Clip_7 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 7; Tag "Mithril Bullets"; } }
class DFAmmo_Clip_8 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 8; Tag "Ebony Bullets"; } }
class DFAmmo_Clip_9 : DoomerfallAmmoClip { Default { DoomerfallAmmoPickup.Tier 9; Tag "Daedric Bullets"; } }
class DFAmmo_Shell_0 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 0; Tag "Shells"; } }
class DFAmmo_Shell_1 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 1; Tag "Steel Shells"; } }
class DFAmmo_Shell_2 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 2; Tag "Silver Shells"; } }
class DFAmmo_Shell_3 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 3; Tag "Moonstone Shells"; } }
class DFAmmo_Shell_4 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 4; Tag "Dwemer Shells"; } }
class DFAmmo_Shell_5 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 5; Tag "Adamantium Shells"; } }
class DFAmmo_Shell_6 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 6; Tag "Orichalcum Shells"; } }
class DFAmmo_Shell_7 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 7; Tag "Mithril Shells"; } }
class DFAmmo_Shell_8 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 8; Tag "Ebony Shells"; } }
class DFAmmo_Shell_9 : DoomerfallAmmoShell { Default { DoomerfallAmmoPickup.Tier 9; Tag "Daedric Shells"; } }
class DFAmmo_Rocket_0 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 0; Tag "Rockets"; } }
class DFAmmo_Rocket_1 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 1; Tag "Steel Rockets"; } }
class DFAmmo_Rocket_2 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 2; Tag "Silver Rockets"; } }
class DFAmmo_Rocket_3 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 3; Tag "Moonstone Rockets"; } }
class DFAmmo_Rocket_4 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 4; Tag "Dwemer Rockets"; } }
class DFAmmo_Rocket_5 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 5; Tag "Adamantium Rockets"; } }
class DFAmmo_Rocket_6 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 6; Tag "Orichalcum Rockets"; } }
class DFAmmo_Rocket_7 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 7; Tag "Mithril Rockets"; } }
class DFAmmo_Rocket_8 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 8; Tag "Ebony Rockets"; } }
class DFAmmo_Rocket_9 : DoomerfallAmmoRocket { Default { DoomerfallAmmoPickup.Tier 9; Tag "Daedric Rockets"; } }
class DFAmmo_Cell_0 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 0; Tag "Energy Cells"; } }
class DFAmmo_Cell_1 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 1; Tag "Steel Energy Cells"; } }
class DFAmmo_Cell_2 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 2; Tag "Silver Energy Cells"; } }
class DFAmmo_Cell_3 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 3; Tag "Moonstone Energy Cells"; } }
class DFAmmo_Cell_4 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 4; Tag "Dwemer Energy Cells"; } }
class DFAmmo_Cell_5 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 5; Tag "Adamantium Energy Cells"; } }
class DFAmmo_Cell_6 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 6; Tag "Orichalcum Energy Cells"; } }
class DFAmmo_Cell_7 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 7; Tag "Mithril Energy Cells"; } }
class DFAmmo_Cell_8 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 8; Tag "Ebony Energy Cells"; } }
class DFAmmo_Cell_9 : DoomerfallAmmoCell { Default { DoomerfallAmmoPickup.Tier 9; Tag "Daedric Energy Cells"; } }
