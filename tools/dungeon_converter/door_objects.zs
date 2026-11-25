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

// Lets a Daggerfall action record react when its door is used. See action_objects.zs.
class DFDoorListener : Actor
{
	virtual void DoorUsed(DFDoor door, Actor user) {}
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
				double tr = t.DD_MoveRadius();	// bodies' movement width (narrower for monsters on Daggerfall maps)
				if (abs(t.pos.x - at.x) >= tr + linkRadius || abs(t.pos.y - at.y) >= tr + linkRadius) continue;
				if (t.pos.z >= top || t.pos.z + t.height <= bottom) continue;
				return false;
			}
		}
		return true;
	}

	bool TryUse(Actor user)
	{
		if (user.pos.z >= top || user.pos.z + user.height <= bottom) return false;	// another floor
		if (listener) listener.DoorUsed(self, user);
		if (moving != 0 && !stalled) return true;									// as ToggleDoor: ignored while moving
		moving = stalled ? -moving : (swung > 0 ? -1 : 1);
		stalled = false;
		UpdateBlocking();
		A_StartSound(moving > 0 ? "doors/dr1_open" : "doors/dr1_clos", CHAN_BODY);
		return true;
	}

	// Action types 18 and 20: open or close, and do nothing if already there or moving.
	void ActionSet(bool open)
	{
		if (moving != 0 || (swung > 0) == open) return;
		moving = open ? 1 : -1;
		UpdateBlocking();
		A_StartSound(open ? "doors/dr1_open" : "doors/dr1_clos", CHAN_BODY);
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
			spawned.Push(door);
		}
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
		Console.Printf("DFDOORS spawned %d, sight links %d", spawned.Size(), linked);
	}
}
