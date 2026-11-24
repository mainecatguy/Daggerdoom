version "4.14"

// Reserve ammo in Daggerfall's inventory. The take run enters Privateer's Hold, picks up a box of bullets by touch,
// spends 5 bullets, waits for Daggerfall's test hook (-dfammotest) to drop 7 bullets and add 20 shells on its side,
// then autosaves. The load run loads that save in fresh copies of both games and reports the counts again.
class AMHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const String AMMO[] = { "Clip", "Shell", "RocketAmmo", "Cell" };
	const LIMIT = 35 * 20;
	const LOADRUN = @LOADRUN@;
	const SAVED = 10;

	int phase, timer, startClip, startShell;
	bool done;

	void Finish(String why)
	{
		Report("final");
		Console.Printf("AMDONE %s", why);
		done = true;
	}

	void Next() { phase++; timer = 0; }

	void Report(String why)
	{
		let p = players[0].mo;
		String line = "AMCOUNT " .. why;
		for (int i = 0; i < AMMO.Size(); i++)
			line = line .. " " .. AMMO[i] .. "=" .. p.CountInv(AMMO[i]);
		Console.Printf("%s", line);
	}

	bool AnyPile()
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		return it.Next() != null;
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
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;
		if (LOADRUN && phase == SAVED) { phase = 20; timer = 0; Report("loaded"); }
		if (LOADRUN && phase < SAVED) return;

		switch (phase)
		{
		case 0: // Enter the dungeon by the test door hook.
			if (inside) { Next(); break; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			Next();
			break;
		case 1: // Daggerfall's pile list shows it is ready in this space.
			if (timer > LIMIT) { Finish("Daggerfall never listed this space"); break; }
			if (!inside || !AnyPile() || timer < 35) break;
			RemoveMonsters();
			startClip = p.CountInv("Clip");
			startShell = p.CountInv("Shell");
			Report("start");
			Next();
			break;
		case 2: // A box of bullets by touch. Stock ClipBox, not DRLA's spawner, so the amount is known.
		{
			// Two boxes, so Daggerfall's hook (60 bullets) runs whatever gun DRLA X started the player with.
			for (int i = 0; i < 2; i++)
			{
				let box = Inventory(Actor.Spawn("ClipBox", p.pos, NO_REPLACE));
				if (box) box.Touch(p);
			}
			Report("after ClipBox");
			Next();
			break;
		}
		case 3: // Spend 5 bullets, as firing would.
			if (timer < 35) break;
			p.TakeInventory("Clip", 5);
			Report("after spending 5");
			Next();
			break;
		case 4: // Daggerfall's test hook drops 7 bullets and adds 20 shells on its side.
			if (timer % 35 == 0) Report("waiting");
			// The hook may already have run if Doom started with 60 or more bullets.
			if (p.CountInv("Shell") >= 20) { Report("after Daggerfall change"); Next(); }
			else if (timer > LIMIT) { Finish("Daggerfall's change never arrived"); }
			break;
		case 5:
			if (timer < 70) break;
			Report("before save");
			Console.Printf("AMSAVE autosave");
			LevelLocals.MakeAutoSave();
			phase = SAVED;
			timer = 0;
			break;
		case SAVED:
			if (timer > 35 * 8) Finish("saved");
			break;
		case 20: // Loaded: give Doom's report time to reach Daggerfall.
			if (timer == 35 * 6) Finish("loaded");
			break;
		}
	}
}
