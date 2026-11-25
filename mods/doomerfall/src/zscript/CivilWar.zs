// Encounters, card 6: Civil War (design section 5.5 and appendix B of
// work/notes/20261123-205402-fractal-encounter-variety.md). No engine change: each Civil War mook gets its army's
// TID, its army's species (so species-filtered projectiles and splash hit the other army but spare teammates) and
// Thing_Hate (special 177) toward the other army's TID, with its army's stance toward the player:
//   hunt 3 (hunt the other army and the player), untilshot 1 (attack the player only when shot), ignore 5.
// Monsters hating the same TID count as allies, so an army never infights. One DoomerfallCivilWar thinker per level
// counts both armies; when one is wiped out, the survivors' hate is cleared with Thing_Hate(0, 0, 3) and they turn on
// the player. TIDs, species, TIDtoHate, the stance flags and this thinker are all saved with the level.
//
// dd_monsters.cpp calls Rig for every Civil War mook it spawns (or claims, for a spawner's monster).

class DoomerfallCivilWar : Thinker
{
	const TID_A = 31741;
	const TID_B = 31742;
	const CHECK_TICS = 35;
	const SETTLE_TICS = 70;  // after the last Rig, so spawner claims (up to 35 tics) land before the first count

	int wait;
	bool ended;
	int winner;              // -1 until the war ends, then the surviving army (or -1 when both died together)
	int riggedA, riggedB, unsafe, turned;
	int aliveA, aliveB;

	static int StanceOf(String s)
	{
		if (s == "untilshot") return 1;
		if (s == "ignore") return 5;
		return 3;
	}

	static DoomerfallCivilWar Find()
	{
		let it = ThinkerIterator.Create("DoomerfallCivilWar", STAT_USER);
		return DoomerfallCivilWar(it.Next());
	}

	static DoomerfallCivilWar Get()
	{
		let w = Find();
		if (w) return w;
		w = new("DoomerfallCivilWar");
		w.ChangeStatNum(STAT_USER);
		w.winner = -1;
		w.wait = SETTLE_TICS;
		return w;
	}

	static int TidOf(int side) { return side ? TID_B : TID_A; }

	// Joins `a` to army `side` (0 or 1) with Thing_Hate type `stance` toward the player.
	static void Rig(Actor a, int side, int stance)
	{
		if (!a || a.health <= 0 || (side != 0 && side != 1)) return;
		if (stance != 1 && stance != 3 && stance != 5) stance = 3;
		let w = Get();
		int own = TidOf(side), enemy = TidOf(1 - side);
		if (own == enemy) return;   // an army must never hate its own TID
		a.ChangeTid(own);
		a.A_SetSpecies(side ? 'DoomerfallArmyB' : 'DoomerfallArmyA');
		// After the war ended (a quest foe coming back later), a new arrival joins the survivors' side of things.
		if (w.ended) level.ExecuteSpecial(177, a, null, false, 0, 0, 3);
		else level.ExecuteSpecial(177, a, null, false, 0, enemy, stance);
		if (side) w.riggedB++; else w.riggedA++;
		if (!w.ended) w.wait = SETTLE_TICS;
		let pool = DoomerfallEncounterPool.Get();
		if (pool)
		{
			for (int i = 0; i < pool.monsters.Size(); i++)
			{
				let m = pool.monsters[i];
				if (m.cls != a.GetClass()) continue;
				if (!m.civilWarSafe) { w.unsafe++; DDLog.Debug(String.Format("DDWAR unsafe %s (%s) in a Civil War", a.GetClassName(), m.unsafeWhy)); }
				break;
			}
		}
	}

	static int Alive(int tid)
	{
		int n = 0;
		let it = level.CreateActorIterator(tid);
		Actor m;
		while (m = it.Next()) if (m.health > 0 && m.bIsMonster) n++;
		return n;
	}

	override void Tick()
	{
		if (ended || --wait > 0) return;
		wait = CHECK_TICS;
		aliveA = Alive(TID_A);
		aliveB = Alive(TID_B);
		if (aliveA > 0 && aliveB > 0) return;
		ended = true;
		winner = aliveA > 0 ? 0 : aliveB > 0 ? 1 : -1;
		if (winner < 0) { DDLog.Debug(String.Format("DDWAR both armies are gone")); return; }
		let it = level.CreateActorIterator(TidOf(winner));
		Actor m;
		while (m = it.Next())
		{
			if (m.health <= 0 || !m.bIsMonster) continue;
			level.ExecuteSpecial(177, m, null, false, 0, 0, 3);
			turned++;
		}
		DDLog.Debug(String.Format("DDWAR army %s wiped out; %d survivors of army %s turn on the player", winner ? "A" : "B", turned, winner ? "B" : "A"));
	}
}
