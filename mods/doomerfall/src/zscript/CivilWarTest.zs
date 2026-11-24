// Test hook (card 6): with +set dd_civilwar_test AB (A and B are the two armies' Thing_Hate stances: 3 hunt,
// 1 untilshot, 5 ignore; e.g. 31), it spawns 100 Imps (army A) against 100 Shotgun Guys (army B) on the open test map
// from tools/encounter_placer/civilwar_test.py, rigs them with DoomerfallCivilWar.Rig, and prints "DDWARTEST" lines:
//   tic 5 spawn; tic 350 the player shoots one monster of each army; tic 560 the rest of army B is killed;
//   tic 980 the summary. A loaded save (same cvar) prints the rig state at load and carries on with the timeline.
// The player is in god mode and never fires.
class DoomerfallCivilWarTest : StaticEventHandler
{
	const SPAWN_TIC = 5;
	const SHOOT_TIC = 350;
	const WIPE_TIC = 560;
	const END_TIC = 980;

	int stance[2];
	bool active, spawned;
	double last;
	double frameSum, frameMax;
	int frames;
	int targetedBefore[2], targetedAfterWipe, sameArmyTarget[2];
	int damageToPlayer[2], crossDamage[2], sameDamage[2];
	int killed[2];
	Actor shot[2];
	bool shotRetaliated[2];

	override void WorldLoaded(WorldEvent e)
	{
		let flag = CVar.FindCVar("dd_civilwar_test");
		if (!flag || !flag.GetInt()) return;
		active = true;
		stance[0] = flag.GetInt() / 10;
		stance[1] = flag.GetInt() % 10;
		if (e.IsSaveGame)
		{
			spawned = true;
			Console.Printf("DDWARTEST loaded at tic %d", level.maptime);
			Report("load");
		}
	}

	private PlayerPawn Me() { return players[consoleplayer].mo; }

	private void Report(String when)
	{
		let w = DoomerfallCivilWar.Find();
		for (int side = 0; side < 2; side++)
		{
			int tid = DoomerfallCivilWar.TidOf(side), enemy = DoomerfallCivilWar.TidOf(1 - side);
			int alive = 0, badSpecies = 0, badHate = 0, badFlags = 0;
			let it = level.CreateActorIterator(tid);
			Actor m;
			while (m = it.Next())
			{
				if (m.health <= 0) continue;
				alive++;
				if (m.Species != (side ? 'DoomerfallArmyB' : 'DoomerfallArmyA')) badSpecies++;
				bool turned = w && w.ended;
				if (m.TIDtoHate != (turned ? 0 : enemy)) badHate++;
				int st = turned ? 3 : stance[side];
				if (m.bHuntPlayers != (st == 3) || m.bNoHatePlayers != (st == 5)) badFlags++;
			}
			Console.Printf("DDWARTEST state %s army %s tid %d alive %d bad-species %d bad-hate %d bad-flags %d", when, side ? "B" : "A", tid, alive, badSpecies, badHate, badFlags);
		}
		if (w) Console.Printf("DDWARTEST state %s watcher ended %d winner %d riggedA %d riggedB %d unsafe %d turned %d", when, w.ended, w.winner, w.riggedA, w.riggedB, w.unsafe, w.turned);
		else Console.Printf("DDWARTEST state %s watcher none", when);
	}

	private int SideOf(Actor a)
	{
		if (!a) return -1;
		if (a.tid == DoomerfallCivilWar.TID_A) return 0;
		if (a.tid == DoomerfallCivilWar.TID_B) return 1;
		return -1;
	}

	private void Spawn()
	{
		spawned = true;
		players[consoleplayer].cheats |= CF_GODMODE;
		for (int side = 0; side < 2; side++)
		{
			class<Actor> cls = side ? "ShotgunGuy" : "DoomImp";
			for (int i = 0; i < 100; i++)
			{
				double x = (side ? 300 : -1200) + (i % 10) * 96;
				double y = -400 + (i / 10) * 96;
				let a = Actor.Spawn(cls, (x, y, 0));
				if (!a) continue;
				a.angle = side ? 180 : 0;
				DoomerfallCivilWar.Rig(a, side, stance[side]);
			}
		}
		Report("spawn");
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!active || !e.DamageSource) return;
		int from = SideOf(e.DamageSource);
		if (from < 0) return;
		if (e.Thing == Me()) damageToPlayer[from] += e.Damage;
		else
		{
			int to = SideOf(e.Thing);
			if (to == from) sameDamage[from] += e.Damage;
			else if (to >= 0) crossDamage[from] += e.Damage;
		}
	}

	override void WorldThingDied(WorldEvent e)
	{
		if (!active) return;
		int side = SideOf(e.Thing);
		if (side >= 0) killed[side]++;
	}

	override void WorldTick()
	{
		if (!active) return;
		double now = MSTimeF();
		if (last > 0 && level.maptime > SPAWN_TIC + 10 && level.maptime < WIPE_TIC)
		{
			double d = now - last;
			frameSum += d;
			frameMax = max(frameMax, d);
			frames++;
		}
		last = now;
		int t = level.maptime;
		if (!spawned && t >= SPAWN_TIC) Spawn();
		let me = Me();
		let w = DoomerfallCivilWar.Find();
		for (int side = 0; side < 2; side++)
		{
			let it = level.CreateActorIterator(DoomerfallCivilWar.TidOf(side));
			Actor m;
			while (m = it.Next())
			{
				if (m.health <= 0 || !m.target) continue;
				if (m.target == me)
				{
					if (t < SHOOT_TIC) targetedBefore[side]++;
					if (w && w.ended) targetedAfterWipe++;
				}
				else if (SideOf(m.target) == side) sameArmyTarget[side]++;
			}
			if (t < WIPE_TIC && shot[side] && shot[side].health > 0 && shot[side].target == me && !shotRetaliated[side])
			{
				shotRetaliated[side] = true;
				Console.Printf("DDWARTEST army %s shot monster %s targets the player at tic %d: tidtohate %d hunt %d nohate %d lastenemy-player %d",
					side ? "B" : "A", shot[side].GetClassName(), t, shot[side].TIDtoHate, shot[side].bHuntPlayers, shot[side].bNoHatePlayers,
					shot[side].lastenemy == me);
			}
		}
		if (t == SHOOT_TIC) Report("before-shot");
		// The player shoots one monster per army every 5 tics for 2 s (1 damage). Doom lets a monster busy with a
		// visible hated enemy ignore a hit half the time (OkayToSwitchTarget), so one shot is not a fair test.
		if (t >= SHOOT_TIC && t <= SHOOT_TIC + 70 && (t - SHOOT_TIC) % 5 == 0)
		{
			for (int side = 0; side < 2; side++)
			{
				if (!shot[side] || shot[side].health <= 1)
				{
					shot[side] = null;
					let it = level.CreateActorIterator(DoomerfallCivilWar.TidOf(side));
					Actor m;
					while (m = it.Next()) if (m.health > 1 && (!shot[side] || m.health > shot[side].health)) shot[side] = m;
				}
				if (shot[side]) shot[side].DamageMobj(me, me, 1, 'None');
			}
		}
		if (t == WIPE_TIC)
		{
			Report("before-wipe");
			let it = level.CreateActorIterator(DoomerfallCivilWar.TID_B);
			Actor m;
			while (m = it.Next()) if (m.health > 0) m.DamageMobj(null, null, m.health + 1000, 'None', DMG_FORCED);
		}
		if (t == WIPE_TIC + 140) Report("after-wipe");
		if (t == END_TIC)
		{
			Report("end");
			for (int side = 0; side < 2; side++)
				Console.Printf("DDWARTEST army %s stance %d killed %d targeted-player-before-shot %d shot-retaliated %d same-army-target %d same-army-damage %d cross-damage %d damage-to-player %d",
					side ? "B" : "A", stance[side], killed[side], targetedBefore[side], shotRetaliated[side], sameArmyTarget[side], sameDamage[side], crossDamage[side], damageToPlayer[side]);
			Console.Printf("DDWARTEST survivors-targeted-player-after-wipe %d", targetedAfterWipe);
			Console.Printf("DDWARTEST frames %d avg %.2f ms max %.2f ms", frames, frames ? frameSum / frames : 0., frameMax);
			Console.Printf("DDWARTEST done");
		}
	}
}
