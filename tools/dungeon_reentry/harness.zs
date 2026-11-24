version "4.14"

// Repeats one door: stand outside, press Use, stay inside, optionally get shot at, leave, and repeat.
class DRState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int cycle, phase, timer;
	double startX, startY;
}

class DRHarness : StaticEventHandler
{
	static const double DOORSPOT[] = { @DOOR@ };	// x, y, z, nx, ny
	static const double EXITSPOT[] = { @EXIT@ };	// x, y, z, nx, ny, or all zero when the landing faces the door
	const CYCLES = @CYCLES@;
	const FIREBALL = @FIREBALL@;
	const LIMIT = 35 * 10;
	bool done;

	void Finish(String why) { Console.Printf("DRDONE %s", why); done = true; }

	static int CountClass(Class<Actor> cls)
	{
		int n = 0;
		let it = ThinkerIterator.Create(cls);
		while (it.Next()) n++;
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
		let st = DRState(p.FindInventory("DRState"));
		if (!st) st = DRState(p.GiveInventoryType("DRState"));
		if (!st) return;
		p.bNOTARGET = !FIREBALL;
		players[0].cheats |= CF_GODMODE;
		if (st.cycle >= CYCLES) { Finish(String.Format("cycles=%d", CYCLES)); return; }
		Vector3 door = (DOORSPOT[0], DOORSPOT[1], DOORSPOT[2]);
		Vector2 normal = (DOORSPOT[3], DOORSPOT[4]);
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		st.timer++;
		if (level.maptime % 35 == 1) Console.Printf("DRTICK map=%s maptime=%d phase=%d cycle=%d timer=%d", level.MapName, level.maptime, st.phase, st.cycle, st.timer);
		switch (st.phase)
		{
		case 0:	// Outside: stand at the door, then press Use.
			if (inside || level.maptime < 4) break;
			int bridged = @BRIDGE@;	// A local, because a constant false here stopped the whole handler from running.
			if (bridged != 0 && (CVar.FindCVar("dd_sync_df_phase").GetInt() != 3 || CVar.FindCVar("dd_ui_test_hold").GetInt())) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (level.maptime < 8) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase = 1;
			st.timer = 0;
			break;
		case 1:	// Wait for the far side.
			if (inside) { st.phase = 2; st.timer = 0; break; }
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			if (st.timer > LIMIT) { Console.Printf("DRFAIL cycle=%d door did not open", st.cycle); Finish("stuck"); }
			break;
		case 2:	// Inside: report, optionally take live fire, then use the exit.
			if (st.timer == 2)
			{
				st.startX = p.pos.x;
				st.startY = p.pos.y;
				Console.Printf("DRARRIVE cycle=%d map=%s pos=%.1f,%.1f,%.1f floor=%.1f room=%.1f monsters=%d corpses=%d", st.cycle, level.MapName, p.pos.x, p.pos.y, p.pos.z, p.floorz, p.ceilingz - p.floorz, CountMonsters(true), CountMonsters(false));
				if (FIREBALL)
				{
					Console.Printf("DRCARRIED cycle=%d projectiles=%d", st.cycle, CountClass("DoomImpBall"));	// A still ball was left here on the last trip.
					Vector3 at = p.pos + (Actor.AngleToVector(p.angle, 96), 8);
					let imp = Actor.Spawn("DoomImp", at);
					if (imp) { imp.target = p; imp.angle = imp.AngleTo(p); }
					let ball = Actor.Spawn("DoomImpBall", at + (0, 0, 24));
					if (ball)
					{
						ball.target = imp;
						ball.angle = ball.AngleTo(p);
						ball.Vel3DFromAngle(ball.speed, ball.angle, 0);
					}
				}
			}
			if (st.timer == 12 && FIREBALL) Console.Printf("DRFIRE cycle=%d projectiles=%d", st.cycle, CountClass("DoomImpBall"));
			if (st.timer == 24)
			{
				p.vel = (0, 0, 0);
				if (EXITSPOT[3] != 0 || EXITSPOT[4] != 0)
				{
					p.SetOrigin((EXITSPOT[0] + EXITSPOT[3] * 40, EXITSPOT[1] + EXITSPOT[4] * 40, EXITSPOT[2]), false);
					p.angle = atan2(-EXITSPOT[4], -EXITSPOT[3]);
				}
				else
				{
					p.SetOrigin((st.startX, st.startY, p.floorz), false);
					p.angle += 180;
				}
			}
			if (st.timer == 27 && FIREBALL)
			{
				let still = Actor.Spawn("DoomImpBall", (st.startX, st.startY, p.floorz + 40));
				if (still) still.vel = (0, 0, 0);
			}
			if (st.timer == 28) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { st.phase = 3; st.timer = 0; break; }
			if (st.timer > LIMIT) { Console.Printf("DRFAIL cycle=%d exit did not work", st.cycle); Finish("stuck"); }
			break;
		case 3:	// Back outside.
			if (st.timer != 3) break;
			Console.Printf("DRRETURN cycle=%d map=%s error=%.2f", st.cycle, level.MapName, (p.pos.xy - (door.xy + normal * 31.5)).Length());
			st.cycle++;
			st.phase = 0;
			st.timer = 0;
			break;
		}
	}
}
