version "4.14"

// Test only: Doom's live door locks and Daggerfall's door order, with no Daggerfall (run_doorgate.py). Load after a
// converted dungeon's pk3s and doomerfall.pk3, run with +dd_lockdoor <LoadID of a door with a starting lock>.
// Daggerfall's answers are played by this harness as the network events dd_doors.cpp would deliver. The real minigame
// runs. Prints DGTEST lines and "DGTEST done <passed>/<total>".

// Records the door's calls to its action record: D = door trigger (ExecuteActionOnToggle), X = direct trigger.
class DGRecorder : DFDoorListener
{
	String calls;
	bool firstText;
	override bool IsFirstDoorText() { return firstText; }
	override void DoorTrigger(Actor user) { calls = calls .. "D"; firstText = false; }
	override void DirectTrigger(Actor user) { calls = calls .. "X"; }
}

class DGPresser : Thinker
{
	int press;
	override void Tick() { if (press) { players[0].cmd.buttons |= press; press = 0; } }
}

class DGTest : EventHandler
{
	int step, timer, passed, total, asks;
	String lastAsk;
	bool done, started;
	DFDoor door, other;
	DGRecorder rec;
	DGPresser presser;
	vector3 spot;
	double face;

	void Check(bool ok, String what) { total++; if (ok) passed++; Console.Printf("DGTEST %s %s", ok ? "PASS" : "FAIL", what); }

	override void NetworkProcess(ConsoleEvent e) { if (e.Name.Left(11) == "dfdoor_ask:") { asks++; lastAsk = e.Name; } }

	DoomerfallPickGame Game()
	{
		let h = DoomerfallLockpick(EventHandler.Find("DoomerfallLockpick"));
		return h ? h.game : null;
	}

	bool PlaceAtDoor(PlayerPawn p)
	{
		int n = door.links.Size();
		if (n == 0) return false;
		vector2 mid = door.links[n / 2].pos.xy;
		vector2 dir = n > 1 ? (door.links[n - 1].pos.xy - door.links[0].pos.xy).Unit() : (cos(door.closedAngle), sin(door.closedAngle));
		vector2 perp = (-dir.y, dir.x);
		for (int s = 1; s >= -1; s -= 2)
		{
			vector2 at = mid + perp * s * 40;
			p.SetOrigin((at, door.bottom), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(mid.y - at.y, mid.x - at.x);
			p.pitch = 0;
			if (!p.TestMobjLocation()) continue;
			FLineTraceData t;
			p.LineTrace(p.angle, 64, 0, 0, p.player.viewheight, 0, 0, t);
			if (t.HitType == TRACE_HitActor && t.HitActor is "DFDoorBlocker") { spot = p.pos; face = p.angle; return true; }
		}
		return false;
	}

	void Back(PlayerPawn p)
	{
		p.SetOrigin(spot, false);
		p.vel = (0, 0, 0);
		p.angle = face;
		p.pitch = 0;
	}

	// The real Use: PlayerPawn.CheckUse -> DFDoorBlocker.Used -> DFDoor.TryUse.
	void PressUse(PlayerPawn p)
	{
		Back(p);
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	// A Daggerfall action record of this type on the door, through the converter's real DFAction.Perform.
	void Lever(int type)
	{
		let a = DFAction(Actor.Spawn("DFAction", door.pos, NO_REPLACE));
		a.flag = type;
		a.door = door;
		a.Perform(players[0].mo);
		a.Destroy();
	}

	void Next() { step++; timer = 0; started = false; }

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		if (level.maptime < 10) return;
		if (!presser) { presser = new("DGPresser"); presser.ChangeStatNum(Thinker.STAT_USER); }
		timer++;
		let g = Game();
		if (g) started = true;
		int id = door ? door.loadId : 0;
		switch (step)
		{
		case 0:
		{
			int want = CVar.FindCVar("dd_lockdoor").GetInt();
			let it = ThinkerIterator.Create("DFDoor");
			DFDoor d;
			while (d = DFDoor(it.Next())) { if (d.loadId == want) door = d; else if (!other && d.loadId != 0 && d.startingLock == 0) other = d; }
			Check(door && other && door.startingLock > 0 && door.startingLock < 20, String.Format("found door %d with starting lock %d, and an unlockable door", want, door ? door.startingLock : -1));
			if (!door || !other || !PlaceAtDoor(p)) { Check(false, "a spot in front of the door"); step = 99; break; }
			Actor mo;
			let mi = ThinkerIterator.Create("Actor");
			while (mo = Actor(mi.Next())) if (mo.bISMONSTER && !mo.player) mo.Destroy();
			rec = DGRecorder(Actor.Spawn("DGRecorder", door.pos, NO_REPLACE));
			door.listener = rec;
			Check(!door.armed && door.lockValue == 0, "without Daggerfall the door is not locked");
			Lever(16);
			Check(door.lockValue == 0, "without Daggerfall action 16 does not lock it (no door nobody can open)");
			PressUse(p);
			Check(door.moving > 0 && rec.calls == "DX", String.Format("without Daggerfall Use opens it: door trigger, then direct trigger (%s)", rec.calls));
			Next();
			break;
		}
		case 1:
			if (timer == 70) Lever(20);
			if (timer < 140) break;
			Check(door.IsShut() && door.lockValue == 0, "without Daggerfall action 20 closes it and leaves it unlocked");
			EventHandler.SendNetworkEvent(String.Format("dfdoor_fact:%d:0", id)); // ignored: not armed
			EventHandler.SendNetworkEvent("dfdoor_arm");
			Next();
			break;
		case 2:
			if (timer < 5) break;
			Check(door.armed && door.lockValue == door.startingLock && other.armed && other.lockValue == 0, String.Format("Daggerfall's arm locks each door at its starting lock (%d, other %d)", door.lockValue, other.lockValue));
			rec.calls = "";
			PressUse(p);
			Check(door.IsShut() && rec.calls == "X", String.Format("locked: Use runs no door trigger, the direct trigger still runs (%s)", rec.calls));
			Next();
			break;
		case 3:
			if (timer < 35) break;
			Check(asks == 1 && lastAsk == String.Format("dfdoor_ask:%d:%d", id, door.startingLock), "locked: Doom asks Daggerfall once, with the lock value (" .. lastAsk .. ")");
			Check(door.IsShut() && !started, "refused (no answer): the door stays shut and no minigame starts");
			rec.calls = "";
			rec.firstText = true;
			PressUse(p);
			Check(door.IsShut() && rec.calls == "DX", String.Format("a first DoorText record runs before the lock check, the door stays shut (%s)", rec.calls));
			door.lockValue = 25;
			rec.calls = "";
			PressUse(p);
			Next();
			break;
		case 4:
			if (timer < 10) break;
			Check(asks == 3 && lastAsk == String.Format("dfdoor_ask:%d:25", id) && door.IsShut() && rec.calls == "X" && !started, "magically held: Doom asks with lock 25, stays shut, no minigame");
			rec.calls = "";
			EventHandler.SendNetworkEvent(String.Format("dfdoor_open:%d", id)); // Castle Daggerfall's foyer doors
			Next();
			break;
		case 5:
			if (timer == 5) Check(door.lockValue == 0 && door.moving > 0 && rec.calls == "", "dfdoor_open unlocks and opens it, not as the player's toggle");
			if (timer == 90) Lever(20);
			if (timer < 160) break;
			Check(door.IsShut() && door.lockValue == door.startingLock, "action 20 closes it and restores its starting lock");
			EventHandler.SendNetworkEvent(String.Format("dflp_start:50:%d", id)); // Daggerfall's answer: start the minigame
			Next();
			break;
		case 6: // a miss
			Back(p);
			if (g && g.Off(g.pointer) >= 120) presser.press = BT_ATTACK;
			if (timer < 35 * 4) break;
			Check(started && !g && door.IsShut() && door.lockValue == door.startingLock, "a miss leaves it locked and shut");
			EventHandler.SendNetworkEvent(String.Format("dflp_start:50:%d", id));
			Next();
			break;
		case 7: // a cancel
			Back(p);
			if (timer == 20) EventHandler.SendNetworkEvent("dflp_cancel");
			if (timer < 70) break;
			Check(started && !g && door.IsShut() && door.lockValue == door.startingLock, "a cancel leaves it locked and shut");
			rec.calls = "";
			EventHandler.SendNetworkEvent(String.Format("dflp_start:95:%d", id));
			Next();
			break;
		case 8: // a hit
			Back(p);
			if (g && g.Off(g.pointer) <= g.arc / 2 - 0.01) presser.press = BT_ATTACK;
			if (timer < 35 * 4) break;
			Check(started && !g && door.lockValue == 0 && door.swung > 0 && rec.calls == "D", String.Format("a hit unlocks it and toggles it as the player: door trigger once, no direct trigger (%s)", rec.calls));
			Next();
			break;
		case 9:
			if (!door.IsFullyOpen() && timer < 35 * 5) break;
			rec.calls = "";
			PressUse(p);
			Check(door.moving < 0 && rec.calls == "DX", String.Format("Use on the open door closes it: door trigger, then direct trigger (%s)", rec.calls));
			Next();
			break;
		case 10:
			if (timer == 5) { rec.calls = ""; PressUse(p); Check(door.moving < 0 && rec.calls == "X", "Use while it moves changes nothing but the direct trigger"); }
			if (timer < 70) break;
			Check(door.IsShut() && door.lockValue == 0, "closing by Use leaves a picked door unlocked");
			Lever(16);
			Check(door.lockValue == 16, "action 16 locks it at 16");
			door.lockValue = 5;
			Lever(16);
			Check(door.lockValue == 5, "action 16 leaves a locked door's value");
			Lever(17);
			Check(door.lockValue == 0, "action 17 unlocks it");
			door.lockValue = 3;
			Lever(20);
			Check(door.IsShut() && door.lockValue == 3, "action 20 on a shut door does nothing");
			Lever(18);
			Check(door.lockValue == 0 && door.moving > 0, "action 18 unlocks and opens it");
			Next();
			break;
		case 11:
			if (timer < 70) break;
			Lever(20);
			Check(door.moving < 0 && door.lockValue == door.startingLock, "action 20 closes it and relocks it at its starting lock");
			EventHandler.SendNetworkEvent(String.Format("dflp_result:%d:hit", other.loadId)); // a hit never asked for
			EventHandler.SendNetworkEvent(String.Format("dfdoor_fact:%d:0", id));
			EventHandler.SendNetworkEvent("dfdoor_arm");
			Next();
			break;
		case 12:
			if (timer < 70) break;
			Check(other.IsShut() && other.lockValue == 0, "a hit on a door that is not locked does nothing");
			Check(door.IsShut() && door.lockValue == 0, "Daggerfall's fact (picked open earlier) unlocks it, and a second arm does not relock armed doors");
			step = 99;
			break;
		case 99:
			Console.Printf("DGTEST done %d/%d", passed, total);
			done = true;
			break;
		}
	}
}
