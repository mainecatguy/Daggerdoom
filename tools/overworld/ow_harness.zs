version "4.14"

// Overworld test harness. Prints OWDONE when finished so the runner can close the game.
class OWHarness : EventHandler
{
	const TILE = 192.0;
	const SPEED = 60.0;
	const LEG_LENGTH = 15000.0;
	const AWAY = 40000.0;

	int phase, waitUntil, leg, stuck, jumps, under, stuckLegs;
	int posX, negX, posY, negY, lastOX, lastOY;
	bool hasLast, done, savedOnce;
	double lastX, lastY, legX, legY, homeX, homeY, maxStep;

	Array<double> killX, killY, hurtX, hurtY, hurtHP, calmX, calmY, itemX, itemY, itemAmt, goneX, goneY;
	Actor edgeItem;
	Array<Actor> itemRef;
	double itemDrift;
	Array<int> itemSeen;
	Array<String> killC, hurtC, calmC, itemC, goneC;

	clearscope static int OX() { return CVar.FindCVar("dd_tm_originx").GetInt(); }
	clearscope static int OY() { return CVar.FindCVar("dd_tm_originy").GetInt(); }
	clearscope static double GX(Actor a) { return a.pos.x + OX() * TILE; }
	clearscope static double GY(Actor a) { return a.pos.y + OY() * TILE; }

	void Finish(String text)
	{
		Console.Printf("OWRESULT %s", text);
		Console.Printf("OWDONE");
		done = true;
	}

	void Track(Actor p)
	{
		int ox = OX(), oy = OY();
		if (hasLast)
		{
			if (ox > lastOX) posX++;
			if (ox < lastOX) negX++;
			if (oy > lastOY) posY++;
			if (oy < lastOY) negY++;
			double step = (GX(p) - lastX, GY(p) - lastY).Length();
			maxStep = max(maxStep, step);
			if (step > SPEED * 1.6) jumps++;
			stuck = step < 4 ? stuck + 1 : 0;
		}
		if (p.pos.z < p.floorz - 0.1) under++;
		lastOX = ox;
		lastOY = oy;
		lastX = GX(p);
		lastY = GY(p);
		hasLast = true;
	}

	void Drive(Actor p, Vector2 dir)
	{
		p.vel.x = dir.x * SPEED;
		p.vel.y = dir.y * SPEED;
	}

	// ---- All-direction route ----
	void Compass(Actor p)
	{
		static const double DX[] = { 1, -1, 0, 0, 0.7071, -0.7071, -0.7071, 0.7071 };
		static const double DY[] = { 0, 0, 1, -1, 0.7071, -0.7071, 0.7071, -0.7071 };
		if (phase == 0)
		{
			legX = GX(p);
			legY = GY(p);
			phase = 1;
		}
		Drive(p, (DX[leg], DY[leg]));
		bool blocked = stuck > 35;
		if ((GX(p) - legX, GY(p) - legY).Length() >= LEG_LENGTH || blocked)
		{
			if (blocked) stuckLegs++;
			Console.Printf("OWLEG %d end=%.0f,%.0f shifts=%d blocked=%d", leg, GX(p), GY(p), CVar.FindCVar("dd_tm_shifts").GetInt(), blocked);
			stuck = 0;
			leg++;
			legX = GX(p);
			legY = GY(p);
			if (leg >= 8)
				Finish(String.Format("compass legs=8 blockedLegs=%d shifts=%d +x=%d -x=%d +y=%d -y=%d jumps=%d under=%d maxStep=%.1f",
					stuckLegs, CVar.FindCVar("dd_tm_shifts").GetInt(), posX, negX, posY, negY, jumps, under, maxStep));
		}
	}

	// ---- Kill, leave, return ----
	Actor FindAt(String cls, double x, double y, double tolerance)
	{
		Class<Actor> type = cls;
		let it = ThinkerIterator.Create(type);
		Actor a;
		while (a = Actor(it.Next()))
		{
			if (Inventory(a) && Inventory(a).Owner) continue;
			if ((GX(a) - x, GY(a) - y).Length() <= tolerance) return a;
		}
		return null;
	}

	void Prepare(Actor p)
	{
		Array<Actor> pack;
		Actor nearest;
		double best = 1e12;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next()))
			if (a.bIsMonster && a.health > 0 && p.Distance2D(a) < best) { best = p.Distance2D(a); nearest = a; }
		if (!nearest) { Finish("persist FAIL no monsters"); return; }
		it = ThinkerIterator.Create("Actor");
		while (a = Actor(it.Next()))
			if (a.bIsMonster && a.health > 0 && a.Distance2D(nearest) < 700) pack.Push(a);
		if (pack.Size() < 10) { Finish("persist FAIL small pack"); return; }
		for (int i = 0; i < pack.Size(); i++)
		{
			a = pack[i];
			if (i < max(5, pack.Size() / 2))
			{
				killX.Push(GX(a)); killY.Push(GY(a)); killC.Push(a.GetClassName());
				a.DamageMobj(null, null, 100000, 'None');
			}
			else if (i < max(5, pack.Size() / 2) + 3)
			{
				a.health -= 3 + (i % 7);
				hurtX.Push(GX(a)); hurtY.Push(GY(a)); hurtHP.Push(a.health); hurtC.Push(a.GetClassName());
			}
			else
			{
				calmX.Push(GX(a)); calmY.Push(GY(a)); calmC.Push(a.GetClassName());
			}
		}
		homeX = GX(p);
		homeY = GY(p);
		// A drop just inside the window edge: the case where a shift must not lose it.
		double ex = 12288 - 20, ey = p.pos.y;
		edgeItem = Actor.Spawn("Clip", (ex, ey, p.GetZAt(ex, ey, 0, GZF_ABSOLUTEPOS)));
		if (edgeItem) edgeItem.bDropped = true;
	}

	void RecordItems(Actor p)
	{
		Array<Inventory> items;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next()))
			if (!inv.Owner) items.Push(inv);
		int pick = -1;
		for (int i = 0; i < items.Size() && pick < 0; i++)
			if (items[i] != edgeItem) pick = i;
		for (int i = 0; i < items.Size(); i++)
		{
			inv = items[i];
			if (i == pick)
			{
				goneX.Push(GX(inv)); goneY.Push(GY(inv)); goneC.Push(inv.GetClassName());
				inv.SetOrigin(p.pos, false);
				inv.CallTryPickup(p);
			}
			else
			{
				itemX.Push(GX(inv)); itemY.Push(GY(inv)); itemC.Push(inv.GetClassName()); itemAmt.Push(inv.Amount); itemRef.Push(inv); itemSeen.Push(0);
			}
		}
	}

	void Check()
	{
		int deadOK = 0, hurtOK = 0, calmOK = 0, itemOK = 0, goneOK = 0;
		for (int i = 0; i < killX.Size(); i++)
		{
			let a = FindAt(killC[i], killX[i], killY[i], 1.0);
			if (a && a.health <= 0 && a.bCorpse && !a.bShootable) deadOK++;
			else Console.Printf("OWBAD kill %d %s found=%d", i, killC[i], a != null);
		}
		for (int i = 0; i < hurtX.Size(); i++)
		{
			let a = FindAt(hurtC[i], hurtX[i], hurtY[i], 1.0);
			if (a && a.health == int(hurtHP[i])) hurtOK++;
			else Console.Printf("OWBAD hurt %d %s found=%d hp=%d want=%d", i, hurtC[i], a != null, a ? a.health : 0, int(hurtHP[i]));
		}
		for (int i = 0; i < calmX.Size(); i++)
		{
			let a = FindAt(calmC[i], calmX[i], calmY[i], 1.0);
			if (a && a.health > 0) calmOK++;
			else Console.Printf("OWBAD calm %d %s found=%d", i, calmC[i], a != null);
		}
		for (int i = 0; i < itemX.Size(); i++)
		{
			let a = Inventory(FindAt(itemC[i], itemX[i], itemY[i], 1.0));
			if (a && a.Amount == int(itemAmt[i])) itemOK++;
			else
			{
				double near = 1e9;
				int same = 0;
				Class<Actor> type = itemC[i];
				let iter = ThinkerIterator.Create(type);
				Actor o;
				while (o = Actor(iter.Next()))
				{
					if (Inventory(o) && Inventory(o).Owner) continue;
					same++;
					near = min(near, (GX(o) - itemX[i], GY(o) - itemY[i]).Length());
				}
				Console.Printf("OWBAD item %d %s found=%d wanted=%.2f,%.2f amount=%d groundCount=%d nearest=%.3f", i, itemC[i], a != null, itemX[i], itemY[i], int(itemAmt[i]), same, near);
			}
		}
		for (int i = 0; i < goneX.Size(); i++)
			if (!FindAt(goneC[i], goneX[i], goneY[i], 1.0)) goneOK++;
			else Console.Printf("OWBAD picked-up item %s came back", goneC[i]);
		bool ok = deadOK == killX.Size() && hurtOK == hurtX.Size() && calmOK == calmX.Size() && itemOK == itemX.Size() && goneOK == goneX.Size();
		Finish(String.Format("persist %s corpses=%d/%d hurt=%d/%d untouched=%d/%d drops=%d/%d pickedGone=%d/%d records=%d shifts=%d itemDriftPerTic=%.2f",
			ok ? "PASS" : "FAIL", deadOK, killX.Size(), hurtOK, hurtX.Size(), calmOK, calmX.Size(), itemOK, itemX.Size(), goneOK, goneX.Size(),
			CVar.FindCVar("dd_tm_records").GetInt(), CVar.FindCVar("dd_tm_shifts").GetInt(), itemDrift));
	}

	void Persist(Actor p, bool withSave)
	{
		p.player.cheats |= CF_NOTARGET;
		if (phase >= 2) p.bPickup = false;	// Travel must not collect the drops under test.
		// Drops can still slide on slopes, so the expected spot is where each was last seen before it was stored.
		if (phase < 3)
			for (int i = 0; i < itemRef.Size(); i++)
				if (!itemRef[i])
				{
					// A drop that disappears while its spot is still inside the window was not parked.
					double lx = itemX[i] - OX() * TILE, ly = itemY[i] - OY() * TILE;
					if (itemSeen[i] == 0 && abs(lx) < 12288 && abs(ly) < 12288)
						Console.Printf("OWVANISH item %d %s tic=%d local=%.1f,%.1f", i, itemC[i], level.maptime, lx, ly);
					itemSeen[i] = 1;
				}
				else
				{
					itemDrift = max(itemDrift, (GX(itemRef[i]) - itemX[i], GY(itemRef[i]) - itemY[i]).Length());
					itemX[i] = GX(itemRef[i]);
					itemY[i] = GY(itemRef[i]);
				}
		switch (phase)
		{
		case 0:
			if (level.maptime < 10) return;
			Prepare(p);
			if (done) return;
			waitUntil = level.maptime + 90;
			phase = 1;
			return;
		case 1:
			if (level.maptime < waitUntil) return;
			RecordItems(p);
			Console.Printf("OWSETUP killed=%d hurt=%d untouched=%d drops=%d pickedUp=%d", killX.Size(), hurtX.Size(), calmX.Size(), itemX.Size(), goneX.Size());
			phase = 2;
			return;
		case 2:
			Drive(p, (1, 0));
			if (GX(p) - homeX < AWAY) return;
			{
				int stillLive = 0;
				for (int i = 0; i < killX.Size(); i++)
					if (FindAt(killC[i], killX[i], killY[i], 1.0)) stillLive++;
				Console.Printf("OWAWAY dist=%.0f victimsStillLoaded=%d records=%d", GX(p) - homeX, stillLive, CVar.FindCVar("dd_tm_records").GetInt());
			}
			p.vel = (0, 0, 0);
			phase = 3;
			if (withSave)
			{
				waitUntil = level.maptime + 3;
				phase = 5;
			}
			return;
		case 5:
			if (level.maptime < waitUntil) return;
			phase = 6;
			Level.MakeAutoSave();
			waitUntil = level.maptime + 2;
			return;
		case 6:
			if (level.maptime < waitUntil) return;
			phase = 3;
			if (!savedOnce)
			{
				savedOnce = true;
				Console.Printf("OWSAVED");
			}
			return;
		case 3:
		{
			Vector2 to = (homeX - GX(p), homeY - GY(p));
			if (to.Length() < 90)
			{
				p.vel = (0, 0, 0);
				waitUntil = level.maptime + 120;
				phase = 4;
				return;
			}
			Drive(p, to.Unit());
			return;
		}
		case 4:
			if (level.maptime >= waitUntil) Check();
			return;
		}
	}

	// ---- Large-pack stress ----
	void Pack(Actor p)
	{
		if (phase == 0)
		{
			homeX = GX(p);
			phase = 1;
			int count = 0;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next())) if (a.bIsMonster) { count++; a.target = p; a.SetState(a.SeeState); }
			Console.Printf("OWPACK monsters=%d", count);
		}
		Drive(p, (1, 0));
		if (GX(p) - homeX >= 6144 * 6)
		{
			int count = 0;
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			while (a = Actor(it.Next())) if (a.bIsMonster && a.health > 0) count++;
			Finish(String.Format("pack liveMonsters=%d shifts=%d jumps=%d under=%d records=%d", count, CVar.FindCVar("dd_tm_shifts").GetInt(), jumps, under, CVar.FindCVar("dd_tm_records").GetInt()));
		}
	}

	// Prints floor heights at tile vertices for comparison with the Python sampler.
	void Heights(Actor p)
	{
		for (int j = 0; j <= 128; j += 16)
			for (int i = 0; i <= 128; i += 16)
			{
				double x = clamp(i * TILE - 12288, -12287, 12287), y = clamp(j * TILE - 12288, -12287, 12287);
				if (i == 128 || j == 128 || i == 0 || j == 0) continue;
				Console.Printf("OWZ %d %d %.3f", OX() + i, OY() + j, p.GetZAt(x, y, 0, GZF_ABSOLUTEPOS));
			}
		Finish("heights");
	}

	override void WorldTick()
	{
		let p = players[0].mo;
		if (done || !p || level.MapName != "DDOVER01" || level.maptime < 2) return;
		p.player.cheats |= CF_GODMODE;
		Track(p);
		String mode = "@MODE@";
		if (mode == "compass") Compass(p);
		else if (mode == "persist") Persist(p, false);
		else if (mode == "persistsave") Persist(p, true);
		else if (mode == "pack") Pack(p);
		else if (mode == "heights") Heights(p);
	}
}
