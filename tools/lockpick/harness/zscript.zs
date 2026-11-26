version "4.10"

// Test only: drives the lockpicking minigame (mods/doomerfall DoomerfallLockpick.zs) on any map, without Daggerfall.
// Cases, in order: hit, miss, damage cancel, move cancel, Use cancel, and a hard (5%) hit. It presses Fire and Use by
// writing the player's command from a thinker created before each attempt, so it ticks just before the game's.
// Prints LPTEST lines and finally "LPTEST done <passed>/<total>".

class LPTestPresser : Thinker
{
	int press;	// buttons to add this tic
	override void Tick() { if (press) { players[0].cmd.buttons |= press; press = 0; } }
}

class LPTest : EventHandler
{
	LPTestPresser presser;
	int step, wait, passed, total;
	String expect;
	int ammoBefore;
	vector3 home;

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(12) != "dflp_result:") return;
		Array<String> f;
		e.Name.Split(f, ":");
		String got = f.Size() > 2 ? f[2] : "?";
		total++;
		let ammo = players[0].mo.CountInv("Clip");
		bool ok = got == expect && ammo == ammoBefore;
		if (ok) passed++;
		Console.Printf("LPTEST case %d expect %s got %s ammo %d->%d %s", step, expect, got, ammoBefore, ammo, ok ? "PASS" : "FAIL");
		step++;
		wait = 10;
		players[0].mo.SetOrigin(home, false);
	}

	DoomerfallPickGame Game()
	{
		let h = DoomerfallLockpick(EventHandler.Find("DoomerfallLockpick"));
		return h ? h.game : null;
	}

	void Start(int chance, String want)
	{
		expect = want;
		ammoBefore = players[0].mo.CountInv("Clip");
		if (!presser) { presser = new("LPTestPresser"); presser.ChangeStatNum(Thinker.STAT_USER); }
		if (step % 2) EventHandler.SendNetworkEvent(String.Format("dflp_start:%d:%d", chance, 100 + step)); // name-only form
		else EventHandler.SendNetworkEvent("dflp_start", chance, 100 + step);
		wait = -1;
	}

	override void WorldTick()
	{
		let pmo = players[0].mo;
		if (!pmo) return;
		if (level.maptime == 5) { home = pmo.pos; pmo.bNODAMAGE = false; }
		if (level.maptime < 20) return;
		if (wait > 0) { wait--; return; }
		let g = Game();
		if (wait == 0)
		{
			switch (step)
			{
				case 0: Start(50, "hit"); break;
				case 1: Start(50, "miss"); break;
				case 2: Start(50, "cancel"); break;
				case 3: Start(50, "cancel"); break;
				case 4: Start(50, "cancel"); break;
				case 5: Start(5, "hit"); break;
				default:
					Console.Printf("LPTEST done %d/%d", passed, total);
					wait = -2;
					return;
			}
			return;
		}
		if (wait != -1 || !g) return;
		// Act on the attempt in flight. The presser ticks before the game, so a press set now is judged next tic against
		// the pointer as it stands now (the game judges before it moves).
		double next = g.pointer;
		switch (step)
		{
			case 0: case 5: if (g.Off(next) <= g.arc / 2 - 0.01) presser.press = BT_ATTACK; break;
			case 1: if (g.Off(next) >= 120) presser.press = BT_ATTACK; break;
			case 2: if (g.age == 8) pmo.DamageMobj(null, null, 1, 'None', DMG_NO_ARMOR); break;
			case 3: if (g.age == 8) pmo.SetOrigin(pmo.pos + (100, 0, 0), false); break;
			case 4: if (g.age == 8) presser.press = BT_USE; break;
		}
	}
}
