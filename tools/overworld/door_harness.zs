version "4.14"

// Door test. For each listed door: stand in front of it, press Use, check the arrival, walk, come back,
// and check the player returned to that door. The first door also checks that world state survives.
class DTState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int leg, phase, timer, visits, killed;
	double startX, startY;
	String home;
}

class DTHarness : EventHandler
{
	// x, y, z, nx, ny of each town door.
	static const double DOORS[] = { @DOORS@ };
	// x, y, z, nx, ny of each dungeon exit. Empty for buildings, whose landing faces the door.
	static const double EXITS[] = { @EXITS@ };
	const FIELDS = 5;
	const LIMIT = 35 * 14;
	bool done;

	void Finish(String why) { Console.Printf("DTDONE %s", why); done = true; }

	static int CountNear(Class<Actor> cls, Vector3 at, double range)
	{
		int n = 0;
		let it = ThinkerIterator.Create(cls);
		Actor a;
		while (a = Actor(it.Next())) if (a.Distance2D(players[0].mo) >= 0 && (a.pos.xy - at.xy).Length() < range) n++;
		return n;
	}

	static int CountMonsters(bool alive)
	{
		int n = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor a;
		while (a = Actor(it.Next())) if (a.bISMONSTER && (a.health > 0) == alive) n++;
		return n;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = DTState(p.FindInventory("DTState"));
		if (!st) st = DTState(p.GiveInventoryType("DTState"));
		if (!st) return;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		int count = DOORS.Size() / FIELDS;
		if (st.leg >= count) { Finish(String.Format("legs=%d", count)); return; }
		int at = st.leg * FIELDS;
		Vector3 door = (DOORS[at], DOORS[at + 1], DOORS[at + 2]);
		Vector2 normal = (DOORS[at + 3], DOORS[at + 4]);
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		st.timer++;
		switch (st.phase)
		{
		case 0:	// In town: first visit sets up world state, then stand at the door and press Use.
			if (inside || level.maptime < 4) break;
			if (st.home.Length() == 0)
			{
				st.home = level.MapName;
				Actor.Spawn("Clip", (door.xy + normal * 90, door.z));
				let imp = Actor.Spawn("DoomImp", (door.xy + normal * 150, door.z));
				if (imp) imp.DamageMobj(null, null, 100000, 'None');
				Console.Printf("DTSETUP town clip and imp corpse placed");
			}
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (level.maptime < 8) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase = 1;
			st.timer = 0;
			break;
		case 1:	// Wait for the interior. A not-yet-converted one takes a few seconds.
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			if (inside) { st.phase = 2; st.timer = 0; break; }
			if (st.timer > LIMIT) { Console.Printf("DTFAIL leg=%d door did not open", st.leg); st.leg++; st.phase = 0; }
			break;
		case 2:	// Arrived. Report the landing, then walk forward to prove the player is not stuck.
			if (st.timer == 2)
			{
				st.startX = p.pos.x;
				st.startY = p.pos.y;
				Console.Printf("DTARRIVE leg=%d map=%s pos=%.1f,%.1f,%.1f floor=%.1f room=%.1f angle=%.1f monsters=%d corpses=%d", st.leg, level.MapName, p.pos.x, p.pos.y, p.pos.z, p.floorz, p.ceilingz - p.floorz, p.angle, CountMonsters(true), CountMonsters(false));
				if (st.leg == 0 && st.visits == 0)
				{
					Actor.Spawn("Shell", p.pos + (Actor.AngleToVector(p.angle, 24), 0));
					if (level.MapName ~== "MAP01")
					{
						let it = ThinkerIterator.Create("Actor");
						Actor a;
						while (a = Actor(it.Next())) if (a.bISMONSTER && a.health > 0) { a.DamageMobj(null, null, 100000, 'None'); st.killed = 1; break; }
					}
				}
				if (st.leg == 0 && st.visits == 1)
					Console.Printf("DTPERSIST inside shells=%d monsters=%d corpses=%d", CountNear("Shell", p.pos, 64), CountMonsters(true), CountMonsters(false));
			}
			if (st.timer > 2 && st.timer < 22) p.vel.xy = Actor.AngleToVector(p.angle, 6);
			if (st.timer == 24)
			{
				Console.Printf("DTWALK leg=%d moved=%.1f", st.leg, (p.pos.xy - (st.startX, st.startY)).Length());
				p.vel = (0, 0, 0);
				if (EXITS.Size() >= FIELDS)
				{
					p.SetOrigin((EXITS[0] + EXITS[3] * 40, EXITS[1] + EXITS[4] * 40, EXITS[2]), false);
					p.angle = atan2(-EXITS[4], -EXITS[3]);
				}
				else
				{
					p.SetOrigin((st.startX, st.startY, p.floorz), false);
					p.angle += 180;
				}
			}
			if (st.timer == 28) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (st.timer > 40 && !inside) { st.phase = 3; st.timer = 0; }
			if (st.timer > LIMIT) { Console.Printf("DTFAIL leg=%d exit did not work", st.leg); Finish("stuck"); }
			break;
		case 3:	// Back at the door the player used.
			if (st.timer != 3) break;
			double err = (p.pos.xy - (door.xy + normal * 31.5)).Length();
			Console.Printf("DTRETURN leg=%d map=%s error=%.2f z=%.1f floor=%.1f clips=%d corpses=%d", st.leg, level.MapName, err, p.pos.z, p.floorz, CountNear("Clip", (door.xy + normal * 90, door.z), 48), CountMonsters(false));
			if (st.leg == 0 && st.visits == 0) st.visits = 1;	// Go through the first door a second time.
			else st.leg++;
			st.phase = 0;
			st.timer = 0;
			break;
		}
	}
}
