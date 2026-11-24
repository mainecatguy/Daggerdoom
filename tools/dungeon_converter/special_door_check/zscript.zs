version "4.10"

// In-game check of secret door panels: non-door models with door actions (DaggerfallActionDoorSpecial). Load this folder after
// <slug>_doors.pk3, with the real game's 10.5 player width (overworld.pk3). Prints one SD row per panel, then SDDONE.
// The real player cannot cross a closed panel and can cross an open one. A body in the swing is neither carried nor trapped.
// Values: 1 pass, 0 fail, - no standing room on that side.

class DFSpecialDoorCheck : EventHandler
{
	const SWING = 70;
	Array<DFAction> specials, roots;
	int index, startTic, chainTic;
	vector3 parked;
	bool finished;
	String row;

	PlayerPawn Pawn() { return PlayerPawn(players[consoleplayer].mo); }
	vector3 Mid(DFAction a) { return ((a.boxMin.x + a.boxMax.x) / 2, (a.boxMin.y + a.boxMax.y) / 2, a.boxMin.z); }
	int SolidCells(DFAction a) { int n = 0; foreach (c : a.cells) if (c.bSOLID) n++; return n; }

	// The world direction across a closed panel's thin side.
	vector2 Across(DFAction a)
	{
		vector3 m = Mid(a), o = a.ToWorld(m, 0);
		bool thinX = a.boxMax.x - a.boxMin.x < a.boxMax.y - a.boxMin.y;
		vector3 t = a.ToWorld(m + (thinX ? 1 : 0, thinX ? 0 : 1, 0), 0);
		return (t.x - o.x, t.y - o.y);
	}

	bool Stand(PlayerPawn p, double x, double y, double z)
	{
		p.SetOrigin((x, y, z + 2), false);
		p.vel = (0, 0, 0);
		p.FindFloorCeiling();
		if (abs(p.floorz - z) > 24 || p.ceilingz - p.floorz < p.height) return false;
		p.SetZ(p.floorz);
		return p.TestMobjLocation();
	}

	// "1" crossed in some lane, "0" stopped in every lane, "-" the near side has no standing room.
	String WalkAcross(PlayerPawn p, DFAction a, double side, double reach)
	{
		vector3 c = a.ToWorld(Mid(a), 0);
		vector2 n = Across(a);
		String result = "-";
		for (int lane = -12; lane <= 12; lane += 3)
		{
			double ox = c.x - n.y * lane, oy = c.y + n.x * lane;
			if (!Stand(p, ox + n.x * side * reach, oy + n.y * side * reach, c.z)) continue;
			bool through = true;
			for (double d = reach - 3; d >= -reach && through; d -= 3)
			{
				through = p.TryMove((ox + n.x * side * d, oy + n.y * side * d), true);
				if (through) p.SetZ(p.floorz);
			}
			if (through) return "1";
			result = "0";
		}
		return result;
	}

	String CrossBoth(PlayerPawn p, DFAction a) { return WalkAcross(p, a, 1, 28) .. WalkAcross(p, a, -1, 28); }

	override void WorldTick()
	{
		if (finished) return;
		let p = Pawn();
		int t = level.maptime;
		if (t < 10) return;
		if (t == 10)
		{
			let it = ThinkerIterator.Create("DFAction");
			DFAction a;
			// Flat trapdoors have their own test in trapdoor_check.
			while (a = DFAction(it.Next())) if (a.IsSpecialDoor() && a.boxMax.z - a.boxMin.z > 16) specials.Push(a);
			Console.Printf("SDSTART specials=%d radius=%.1f", specials.Size(), p.radius);
			startTic = t + 1;
			if (specials.Size() == 0) { Console.Printf("SDDONE"); finished = true; }
			return;
		}
		if (chainTic > 0)
		{
			if (t >= chainTic) ReportChains();
			return;
		}
		if (t < startTic) return;
		let a = specials[index];
		int s = t - startTic;
		if (s == 0)
		{
			row = String.Format("SD record=%d panel at %.0f,%.0f,%.0f cells=%d closedSolid=%d crossClosed=%s", a.id, a.pivot.x, a.pivot.y, a.pivot.z, a.cells.Size(), SolidCells(a) == a.cells.Size(), CrossBoth(p, a));
			vector3 c = a.ToWorld(Mid(a), 0.5);
			p.SetOrigin(c, false); // a body in the swing path
			p.vel = (0, 0, 0);
			parked = p.pos;
			a.Perform(p);
			row = row .. String.Format(" started=%d", a.phase == DFAction.FORWARD);
		}
		else if (s < SWING)
		{
			p.SetOrigin((parked.x, parked.y, p.pos.z), false); // hold the body in place sideways; gravity still acts
			p.vel.xy = (0, 0);
		}
		else if (s == SWING)
		{
			row = row .. String.Format(" opened=%d carried=%.1f", a.phase == DFAction.AT_END && a.fraction >= 1, (p.pos.xy - parked.xy).Length());
			p.SetOrigin((a.pivot.x + 300, a.pivot.y + 300, a.pivot.z + 2000), false);
		}
		else if (s == SWING + 4)
		{
			row = row .. String.Format(" openSolid=%d crossOpen=%s", SolidCells(a) == a.cells.Size(), CrossBoth(p, a));
			p.SetOrigin((a.pivot.x + 300, a.pivot.y + 300, a.pivot.z + 2000), false);
			int was = a.flag;
			a.flag = 20;
			a.Perform(p);
			a.flag = was;
			row = row .. String.Format(" closing=%d", a.phase == DFAction.REVERSE);
		}
		else if (s == SWING + 62)
		{
			row = row .. String.Format(" closed=%d endSolid=%d", a.phase == DFAction.AT_START && a.fraction <= 0, SolidCells(a) == a.cells.Size());
			Console.Printf("%s", row);
			index++;
			startTic = t + 1;
			if (index >= specials.Size()) { FireChains(p); chainTic = t + 3; index = specials.Size() - 1; startTic = 1 << 30; }
		}
	}

	// Fires each panel's chain from its first record through that record's own trigger type.
	void FireChains(PlayerPawn p)
	{
		Array<DFAction> fired;
		foreach (a : specials)
		{
			DFAction root = a;
			for (int depth = 0; depth < 64; depth++)
			{
				DFAction before = null;
				let it = ThinkerIterator.Create("DFAction");
				DFAction o;
				while (o = DFAction(it.Next())) if (o.nextAction == root) { before = o; break; }
				if (!before) break;
				root = before;
			}
			roots.Push(root);
			if (root == a || fired.Find(root) != fired.Size()) continue;
			fired.Push(root);
			int source = root.trigger == DFAction.TR_WALKON ? DFAction.FROM_WALKON : root.trigger == DFAction.TR_WALKINTO ? DFAction.FROM_WALKINTO
				: root.trigger == DFAction.TR_ATTACK ? DFAction.FROM_ATTACK : root.trigger == DFAction.TR_DOOR ? DFAction.FROM_DOOR : DFAction.FROM_DIRECT;
			root.Receive(p, source);
		}
	}

	void ReportChains()
	{
		for (int i = 0; i < specials.Size(); i++)
			Console.Printf("SDCHAIN record=%d root=%d rootFlag=%d rootTrigger=%d fired=%d", specials[i].id, roots[i].id, roots[i].flag, roots[i].trigger, roots[i] != specials[i] && specials[i].phase != DFAction.AT_START);
		Console.Printf("SDDONE");
		finished = true;
	}
}
