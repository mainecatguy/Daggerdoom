version "4.14"

// Use key test on a regular WAD with no bridge (DOOM.WAD E1M1). Doom's own Use button, pressed through the QA channel
// as in harness.zs, opens the nearest Use door line and then presses the exit switch.
class UKWadHarness : EventHandler
{
	int phase, timer, doorLine, passed, failed;
	bool done, wantUse;
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

	override void WorldUnloaded(WorldEvent e)
	{
		if (phase == 3 && !done) { Report(true, "the exit switch ended the level"); Finish(); }
	}

	Line FindLine(PlayerPawn p, bool exitSwitch)
	{
		Line best = null;
		double range = 1e12;
		for (int i = 0; i < level.lines.Size(); i++)
		{
			Line l = level.lines[i];
			if (!(l.activation & SPAC_Use)) continue;
			bool door = l.special == 11 || l.special == 12; // Door_Open, Door_Raise (no key needed)
			if (exitSwitch ? l.special != 243 : !door) continue; // Exit_Normal
			double d = ((l.v1.p + l.v2.p) / 2 - p.pos.xy).Length();
			if (d < range) { range = d; best = l; }
		}
		return best;
	}

	void FaceLine(PlayerPawn p, Line l)
	{
		vector2 mid = (l.v1.p + l.v2.p) / 2;
		vector2 normal = (l.delta.y, -l.delta.x).Unit(); // The front side.
		vector2 at = mid + normal * 40;
		p.SetOrigin((at, l.frontsector.floorplane.ZatPoint(at)), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
		p.pitch = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE;
		if (wantUse)
		{
			if (!(players[0].cmd.buttons & BT_USE)) { p.vel = (0, 0, 0); return; }
			wantUse = false;
			Console.Printf("UKUSED");
		}
		timer++;
		if (level.maptime < 8) return;
		switch (phase)
		{
		case 0:
			{
				let l = FindLine(p, false);
				if (!l || !l.backsector) { Report(false, "no door line found"); Finish(); break; }
				FaceLine(p, l);
				doorLine = l.Index();
				before = l.backsector.ceilingplane.ZatPoint(l.backsector.centerspot);
				Console.Printf("UKPRESS door line %d special %d at %.0f,%.0f, player %.0f,%.0f", doorLine, l.special, l.v1.p.x, l.v1.p.y, p.pos.x, p.pos.y);
				wantUse = true; Console.Printf("UKUSE");
				phase = 1; timer = 0;
			}
			break;
		case 1:
			if (timer == 5)
			{
				// Doom's door mover for this line's sector (Door_Raise acts on the sector behind the line).
				let s = level.lines[doorLine].backsector;
				int movers = 0;
				let it = ThinkerIterator.Create("Door", Thinker.STAT_SECTOREFFECT);
				Door d;
				while (d = Door(it.Next())) movers++;
				double now = s.ceilingplane.ZatPoint(s.centerspot);
				Report(movers > 0, String.Format("Use started a door (%d door movers, ceiling %.0f to %.0f, floor %.0f)", movers, before, now, s.floorplane.ZatPoint(s.centerspot)));
				phase = 2; timer = 0;
			}
			break;
		case 2:
			{
				let l = FindLine(p, true);
				if (!l) { Report(false, "no exit switch found"); Finish(); break; }
				FaceLine(p, l);
				Console.Printf("UKPRESS exit switch line %d", l.Index());
				wantUse = true; Console.Printf("UKUSE");
				phase = 3; timer = 0;
			}
			break;
		case 3:
			if (timer > 35 * 3) { Report(false, "the exit switch did not end the level"); Finish(); }
			break;
		}
	}
}
