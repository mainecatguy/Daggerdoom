version "4.14"

// Pickup rule test on the real dungeon: spawns real classes and checks touch, Use, and loot piles.
// Use is pressed through the real P_CheckUse. A console "+use" never reaches a minimized UZDoom, so the
// town door press is left to the play-test list.
class APHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const String TOUCH[] = { @TOUCH@ };
	static const String USE[] = { @USE@ };
	const LIMIT = 35 * 20;

	int phase, timer, index, passed, failed, step, pileRound;
	bool done;
	Actor item;
	String pileId;
	vector3 home;
	vector2 ahead;

	void Finish()
	{
		Console.Printf("APRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("APDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("APCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	// Doom only checks touches while the player moves.
	void Wiggle(PlayerPawn p)
	{
		p.TryMove(p.pos.xy + ahead * ((timer & 1) ? 1 : -1), 0);
		p.vel = (0, 0, 0);
	}

	void PressUse(PlayerPawn p, bool crouch)
	{
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		if (crouch) players[0].cmd.buttons |= BT_CROUCH;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	void FindClearSpot(PlayerPawn p)
	{
		home = p.pos;
		for (int a = 0; a < 360; a += 45)
		{
			FLineTraceData t;
			if (!p.LineTrace(a, 96, 0, TRF_THRUACTORS, 16, 0, 0, t) || t.HitType == TRACE_HitNone)
			{
				p.angle = a;
				break;
			}
		}
		ahead = (cos(p.angle), sin(p.angle));
		p.pitch = 0;
	}

	void GoHome(PlayerPawn p)
	{
		p.SetOrigin(home, false);
		p.vel = (0, 0, 0);
		p.angle = atan2(ahead.y, ahead.x);
		p.pitch = 0;
	}

	DoomerfallWorldItem NearestPile(PlayerPawn p)
	{
		DoomerfallWorldItem best = null, pile;
		double range = 1e12;
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		while (pile = DoomerfallWorldItem(it.Next()))
		{
			double d = (pile.pos - p.pos).Length();
			if (d < range) { range = d; best = pile; }
		}
		return best;
	}

	DoomerfallWorldItem PileById(String id)
	{
		DoomerfallWorldItem pile;
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		while (pile = DoomerfallWorldItem(it.Next()))
			if (pile.dfId == id) return pile;
		return null;
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	void AimAt(PlayerPawn p, Actor target)
	{
		vector2 flat = target.pos.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(target.pos.z - (p.pos.z + players[0].viewheight), flat.Length());
		p.vel = (0, 0, 0);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;

		switch (phase)
		{
		case 0: // Enter the dungeon by the test door hook. The handler starts fresh on each map.
			if (inside) { phase = 1; timer = 0; break; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			phase = 1;
			timer = 0;
			break;
		case 1: // Wait for Daggerfall's pile list.
			if (timer > LIMIT) { Report(false, "no piles listed"); Finish(); break; }
			if (timer % 70 == 0) Console.Printf("APWAIT map %s inside %d pile %d", level.MapName, inside, NearestPile(p) != null);
			if (!inside || NearestPile(p) == null || timer < 35) break;
			RemoveMonsters();
			FindClearSpot(p);
			phase = 2;
			timer = 0;
			break;
		case 2: TouchCase(p); break;
		case 3: UseCase(p); break;
		case 4: PileCase(p); break;
		}
	}

	void TouchCase(PlayerPawn p)
	{
		if (index >= TOUCH.Size()) { index = 0; step = 0; timer = 0; phase = 3; return; }
		if (step == 0)
		{
			class<Actor> cls = TOUCH[index];
			if (!cls) { Report(false, "missing class " .. TOUCH[index]); index++; return; }
			GoHome(p);
			// Health items refuse a full player. A small drop keeps Daggerfall's synchronized HP far from death.
			if (p.health >= 98) p.health = players[0].health = 97;
			for (Inventory i = p.Inv; i; i = i.Inv)
				if (i is "Ammo") i.Amount = 0;
			item = Actor.Spawn(cls, p.pos, NO_REPLACE);
			timer = 0;
			step = 1;
			return;
		}
		Wiggle(p);
		if (!item || !item.bSPECIAL || item is "Inventory" && Inventory(item).Owner)
		{
			Report(true, "touch " .. TOUCH[index]);
			if (item) item.Destroy();
		}
		else if (timer > 20)
		{
			Report(false, "touch " .. TOUCH[index] .. " stayed on the floor");
			item.Destroy();
		}
		else return;
		item = null;
		index++;
		step = 0;
	}

	void UseCase(PlayerPawn p)
	{
		if (index >= USE.Size()) { index = 0; step = 0; timer = 0; phase = 4; return; }
		switch (step)
		{
		case 0:
		{
			class<Actor> cls = USE[index];
			if (!cls) { Report(false, "missing class " .. USE[index]); index++; return; }
			GoHome(p);
			let armor = p.FindInventory("BasicArmor");
			if (armor) armor.Amount = 0; // The Megasphere touch case leaves 200 armor, and Doom then refuses GreenArmor.
			item = Actor.Spawn(cls, (home.xy + ahead * 48, home.z), NO_REPLACE);
			timer = 0;
			step = 1;
			break;
		}
		case 1: // DRLA weapons only become pickups after landing.
			if (!item) { Report(false, "use " .. USE[index] .. " vanished at spawn"); index++; step = 0; break; }
			if (item.bSPECIAL) { p.SetOrigin((item.pos.xy, home.z), false); timer = 0; step = 2; break; }
			if (timer > 70) { Report(false, "use " .. USE[index] .. " never became a pickup"); item.Destroy(); index++; step = 0; }
			break;
		case 2: // Standing on it must not pick it up.
			Wiggle(p);
			if (!item || !item.bSPECIAL) { Report(false, "use " .. USE[index] .. " was taken by touch"); index++; step = 0; break; }
			if (timer < 16) break;
			GoHome(p);
			timer = 0;
			step = 3;
			break;
		case 3: // Press the real Use check while looking straight ahead.
			if (timer == 3) PressUse(p, false);
			if (timer < 6) break;
			bool taken = !item || !item.bSPECIAL;
			let armor = p.FindInventory("BasicArmor");
			Report(taken, "use " .. USE[index] .. (taken ? " taken by Use" : String.Format(" not taken by Use (armor %d)", armor ? armor.Amount : -1)));
			if (item && !taken) item.Destroy();
			item = null;
			index++;
			step = 0;
			break;
		}
	}

	void PileCase(PlayerPawn p)
	{
		switch (step)
		{
		case 0:
		{
			let pile = NearestPile(p);
			if (!pile) { Report(false, "no pile left for round " .. pileRound); Finish(); return; }
			pileId = pile.dfId;
			// Stand 40 units away on a side with room and a clear view.
			for (int a = 0; a < 360; a += 45)
			{
				p.SetOrigin((pile.pos.xy + (cos(a), sin(a)) * 40, pile.pos.z), false);
				if (p.TestMobjLocation() && p.CheckSight(pile, SF_IGNOREVISIBILITY)) break;
			}
			Console.Printf("APSTAND %.0f from pile, sight %d", (pile.pos.xy - p.pos.xy).Length(), p.CheckSight(pile, SF_IGNOREVISIBILITY));
			timer = 0;
			step = 1;
			break;
		}
		case 1: // Let the hidden Daggerfall player catch up.
		{
			let pile = PileById(pileId);
			if (pile) AimAt(p, pile);
			if (timer < 35) break;
			Console.Printf("APPILE %s press %s", pileId, pileRound == 0 ? "steal" : "grab");
			PressUse(p, pileRound == 0);
			timer = 0;
			step = 2;
			break;
		}
		case 2:
			if (PileById(pileId) == null)
			{
				Report(true, String.Format("pile taken by Use (%s)", pileRound == 0 ? "crouching" : "standing"));
				pileRound++;
				step = 0;
				timer = 0;
				if (pileRound == 2) Finish();
			}
			else if (timer > 35 * 6) { Report(false, "pile still there"); Finish(); }
			break;
		}
	}
}
