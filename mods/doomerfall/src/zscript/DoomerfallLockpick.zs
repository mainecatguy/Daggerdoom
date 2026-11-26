// The lockpicking minigame (owner, 2026-11-25). It replaces Daggerfall's lockpick dice roll: a ring outline with one
// short solid white arc, and a chevron that spins around the ring. Fire while the chevron is over the white arc opens
// the lock; Fire anywhere else breaks one pick. Doom keeps running. Taking damage, moving away, or pressing Use again
// cancels the attempt at no cost.
//
// Doom decides only the timing. Daggerfall owns the lock, its chance, the picks and the skill: the attempt starts with
// Daggerfall's own lockpicking chance (FormulaHelper, 5 to 95), and the result goes back to the engine as
// "dflp_result:<token>:<hit|miss|cancel>", which forwards it to Daggerfall. Start one with the network event
// "dflp_start" (args: chance, token). The engine sends it when the player uses a pickable locked door with picks; at the
// console, `netevent dflp_start 50 0` starts a test attempt at 50% on any map.
//
// Difficulty: t = (chance - 5) / 90. The white arc is 14 + 56t degrees wide and the chevron turns at 230 - 105t degrees a
// second. At 5% the arc passes under the chevron in about 61 ms (two tics), so a hopeless lock is very hard but never
// impossible; at 95% the window is about 0.56 s.
//
// Fire and Use are taken out of the player's command while an attempt runs, by a thinker that ticks before players do
// (STAT_USER), so the gun does not shoot and Use does not reach doors. Nothing changes when no attempt runs.

class DoomerfallPickGame : Thinker
{
	const ARC_HARD = 14.0;		const ARC_EASY = 70.0;
	const SPEED_HARD = 230.0;	const SPEED_EASY = 125.0;
	const LEAVE_DIST = 64.0;	// moving this far from where the attempt started cancels it

	int pnum, token, chance;
	double arc, speed;			// degrees, degrees per second
	double center;				// the white arc's middle, degrees clockwise from the top
	double pointer, lastPointer;
	vector3 startPos;
	int lastHealth, lastDamage, held, age;

	static DoomerfallPickGame Begin(int pnum, int chance, int token)
	{
		let g = new("DoomerfallPickGame");
		g.ChangeStatNum(STAT_USER);
		g.pnum = pnum;
		g.token = token;
		g.chance = clamp(chance, 5, 95);
		double t = (g.chance - 5) / 90.0;
		g.arc = ARC_HARD + (ARC_EASY - ARC_HARD) * t;
		g.speed = SPEED_HARD + (SPEED_EASY - SPEED_HARD) * t;
		g.pointer = g.lastPointer = 0;
		g.center = 90 + frandom(0, 180);	// never under the chevron at the start
		let p = players[pnum];
		g.startPos = p.mo.pos;
		g.lastHealth = p.health;
		g.lastDamage = p.damagecount;
		g.held = p.cmd.buttons & (BT_ATTACK | BT_USE);	// a button held from before the start does not count
		DDLog.Debug(String.Format("DFLOCKPICK start token %d chance %d arc %.1f speed %.1f", token, g.chance, g.arc, g.speed));
		return g;
	}

	// The angle between the chevron and the white arc's middle, 0 to 180.
	double Off(double a) { double d = abs((a - center) % 360.0); return d > 180 ? 360 - d : d; }

	override void Tick()
	{
		if (pnum < 0 || !playeringame[pnum] || !players[pnum].mo || players[pnum].health <= 0) { Finish("cancel", "dead"); return; }
		let p = players[pnum];
		int buttons = p.cmd.buttons;
		p.cmd.buttons &= ~(BT_ATTACK | BT_USE);
		int pressed = buttons & ~held & (BT_ATTACK | BT_USE);
		held = buttons & (BT_ATTACK | BT_USE);
		age++;

		if (p.health < lastHealth || p.damagecount > lastDamage) { Finish("cancel", "damage"); return; }
		lastHealth = p.health;
		lastDamage = p.damagecount;
		if ((p.mo.pos.xy - startPos.xy).Length() > LEAVE_DIST || abs(p.mo.pos.z - startPos.z) > LEAVE_DIST) { Finish("cancel", "moved"); return; }
		if (pressed & BT_USE) { Finish("cancel", "use"); return; }
		if (pressed & BT_ATTACK)
		{
			bool hit = Off(pointer) <= arc / 2;
			Finish(hit ? "hit" : "miss", String.Format("pointer %.1f centre %.1f arc %.1f", pointer, center, arc));
			return;
		}
		lastPointer = pointer;
		pointer = (pointer + speed / TICRATE) % 360.0;
	}

	void Finish(String result, String why)
	{
		DDLog.Debug(String.Format("DFLOCKPICK %s token %d (%s)", result, token, why));
		EventHandler.SendNetworkEvent(String.Format("dflp_result:%d:%s", token, result));
		let h = DoomerfallLockpick(EventHandler.Find("DoomerfallLockpick"));
		if (h && h.game == self) h.game = null;
		Destroy();
	}
}

class DoomerfallLockpick : EventHandler
{
	DoomerfallPickGame game;

	override void NetworkProcess(ConsoleEvent e)
	{
		// "dflp_start" with args (chance, token), or "dflp_start:<chance>:<token>", the name-only form the engine's
		// outgoing event queue sends (dd_items.cpp doomOutgoing).
		if (e.Name == "dflp_start" || e.Name.Left(11) == "dflp_start:")
		{
			if (e.Player < 0 || !players[e.Player].mo) return;
			int chance = e.Args[0], token = e.Args[1];
			if (e.Name.Length() > 10)
			{
				Array<String> f;
				e.Name.Split(f, ":");
				if (f.Size() < 3) return;
				chance = f[1].ToInt();
				token = f[2].ToInt();
			}
			if (game) game.Finish("cancel", "restarted");
			game = DoomerfallPickGame.Begin(e.Player, chance, token);
		}
		else if (e.Name == "dflp_cancel" && game) game.Finish("cancel", "engine");
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (!game || automapactive || game.pnum != consoleplayer) return;
		int vx, vy, vw, vh;
		[vx, vy, vw, vh] = Screen.GetViewWindow();
		double cx = vx + vw / 2.0, cy = vy + vh / 2.0;
		double r = max(24.0, Screen.GetHeight() / 14.0);
		double thin = max(1.0, r / 18.0), thick = max(3.0, r / 6.0);

		// The ring: an outline, transparent inside.
		int segs = 72;
		for (int i = 0; i < segs; i++)
		{
			double a0 = i * 360.0 / segs, a1 = (i + 1) * 360.0 / segs;
			Screen.DrawThickLine(int(cx + r * sin(a0)), int(cy - r * cos(a0)), int(cx + r * sin(a1)), int(cy - r * cos(a1)), thin, Color(255, 200, 200, 200), 200);
		}
		// The white arc.
		int steps = max(2, int(game.arc / 2));
		for (int i = 0; i < steps; i++)
		{
			double a0 = game.center - game.arc / 2 + game.arc * i / steps, a1 = game.center - game.arc / 2 + game.arc * (i + 1) / steps;
			Screen.DrawThickLine(int(cx + r * sin(a0)), int(cy - r * cos(a0)), int(cx + r * sin(a1)), int(cy - r * cos(a1)), thick, Color(255, 255, 255, 255), 255);
		}
		// The chevron, just outside the ring and pointing in at it.
		double d = game.pointer - game.lastPointer;
		if (d < 0) d += 360;
		double a = game.lastPointer + d * e.FracTic;
		double tipR = r + thick, backR = r + thick + r / 4, wing = 9.0;
		int tx = int(cx + tipR * sin(a)), ty = int(cy - tipR * cos(a));
		Screen.DrawThickLine(tx, ty, int(cx + backR * sin(a - wing)), int(cy - backR * cos(a - wing)), thick * 0.6, Color(255, 255, 210, 60), 255);
		Screen.DrawThickLine(tx, ty, int(cx + backR * sin(a + wing)), int(cy - backR * cos(a + wing)), thick * 0.6, Color(255, 255, 210, 60), 255);
	}
}
