// The Light Carbine (owner, 2026-11-26): DRLA's Battle Rifle, "only semi-automatic and +20% damage. That's it."
// Always in the game, with or without DRLA. A rifle (DoomerfallRifleTag.IsRifle).
//
// Copied from DoomRL Arsenal 1.1.5 standard/BattleRifle.txt, the gun with no mods: the same spread (2, 0.5), 20-round
// magazine loaded from bullets (Clip), reload frames and timings, sounds and sprites (copied into this mod by owner
// permission, renamed DFLC*). Changes:
//   - Damage 6 x 1d3 per shot, where the Battle Rifle does 5 x 1d3 (its base damage numbers + 20%).
//   - Semi-automatic: +WEAPON.NOAUTOFIRE and no A_ReFire, so one shot per trigger pull. A shot takes the Battle
//     Rifle's 4 tics, and the trigger must be up for a tic before the next, so it never fires faster.
//   - DRLA's mods, assembly, scavenging, perks and weapon tokens are left out: they need DRLA. The puff is Doom's
//     BulletPuff, which DRLA replaces with the Battle Rifle's RLBulletPuff when it is loaded.
//   - DRLA's recoil actors (pitch nudges over a few tics) are the same nudges done in the weapon's own frames.
// The magazine is DoomerfallLightCarbineClip, named <weapon>Clip so a hotkey swap or a drop carries it
// (DoomerfallGuns.zs). The gun is its own world pickup, like stock Doom's guns.
class DoomerfallLightCarbine : Weapon
{
	const MagazineSize = 20;

	Default
	{
		Tag "Light Carbine";
		Obituary "%o was picked off by %k's light carbine.";
		Inventory.PickupMessage "Picked up a Light Carbine.";
		Inventory.PickupSound "doomerfall/carbine/pickup";
		Inventory.Icon "DFLCICON";
		Decal "BulletChip";
		Weapon.SelectionOrder 25;
		Weapon.SlotNumber 4;
		Weapon.AmmoUse1 1;
		Weapon.AmmoGive1 0;
		Weapon.AmmoType1 "DoomerfallLightCarbineClip";
		Weapon.AmmoType2 "Clip";
		Weapon.AmmoGive2 0;
		Weapon.UpSound "doomerfall/carbine/raise";
		Weapon.Kickback 40;
		Weapon.BobStyle "Alpha";
		Weapon.BobSpeed 2.5;
		Weapon.BobRangeX 0.2;
		Weapon.BobRangeY 0.5;
		+WEAPON.AMMO_OPTIONAL
		+WEAPON.NOALERT
		+WEAPON.NOAUTOFIRE
	}

	// As DRLA's Battle Rifle pickup: the first one gives only the gun, another one gives 20 bullets.
	override bool HandlePickup(Inventory item)
	{
		if (item.GetClass() != GetClass()) return Super.HandlePickup(item);
		if (AmmoType2 && Owner.CountInv(AmmoType2) < GetDefaultByType(AmmoType2).MaxAmount)
		{
			Owner.GiveInventory(AmmoType2, 20);
			item.bPickupGood = true;
		}
		return true;
	}

	// Nudges the view up (positive) or down, as DRLA's recoil actors do.
	action void Kick(double up)
	{
		A_SetPitch(pitch - up, SPF_INTERPOLATE);
	}

	// Moves bullets from the reserve into the magazine, up to a full magazine.
	action void LoadMagazine()
	{
		int want = MagazineSize - CountInv(invoker.AmmoType1);
		int take = min(want, CountInv(invoker.AmmoType2));
		if (take <= 0) return;
		TakeInventory(invoker.AmmoType2, take);
		GiveInventory(invoker.AmmoType1, take);
	}

	States
	{
	Spawn:
		DFLC X -1;
		Stop;
	Ready:
		DFLC A 1 A_WeaponReady(WRF_ALLOWZOOM | WRF_ALLOWRELOAD);
		Loop;
	Deselect:
		TNT1 A 0 A_Lower;
		DFLC A 1 A_Lower;
		Loop;
	Select:
		TNT1 A 0 A_Raise;
		DFLC A 1 A_Raise;
		Loop;
	Fire:
		TNT1 A 0 A_JumpIfNoAmmo("Reload");
		TNT1 A 0 A_AlertMonsters;
		TNT1 A 0 A_FireBullets(2, 0.5, -1, 6, "BulletPuff");
		TNT1 A 0 A_StartSound("doomerfall/carbine/fire", CHAN_WEAPON, CHANF_DEFAULT, 1, 0.7);
		TNT1 A 0 A_StartSound("doomerfall/carbine/fire", 7, CHANF_DEFAULT, 0.05, 0.2);
		DFLC Y 1 Bright { A_GunFlash(); Kick(0.35); }
		DFLC Z 1 Bright Kick(-0.05);
		TNT1 A 0 A_JumpIf(CountInv(invoker.AmmoType1) > 0, "FireLoaded");
		DFLC V 1 Kick(-0.25);
		DFLC B 1 Kick(-0.05);
		Goto Ready;
	FireLoaded:
		DFLC W 1 Kick(-0.25);
		DFLC A 1 Kick(-0.05);
		Goto Ready;
	Reload:
		DFLC A 1 A_WeaponReady(WRF_NOPRIMARY | WRF_ALLOWZOOM);
		TNT1 A 0 A_JumpIf(CountInv(invoker.AmmoType1) >= MagazineSize || CountInv(invoker.AmmoType2) < 1, "Ready");
		TNT1 A 0 A_JumpIf(CountInv(invoker.AmmoType1) >= 1, "ReloadPartial"); // As DRLA: C-J with rounds left, N-U when empty.
		DFLC N 2;
		DFLC O 2;
		DFLC P 2;
		DFLC Q 2 { A_StartSound("doomerfall/carbine/unload", CHAN_ITEM); Kick(0.45); }
		DFLC R 8 Kick(0.33);
		DFLC S 2 Kick(-0.1);
		DFLC T 2 Kick(-0.05);
		DFLC U 2 Kick(-0.03);
		Goto ReloadFinish;
	ReloadPartial:
		DFLC C 2;
		DFLC D 2;
		DFLC E 2;
		DFLC F 2 { A_StartSound("doomerfall/carbine/unload", CHAN_ITEM); Kick(0.45); }
		DFLC G 8 Kick(0.33);
		DFLC H 2 Kick(-0.1);
		DFLC I 2 Kick(-0.05);
		DFLC J 2 Kick(-0.03);
	ReloadFinish:
		TNT1 A 0 { LoadMagazine(); A_StartSound("doomerfall/carbine/load", 7); }
		DFLC K 3 Kick(-0.45);
		DFLC L 5 Kick(-0.33);
		DFLC M 3 Kick(0.1);
		DFLC A 6 Kick(0.08);
		Goto Ready;
	Flash:
		TNT1 A 1 A_Light1;
		TNT1 A 1 A_Light2;
		Goto LightDone;
	}
}

// The carbine's magazine. Not a Clip: Doomerfall tells a gun's magazine from its reserve by that (dd_items.cpp).
class DoomerfallLightCarbineClip : Ammo
{
	Default
	{
		+INVENTORY.IGNORESKILL
		Inventory.MaxAmount 20;
		Inventory.Icon "";
	}
}

// Drops (owner, 2026-11-26): with DRLA Monsters, half the Battle Rifles that the Battle Rifle monsters drop become
// Light Carbines. Those are the Former Human, Former Commando, Elite Former Human and Former Cyborg with a battle
// rifle (and their variants): each has one of the drop helpers below in its drop list, and the helper drops
// RLBattleRiflePickup where the corpse lies (DRLA Monsters 7.3, MonsterStuff.txt RLEnemyWeaponDrop and the monsters'
// own files). A Battle Rifle from anywhere else (a map, another drop, a spawner, a modded one) stays a Battle Rifle.
// Does nothing without DRLA Monsters.
//
// The pickup is told by where it appears: on the spot of such a monster that died lately. (The helper drops while it
// is being spawned, before the engine reports it, so the helper itself cannot be watched.) The coin is the drop's
// fixed loot seed when the engine gave it one (a Daggerfall map: the same monster drops the same gun every time, and
// no random number is drawn, so no other roll moves), else Doom's random numbers. The swap is made in the next tic,
// out of Doom's drop code: the carbine takes the rifle's place, toss and loot identity.
class DoomerfallLightCarbineDrops : EventHandler
{
	const DropTics = 10 * TICRATE; // A corpse is watched this long after the death; its drop comes within a second.
	const NearCorpse = 16; // The helper drops on the corpse's spot; in a test of 200 deaths 2 were off by more than 1.

	Array<Actor> swaps;
	Array<Actor> dying;
	Array<int> diedAt;

	static bool DropsBattleRifle(Actor monster)
	{
		for (let d = monster.GetDropItems(); d; d = d.Next)
		{
			Name n = d.Name;
			if (n == 'RLFormerHumanBattleRifleDrop' || n == 'RLFormerCommandoBattleRifleDrop' || n == 'RLEliteHumanBattleRifleDrop') return true;
		}
		return false;
	}

	// True for half the drops: the carbine's coin.
	static bool Heads(Actor pickup)
	{
		int seed = pickup.DD_LootSeed();
		if (seed == 0) return random[DoomerfallCarbine](0, 1) == 1;
		uint h = uint(seed) * 2654435761u;
		return ((h >> 16) & 1) == 1;
	}

	override void WorldThingDied(WorldEvent e)
	{
		if (!e.Thing || !e.Thing.bIsMonster || !DropsBattleRifle(e.Thing)) return;
		dying.Push(e.Thing);
		diedAt.Push(level.maptime);
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		let a = e.Thing;
		if (!a || dying.Size() == 0 || a.GetClassName() != 'RLBattleRiflePickup') return;
		for (int i = 0; i < dying.Size(); i++)
		{
			if (!dying[i] || (dying[i].pos.xy - a.pos.xy).Length() > NearCorpse) continue;
			if (Heads(a)) swaps.Push(a);
			dying.Delete(i); // One rifle per death.
			diedAt.Delete(i);
			return;
		}
	}

	override void WorldTick()
	{
		for (int i = dying.Size() - 1; i >= 0; i--)
			if (!dying[i] || level.maptime - diedAt[i] > DropTics) { dying.Delete(i); diedAt.Delete(i); }
		if (swaps.Size() == 0) return;
		for (int i = 0; i < swaps.Size(); i++)
		{
			let rifle = swaps[i];
			if (!rifle || (Inventory(rifle) && Inventory(rifle).Owner)) continue;
			let carbine = Actor.Spawn("DoomerfallLightCarbine", rifle.pos, NO_REPLACE);
			if (carbine)
			{
				carbine.angle = rifle.angle;
				carbine.vel = rifle.vel;
				carbine.bDropped = true;
				Inventory(carbine).bTossed = true;
				carbine.DD_TakeLootId(rifle); // Daggerfall rolls the gun's material from it (dd_items.cpp).
			}
			rifle.Destroy();
		}
		swaps.Clear();
	}
}
