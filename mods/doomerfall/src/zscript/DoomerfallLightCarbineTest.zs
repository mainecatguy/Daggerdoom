// Test hook for the Light Carbine (DoomerfallLightCarbine.zs). tools/light_carbine/run_carbine_test.py runs it and
// checks the "CARBINE" and "CARBDROP" lines.
//   +set dd_carbine_test 1: gives the carbine with an empty magazine and 100 bullets and puts a target in front. The
//     runner pulls the trigger with a repeating console script; on a round's first press (alt-fire) the magazine is
//     emptied and the reserve set to 100. Each round pulls once on the empty gun (it reloads), held for 40 tics (one
//     shot), tapped every other tic (shot spacing), then the reload key. This reports presses, hits ("CARBINE hit")
//     and the magazine. With DRLA it then gives DRLA's Battle Rifle for the runner's last, held press.
//   +set dd_carbine_test 2 (DRLA and DRLA Monsters): kills 50 of each Battle Rifle monster and counts the rifles and
//     carbines they drop, then spawns 100 loose Battle Rifles, which must stay Battle Rifles.
class DoomerfallLightCarbineTest : StaticEventHandler
{
	int mode, phase, wait, tic;
	bool finished;
	Actor target;
	int riflesSpawned, carbinesSpawned;
	int lastButtons, lastAlt, lastMag, lastReserve, reloadTic, lastFrame;
	bool sawPress;

	override void WorldLoaded(WorldEvent e)
	{
		let flag = CVar.FindCVar("dd_carbine_test");
		mode = flag ? flag.GetInt() : 0;
		if (finished) mode = 0;
		phase = 0;
		wait = 35;
		reloadTic = -1;
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		if (mode != 2 || !e.Thing) return;
		Name n = e.Thing.GetClassName();
		if (n == 'RLBattleRiflePickup') riflesSpawned++;
		else if (n == 'DoomerfallLightCarbine') carbinesSpawned++;
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (mode != 1 || !target || e.Thing != target) return;
		let p = players[consoleplayer];
		String gun = p.ReadyWeapon ? String.Format("%s", p.ReadyWeapon.GetClassName()) : "none";
		Console.Printf("%s hit tic=%d damage=%d", gun == "DoomerfallLightCarbine" ? "CARBINE" : "BATTLERIFLE", level.maptime, e.Damage);
	}

	static int Count(Name cls)
	{
		int n = 0;
		let it = ThinkerIterator.Create(cls);
		while (it.Next()) n++;
		return n;
	}

	override void WorldTick()
	{
		if (mode == 0 || finished) return;
		let p = players[consoleplayer];
		if (!p.mo) return;
		if (mode == 1) TickFire(p);
		else TickDrops(p);
	}

	bool Settled(PlayerInfo p, Name cls)
	{
		let w = p.ReadyWeapon;
		if (!w || w.GetClassName() != cls || p.PendingWeapon != WP_NOCHANGE) return false;
		let psp = p.FindPSprite(PSP_WEAPON);
		State ready = w.FindState("Ready");
		return psp && psp.CurState && ready && psp.CurState.InStateSequence(ready);
	}

	// The trigger is pulled by console commands the test runner passes (+attack, +reload and wait): a script cannot
	// press buttons, because the engine copies the player's input over them before the player thinks. This only
	// watches and reports presses, releases, hits and the magazine.
	void TickFire(PlayerInfo p)
	{
		let mo = p.mo;
		if (wait > 0) { wait--; return; }
		tic++;
		String gun = p.ReadyWeapon && p.ReadyWeapon.GetClassName() == 'RLBattleRifle' ? "BATTLERIFLE" : "CARBINE";
		int buttons = p.cmd.buttons;
		if (phase >= 2)
		{
			if ((buttons & BT_ATTACK) != (lastButtons & BT_ATTACK))
				Console.Printf("%s %s tic=%d", gun, (buttons & BT_ATTACK) ? "press" : "release", level.maptime);
			if ((buttons & BT_RELOAD) && !(lastButtons & BT_RELOAD))
			{
				Console.Printf("%s reloadpress tic=%d", gun, level.maptime);
				reloadTic = level.maptime;
			}
			int mag = mo.CountInv("DoomerfallLightCarbineClip"), reserve = mo.CountInv("Clip");
			if (phase == 2 && (mag != lastMag || reserve != lastReserve))
				Console.Printf("CARBINE mag=%d reserve=%d tic=%d", mag, reserve, level.maptime);
			lastMag = mag;
			lastReserve = reserve;
			// Reload frames (C to U): the runner checks C-J with rounds left and N-U on an empty magazine, as DRLA.
			let psp = p.FindPSprite(PSP_WEAPON);
			int frame = psp && p.ReadyWeapon && p.ReadyWeapon.GetClassName() == 'DoomerfallLightCarbine' && psp.Sprite == Actor.GetSpriteIndex('DFLC') ? psp.Frame : -1;
			if (phase == 2 && frame != lastFrame && frame >= 2 && frame <= 20)
				Console.Printf("CARBINE frame=%c mag=%d tic=%d", 65 + frame, mag, level.maptime);
			lastFrame = frame;
		}
		lastAlt = lastButtons;
		lastButtons = buttons;
		switch (phase)
		{
		case 0:
		{
			// Pickups, as DRLA's Battle Rifle: the first gives only the gun, another gives 20 bullets.
			mo.SetInventory("Clip", 0);
			let first = Inventory(Actor.Spawn("DoomerfallLightCarbine", mo.pos));
			first.CallTryPickup(mo);
			int afterFirst = mo.CountInv("Clip");
			let second = Inventory(Actor.Spawn("DoomerfallLightCarbine", mo.pos));
			second.CallTryPickup(mo);
			Console.Printf("CARBINE pickup has=%d firstClip=%d secondClip=%d", mo.CountInv("DoomerfallLightCarbine"), afterFirst, mo.CountInv("Clip"));
			if (second && !second.Owner) second.Destroy();
		}
			mo.GiveInventory("DoomerfallLightCarbine", 1);
			mo.SetInventory("DoomerfallLightCarbineClip", 0);
			mo.SetInventory("Clip", 100);
			p.PendingWeapon = Weapon(mo.FindInventory("DoomerfallLightCarbine"));
			mo.A_SetPitch(0);
			target = Actor.Spawn("DoomerfallCarbineTestTarget", mo.Vec3Angle(80, mo.angle));
			Console.Printf("CARBINE given rifle=%d", DoomerfallRifleTag.IsRifle(Weapon(mo.FindInventory("DoomerfallLightCarbine"))));
			phase = 1; tic = 0;
			break;
		case 1:
			if (!Settled(p, 'DoomerfallLightCarbine')) break;
			Console.Printf("CARBINE ready tic=%d", level.maptime);
			phase = 11; tic = 0;
			break;
		case 11: // The runner's script repeats; each round starts with an alt-fire press. Start clean on one.
			if (!(buttons & BT_ALTATTACK) || (lastAlt & BT_ALTATTACK)) break;
			mo.SetInventory("DoomerfallLightCarbineClip", 0);
			mo.SetInventory("Clip", 100);
			Console.Printf("CARBINE round tic=%d", level.maptime);
			lastMag = lastReserve = -1;
			phase = 2; tic = 0;
			break;
		case 2: // Until 80 tics after the reload key.
			if (reloadTic < 0 || level.maptime < reloadTic + 80) { if (tic > 4000) phase = 9; break; }
			Console.Printf("CARBINE reloaded mag=%d reserve=%d", mo.CountInv("DoomerfallLightCarbineClip"), mo.CountInv("Clip"));
			phase = 6; tic = 0;
			break;
		case 6: // DRLA's Battle Rifle, for comparison: the runner's last press is held 40 tics.
		{
			String brName = "RLBattleRifle", brClipName = "RLBattleRifleClip"; // Looked up at run time: only DRLA has them.
			class<Weapon> br = brName;
			class<Inventory> brClip = brClipName;
			if (!br || !brClip) { phase = 9; break; }
			mo.GiveInventory(br, 1);
			mo.SetInventory(brClip, 20);
			p.PendingWeapon = Weapon(mo.FindInventory(br));
			phase = 7; tic = 0;
			break;
		}
		case 7:
			if (!Settled(p, 'RLBattleRifle')) { if (tic > 200) phase = 9; break; }
			Console.Printf("BATTLERIFLE ready tic=%d", level.maptime);
			phase = 8; tic = 0;
			break;
		case 8: // Until the runner's last release, or a time limit.
			if (lastButtons & BT_ATTACK) { sawPress = true; break; }
			if (sawPress || tic > 2000) { phase = 10; tic = 0; }
			break;
		case 10:
			if (tic < 20) break;
			phase = 9;
			break;
		default:
		{
			// Like other guns: Doom's drop tosses it into the world, and an inventory clear removes it.
			let w = mo.FindInventory("DoomerfallLightCarbine");
			let dropped = w ? mo.DropInventory(w) : null;
			bool dropOk = dropped && dropped.GetClassName() == 'DoomerfallLightCarbine' && !dropped.Owner && !mo.FindInventory("DoomerfallLightCarbine");
			if (dropped) dropped.Destroy();
			mo.GiveInventory("DoomerfallLightCarbine", 1);
			mo.ClearInventory();
			Console.Printf("CARBINE inventory dropped=%d cleared=%d", dropOk, !mo.FindInventory("DoomerfallLightCarbine"));
			finished = true;
			Console.Printf("CARBINE done");
			break;
		}
		}
	}

	void TickDrops(PlayerInfo p)
	{
		static const Name kinds[] = { 'RLFormerHumanBattleRifle', 'RLFormerCommandoBattleRifle', 'RLEliteHumanBattleRifle', 'RLFormerCyborgBattleRifle' };
		let mo = p.mo;
		mo.bPickup = false; // Nothing is picked up, so every drop can be counted.
		if (wait > 0) { wait--; return; }
		tic++;
		if (phase == 0)
		{
			for (int k = 0; k < kinds.Size(); k++)
			{
				class<Actor> c = kinds[k];
				if (!c) { Console.Printf("CARBDROP absent %s", kinds[k]); continue; }
				for (int i = 0; i < 5; i++)
				{
					let m = Actor.Spawn(c, mo.Vec3Angle(96, mo.angle + (i - 2) * 10));
					if (m) m.DamageMobj(null, null, m.health, 'None', DMG_FORCED | DMG_NO_ARMOR);
				}
			}
			if (tic >= 10) { phase = 1; tic = 0; }
		}
		else if (phase == 1 && tic >= 175)
		{
			Console.Printf("CARBDROP kills rifleSpawns=%d carbineSpawns=%d liveRifles=%d liveCarbines=%d", riflesSpawned, carbinesSpawned, Count('RLBattleRiflePickup'), Count('DoomerfallLightCarbine'));
			riflesSpawned = carbinesSpawned = 0;
			String rifleName = "RLBattleRiflePickup";
			class<Actor> rifle = rifleName;
			for (int i = 0; rifle && i < 100; i++) Actor.Spawn(rifle, mo.Vec3Angle(64, mo.angle + 180 + (i % 10) * 3));
			phase = 2; tic = 0;
		}
		else if (phase == 2 && tic >= 35)
		{
			Console.Printf("CARBDROP loose rifleSpawns=%d carbineSpawns=%d", riflesSpawned, carbinesSpawned);
			finished = true;
			Console.Printf("CARBINE done");
		}
	}
}

// A target that takes every hit and never dies, moves or bleeds.
class DoomerfallCarbineTestTarget : Actor
{
	Default
	{
		Health 1000000;
		Radius 24;
		Height 64;
		Mass 100000;
		+SHOOTABLE
		+SOLID
		+NOBLOOD
		+DONTTHRUST
		+NOPAIN
	}
	States
	{
	Spawn:
		PLAY A -1;
		Stop;
	}
}
