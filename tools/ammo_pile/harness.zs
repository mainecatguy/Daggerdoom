version "4.14"

// Dropped ammo piles (tools/ammo_pile/ammo_pile.py). The first run enters Privateer's Hold, gives the player all four
// ammo types, and waits while Daggerfall's -dfammopiletest hook drops five piles through its inventory window. It prints
// the piles near the player (APPILE), leaves to town, comes back, prints them again, and autosaves inside. The load run
// loads that save and prints them a third time.
class APHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 25;
	const LOADRUN = @LOADRUN@;
	const SAVED = 10;
	const NEAR = 768;
	int phase, timer, startPiles;
	bool done;
	vector3 spot;

	void Finish(String why) { Console.Printf("APDONE %s", why); done = true; }
	void Next() { phase++; timer = 0; }

	// Piles within NEAR of spot: count, and with print, one line each.
	int Piles(String when, bool print)
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		Actor mo;
		int n = 0;
		while (mo = Actor(it.Next()))
		{
			if ((mo.pos.xy - spot.xy).Length() > NEAR) continue;
			n++;
			if (!print) continue;
			let item = DoomerfallWorldItem(mo);
			Console.Printf("APPILE %s id=%s sprite=%s items=%d scale=%.2f,%.2f at %d,%d,%d", when, item.dfId, TexMan.GetName(mo.picnum), item.dfCount,
				mo.scale.x, mo.scale.y, int(mo.pos.x), int(mo.pos.y), int(mo.pos.z));
		}
		if (print) Console.Printf("APCOUNT %s %d piles near the drop spot", when, n);
		return n;
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		bool ready = level.maptime >= 8 && CVar.FindCVar("dd_sync_df_phase").GetInt() == 3;
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (LOADRUN && phase == SAVED) { phase = 20; timer = 0; }
		if (LOADRUN && phase < SAVED) return;

		switch (phase)
		{
		case 0: // Enter the dungeon by the door.
		case 4:
			if (inside) { Next(); break; }
			if (!ready) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer == 12 || timer % 175 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (timer > LIMIT) Finish("no entry");
			break;
		case 1: // Inside: clear it, give the ammo Daggerfall's hook drops, and wait for its five piles.
			if (timer == 35)
			{
				RemoveMonsters();
				spot = p.pos;
				startPiles = Piles("before", true);
				p.GiveInventory("Clip", 60);
				p.GiveInventory("Shell", 8);
				p.GiveInventory("RocketAmmo", 6);
				p.GiveInventory("Cell", 40);
				Console.Printf("APGIVE Clip=%d Shell=%d RocketAmmo=%d Cell=%d", p.CountInv("Clip"), p.CountInv("Shell"), p.CountInv("RocketAmmo"), p.CountInv("Cell"));
			}
			if (timer < 35) break;
			if (timer % 35 == 0) RemoveMonsters();
			if (Piles("", false) >= startPiles + 5 && timer > 35 * 8) { Piles("dropped", true); Next(); break; }
			if (timer > LIMIT * 2) { Piles("dropped", true); Finish("the five piles never appeared"); }
			break;
		case 2: // Leave by the exit.
			if (timer == 1)
			{
				p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
				p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
				p.vel = (0, 0, 0);
			}
			if (timer == 10 || timer % 175 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { Console.Printf("APLEFT in town"); Next(); }
			else if (timer > LIMIT) Finish("exit did not work");
			break;
		case 3: // In town a few seconds, then back in (case 4).
			if (timer > 35 * 4) Next();
			break;
		case 5: // Back inside: the piles are put back. Stand at the drop spot, print them, and save.
			if (timer == 35) { p.SetOrigin(spot, false); p.vel = (0, 0, 0); RemoveMonsters(); }
			if (timer < 35 * 6) break;
			Piles("returned", true);
			Console.Printf("APSAVE autosave");
			LevelLocals.MakeAutoSave();
			phase = SAVED;
			timer = 0;
			break;
		case SAVED:
			if (timer > 35 * 3) Finish("saved");
			break;
		case 20: // Loaded.
			if (timer % 35 == 0) RemoveMonsters();
			if (timer < 35 * 8) break;
			spot = p.pos;
			Piles("loaded", true);
			Finish("loaded");
			break;
		}
	}
}
