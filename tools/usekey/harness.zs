version "4.14"

// Use key test. Every press is Doom's own Use button: the harness prints UKUSE and holds still, and usekey.py asks the
// QA channel (-ddqa, dd_qa.cpp) for one press, which sets BT_USE in the next built ticcmd exactly as the +use control
// does. So it runs Doom's whole Use path (the town door check, P_CheckUse, Daggerfall action objects). Nothing sends
// netevent df_interact. Modes:
//   shop:    town door into a store, a shelf, the shopkeeper twice (shop menu, then talk), crouch-Use (steal).
//   dungeon: dungeon entrance, a Doom drop, a Daggerfall pile, a hinged door, a lever.
// wad_harness.zs is the regular WAD check.
// Results are UKCASE lines; the runner also reads Daggerfall's log for the windows each press opened.
class UKHarness : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const MODE = "@MODE@";
	const LIMIT = 35 * 25;

	int phase, timer, presses, passed, failed;
	bool done, wantUse, crouchHold;
	double holdAngle, holdPitch;
	Actor target, npc, box;
	double before;

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("UKCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void Finish()
	{
		Console.Printf("UKRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("UKDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	void Next(int to) { phase = to; timer = 0; }

	static void Face(PlayerPawn p, vector3 aim)
	{
		vector2 flat = aim.xy - p.pos.xy;
		p.angle = atan2(flat.y, flat.x);
		p.pitch = -atan2(aim.z - (p.pos.z + p.player.viewheight), flat.Length());
	}

	// A spot about `reach` from aim where the player fits and sees aim. Moves the player there and faces aim.
	static bool StandBy(PlayerPawn p, vector3 aim, double reach)
	{
		for (int a = 0; a < 360; a += 30)
		{
			vector2 at = aim.xy + (cos(a), sin(a)) * reach;
			vector3 old = p.pos;
			p.SetOrigin((at, aim.z), false);
			double floor = p.CurSector.NextLowestFloorAt(at.x, at.y, aim.z + 24);
			p.SetZ(floor);
			if (abs(p.pos.z - aim.z) < 64 && p.TestMobjLocation())
			{
				Face(p, aim);
				FLineTraceData t;
				p.LineTrace(p.angle, reach + 16, p.pitch, TRF_THRUACTORS, p.player.viewheight, 0, 0, t);
				if (t.HitType == TRACE_HitNone || t.Distance > reach - 24) { p.vel = (0, 0, 0); return true; }
			}
			p.SetOrigin(old, false);
		}
		return false;
	}

	static Actor Nearest(PlayerPawn p, Name cls)
	{
		Actor best = null;
		let it = ThinkerIterator.Create(cls);
		Actor mo;
		while (mo = Actor(it.Next()))
			if (!mo.bInvisible && (!best || (mo.pos - p.pos).Length() < (best.pos - p.pos).Length())) best = mo;
		return best;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (crouchHold) players[0].crouchfactor = 0.5; // Crouched, as holding Crouch leaves the player.
		if (wantUse)
		{
			// Hold still until the press arrives. This tic's player think already ran it when BT_USE shows here.
			if (!(players[0].cmd.buttons & BT_USE))
			{
				p.vel = (0, 0, 0);
				p.angle = holdAngle;
				p.pitch = holdPitch;
				return;
			}
			wantUse = crouchHold = false;
			presses++;
			Console.Printf("UKUSED %d", presses);
		}
		timer++;
		if (timer > LIMIT) { Report(false, String.Format("timeout in phase %d", phase)); Finish(); return; }
		if (MODE == "shop") TickShop(p);
		else TickDungeon(p);
	}

	void Press(PlayerPawn p)
	{
		wantUse = true;
		holdAngle = p.angle;
		holdPitch = p.pitch;
		Console.Printf("UKUSE");
	}

	bool InSpace() { return level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01"; }

	// Outside: stand at the test door and press Use once Daggerfall is in play (TickTownDoors).
	void EnterByUse(PlayerPawn p, String what)
	{
		if (InSpace()) { Report(true, what .. " opened with Use"); Next(1); return; }
		if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) { timer = 0; return; }
		if (timer == 1)
		{
			int k1, k2;
			[k1, k2] = Bindings.GetKeysForCommand("+use");
			int i1, i2;
			[i1, i2] = Bindings.GetKeysForCommand("netevent df_interact");
			Console.Printf("UKBINDS +use keys %d %d (%s), netevent df_interact keys %d %d", k1, k2, KeyBindings.NameKeys(k1, k2, false), i1, i2);
			Report(k1 != 0 && i1 == 0, "Doom's Use is bound and nothing is bound to the old Interact control");
		}
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		p.SetOrigin((door.xy + normal * 48, door.z), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
		p.pitch = 0;
		if (timer == 35) Press(p);
		if (timer > 35 * 20) { Report(false, what .. " did not open with Use"); Finish(); } // An interior may convert first ("Opening...").
	}

	void TickShop(PlayerPawn p)
	{
		switch (phase)
		{
		case 0: EnterByUse(p, "the store's town door"); break;
		case 1: // Wait for Daggerfall's list, then pick the shopkeeper and the nearest shelf.
			if (timer < 35 * 3) break;
			npc = Nearest(p, "DFNpc");
			box = Nearest(p, "DoomerfallWorldContainer");
			Report(npc && box, "the store shows a shopkeeper and a shelf");
			if (!npc || !box) { Finish(); break; }
			Next(2);
			break;
		case 2: // Use on the shelf. Daggerfall's trade window opens; its test hook buys and closes it.
			if (timer == 1)
			{
				let c = DoomerfallWorldContainer(box);
				vector3 aim = ((c.dfMinX + c.dfMaxX) / 2, (c.dfMinY + c.dfMaxY) / 2, (c.dfMinZ + c.dfMaxZ) / 2);
				if (!StandBy(p, aim, 40 + max(c.dfMaxX - c.dfMinX, c.dfMaxY - c.dfMinY) / 2)) Console.Printf("UKNOTE no clear spot by the shelf");
				Console.Printf("UKPRESS shelf");
				Press(p);
			}
			if (timer == 35 * 3) Next(3);
			break;
		case 3: // Use twice on the shopkeeper (shop menu, then talk), then crouch and Use (steal).
			if (timer == 1)
			{
				int w, h;
				[w, h] = TexMan.GetSize(npc.picnum);
				vector3 aim = npc.pos + (0, 0, h * npc.scale.y / 2);
				if (!StandBy(p, aim, 56)) Console.Printf("UKNOTE no clear spot by the shopkeeper");
				bool steal = presses >= 4; // Door, shelf, two standing presses, then this one.
				crouchHold = steal;
				Console.Printf("UKPRESS shopkeeper %s", steal ? "crouching" : "standing");
				Press(p);
			}
			if (timer == 35 * 3) { if (presses >= 5) Finish(); else Next(3); }
			break;
		}
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	void TickDungeon(PlayerPawn p)
	{
		switch (phase)
		{
		case 0: EnterByUse(p, "the dungeon's town door"); break;
		case 1: // Wait for Daggerfall's pile list, clear the monsters, and drop a Doom gun in front of the player.
			if (timer < 35 * 3 || !Nearest(p, "DoomerfallWorldItem")) break;
			RemoveMonsters();
			{
				class<Actor> gun = "RLPistolPickup";
				if (!gun) gun = "Shotgun";
				vector2 ahead = (cos(p.angle), sin(p.angle));
				target = Actor.Spawn(gun, (p.pos.xy + ahead * 48, p.pos.z), NO_REPLACE);
				Console.Printf("UKDROP %s", target ? target.GetClassName() : 'none');
			}
			Next(2);
			break;
		case 3: // A Daggerfall pile: Use opens Daggerfall's loot window (the runner checks Daggerfall's log).
			if (timer == 1)
			{
				// The pile lying closest to its floor (some sit on ledges or mesh shelves), from about 40 units away.
				target = null;
				let it = ThinkerIterator.Create("DoomerfallWorldItem");
				Actor mo;
				while (mo = Actor(it.Next()))
				{
					Console.Printf("UKPILE %s at %.0f,%.0f,%.0f floor %.0f", DoomerfallWorldItem(mo).dfId, mo.pos.x, mo.pos.y, mo.pos.z, mo.floorz);
					if (!target || abs(mo.pos.z - mo.floorz) < abs(target.pos.z - target.floorz)) target = mo;
				}
				if (!target) { Report(false, "no Daggerfall pile here"); Next(4); break; }
				if (!StandBy(p, (target.pos.xy, target.floorz), 40)) p.SetOrigin((target.pos.xy + (40, 0), target.floorz), false);
				p.vel = (0, 0, 0);
			}
			if (target && timer <= 35) Face(p, target.pos); // From where the player landed.
			if (timer == 35) // The hidden Daggerfall player catches up with the move first, as Daggerfall checks the reach.
			{
				Console.Printf("UKPRESS pile %s at distance %.0f, in sight %d", target ? DoomerfallWorldItem(target).dfId : "none",
					target ? (target.pos - p.pos).Length() : 0, target && p.CheckSight(target, SF_IGNOREVISIBILITY));
				Press(p);
			}
			if (timer == 35 + 35 * 3) Next(4);
			break;
		case 2: // The Doom drop: Use takes it (Daggerfall answers, then it leaves the floor).
			if (timer <= 20 && !target) { Report(false, "the Doom drop vanished before the press"); Next(3); break; }
			if (timer == 20) { StandBy(p, target.pos + (0, 0, 8), 40); Console.Printf("UKPRESS doom drop"); Press(p); }
			if (timer > 21 && (!target || !target.bSPECIAL)) { Report(true, "Use took the Doom drop (Daggerfall answered, then it left the floor)"); Next(3); break; }
			if (timer > 35 * 4) { Report(false, "the Doom drop is still on the floor"); Next(3); }
			break;
		case 4: // A hinged Daggerfall door: Use swings it.
			if (timer == 1)
			{
				let d = DFDoor(Nearest(p, "DFDoor"));
				target = d;
				if (!d || !d.links.Size()) { Report(false, "no hinged door in this dungeon"); Next(5); break; }
				let link = d.links[d.links.Size() / 2];
				vector3 aim = link.pos + (0, 0, 40);
				if (!StandBy(p, aim, 48)) Console.Printf("UKNOTE no clear spot by the door");
				before = d.swung;
				Console.Printf("UKPRESS door swung %.1f moving %d", d.swung, d.moving);
				Press(p);
			}
			if (timer == 35)
			{
				let d = DFDoor(target);
				Report(d && (d.swung != before || d.moving != 0), String.Format("Use swung the door (%.1f to %.1f degrees)", before, d ? d.swung : 0));
				Next(5);
			}
			break;
		case 5: // A lever or button (a Daggerfall action object used directly).
			if (timer == 1)
			{
				DFAction lever = null;
				let it = ThinkerIterator.Create("DFAction");
				DFAction a;
				while (a = DFAction(it.Next()))
					if (!a.door && (a.trigger == DFAction.TR_DIRECT || a.trigger == DFAction.TR_DIRECT6 || a.trigger == DFAction.TR_MULTI || a.trigger == DFAction.TR_COLLIDE9)
						&& (!lever || (a.ToWorld(a.center, a.fraction) - p.pos).Length() < (lever.ToWorld(lever.center, lever.fraction) - p.pos).Length())) lever = a;
				target = lever;
				if (!lever) { Console.Printf("UKNOTE no directly used action object here"); Finish(); break; }
				vector3 at = lever.ToWorld(lever.center, lever.fraction);
				if (!StandBy(p, at, 48) && !StandBy(p, at, 32)) Console.Printf("UKNOTE no clear spot by the lever");
				before = lever.activationCount;
				Console.Printf("UKPRESS lever at %.0f,%.0f,%.0f trigger %d", at.x, at.y, at.z, lever.trigger);
				Press(p);
			}
			if (timer == 20)
			{
				let a = DFAction(target);
				Report(a && a.activationCount > before, "Use pressed the lever");
				Finish();
			}
			break;
		}
	}
}
