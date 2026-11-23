version "4.10"

// Automated map check. Inactive unless started with +set dfcheck 1.

class DFProbe : Actor
{
	Default { Radius 10.5; Height 56; MaxStepHeight 24; +NOGRAVITY; +NOBLOCKMAP; +DROPOFF; +NOTRIGGER; } // the 21-wide player box of the 0.75-scale world
	States { Spawn: TNT1 A -1; Stop; }
}

class DFShooter : Actor
{
	Default { Radius 16; Height 56; +NOGRAVITY; +NOBLOCKMAP; }
	States { Spawn: TNT1 A -1; Stop; }
}

// A melee-free imp, so the chase test measures movement instead of stopping to shoot.
class DFChaser : DoomImp
{
	Default { Radius 16; Height 56; +NOPAIN; }
	States { Missile: Goto See; Melee: Goto See; }
}

class DFMapCheck : EventHandler
{
	const BATCH = 1500;
	const SAMPLES = 8;
	Array<int> nx, ny, nf, nc, ea, eb, ed, doorControl;
	int start, phase, cursor, wait, test, closedBlocked, closedTotal;
	int nodeFail, edgeFail, doorStuck, doorsUsed, soundBleed, soundBlocked;
	int walkOk, walkBad, fallOk, fallBad, slabOk, slabBad, ledgeOk, ledgeBad, shotOk, shotBad, slabShotOk, slabShotBad, chaseOk, chaseBad;
	Array<int> falls, ledges, slabA, slabB, chaseFrom, chaseTo;
	DFProbe probe;
	Actor shooter, monster;
	double chaseStart, lastEdgeDz;
	bool active;
	int dbgCount;

	// Doom spawns players on the lowest floor, so converted maps move them to the real entrance.
	override void PlayerEntered(PlayerEvent e)
	{
		int lump = Wads.CheckNumForName("DFPOINTS", Wads.ns_global);
		if (lump < 0 || !players[e.PlayerNumber].mo) return;
		Array<String> head;
		Wads.ReadLump(lump).Left(64).Split(head, " ");
		if (head.Size() < 5 || head[0] != "S") return;
		let mo = players[e.PlayerNumber].mo;
		mo.SetOrigin((head[2].ToInt(), head[3].ToInt(), head[4].ToInt()), false);
		mo.FindFloorCeiling();
	}

	override void WorldLoaded(WorldEvent e)
	{
		if (CVar.FindCVar("dfcheck").GetInt() != 1) return;
		int lump = Wads.CheckNumForName("DFPOINTS", Wads.ns_global);
		if (lump < 0) { Console.Printf("DFCHK ERROR no DFPOINTS lump"); return; }
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n");
		for (int i = 0; i < lines.Size(); i++)
		{
			Array<String> p;
			lines[i].Split(p, " ");
			if (p.Size() < 2) continue;
			if (p[0] == "S") start = p[1].ToInt();
			else if (p[0] == "N") { nx.Push(p[2].ToInt()); ny.Push(p[3].ToInt()); nf.Push(p[4].ToInt()); nc.Push(p[5].ToInt()); }
			else if (p[0] == "E") { ea.Push(p[1].ToInt()); eb.Push(p[2].ToInt()); ed.Push(p[3].ToInt()); }
			else if (p[0] == "D") doorControl.Push(p[1].ToInt());
		}
		active = true;
		Console.Printf("DFCHK LOADED nodes=%d edges=%d doors=%d sectors=%d lines=%d", nx.Size(), ea.Size(), doorControl.Size(), level.sectors.Size(), level.lines.Size());
	}

	bool MoveEdge(int a, int b)
	{
		probe.SetOrigin((nx[a], ny[a], nf[a]), false);
		probe.FindFloorCeiling();
		probe.SetZ(probe.floorz);
		vector2 target = (nx[b], ny[b]);
		vector2 mid = ((nx[a] + nx[b]) / 2.0, (ny[a] + ny[b]) / 2.0);
		lastEdgeDz = 9999; // 9999 means TryMove was blocked
		if (!probe.TryMove(mid, 1)) return false;
		probe.SetZ(probe.floorz);
		if (!probe.TryMove(target, 1)) return false;
		probe.SetZ(probe.floorz);
		lastEdgeDz = probe.pos.z - nf[b]; // sloped floors differ from the converter's node height, so the log keeps the number
		return abs(lastEdgeDz) <= 2;
	}

	override void WorldTick()
	{
		if (!active || !players[0].mo) return;
		if (wait > 0) { wait--; return; }
		PlayerPawn pawn = players[0].mo;
		switch (phase)
		{
		case 0:
			probe = DFProbe(Actor.Spawn("DFProbe", pawn.pos));
			pawn.bINVULNERABLE = true;
			Console.Printf("DFCHK START floor=%d expected=%d", int(pawn.floorz), nf[start]);
			phase = 1;
			break;
		case 1: // Door edges must be blocked while doors are closed.
			for (int n = 0; n < BATCH && cursor < ea.Size(); cursor++)
			{
				if (!ed[cursor]) continue;
				n++;
				closedTotal++;
				if (!MoveEdge(ea[cursor], eb[cursor])) closedBlocked++;
			}
			if (cursor >= ea.Size()) { cursor = 0; phase = 2; }
			break;
		case 2: // Open every door through its real use line.
		{
			Array<int> done;
			for (int i = 0; i < level.lines.Size(); i++)
			{
				Line l = level.lines[i];
				if (l.special != 254 || done.Find(l.args[0]) != done.Size()) continue;
				done.Push(l.args[0]);
				if (l.Activate(pawn, 0, SPAC_Use)) doorsUsed++;
			}
			wait = 105;
			phase = 3;
			break;
		}
		case 3:
			for (int d = 0; d < doorControl.Size(); d++)
			{
				let it = level.CreateSectorTagIterator(doorControl[d]);
				int s;
				while ((s = it.Next()) >= 0)
				{
					Sector sec = level.sectors[s];
					if (sec.ceilingplane.ZAtPoint(sec.centerspot) - sec.floorplane.ZAtPoint(sec.centerspot) > 1) doorStuck++;
				}
			}
			phase = 4;
			break;
		case 4:
			for (int n = 0; n < BATCH && cursor < nx.Size(); n++, cursor++)
			{
				probe.SetOrigin((nx[cursor], ny[cursor], nf[cursor] + 1), false);
				probe.FindFloorCeiling();
				probe.SetZ(probe.floorz); // stand on the floor, so a space exactly 56 high still fits
				bool fits = probe.TestMobjLocation();
				if (!fits || abs(probe.floorz - nf[cursor]) > 2 || abs(probe.ceilingz - nc[cursor]) > 2)
				{
					nodeFail++;
					Console.Printf("DFCHK N %d %d %d %d", cursor, fits, int(probe.floorz), int(probe.ceilingz));
					if (!fits && probe.ceilingz <= probe.floorz && dbgCount < 400) // failures whose ceiling lies below the floor, with the sector's stacked slabs, for diagnosis
					{
						dbgCount++;
						vector2 at = (nx[cursor], ny[cursor]);
						Sector sc = level.PointInSector(at);
						String t = String.Format("DFDBG node %d at %d,%d,%d sector %d floor %.0f ceil %.0f ff=%d:", cursor, nx[cursor], ny[cursor], nf[cursor], sc.Index(), sc.floorplane.ZAtPoint(at), sc.ceilingplane.ZAtPoint(at), sc.Get3DFloorCount());
						for (int q = 0; q < sc.Get3DFloorCount(); q++)
						{
							F3DFloor ff = sc.Get3DFloor(q);
							t = t .. String.Format(" [%.0f..%.0f f%x]", ff.bottom.ZAtPoint(at), ff.top.ZAtPoint(at), ff.flags);
						}
						Console.Printf("%s", t);
					}
				}
			}
			if (cursor >= nx.Size()) { cursor = 0; phase = 5; }
			break;
		case 5:
			for (int n = 0; n < BATCH && cursor < ea.Size(); n++, cursor++)
				if (!MoveEdge(ea[cursor], eb[cursor]))
				{
					edgeFail++;
					Console.Printf("DFCHK E %d %d %d", ea[cursor], eb[cursor], int(lastEdgeDz));
				}
			if (cursor >= ea.Size()) { cursor = 0; FindSamples(); phase = 6; }
			break;
		case 6: WalkTest(pawn); break;
		case 7: FallTest(pawn); break;
		case 8: SightTest(pawn); break;
		case 9: ShotTest(pawn); break;
		case 10: ChaseTest(pawn); break;
		case 11:
			Console.Printf("DFCHK DOORS closed_edges=%d blocked_while_closed=%d opened_by_use=%d stuck=%d", closedTotal, closedBlocked, doorsUsed, doorStuck);
			Console.Printf("DFCHK RESULT node_fail=%d edge_fail=%d", nodeFail, edgeFail);
			Console.Printf("DFCHK PLAYER walk_ok=%d walk_bad=%d fall_ok=%d fall_bad=%d", walkOk, walkBad, fallOk, fallBad);
			Console.Printf("DFCHK COMBAT slab_sight_blocked=%d slab_sight_leak=%d ledge_sight=%d ledge_blind=%d shot_hit=%d shot_miss=%d slab_shot_blocked=%d slab_shot_leak=%d chase_closer=%d chase_failed=%d",
				slabOk, slabBad, ledgeOk, ledgeBad, shotOk, shotBad, slabShotOk, slabShotBad, chaseOk, chaseBad);
			Console.Printf("DFCHK SOUND through_slab=%d blocked_by_slab=%d", soundBleed, soundBlocked);
			Console.Printf("DFCHK DONE");
			phase = 12;
			break;
		}
	}

	void FindSamples()
	{
		int step = max(1, ea.Size() / 4000);
		for (int i = 0; i < ea.Size() && (falls.Size() < SAMPLES || ledges.Size() < SAMPLES); i += step)
		{
			int drop = nf[ea[i]] - nf[eb[i]];
			if (drop > 40 && falls.Size() < SAMPLES) falls.Push(i);
			if (drop > 24 && nc[eb[i]] > nf[ea[i]] + 40 && ledges.Size() < SAMPLES) ledges.Push(i);
		}
		// Nodes in the same column on different levels have a solid slab between them.
		int stride = max(1, nx.Size() / 3000);
		for (int i = 0; i < nx.Size() && slabA.Size() < SAMPLES; i += stride)
			for (int j = i + 1; j < min(i + 8, nx.Size()); j++)
				if (nx[i] == nx[j] && ny[i] == ny[j] && (nf[j] >= nc[i] || nf[i] >= nc[j])) { slabA.Push(i); slabB.Push(j); break; }
		Console.Printf("DFCHK SAMPLES falls=%d ledges=%d slabs=%d", falls.Size(), ledges.Size(), slabA.Size());
	}

	void Place(Actor who, int node, double extra = 0)
	{
		who.SetOrigin((nx[node], ny[node], nf[node] + extra), false);
		who.vel = (0, 0, 0);
		who.FindFloorCeiling();
	}

	void Next(int newPhase) { phase = newPhase; test = 0; cursor = 0; }

	void WalkTest(PlayerPawn pawn)
	{
		if (test >= SAMPLES * 2) { Next(7); return; }
		int e = (ea.Size() - 1) * (test / 2) / SAMPLES;
		if (test % 2 == 0)
		{
			Place(pawn, ea[e]);
			vector2 d = (nx[eb[e]] - nx[ea[e]], ny[eb[e]] - ny[ea[e]]);
			pawn.vel.xy = d.Unit() * 8;
			chaseStart = pawn.Distance2D(probe);
			probe.SetOrigin((nx[ea[e]], ny[ea[e]], nf[ea[e]]), false);
			wait = 6;
		}
		else if (pawn.Distance2D(probe) >= 16) walkOk++;
		else { walkBad++; Console.Printf("DFCHK WALKFAIL edge %d->%d", ea[e], eb[e]); }
		test++;
	}

	void FallTest(PlayerPawn pawn)
	{
		if (test >= falls.Size() * 2) { Next(8); return; }
		int e = falls[test / 2], b = eb[e];
		if (test % 2 == 0)
		{
			Place(pawn, b, nf[ea[e]] - nf[b]);
			wait = 70;
		}
		else if (abs(pawn.pos.z - nf[b]) <= 2) fallOk++;
		else { fallBad++; Console.Printf("DFCHK FALLFAIL node %d z=%d expected=%d", b, int(pawn.pos.z), nf[b]); }
		test++;
	}

	void SightTest(PlayerPawn pawn)
	{
		if (!shooter) shooter = Actor.Spawn("DFShooter", pawn.pos);
		for (int i = 0; i < slabA.Size(); i++)
		{
			Place(pawn, slabA[i]);
			Place(shooter, slabB[i]);
			if (shooter.CheckSight(pawn, SF_IGNOREVISIBILITY)) { slabBad++; Console.Printf("DFCHK SLABSIGHT %d %d", slabA[i], slabB[i]); }
			else slabOk++;
			// Noise is tracked per sector, so check whether it passes through the slab.
			shooter.CurSector.SoundTarget = null;
			pawn.SoundAlert(pawn);
			if (shooter.CurSector.SoundTarget == pawn) soundBleed++;
			else soundBlocked++;
			shooter.CurSector.SoundTarget = null;
		}
		for (int i = 0; i < ledges.Size(); i++)
		{
			Place(pawn, eb[ledges[i]]);
			Place(shooter, ea[ledges[i]]);
			if (shooter.CheckSight(pawn, SF_IGNOREVISIBILITY)) ledgeOk++;
			else { ledgeBad++; Console.Printf("DFCHK LEDGEBLIND edge %d", ledges[i]); }
		}
		Next(9);
	}

	// Odd steps fire, even steps score. Ledge shots should hit, shots into a slab should not.
	void ShotTest(PlayerPawn pawn)
	{
		int total = ledges.Size() + slabA.Size();
		if (test >= total * 2) { pawn.bINVULNERABLE = true; pawn.health = pawn.player.health = 100; Next(10); return; }
		int index = test / 2;
		bool isLedge = index < ledges.Size();
		if (test % 2 == 0)
		{
			pawn.bINVULNERABLE = false;
			pawn.health = pawn.player.health = 100;
			Place(pawn, isLedge ? eb[ledges[index]] : slabA[index - ledges.Size()]);
			Place(shooter, isLedge ? ea[ledges[index]] : slabB[index - ledges.Size()], 8);
			shooter.target = pawn;
			shooter.SpawnMissile(pawn, "DoomImpBall");
			wait = 50;
		}
		else
		{
			bool hit = pawn.health < 100;
			if (isLedge) { if (hit) shotOk++; else shotBad++; }
			else { if (hit) slabShotBad++; else slabShotOk++; }
			pawn.health = pawn.player.health = 100;
		}
		test++;
	}

	void ChaseTest(PlayerPawn pawn)
	{
		if (test == 0) FindChasePairs();
		if (test >= chaseFrom.Size() * 2) { Next(11); return; }
		int index = test / 2;
		if (test % 2 == 0)
		{
			Place(pawn, chaseTo[index]);
			monster = Actor.Spawn("DFChaser", (nx[chaseFrom[index]], ny[chaseFrom[index]], nf[chaseFrom[index]]));
			if (monster)
			{
				monster.target = pawn;
				monster.SetState(monster.SeeState);
				chaseStart = monster.Distance3D(pawn);
			}
			wait = 175;
		}
		else
		{
			if (monster && monster.Distance3D(pawn) < chaseStart - 48) chaseOk++;
			else
			{
				chaseBad++;
				Console.Printf("DFCHK CHASEFAIL %d -> %d start=%d end=%d", chaseFrom[index], chaseTo[index], int(chaseStart), monster ? int(monster.Distance3D(pawn)) : -1);
			}
			if (monster) monster.Destroy();
		}
		test++;
	}

	// Walks the edge list to find routes about 12 steps long that change floor height.
	void FindChasePairs()
	{
		Array<int> first, next;
		first.Reserve(nx.Size());
		next.Reserve(ea.Size());
		for (int i = 0; i < nx.Size(); i++) first[i] = -1;
		for (int i = 0; i < ea.Size(); i++) { next[i] = first[ea[i]]; first[ea[i]] = i; }
		int stride = max(1, nx.Size() / 400);
		for (int i = 0; i < nx.Size() && chaseFrom.Size() < SAMPLES; i += stride)
		{
			int at = i, previous = -1;
			for (int hop = 0; hop < 12; hop++)
			{
				int choice = -1;
				for (int e = first[at]; e >= 0; e = next[e])
					if (eb[e] != previous && abs(nf[eb[e]] - nf[at]) <= 24) { choice = eb[e]; if (nf[choice] != nf[at]) break; }
				if (choice < 0) break;
				previous = at;
				at = choice;
			}
			if (abs(nf[at] - nf[i]) >= 32 && (nx[at] - nx[i]) ** 2 + (ny[at] - ny[i]) ** 2 > 128 * 128) { chaseFrom.Push(i); chaseTo.Push(at); }
		}
		Console.Printf("DFCHK CHASEPAIRS %d", chaseFrom.Size());
	}
}
