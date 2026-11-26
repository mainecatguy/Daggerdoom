version "4.14"

// Drop labels (test only, loaded by tools/droplabel/droplabel.py): Doom guns on the floor show their Daggerfall material
// in the look label before pickup, and the inventory gets the same name. Every step prints a PDL line; the look label
// itself is the engine's own "look:" log line (dd_look.cpp), read by the script between PDLAT and PDLEND.
//   save mode: a real New Game in Privateer's Hold. Kill the start's monsters; look at and take a dropped gun (A); look
//     at and take a script-spawned shotgun (C, no lasting id); Daggerfall's -dfgundroptest then drops that shotgun from
//     its inventory (D, which carries its material); look at D and a second dropped gun (B), left on the floor; autosave;
//     leave through the exit and come back through the door; look at B and D again; take D.
//   load mode: the save run's autosave, loaded by the bridge: look at B and D (positions from the save run); take D.
// Static, so it keeps its state across the exit and the re-entry. The positions of B and D come in as @BPOS@ / @DPOS@.
class PDLabels : StaticEventHandler
{
	static const double DOORSPOT[] = { @DOOR@ };	// The dungeon door on DDT07154: x, y, z, nx, ny.
	static const double EXITSPOT[] = { 834.750, 342.750, 1153.500, 0.7071, 0.7071 };	// Privateer's Hold's exit.
	static const double BPOS[] = { @BPOS@ };
	static const double DPOS[] = { @DPOS@ };
	static int Mode() { return @MODE@; }	// 0 save, 1 load
	const RADIUS = 1200;
	const LOOKTICS = 105;	// Daggerfall answers in a few tics; the first answer for a class may wait for its art (35 tics).

	int phase, timer, step, round;
	bool done;
	vector3 start, bAt, dAt, eAt;
	Array<Actor> before;
	Actor gunA, gunB, gunC, gunD, gunE, gunF;

	// Unclaimed shotguns without a carried material on E's spot (E and F, the same class on the same spot).
	int CountAtE()
	{
		int n = 0;
		let it = ThinkerIterator.Create("Inventory");
		Inventory a;
		while (a = Inventory(it.Next())) if (!a.Owner && a.GetClassName() == "RLShotgunPickup" && !Carried(a) && (a.pos.xy - eAt.xy).Length() < 8) n++;
		return n;
	}
	String bClass;

	void Finish(String how) { Console.Printf("PDDONE %s", how); done = true; }

	void PressUse(PlayerPawn p)
	{
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	static bool IsGunPickup(Actor a)
	{
		String n = a.GetClassName();
		return n.Left(2) == "RL" && n.Mid(n.Length() - 6) == "Pickup" && Inventory(a) && !Inventory(a).Owner && a.bSPECIAL;
	}

	static int Carried(Actor a)
	{
		if (!a) return 0;
		let m = a.FindInventory("DoomerfallGunMaterial");
		return m ? m.Amount : 0;
	}

	// A clear direction from the player, other than the one given (-1 for any).
	static double ClearAngle(PlayerPawn p, double avoid, double dist = 96)
	{
		for (int a = 0; a < 360; a += 45)
		{
			if (avoid >= 0 && abs(a - avoid) < 60) continue;
			FLineTraceData t;
			if (!p.LineTrace(a, dist, 0, TRF_THRUACTORS, 16, 0, 0, t) || t.HitType == TRACE_HitNone) return a;
		}
		return 0;
	}

	// Stand in front of the item, looking at it, for LOOKTICS. True on the tic the look window ends.
	bool LookStep(PlayerPawn p, Actor item, String tag)
	{
		if (!item) return true;
		if (timer == 1)
		{
			p.SetOrigin((item.pos.xy - Actor.AngleToVector(p.angle, 48), item.pos.z), false);
			p.vel = (0, 0, 0);
			p.pitch = 0;
			Console.Printf("PDLAT %s %s seed %08x carried %d at %.0f %.0f %.0f", tag, item.GetClassName(), item.DD_LootSeed(), Carried(item), item.pos.x, item.pos.y, item.pos.z);
		}
		if (timer < LOOKTICS) return false;
		Console.Printf("PDLEND %s", tag);
		return true;
	}

	void TurnAway(PlayerPawn p) { p.angle += 180; }

	Actor Nearest(String cls, vector3 at, bool carrying)
	{
		Actor best;
		double bestD = 128;
		let it = ThinkerIterator.Create("Inventory");
		Inventory a;
		while (a = Inventory(it.Next()))
		{
			if (a.Owner || a.GetClassName() != cls || (carrying && !Carried(a))) continue;
			double d = (a.pos.xy - at.xy).Length();
			if (d < bestD) { best = a; bestD = d; }
		}
		return best;
	}

	override void WorldTick()
	{
		if (done || !players[0].mo) return;
		let p = PlayerPawn(players[0].mo);
		timer++;
		players[0].cheats |= CF_GODMODE;
		p.bNOTARGET = true;
		bool inside = level.MapName ~== "MAP01";
		bool ready = CVar.FindCVar("dd_sync_df_phase").GetInt() == 3;
		if (phase < 2 || (phase == 2 && timer < 35)) level.SetFrozen(true);
		switch (phase)
		{
		case 0: // Arrival in the dungeon with Daggerfall in play (New Game, or the bridge's load of the autosave).
			if (!inside || !ready) { timer = 0; break; }
			if (timer < 35 * 3) break;
			start = p.pos;
			Console.Printf("PDLARRIVED %s at %.0f %.0f %.0f", level.MapName, p.pos.x, p.pos.y, p.pos.z);
			phase = Mode() == 1 ? 20 : 2; timer = 0;
			break;
		case 2: // Kill the start's monsters; the rest of the dungeon stays dormant.
		{
			if (timer < 35) break;
			level.SetFrozen(false);
			before.Clear();
			Array<Actor> victims;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next()))
			{
				if (a is "Inventory" && !Inventory(a).Owner) before.Push(a);
				if (!a.bISMONSTER || a.player || a.health <= 0) continue;
				if ((a.SpawnPoint - (380, 1270, 0)).Length() < RADIUS) victims.Push(a); else a.Deactivate(null);
			}
			for (int i = 0; i < victims.Size(); i++)
			{
				a = victims[i];
				if (!a.bSHOOTABLE && a.SeeState) { a.target = p; a.SetState(a.SeeState); }
				a.DamageMobj(p, p, 100000, 'None', DMG_FORCED);
			}
			Console.Printf("PDLKILLED %d", victims.Size());
			phase = 3; timer = 0;
			break;
		}
		case 3: // The dropped guns: A (taken now) and B (left on the floor).
		{
			if (timer < 35 * 8) break;
			let it = ThinkerIterator.Create("Inventory");
			Inventory a;
			while (a = Inventory(it.Next()))
			{
				if (before.Find(a) != before.Size() || !IsGunPickup(a) || !a.DD_LootSeed()) continue;
				if (!gunA) gunA = a; else if (!gunB) gunB = a;
			}
			String an = "none", bn = "none";
			if (gunA) an = gunA.GetClassName();
			if (gunB) bn = gunB.GetClassName();
			Console.Printf("PDLGUNS A %s B %s", an, bn);
			if (!gunA) { Finish("nogun"); break; }
			// Carried to clear spots by the start, away from the corpses' loot piles, as tools/fixed_drops/paired.zs does.
			p.SetOrigin(start, false);
			p.vel = (0, 0, 0);
			// B lies further along A's clear line, out of reach from in front of D, which takes A's spot later.
			double aa = ClearAngle(p, -1, 240), ab = aa;
			p.angle = aa;
			gunA.SetOrigin((start.xy + Actor.AngleToVector(aa, 96), start.z), false);
			gunA.vel = (0, 0, 0);
			if (gunB) { gunB.SetOrigin((start.xy + Actor.AngleToVector(ab, 208), start.z), false); gunB.vel = (0, 0, 0); bAt = gunB.pos; bClass = gunB.GetClassName(); }
			phase = 4; timer = 0;
			break;
		}
		case 4: // A: look, then take.
			if (timer == 1) p.angle = atan2(gunA.pos.y - p.pos.y, gunA.pos.x - p.pos.x);
			if (timer <= LOOKTICS) { LookStep(p, gunA, "A"); break; }
			if (timer == LOOKTICS + 1) { Console.Printf("PDLUSE A"); PressUse(p); }
			if (timer < LOOKTICS + 10) break;
			if (!gunA || !gunA.bSPECIAL) { Console.Printf("PDLTAKEN A"); TurnAway(p); phase = 5; timer = 0; }
			else if (timer > LOOKTICS + 35 * 5) Finish("A still on the floor");
			break;
		case 5: // C: a shotgun a script spawns, with no lasting id. Look, then take.
			if (timer == 10)
			{
				p.SetOrigin(start, false);
				p.angle = ClearAngle(p, -1);
				gunC = Actor.Spawn("RLShotgunPickup", (start.xy + Actor.AngleToVector(p.angle, 96), start.z));
				Console.Printf("PDLSPAWNED C %d seed %08x", gunC != null, gunC ? gunC.DD_LootSeed() : 0);
				if (!gunC) { Finish("no shotgun"); break; }
			}
			if (timer <= 10) break;
			if (timer <= 10 + LOOKTICS) { timer -= 10; LookStep(p, gunC, "C"); timer += 10; break; }
			if (timer == 11 + LOOKTICS) { Console.Printf("PDLUSE C"); PressUse(p); }
			if (timer < 20 + LOOKTICS) break;
			if (!gunC || !gunC.bSPECIAL) { Console.Printf("PDLTAKEN C"); TurnAway(p); phase = 6; timer = 0; }
			else if (timer > LOOKTICS + 35 * 5) Finish("C still on the floor");
			break;
		case 6: // D: Daggerfall's gun drop test drops the shotgun from its inventory after 6 s.
		{
			let it = ThinkerIterator.Create("Inventory");
			Inventory a;
			while (a = Inventory(it.Next()))
				if (!a.Owner && a.GetClassName() == "RLShotgunPickup" && Carried(a)) gunD = a;
			if (!gunD) { if (timer > 35 * 20) Finish("no drop from the inventory"); break; }
			if (timer < 35 * 2 + 10) break;	// Let it land.
			p.SetOrigin(start, false);
			double ad = bClass != "" ? atan2(bAt.y - start.y, bAt.x - start.x) : ClearAngle(p, -1);
			gunD.SetOrigin((start.xy + Actor.AngleToVector(ad, 96), start.z), false);
			gunD.vel = (0, 0, 0);
			dAt = gunD.pos;
			// E: a script-spawned gun nobody looks at before the first leave and return, so it is first recorded with no
			// lasting id of its own; looked at after the return, then again after a second leave and return.
			double ae = ClearAngle(p, ad);
			gunE = Actor.Spawn("RLShotgunPickup", (start.xy + Actor.AngleToVector(ae, 96), start.z));
			if (gunE) { eAt = gunE.pos; gunF = Actor.Spawn("RLShotgunPickup", eAt); }
			Console.Printf("PDLSPAWNED E %d at %.0f %.0f", gunE != null, eAt.x, eAt.y);
			Console.Printf("PDLDROPPED D carried %d", Carried(gunD));
			phase = 7; timer = 0;
			break;
		}
		case 7: // Look at D, then B; then the autosave with both on the floor.
			if (step == 0) { if (timer == 1) p.angle = atan2(gunD.pos.y - start.y, gunD.pos.x - start.x); if (LookStep(p, gunD, "D1")) { TurnAway(p); step = 1; timer = 0; } break; }
			if (step == 1) { if (timer < 10) break; if (timer == 10) p.angle = gunB ? atan2(gunB.pos.y - start.y, gunB.pos.x - start.x) : 0; timer -= 9; bool end = LookStep(p, gunB, "B1"); timer += 9; if (end) { TurnAway(p); step = 2; timer = 0; } break; }
			if (timer == 10)
			{
				Console.Printf("PDLPOS B %.3f, %.3f, %.3f D %.3f, %.3f, %.3f", bAt.x, bAt.y, bAt.z, dAt.x, dAt.y, dAt.z);
				Console.Printf("PDLSAVE autosave");
				LevelLocals.MakeAutoSave();
			}
			// The autosave recorded the place (MakeRecord): unnamed E and F now hold lasting ids of their own.
			if (timer == 35 * 5) Console.Printf("PDLESEED E %08x F %08x", gunE ? gunE.DD_LootSeed() : 0, gunF ? gunF.DD_LootSeed() : 0);
			if (timer >= 35 * 6) { phase = 8; timer = 0; step = 0; }
			break;
		case 8: // Leave through the exit.
			if (!inside) { Console.Printf("PDLOUT %s", level.MapName); phase = 9; timer = 0; break; }
			p.SetOrigin((EXITSPOT[0] + EXITSPOT[3] * 40, EXITSPOT[1] + EXITSPOT[4] * 40, EXITSPOT[2]), false);
			p.angle = atan2(-EXITSPOT[4], -EXITSPOT[3]);
			p.vel = (0, 0, 0);
			if (timer % 35 == 4) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (timer > 35 * 20) Finish("could not leave");
			break;
		case 9: // Outside: back in through the door.
			if (inside) { Console.Printf("PDLBACK"); phase = 10; timer = 0; break; }
			if (timer < 35 * 2) break;
			p.SetOrigin((DOORSPOT[0] + DOORSPOT[3] * 48, DOORSPOT[1] + DOORSPOT[4] * 48, DOORSPOT[2]), false);
			p.angle = atan2(-DOORSPOT[4], -DOORSPOT[3]);
			p.vel = (0, 0, 0);
			if (timer % 70 == 0) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (timer > 35 * 40) Finish("could not come back");
			break;
		case 10: // Back inside: B and D where they were left.
			if (round == 1)
			{
				if (timer < 35 * 3 || !ready) break;
				gunE = Nearest("RLShotgunPickup", eAt, false);
				Console.Printf("PDLFOUND E %d same spot %d", gunE != null, CountAtE());
				phase = 13; timer = 0;
				break;
			}
			if (timer < 35 * 3 || !ready) break;
			gunB = bClass != "" ? Nearest(bClass, bAt, false) : null;
			gunD = Nearest("RLShotgunPickup", dAt, true);
			Console.Printf("PDLFOUND B %d D %d", gunB != null, gunD != null);
			if (!gunD) { Finish("D gone after the return"); break; }
			phase = 11; timer = 0; step = 0;
			break;
		case 12: // E after the first return, then leave and come back once more.
			if (timer == 1 && gunE) p.angle = atan2(gunE.pos.y - p.pos.y, gunE.pos.x - p.pos.x);
			if (LookStep(p, gunE, "E1")) { TurnAway(p); round = 1; phase = 8; timer = 0; }
			break;
		case 13: // E after the second return.
			if (timer == 1 && gunE) p.angle = atan2(gunE.pos.y - p.pos.y, gunE.pos.x - p.pos.x);
			if (!LookStep(p, gunE, "E2")) break;
			if (!gunE) { Finish("E gone after the second return"); break; }
			TurnAway(p);
			gunD = Nearest("RLShotgunPickup", dAt, true);
			if (!gunD) { Finish("D gone after the second return"); break; }
			p.SetOrigin((gunD.pos.xy - Actor.AngleToVector(atan2(gunD.pos.y - start.y, gunD.pos.x - start.x), 48), gunD.pos.z), false);
			p.angle = atan2(gunD.pos.y - p.pos.y, gunD.pos.x - p.pos.x);
			p.vel = (0, 0, 0);
			phase = 11; step = 2; timer = 0;
			break;
		case 20: // Load: B and D from the save run's positions.
			if (timer < 35) break;
			bClass = "";
			gunB = null;
			if (BPOS.Size() == 3)
			{
				vector3 at = (BPOS[0], BPOS[1], BPOS[2]);
				let it = ThinkerIterator.Create("Inventory");
				Inventory a;
				while (a = Inventory(it.Next()))
					if (!a.Owner && IsGunPickup(a) && (a.pos.xy - at.xy).Length() < 8) gunB = a;
			}
			gunD = Nearest("RLShotgunPickup", (DPOS[0], DPOS[1], DPOS[2]), true);
			start = p.pos;
			Console.Printf("PDLFOUND B %d D %d", gunB != null, gunD != null);
			if (!gunD) { Finish("D gone after the load"); break; }
			phase = 11; timer = 0; step = 0;
			break;
		case 11: // Look at B and D again, then take D.
			if (step == 0) { if (timer == 1 && gunB) p.angle = atan2(gunB.pos.y - p.pos.y, gunB.pos.x - p.pos.x); if (LookStep(p, gunB, "B2")) { TurnAway(p); step = 1; timer = 0; } break; }
			if (step == 1) { if (timer < 10) break; if (timer == 10) p.angle = atan2(gunD.pos.y - p.pos.y, gunD.pos.x - p.pos.x); timer -= 9; bool end = LookStep(p, gunD, "D2"); timer += 9; if (end) { step = 2; timer = 0; } break; }
			// The save run looks at E and leaves and comes back once more before D is taken, so every autosave (the load
			// run takes the newest) still has D on the floor.
			if (Mode() == 0 && round == 0)
			{
				gunE = Nearest("RLShotgunPickup", eAt, false);
				Console.Printf("PDLFOUND E %d same spot %d", gunE != null, CountAtE());
				phase = 12; timer = 0;
				break;
			}
			if (timer == 1) { Console.Printf("PDLUSE D"); PressUse(p); }
			if (timer < 10) break;
			if (!gunD || !gunD.bSPECIAL) { Console.Printf("PDLTAKEN D"); Finish("passed"); }
			else if (timer > 35 * 5) Finish("D still on the floor");
			break;
		}
	}
}
