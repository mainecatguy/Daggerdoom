version "4.14"

// Town corpses test (tools/town_corpses/town_corpses.py). Modes in @MODE@:
//   kill   wait for townspeople, stand 96 units from the nearest one facing it, kill it (test only), list corpses,
//          ask for screenshots, walk 30000 units away, list, walk back into town, list again, and autosave.
//   load   after a load: wait for Daggerfall's list, stand where the corpse is, list corpses, ask for a screenshot.
//   guard  (with Daggerfall's -dfguardtest) enter the Gothway tavern; once Daggerfall's guards come in as bots, kill one
//          (test only), list corpses, ask for screenshots, go out and back in, list again, and autosave.
//   guardload  as load, for the guard run's autosave inside the tavern.
class TCHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LIMIT = 35 * 100;
	int phase, timer, backAt;
	vector3 spot, land;
	double face, landAngle;
	bool landed;

	static bool Inside() { return level.MapName.Left(3) ~== "DDS"; }

	// A living guard bot (any player but player 0), or null.
	static Actor Guard()
	{
		for (int i = 1; i < MAXPLAYERS; i++)
			if (playeringame[i] && players[i].mo && players[i].mo.health > 0) return players[i].mo;
		return null;
	}

	void AtDoor(PlayerPawn p)
	{
		p.SetOrigin((DOORDATA[0] + DOORDATA[3] * 48, DOORDATA[1] + DOORDATA[4] * 48, DOORDATA[2]), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-DOORDATA[4], -DOORDATA[3]);
		p.pitch = 0;
	}

	static int Corpses(String tag)
	{
		let it = ThinkerIterator.Create((class<Actor>)("DFCorpse"));
		Actor mo;
		int count = 0;
		while (mo = Actor(it.Next()))
		{
			Console.Printf("TCCORPSE %s %08x%08x %.1f %.1f %.1f %s %s scale %.3f %.3f", tag, mo.args[1], mo.args[0], mo.pos.x, mo.pos.y, mo.pos.z,
				TexMan.GetName(mo.picnum), mo.bINVISIBLE ? "hidden" : "shown", mo.scale.x, mo.scale.y);
			count++;
		}
		Console.Printf("TCCOUNT %s %d map %s", tag, count, level.MapName);
		return count;
	}

	static Actor FirstCorpse()
	{
		let it = ThinkerIterator.Create((class<Actor>)("DFCorpse"));
		return Actor(it.Next());
	}

	void LookAt(PlayerPawn p, Actor mo)
	{
		vector2 d = (mo.pos.x - p.pos.x, mo.pos.y - p.pos.y);
		double len = max(d.Length(), 1);
		p.SetOrigin((mo.pos.xy - d / len * 96, p.pos.z), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(d.y, d.x);
		p.pitch = 20;
	}

	override void WorldTick()
	{
		if (phase == 9 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		String mode = "@MODE@";
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		timer++;
		if (timer > LIMIT) { Console.Printf("TCDONE timeout phase %d", phase); phase = 9; return; }
		switch (phase)
		{
		case 0:
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (mode.IndexOf("kill") >= 0 && timer < 300)
			{
				// Stand outside the Gothway tavern, where townspeople walk at noon (as the townspeople test does).
				p.SetOrigin((DOORDATA[0] + DOORDATA[3] * 64, DOORDATA[1] + DOORDATA[4] * 64, DOORDATA[2]), false);
				p.vel = (0, 0, 0);
				p.angle = atan2(DOORDATA[4], DOORDATA[3]);
			}
			if (mode == "guard")
			{
				if (Inside() || timer < 60) break;
				AtDoor(p);
				if (timer == 80) { CVar.FindCVar("dd_tm_use").SetInt(1); phase = 30; timer = 0; }
				break;
			}
			if (timer < 420) break;
			if (mode.IndexOf("load") >= 0)
			{
				Corpses("loaded");
				let c = FirstCorpse();
				if (c) LookAt(p, c);
				phase = 20;
				timer = 0;
				break;
			}
			Actor best;
			double range = 1000000000.0;
			let it = ThinkerIterator.Create((class<Actor>)("DFTownsperson"));
			Actor mo;
			while (mo = Actor(it.Next()))
				if (p.Distance2D(mo) < range) { range = p.Distance2D(mo); best = mo; }
			if (!best) { if (timer > 1400) { Console.Printf("TCDONE nobody to kill"); phase = 9; } break; }
			LookAt(p, best);
			Console.Printf("TCKILL %08x%08x at %.1f %.1f %s", best.args[1], best.args[0], best.pos.x, best.pos.y, TexMan.GetName(best.picnum));
			Console.Printf("TCSHOT before");
			phase = 1;
			timer = 0;
			best.Die(p, p);
			break;
		case 1:
			if (timer == 3) Console.Printf("TCSHOT blood");
			if (timer < 70) break;
			Corpses("afterkill");
			let c = FirstCorpse();
			if (c) { LookAt(p, c); spot = p.pos; face = p.angle; }
			Console.Printf("TCSHOT corpse");
			phase = 2;
			timer = 0;
			break;
		case 2:	// Leave town into the wilderness, as the townspeople test does.
			if (timer == 20) { Console.Printf("TCLEAVE from %s", level.MapName); p.SetOrigin(p.pos + (30000, 0, 0), false); }
			if (timer < 300) break;
			Corpses("away");
			phase = 3;
			timer = 0;
			break;
		case 3:	// Walk back toward town until Doom stitches into the town map, then on to the corpse.
			if (level.MapName.Left(3) ~== "DDT" && backAt == 0) { backAt = timer; Console.Printf("TCBACK map %s after %d tics", level.MapName, timer); }
			if (backAt > 0 && timer >= backAt + 140)
			{
				p.SetOrigin(spot, false);
				p.angle = face;
				p.vel = (0, 0, 0);
				if (timer < backAt + 300) break;
				Corpses("return");
				let c = FirstCorpse();
				if (c) LookAt(p, c);
				Console.Printf("TCSHOT return");
				phase = 4;
				timer = 0;
				break;
			}
			if (backAt == 0) { p.vel = (0, 0, 0); p.SetOrigin((p.pos.x - 48, p.pos.y, p.floorz), false); }
			break;
		case 4:
			if (timer < 40) break;
			Console.Printf("TCSAVE");
			level.MakeAutoSave();
			phase = 5;
			timer = 0;
			break;
		case 5:
			if (timer < 210) break;
			Console.Printf("TCDONE ok");
			phase = 9;
			break;
		case 30:	// Inside the tavern: wait for Daggerfall's guards to come in as bots, then kill one.
			if (!Inside()) { if (timer > 35 * 20) { Console.Printf("TCDONE door did not open"); phase = 9; } break; }
			if (!landed) { landed = true; land = p.pos; landAngle = p.angle; Console.Printf("TCINSIDE %s", level.MapName); }
			let g = Guard();
			if (!g) { if (timer > 35 * 40) { Console.Printf("TCDONE no guard came"); phase = 9; } break; }
			if (timer < 35 * 2) break;
			LookAt(p, g);
			Console.Printf("TCGUARD player %d at %.1f %.1f %s", g.PlayerNumber(), g.pos.x, g.pos.y, TexMan.GetName(g.picnum));
			Console.Printf("TCSHOT gbefore");
			g.DamageMobj(p, p, 1000000, 'None', DMG_FORCED);
			phase = 31;
			timer = 0;
			break;
		case 31:
			if (timer == 3) Console.Printf("TCSHOT gblood");
			if (timer < 70) break;
			Corpses("gafterkill");
			let gc = FirstCorpse();
			if (gc) LookAt(p, gc);
			Console.Printf("TCSHOT gcorpse");
			phase = 32;
			timer = 0;
			break;
		case 32:	// Out through the way in (a landing faces away from its door), then back in.
			if (timer == 20) { p.SetOrigin(land, false); p.angle = landAngle + 180; p.vel = (0, 0, 0); }
			if (timer == 26) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!Inside() && timer > 26) { Console.Printf("TCLEAVE to %s", level.MapName); phase = 33; timer = 0; break; }
			if (timer > 35 * 20) { Console.Printf("TCDONE exit did not work"); phase = 9; }
			break;
		case 33:
			if (timer < 70) break;
			if (timer == 70) Corpses("goutside");
			AtDoor(p);
			if (timer == 90) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (Inside()) { Console.Printf("TCBACK map %s", level.MapName); phase = 34; timer = 0; break; }
			if (timer > 35 * 20) { Console.Printf("TCDONE no re-entry"); phase = 9; }
			break;
		case 34:
			if (timer < 35 * 4) break;
			Corpses("greturn");
			let rc = FirstCorpse();
			if (rc) LookAt(p, rc);
			Console.Printf("TCSHOT greturn");
			phase = 4;
			timer = 0;
			break;
		case 20:
			if (timer == 40) Console.Printf("TCSHOT loaded");
			if (timer < 100) break;
			Corpses("loaded-late");
			Console.Printf("TCDONE ok");
			phase = 9;
			break;
		}
	}
}
