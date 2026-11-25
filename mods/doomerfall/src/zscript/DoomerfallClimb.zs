// Climbing on generated Daggerfall maps, with Daggerfall's Climbing skill rolls (Daggerfall's ClimbingMotor.cs).
// In:  "dfi_rules:<0|1>" (dd_items.cpp: 1 on a generated Daggerfall map in a bridge session),
//      "dfi_climb:<start>:<grasp>:<continue>:<regain>:<enhanced>" (dd_climb.cpp: Daggerfall's percent chances),
//      the player's input, position, and the wall in front.
// Out: the player's velocity while climbing, the "Climbing" message and overlay, a 70-degree walkable slope limit
//      on Daggerfall maps, and "dfc_uses:<n>" events (skill rolls made) that dd_climb.cpp sends to Daggerfall.
// WorldTick runs after the player's input thrust (P_PlayerThink) and before movement, so velocity set here is final.
// Nothing here runs unless the engine sends dfi_rules:1 and valid chances.
class DoomerfallClimbState
{
	int pushTics;      // tics pushing forward into a climbable surface while not climbing
	bool climbing;
	bool slipping;
	int rollTics;      // tics until the next continue or regain roll
	double speed;      // climb speed in units per tic, fixed when the climb starts, as in Daggerfall
	Vector2 normal;    // horizontal normal of the surface, pointing out toward the player
	bool savedNoGravity;
	Vector3 lastPos;
	int uses;          // skill rolls not yet reported
}

class DoomerfallClimb : StaticEventHandler
{
	const StartTics = 35;      // owner: pushing for more than one second
	const ContinueTics = 30;   // Daggerfall: 15 timer units, about 0.86 s
	const RegainTics = 11;     // Daggerfall: 5 timer units, about 0.30 s
	const SteepNormalZ = 0.34202; // cos 70: steeper planes are climbed, shallower ones walked (Daggerfall's slope limit)
	const Facing = 0.5;        // the view must face the surface within 60 degrees to start
	const Touch = 12.0;        // how far beyond the player's radius a surface still counts as touching
	const StillMove = 2.0;     // moving less than this per tic while pushing counts as blocked
	const Hug = 1.0;           // velocity into the wall while climbing, which keeps contact
	const UsesEvery = 35;

	bool rules;
	bool haveChances;
	int chance[4];             // DFB_CLIMB_START, _GRASP, _CONTINUE, _REGAIN
	bool enhanced;
	DoomerfallClimbState st[MAXPLAYERS];

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) == "dfi_rules:")
		{
			rules = e.Name.Mid(10) == "1";
			if (!rules) EndAll();
		}
		else if (e.Name.Left(10) == "dfi_climb:")
		{
			Array<String> f;
			e.Name.Split(f, ":");
			haveChances = f.Size() >= 6;
			if (haveChances)
			{
				for (int i = 0; i < 4; i++) chance[i] = f[i + 1].ToInt();
				enhanced = f[5].ToInt() != 0;
			}
			else EndAll();
		}
	}

	override void WorldLoaded(WorldEvent e)
	{
		// The climb is not saved. A save made mid-climb loads with the player's gravity switched back on.
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || !players[i].mo) continue;
			let mo = players[i].mo;
			if (e.IsSaveGame && mo.bNoGravity && !mo.default.bNoGravity && !mo.bFly) mo.bNoGravity = false;
			st[i] = null;
		}
	}

	void EndAll()
	{
		for (int i = 0; i < MAXPLAYERS; i++)
			if (st[i] && playeringame[i] && players[i].mo) EndClimb(players[i].mo, st[i]);
	}

	clearscope bool Active() const { return rules && haveChances; }

	override void WorldTick()
	{
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i]) continue;
			let mo = players[i].mo;
			if (!mo) continue;
			// Daggerfall's walkable limit is 70 degrees. Doom keeps its own 24-unit step height.
			double steep = Active() ? SteepNormalZ : mo.default.MaxSlopeSteepness;
			if (mo.MaxSlopeSteepness != steep) mo.MaxSlopeSteepness = steep;
			if (!Active()) continue;
			if (!st[i]) { st[i] = new("DoomerfallClimbState"); st[i].lastPos = mo.pos; }
			Think(players[i], mo, st[i]);
			st[i].lastPos = mo.pos;
		}
	}

	// Daggerfall's Dice100: success if a 0-99 roll is below the chance. Every roll, pass or fail, is one skill use.
	bool Roll(PlayerPawn mo, DoomerfallClimbState s, int which)
	{
		s.uses++;
		if (Random[DoomerfallClimb](0, 99) < chance[which]) return true;
		return mo.waterlevel > 0; // Daggerfall: a failed roll counts as a success in water.
	}

	// The climbable surface in direction ang, touching the player, between Doom's step height and the player's head.
	// Walls, 3D floor sides, and planes of 70 degrees or steeper count. Actors (doors, monsters) and ceilings do not.
	Vector2 found;    // the surface normal FindSurface found (an out Vector2 parameter breaks the JIT)

	bool FindSurface(PlayerPawn mo, double ang, double offz)
	{
		FLineTraceData t;
		Vector2 n = (0, 0);
		found = n;
		double reach = mo.radius + Touch;
		if (!mo.LineTrace(ang, reach * 2, 0, TRF_THRUACTORS, offz, data: t)) return false;
		if (t.HitType == FLineTraceData.TRACE_HitWall && t.HitLine)
		{
			Vector2 d = t.HitLine.delta;
			if (d.Length() < 0.001) return false;
			n = (d.y, -d.x).Unit();
			Vector2 toPlayer = mo.pos.xy - t.HitLocation.xy;
			if (n dot toPlayer < 0) n = -n;
			Sector far = t.LineSide == Line.front ? t.HitLine.backsector : t.HitLine.frontsector;
			if (far && (far.PlaneMoving(Sector.floor) || far.PlaneMoving(Sector.ceiling))) return false; // Daggerfall: not moving objects
		}
		else if (t.HitType == FLineTraceData.TRACE_HitFloor && t.HitSector && !t.Hit3DFloor)
		{
			Vector3 pn = t.HitSector.floorplane.Normal;
			if (pn.z > SteepNormalZ || pn.xy.Length() < 0.001) return false;
			n = pn.xy.Unit();
		}
		else return false;
		// Touching: the player's center is within radius plus a little of the surface, measured along its normal.
		Vector2 dir = (cos(ang), sin(ang));
		found = n;
		return t.Distance * max(0.05, -(dir dot n)) <= reach;
	}

	// Doom's top ground speed for this run state, in units per tic: thrust / (1 - friction) on normal ground.
	double GroundSpeed(PlayerPawn mo, bool running)
	{
		double fm, sm;
		[fm, sm] = mo.TweakSpeeds(gameinfo.normforwardmove[running ? 1 : 0] * 256, 0);
		return fm * mo.Speed / 256 * Actor.ORIG_FRICTION_FACTOR / (1 - Actor.ORIG_FRICTION);
	}

	void Start(PlayerInfo p, PlayerPawn mo, DoomerfallClimbState s, Vector2 n)
	{
		s.climbing = true;
		s.slipping = false;
		s.rollTics = ContinueTics;
		s.normal = n;
		// Daggerfall climbs at a third of the move speed the climb began with, doubled by a Climbing effect.
		s.speed = GroundSpeed(mo, abs(p.cmd.forwardmove) >= 0x3200) / 3 * (enhanced ? 2 : 1);
		s.savedNoGravity = mo.bNoGravity;
		mo.bNoGravity = true;
		mo.vel = (0, 0, 0);
		if (p == players[consoleplayer]) Console.PrintfEx(PRINT_HIGH, "Climbing");
		DDLog.Debug(String.Format("DFCLIMB start speed=%.3f z=%.1f chances=%d/%d/%d/%d", s.speed, mo.pos.z, chance[0], chance[1], chance[2], chance[3]));
	}

	void EndClimb(PlayerPawn mo, DoomerfallClimbState s)
	{
		if (s.climbing && !s.slipping) mo.bNoGravity = s.savedNoGravity;
		if (s.climbing) DDLog.Debug(String.Format("DFCLIMB stop z=%.1f", mo.pos.z));
		s.climbing = false;
		s.slipping = false;
		s.pushTics = 0;
	}

	void Slip(PlayerPawn mo, DoomerfallClimbState s)
	{
		s.slipping = true;
		s.rollTics = RegainTics;
		mo.bNoGravity = s.savedNoGravity;
		DDLog.Debug(String.Format("DFCLIMB slip z=%.1f", mo.pos.z));
	}

	void Think(PlayerInfo p, PlayerPawn mo, DoomerfallClimbState s)
	{
		if (s.uses > 0 && level.maptime % UsesEvery == 0)
		{
			EventHandler.SendNetworkEvent(String.Format("dfc_uses:%d", s.uses));
			s.uses = 0;
		}
		if (p.health <= 0 || p.playerstate != PST_LIVE || (p.cheats & CF_NOCLIP2) || mo.bFly)
		{
			EndClimb(mo, s);
			return;
		}
		if (!s.climbing) { TryStart(p, mo, s); return; }

		UserCmd cmd = p.cmd;
		if ((cmd.buttons & BT_JUMP) && !(p.oldbuttons & BT_JUMP))
		{
			EndClimb(mo, s); // Jumping lets go.
			mo.vel.xy = s.normal * 2;
			return;
		}

		double wallAng = atan2(-s.normal.y, -s.normal.x);
		if (!FindSurface(mo, wallAng, mo.MaxStepHeight - 4))
		{
			TopOrLetGo(mo, s);
			return;
		}
		Vector2 n = found;
		s.normal = n;

		if (s.slipping)
		{
			if (mo.pos.z <= mo.floorz) { EndClimb(mo, s); return; }
			mo.vel.xy = -n * Hug;
			if (--s.rollTics <= 0)
			{
				if (Roll(mo, s, 3))
				{
					s.slipping = false;
					s.rollTics = ContinueTics;
					mo.bNoGravity = true;
					mo.vel.z = 0; // Daggerfall: regaining a hold clears the fall.
					DDLog.Debug(String.Format("DFCLIMB regain z=%.1f", mo.pos.z));
				}
				else s.rollTics = RegainTics;
			}
			return;
		}

		// Forward climbs and back descends. Strafing moves along the wall in the direction the view's strafe points.
		int up = cmd.forwardmove > 0 ? 1 : cmd.forwardmove < 0 ? -1 : 0;
		Vector2 tangent = (-n.y, n.x);
		Vector2 right = (cos(mo.angle - 90), sin(mo.angle - 90));
		double along = right dot tangent;
		int side = cmd.sidemove > 0 ? 1 : cmd.sidemove < 0 ? -1 : 0;
		if (abs(along) < 0.1) side = 0;
		else if (along < 0) side = -side;
		if (up < 0 && mo.pos.z <= mo.floorz) { EndClimb(mo, s); return; } // Climbed back down to the ground.
		mo.vel = (tangent * side * s.speed - n * Hug, up * s.speed);
		// Daggerfall rolls to keep climbing while the player climbs. Holding still on the wall does not roll (as in
		// Daggerfall's advanced climbing), so the player can stay put and fight.
		if ((up != 0 || side != 0) && --s.rollTics <= 0)
		{
			s.rollTics = ContinueTics;
			if (!Roll(mo, s, 2)) Slip(mo, s);
		}
	}

	void TryStart(PlayerInfo p, PlayerPawn mo, DoomerfallClimbState s)
	{
		// Pushing: forward into a touching surface the view faces, with little sideways drift along it (Daggerfall's
		// 0.12 m rule). Movement toward and away from the surface does not count, because Doom bounces the player
		// off steep slopes.
		bool pushing = p.cmd.forwardmove > 0 && FindSurface(mo, mo.angle, mo.MaxStepHeight + 4) &&
			(Actor.AngleToVector(mo.angle) dot -found) >= Facing;
		Vector2 n = found;
		if (pushing) pushing = abs((mo.pos.xy - s.lastPos.xy) dot (-n.y, n.x)) < StillMove;
		if (!pushing) { s.pushTics = 0; return; }
		if (++s.pushTics <= StartTics) return;
		bool ground = mo.pos.z <= mo.floorz || mo.bOnMobj;
		if (Roll(mo, s, ground ? 0 : 1)) Start(p, mo, s, n);
		else if (!ground) s.pushTics = 0; // Daggerfall: a failed airborne grab restarts the wait; on the ground it rerolls.
	}

	// The surface ended. Near the top, carry the player over onto the ledge, as Daggerfall's forward push does.
	void TopOrLetGo(PlayerPawn mo, DoomerfallClimbState s)
	{
		Vector2 n = s.normal;
		Vector2 ahead = mo.pos.xy - n * (mo.radius + 8);
		double top = mo.GetZAt(ahead.x, ahead.y, 0, GZF_ABSOLUTEPOS);
		bool atTop = top > mo.pos.z - 1 && top <= mo.pos.z + mo.MaxStepHeight;
		EndClimb(mo, s);
		if (atTop)
		{
			mo.vel = (-n * 4, sqrt(2 * (max(0.0, top - mo.pos.z) + 4) * mo.GetGravity())); // just clears the ledge
			DDLog.Debug(String.Format("DFCLIMB top z=%.1f ledge=%.1f", mo.pos.z, top));
		}
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (!Active() || automapactive || consoleplayer < 0) return;
		let p = players[consoleplayer];
		let s = st[consoleplayer];
		if (!s || !s.climbing || p.mo == null || p.camera != p.mo) return;
		String text = s.slipping ? "Slipping" : "Climbing";
		int scale = DoomerfallText.Scale();
		int w = SmallFont.StringWidth(text) * scale;
		int h = SmallFont.GetHeight() * scale;
		int bottom = min(StatusBar.GetTopOfStatusBar(), int(Screen.GetHeight() * 0.85));
		Screen.DrawText(SmallFont, Font.CR_GOLD, (Screen.GetWidth() - w) / 2, bottom - h * 4, text, DTA_ScaleX, scale, DTA_ScaleY, scale);
	}
}
