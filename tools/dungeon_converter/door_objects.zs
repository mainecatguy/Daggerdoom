version "4.10"

// [DoomDaggerfall] Hinged Daggerfall doors. Active only on a converted map (MAP01 with DFPOINTS and DFDOORS lumps).
// Timing follows DaggerfallActionDoor: 90 degrees in 1.5 s, linear, stays open until used again.

class DFDoorVisual : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY +NOINTERACTION +INTERPOLATEANGLES +DONTSPLASH Radius 24; Height 70; }
	States { Spawn: DFDR A -1 Bright; Stop; }
}

// One link of the door's collision row. Always stops hitscans and projectiles, as Daggerfall's rays and missiles
// still hit an open door's trigger collider. Solid to movement in every pose, unless a body is inside it (see UpdateBlocking).
class DFDoorBlocker : Actor
{
	DFDoor door;
	Default
	{
		Radius 2.25; Height 66; Health 1000000; Mass 1000000;
		+SOLID +SHOOTABLE +NOGRAVITY +NOBLOOD +INVULNERABLE +NORADIUSDMG +NOTAUTOAIMED +NEVERTARGET
		+DONTTHRUST +NOTELEPORT +DONTRIP +DONTSPLASH +CANTSEEK
		RenderStyle "None";
	}
	States { Spawn: TNT1 A -1; Stop; }
	override bool Used(Actor user) { return door && door.TryUse(user); }
}

// The Daggerfall action record on a door. DFDoor.Toggle and TryUse call it in DaggerfallActionDoor's order. See action_objects.zs.
class DFDoorListener : Actor
{
	virtual bool IsFirstDoorText() { return false; }	// a DoorText record (99) not yet activated: it runs before the lock check
	virtual void DoorTrigger(Actor user) {}			// ExecuteActionOnToggle: the player toggled the door
	virtual void DirectTrigger(Actor user) {}		// PlayerActivate's direct trigger, after the door's own handling
}

class DFDoor : Actor
{
	DFDoorListener listener;

	const SWING = 90.0;				// DaggerfallActionDoor.OpenAngle -90 is counterclockwise from above
	const RATE = 90.0 / (1.5 * 35);	// OpenDuration 1.5 s

	Array<DFDoorBlocker> links;
	Array<double> linkX;
	DFDoorVisual visual;
	double pivotX, pivotY, pivotZ, closedAngle, swung, rowY, centerX, centerY, bottom, top, linkRadius;
	double swingDir;				// 1 unless a city gate leaf opens the other way
	int moving;
	int startingLock, loadId;	// Daggerfall's starting lock value and Daggerfall Unity LoadID (0 in older maps)
	int lockValue;				// the live lock, as DaggerfallActionDoor.CurrentLockValue: 0 unlocked, 20 or more magically held
	bool armed;					// locks are live: Daggerfall sent this map's door facts (a bridge session). Never set without Daggerfall
	bool stalled, sightOpen;
	bool solidWhenOpen;			// city gates: also held by any solid actor in the swing, not only by bodies
	bool passable;				// links are currently non-solid to movement, because a body is inside them
	int checkPhase;				// spreads the idle overlap check over the tics of a second
	Array<int> sightSectors;	// control sectors of the see-blocking 3D floors in this doorway
	Array<double> sightTops;

	Default { +NOBLOCKMAP +NOSECTOR +NOGRAVITY +NOINTERACTION RenderStyle "None"; }
	States { Spawn: TNT1 A -1; Stop; }

	vector2 ToWorld(double x, double y, double angle)
	{
		double c = cos(angle), s = sin(angle);
		return (pivotX + x * c - y * s, pivotY + x * s + y * c);
	}

	void Setup(int slot, double px, double py, double pz, double angle, double x0, double x1, double y0, double y1, double z0, double z1)
	{
		pivotX = px; pivotY = py; pivotZ = pz; closedAngle = angle; swingDir = 1;
		centerX = (x0 + x1) / 2; centerY = (y0 + y1) / 2; rowY = centerY;
		bottom = pz + z0; top = pz + z1;
		linkRadius = (y1 - y0) / 2;
		double length = x1 - x0, span = length - 2 * linkRadius;
		int count = int(ceil(span / (2 * linkRadius))) + 1;
		for (int i = 0; i < count; i++)
		{
			linkX.Push(x0 + linkRadius + (count > 1 ? span * i / (count - 1) : 0));
			let link = DFDoorBlocker(Spawn("DFDoorBlocker", (px, py, bottom), NO_REPLACE));
			link.door = self;
			link.A_SetSize(linkRadius, top - bottom, false);
			links.Push(link);
		}
		class<Actor> kind = String.Format("DFDoorVisual%d", slot); // generated per model by DoorExport.cs
		visual = DFDoorVisual(Spawn(kind, (px, py, pz), NO_REPLACE));
		checkPhase = abs(int(px) + int(py)) % 35;
		Place(false);
	}

	void Place(bool interpolate)
	{
		double angle = closedAngle + swung * swingDir;
		for (int i = 0; i < links.Size(); i++)
		{
			vector2 at = ToWorld(linkX[i], rowY, angle);
			links[i].SetOrigin((at.x, at.y, bottom), false);
		}
		vector2 middle = ToWorld(centerX, centerY, angle);
		visual.SetOrigin((middle.x, middle.y, pivotZ), interpolate);
		visual.angle = angle;
		if (!interpolate) visual.ClearInterpolation();
	}

	void SetupSight(int control)
	{
		let it = level.CreateSectorTagIterator(control);
		int s;
		while ((s = it.Next()) >= 0)
		{
			sightSectors.Push(s);
			sightTops.Push(level.Sectors[s].CenterCeiling());
		}
	}

	// A closed door blocks sight. Any other position does not.
	void SetSightOpen(bool open)
	{
		if (sightOpen == open) return;
		sightOpen = open;
		for (int i = 0; i < sightSectors.Size(); i++)
		{
			Sector s = level.Sectors[sightSectors[i]];
			double dest = open ? s.CenterFloor() : sightTops[i];
			s.MoveCeiling(100000, dest, -1, open ? -1 : 1, false);
		}
	}

	// Open doors are solid (owner decision 2026-11-24, unlike DaggerfallActionDoor.MakeTrigger, which lets bodies walk
	// through an open or moving door). A swinging door never enters a body (see Tick), so a body is inside the links only
	// if it was put there, for example spawned or teleported. Doom cannot push it out, and a solid link would hold it
	// fast, so the links stay non-solid until no body overlaps them.
	void UpdateBlocking()
	{
		bool want = !Clear(swung, true);
		if (want == passable) return;
		passable = want;
		foreach (link : links) link.bSOLID = !want;
	}

	// True when the door row at this swing would not overlap any solid actor, or only any player or monster.
	bool Clear(double next, bool bodiesOnly = false)
	{
		double angle = closedAngle + next * swingDir;
		for (int i = 0; i < links.Size(); i++)
		{
			vector2 at = ToWorld(linkX[i], rowY, angle);
			let it = BlockThingsIterator.CreateFromPos(at.x, at.y, bottom, top - bottom, linkRadius, false);
			while (it.Next())
			{
				Actor t = it.thing;
				if (!t.bSOLID || t is "DFDoorBlocker") continue;
				if (bodiesOnly && !t.player && !t.bISMONSTER) continue;
				double tr = t.DD_MoveRadius();	// door leaves are level geometry: monsters squeeze past them (narrower on Daggerfall maps)
				if (abs(t.pos.x - at.x) >= tr + linkRadius || abs(t.pos.y - at.y) >= tr + linkRadius) continue;
				if (t.pos.z >= top || t.pos.z + t.height <= bottom) continue;
				return false;
			}
		}
		return true;
	}

	bool IsShut() { return swung <= 0 && moving == 0; }
	bool IsFullyOpen() { return swung >= SWING && moving == 0; }	// DaggerfallActionDoor.IsOpen

	// The player pressed Use on the door: DaggerfallActionDoor.ToggleDoor(true), then PlayerActivate's direct trigger.
	bool TryUse(Actor user)
	{
		if (user.pos.z >= top || user.pos.z + user.height <= bottom) return false;	// another floor
		Toggle(user);
		if (listener) listener.DirectTrigger(user);
		return true;
	}

	// DaggerfallActionDoor.ToggleDoor(activatedByPlayer: true), in Daggerfall's order. Nothing while moving. Closing runs
	// the door trigger. Opening: a first-activation DoorText record runs first, then the lock check, then the door
	// trigger, then the swing. A shut locked door stays shut and Daggerfall is asked about the player's attempt
	// (its label or the lockpicking minigame). A lockpick hit comes back here with the lock cleared.
	void Toggle(Actor user)
	{
		if (moving != 0 && !stalled) return;
		bool opening = stalled ? moving < 0 : swung <= 0;
		if (!opening)
		{
			if (listener) listener.DoorTrigger(user);
			StartSwing(-1);
			return;
		}
		bool text = listener && listener.IsFirstDoorText();
		if (text) listener.DoorTrigger(user);
		if (lockValue > 0 && IsShut())
		{
			EventHandler.SendNetworkEvent(String.Format("dfdoor_ask:%d:%d", loadId, lockValue));
			return;
		}
		if (!text && listener) listener.DoorTrigger(user);
		StartSwing(1);
	}

	// Starts the door moving: 1 opens, -1 closes. A stalled door turns back.
	void StartSwing(int dir)
	{
		if (moving != 0 && !stalled) return;	// the door trigger already moved it
		moving = dir;
		stalled = false;
		UpdateBlocking();
		A_StartSound(dir > 0 ? "doors/dr1_open" : "doors/dr1_clos", CHAN_BODY);
	}

	// Open or close not by the player (no door trigger, no lock check); nothing if already there or moving.
	// True when the door started moving.
	bool ActionSet(bool open)
	{
		if (moving != 0 || (swung > 0) == open) return false;
		StartSwing(open ? 1 : -1);
		return true;
	}

	// An action record of this type ran on this door: DaggerfallAction's LockDoor (16), UnlockDoor (17), OpenDoor (18)
	// and CloseDoor (20). Locks change only once armed, so a map without Daggerfall never gets a door nobody can open.
	void RunAction(int type)
	{
		switch (type)
		{
			case 16: if (armed && lockValue <= 0) lockValue = 16; break;	// Daggerfall's value
			case 17: if (armed) lockValue = 0; break;
			case 18: if (!IsFullyOpen()) { if (armed) lockValue = 0; ActionSet(true); } break;
			case 20: if (IsFullyOpen()) { ActionSet(false); if (armed) lockValue = startingLock; } break;
		}
	}

	override void Tick()
	{
		if (isFrozen()) return;
		if (moving != 0)
		{
			double next = clamp(swung + moving * RATE, 0.0, SWING);
			// A door that would swing into a body waits, without pushing, and goes on once the way is clear.
			// Using it while it waits sends it back. Ordinary doors ignore solid props; city gates are held by them too.
			stalled = !Clear(next, !solidWhenOpen);
			if (!stalled)
			{
				swung = next;
				Place(true);
				SetSightOpen(swung > 0);
				if (swung <= 0 || swung >= SWING) moving = 0;
			}
		}
		if (passable || level.maptime % 35 == checkPhase) UpdateBlocking();
	}
}

class DFDoorHandler : EventHandler
{
	Array<DFDoor> doors;
	transient bool ticked;	// false again after a save is loaded (transient fields are not saved)

	// A save taken before Daggerfall armed the locks (its answer timed out): ask again on the first tic after the load.
	// The arm sets only doors not yet armed, so live locks in the save are never overwritten. A fresh map asked in
	// WorldLoaded already (maptime 0 or 1 here). Without a bridge session nobody answers.
	override void WorldTick()
	{
		if (ticked) return;
		ticked = true;
		if (level.maptime > 1) foreach (d : doors) if (d && d.loadId != 0 && !d.armed) { EventHandler.SendNetworkEvent("dfdoor_facts"); break; }
	}

	DFDoor Find(int id)
	{
		if (id != 0) foreach (d : doors) if (d && d.loadId == id) return d;
		return null;
	}

	// Daggerfall's door answers (dd_doors.cpp), and the lockpicking minigame's result:
	//   "dfdoor_arm"               lock every door not yet armed at its starting lock value (only Daggerfall sends it)
	//   "dflp_result:<id>:hit"     the minigame hit with Daggerfall's chance: unlock the door and toggle it as the player
	//   "dfdoor_open:<id>"         unlock and open it, not as the player's toggle (Castle Daggerfall's foyer doors)
	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "dfdoor_arm")
		{
			foreach (d : doors) if (d && d.loadId != 0 && !d.armed) { d.armed = true; d.lockValue = d.startingLock; }
			return;
		}
		Array<String> f;
		e.Name.Split(f, ":");
		if (f.Size() < 2) return;
		DFDoor door = Find(f[1].ToInt());
		if (!door) return;
		if (f[0] == "dflp_result" && f.Size() > 2 && f[2] == "hit" && door.lockValue > 0 && door.IsShut() && e.Player >= 0 && playeringame[e.Player])
		{
			door.lockValue = 0;
			door.Toggle(players[e.Player].mo); // DaggerfallActionDoor.AttemptLockpicking: CurrentLockValue = 0, then ToggleDoor(true)
		}
		else if (f[0] == "dfdoor_open" && door.lockValue > 0 && door.IsShut())
		{
			door.lockValue = 0;
			door.ActionSet(true);
		}
	}

	// [Doomerfall] The location record keeps each door open or closed (dd_treadmill.cpp): "<stamp> <hex>", one bit per
	// door in DFDOORS order, a moving door at the end it is heading to. The stamp hashes DFDOORS, so a record made from
	// another conversion is dropped and the doors reset.
	// Once Daggerfall armed the locks, a third field keeps every live lock that differs from the door's starting lock
	// (picked, a lever's unlock or lock, the Castle Daggerfall foyer): "L" then "<index>.<lock>" entries joined by ",".
	// A plain "L" means armed with every door at its starting lock; no third field means the locks were never armed.
	static int Stamp()
	{
		int lump = Wads.CheckNumForFullName("DFDOORS");
		if (lump < 0) return 0;
		String text = Wads.ReadLump(lump);
		int h = -2128831035;	// FNV-1a
		for (int i = 0; i < text.Length(); i++) h = (h ^ text.ByteAt(i)) * 16777619;
		return h | 1;
	}

	static String Distill()
	{
		int stamp = Stamp(), n = 0, nibble = 0;
		String bits = "", locks = "";
		bool armed = false;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while (stamp && (d = DFDoor(it.Next())))
		{
			if (d.moving != 0 ? d.moving > 0 : d.swung > 0) nibble |= 1 << (n & 3);
			if (d.armed)
			{
				armed = true;
				if (d.lockValue != d.startingLock) locks.AppendFormat("%s%d.%d", locks.Length() ? "," : "", n, d.lockValue);
			}
			if ((++n & 3) == 0) { bits.AppendFormat("%x", nibble); nibble = 0; }
		}
		if (n & 3) bits.AppendFormat("%x", nibble);
		if (!n) return "";
		return armed ? String.Format("%08x %s L%s", stamp, bits, locks) : String.Format("%08x %s", stamp, bits);
	}

	// The doors opened, or -1 when the stamp differs (nothing changes). An action keeps its own reset state.
	// A record with locks arms every lockable door at its starting lock and then sets the recorded ones; a door already
	// armed by Daggerfall's arm gets the record's lock too, since the record is newer than the starting lock.
	static int Restore(String record)
	{
		Array<String> f;
		record.Split(f, " ");
		if (f.Size() < 2 || f.Size() > 3 || f[0] != String.Format("%08x", Stamp())) return -1;
		bool withLocks = f.Size() == 3 && f[2].Left(1) == "L";
		Array<String> locks;
		if (withLocks && f[2].Length() > 1) f[2].Mid(1).Split(locks, ",");
		int n = 0, open = 0, changed = 0;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while (d = DFDoor(it.Next()))
		{
			bool want = (n >> 2) < f[1].Length() && (f[1].Mid(n >> 2, 1).ToInt(16) >> (n & 3)) & 1;
			d.moving = 0; d.stalled = false; d.swung = want ? d.SWING : 0;
			d.Place(false); d.SetSightOpen(want); d.UpdateBlocking();
			if (want) open++;
			if (withLocks && d.loadId != 0)
			{
				d.armed = true;
				d.lockValue = d.startingLock;
				String key = String.Format("%d.", n);
				foreach (entry : locks)
					if (entry.Left(key.Length()) == key) { d.lockValue = entry.Mid(key.Length()).ToInt(); changed++; }
			}
			n++;
		}
		if (withLocks) Console.PrintfEx(PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFDOORS locks from the record: %d of %d doors differ from their starting lock", changed, n); // log only
		return open;
	}

	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame || e.IsReopen || !(level.MapName ~== "MAP01")) return;
		if (Wads.CheckNumForName("DFPOINTS", Wads.ns_global) < 0) return;
		int lump = Wads.CheckNumForFullName("DFDOORS");
		if (lump < 0) return;
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, "\n", TOK_SKIPEMPTY);
		Array<DFDoor> spawned;
		foreach (text : lines)
		{
			Array<String> f;
			text.Split(f, " ", TOK_SKIPEMPTY);
			if (f.Size() < 11) continue;
			let door = DFDoor(Actor.Spawn("DFDoor", (f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble()), NO_REPLACE));
			door.Setup(f[0].ToInt(), f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble(), f[4].ToDouble(),
				f[5].ToDouble(), f[6].ToDouble(), f[7].ToDouble(), f[8].ToDouble(), f[9].ToDouble(), f[10].ToDouble());
			if (f.Size() > 11) door.swingDir = f[11].ToDouble();
			if (f.Size() > 13) { door.startingLock = f[12].ToInt(); door.loadId = f[13].ToInt(); }
			spawned.Push(door);
			doors.Push(door);
		}
		// Daggerfall arms the locks with its facts for this dungeon (dd_doors.cpp). Without a bridge session nobody answers.
		if (spawned.Size() > 0 && spawned[0].loadId != 0) EventHandler.SendNetworkEvent("dfdoor_facts");
		// "DC <door> <control>" lines in DFPOINTS link each door to its sight-blocking control sectors.
		Array<String> points;
		Wads.ReadLump(Wads.CheckNumForName("DFPOINTS", Wads.ns_global)).Split(points, "\n", TOK_SKIPEMPTY);
		int linked = 0;
		foreach (text : points)
		{
			if (text.Left(3) != "DC ") continue;
			Array<String> f;
			text.Split(f, " ");
			int index = f[1].ToInt();
			if (index < spawned.Size()) { spawned[index].SetupSight(f[2].ToInt()); linked++; }
		}
		{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFDOORS spawned %d, sight links %d", spawned.Size(), linked); } // diagnostics: on screen only with dd_debugmessages
	}
}
