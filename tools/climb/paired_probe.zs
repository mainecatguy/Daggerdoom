// Paired climbing probe (test only). In a real bridge session on a generated Daggerfall map, once the climb is
// active (real rules and chances from Daggerfall), it puts the player against the nearest wall at least 40 units
// tall and holds forward for 8 seconds. It runs before DoomerfallClimb each tic, so the held forward is what the
// climb reads. Prints CLIMBPROBE lines.
class ClimbProbe : StaticEventHandler
{
	Vector2 SEARCH_FROM;
	int phase, t, startT;
	double z0, zMax;

	override void OnRegister() { SetOrder(-100); SEARCH_FROM = (3616.0, -13410.75); }

	override void WorldTick()
	{
		let mo = players[0].mo;
		let c = DoomerfallClimb(StaticEventHandler.Find("DoomerfallClimb"));
		if (!mo || !c || !c.Active() || phase >= 2) return;
		t++;
		if (phase == 0)
		{
			// Optional start point, so the search runs in town (the guards demo's start, in front of a store).
			if (t == 35 && SEARCH_FROM.x != 0)
			{
				mo.SetOrigin((SEARCH_FROM, mo.GetZAt(SEARCH_FROM.x, SEARCH_FROM.y, 0, GZF_ABSOLUTEPOS)), false);
				Console.Printf("CLIMBPROBE moved to %.0f,%.0f z=%.0f", mo.pos.x, mo.pos.y, mo.pos.z);
			}
			if (t < 105) return;
			double best = 1e9, bestAng = 0;
			Vector3 bestHit;
			for (int a = 0; a < 360; a += 3)
			{
				FLineTraceData d;
				if (mo.LineTrace(a, 768, 0, TRF_THRUACTORS, 40, data: d) && d.HitType == FLineTraceData.TRACE_HitWall && d.Distance > 24 && d.Distance < best)
				{
					best = d.Distance;
					bestAng = a;
					bestHit = d.HitLocation;
				}
			}
			if (best > 1e8) { Console.Printf("CLIMBPROBE no wall near %.0f,%.0f", mo.pos.x, mo.pos.y); phase = 2; return; }
			Vector2 dir = Actor.AngleToVector(bestAng);
			Vector2 at = bestHit.xy - dir * (mo.radius + 2);
			mo.SetOrigin((at, mo.GetZAt(at.x, at.y, 0, GZF_ABSOLUTEPOS)), false);
			mo.angle = bestAng;
			mo.vel = (0, 0, 0);
			z0 = zMax = mo.pos.z;
			Console.Printf("CLIMBPROBE placed at %.0f,%.0f z=%.0f facing %.0f, wall %.0f away", at.x, at.y, z0, bestAng, best);
			phase = 1;
			t = 0;
			startT = -1;
			return;
		}
		players[0].cmd.forwardmove = 6400;
		let s = c.st[0];
		if (startT < 0 && s && s.climbing) startT = t;
		zMax = max(zMax, mo.pos.z);
		if (t == 280)
		{
			Console.Printf("CLIMBPROBE start=%d rose=%.0f chances=%d/%d/%d/%d", startT, zMax - z0, c.chance[0], c.chance[1], c.chance[2], c.chance[3]);
			players[0].cmd.forwardmove = 0;
			phase = 2;
		}
	}
}
