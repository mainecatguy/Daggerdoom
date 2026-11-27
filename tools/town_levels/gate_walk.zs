version "4.14"

// Town levels test: on a walled town's map, stand just inside the gate nearest the start, wait, open the gate, walk
// out through it and on past the town map's exit line onto the overworld, then wait. Daggerfall's -dftownlevellog
// writes the area level at each step. Console lines start with TL.
class TLGateWalk : EventHandler
{
	const SPEED = 12.0;
	const START = @START@;	// tics before the walk starts, so Daggerfall's world level test runs in town first
	int phase, wait, tics;
	bool done;
	Vector2 outside, inside, mid, away;
	Array<DFDoor> leaves;

	static bool InTown() { return CVar.FindCVar("dd_tm_intown").GetInt() != 0; }

	void Drive(Actor p, Vector2 to)
	{
		Vector2 d = to - p.pos.xy;
		double len = d.Length();
		if (len < 1) { p.vel.xy = (0, 0); return; }
		p.vel.xy = d / len * min(SPEED, len);
		p.angle = atan2(d.y, d.x);
	}

	bool FindGate(Actor p)
	{
		Array<DFDoor> all;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while ((d = DFDoor(it.Next()))) all.Push(d);
		if (all.Size() < 2) return false;
		DFDoor best = all[0];
		for (int i = 1; i < all.Size(); i++)
			if ((all[i].pivotX - p.pos.x, all[i].pivotY - p.pos.y).Length() < (best.pivotX - p.pos.x, best.pivotY - p.pos.y).Length()) best = all[i];
		DFDoor mate = null;
		for (int i = 0; i < all.Size(); i++)
		{
			if (all[i] == best) continue;
			if (!mate || (all[i].pivotX - best.pivotX, all[i].pivotY - best.pivotY).Length() < (mate.pivotX - best.pivotX, mate.pivotY - best.pivotY).Length()) mate = all[i];
		}
		leaves.Push(best);
		leaves.Push(mate);
		mid = ((best.pivotX + mate.pivotX) / 2, (best.pivotY + mate.pivotY) / 2);
		Vector2 along = (mate.pivotX - best.pivotX, mate.pivotY - best.pivotY).Unit();
		Vector2 normal = (-along.y, along.x);
		if ((p.pos.xy - mid) dot normal < 0) normal = -normal;	// toward the player's side, which is inside the walls
		inside = mid + normal * 240;
		outside = mid - normal * 260;
		away = -normal;
		return true;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		switch (phase)
		{
		case 0:
			if (level.maptime < START || !InTown()) return;
			if (!FindGate(p)) { Console.Printf("TLDONE FAIL no gate on this map"); done = true; return; }
			p.SetOrigin((inside, p.GetZAt(inside.x, inside.y, 0, GZF_ABSOLUTEPOS)), false);
			p.vel = (0, 0, 0);
			Console.Printf("TLINSIDE gate %.0f,%.0f, standing at %.0f,%.0f", mid.x, mid.y, p.pos.x, p.pos.y);
			wait = level.maptime + 70;
			phase = 1;
			break;
		case 1:	// Stand inside the gate while Daggerfall logs the level.
			p.vel.xy = (0, 0);
			if (level.maptime < wait) return;
			for (int i = 0; i < leaves.Size(); i++) if (leaves[i].swung < 1) leaves[i].TryUse(p);
			wait = level.maptime + 60;
			phase = 2;
			break;
		case 2:	// Let the leaves swing open.
			p.vel.xy = (0, 0);
			if (level.maptime >= wait) { Console.Printf("TLGATEOPEN"); phase = 3; tics = 0; }
			break;
		case 3:	// Out through the gate.
			Drive(p, outside);
			if ((p.pos.xy - outside).Length() < 24) { Console.Printf("TLOUTSIDEGATE at %.0f,%.0f", p.pos.x, p.pos.y); phase = 4; tics = 0; }
			else if (++tics > 700) { Console.Printf("TLDONE FAIL could not pass the gate"); done = true; }
			break;
		case 4:	// Straight on until the town map hands off to the overworld.
			if (InTown())
			{
				p.vel.xy = away * SPEED;
				p.angle = atan2(away.y, away.x);
				if (++tics > 2000) { Console.Printf("TLDONE FAIL never left the town map"); done = true; }
			}
			else
			{
				Console.Printf("TLLEFT tic %d", level.maptime);
				wait = level.maptime + 105;
				phase = 5;
			}
			break;
		case 5:	// Stand just past the exit line while Daggerfall logs the level.
			p.vel.xy = (0, 0);
			if (level.maptime >= wait) { Console.Printf("TLWALKON"); wait = level.maptime + 200; phase = 6; }
			break;
		case 6:	// Walk on about eight tiles (past the town map's outer edge), then stand again.
			p.vel.xy = away * SPEED;
			p.angle = atan2(away.y, away.x);
			if (level.maptime >= wait) { wait = level.maptime + 105; phase = 7; }
			break;
		case 7:
			p.vel.xy = (0, 0);
			if (level.maptime >= wait) { Console.Printf("TLDONE walked out"); done = true; }
			break;
		}
	}
}
