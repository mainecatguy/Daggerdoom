
// [DoomDaggerfall] Daggerfall action records. Active only on a converted map with a DFACTIONS lump.
// Follows DaggerfallAction.cs: triggers, chains, linear moves, and reversing on the next activation.
// Doom does the physical part. Everything Daggerfall decides goes through DFActionRules.

// THE SEAM. The engine bridge replaces this body. Doom must not decide these outcomes itself.
class DFActionRules play
{
	// kind: spell, text, riddle, damage, poison, magicka, dialogue, questvar, doortext, lock, unlock, unknown
	static void Request(DFAction a, String kind, Actor user)
	{
		a.ruleRequests++;
		if (a.ruleRequests == 1)
			{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFRULE %s record=%d flag=%d index=%d axis=%d magnitude=%d", kind, a.id, a.flag, a.index, a.axis, a.magnitude); } // diagnostics: on screen only with dd_debugmessages
	}

	// A type 12 riddle holds its chain until Daggerfall reports the right answer. The bridge calls this.
	static void AnswerAccepted(DFAction a) { if (a) a.ActivateNext(a); }
}

class DFActionVisual : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY +NOINTERACTION +INTERPOLATEANGLES +DONTSPLASH Radius 24; Height 70; }
	States { Spawn: DFAC A -1 Bright; Stop; }
}

class DFActionFlat : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY +NOINTERACTION +DONTSPLASH Radius 8; Height 16; }
}

// An ordinary Daggerfall billboard. It has no collision, as in Daggerfall Unity. ANIMDEFS animates its texture.
class DFDungeonFlat : Actor
{
	Default { +NOBLOCKMAP +NOGRAVITY +NOINTERACTION +DONTSPLASH +NOTONAUTOMAP Radius 1; Height 1; }
	States { Spawn: PLAY A -1 Bright; Stop; }
}

// A Daggerfall NPC in a dungeon. It blocks nothing and takes no damage. args[0] and args[1] hold the low and high halves of its id.
class DFDungeonNpc : DFDungeonFlat {}

// Holds one dungeon light record's light. It draws nothing and touches nothing.
class DFDungeonLight : Actor
{
	Default { +NOINTERACTION +NOBLOCKMAP +NOGRAVITY +DONTSPLASH +NOTONAUTOMAP Radius 1; Height 1; }
	States { Spawn: TNT1 A -1; Stop; }
}

// One cube of a moving model's collision. Solid to movement, hitscans, and projectiles, and can be stood on.
class DFActionCell : Actor
{
	DFAction owner;
	double lx, ly, lz;
	Default
	{
		Radius 8; Height 16; Health 1000000; Mass 1000000;
		+SOLID +SHOOTABLE +NOGRAVITY +NOBLOOD +INVULNERABLE +NORADIUSDMG +NOTAUTOAIMED +NEVERTARGET +ACTLIKEBRIDGE
		+DONTTHRUST +NOTELEPORT +DONTRIP +DONTSPLASH +CANTSEEK
		RenderStyle "None";
	}
	States { Spawn: TNT1 A -1; Stop; }

	// A resting actor is clamped to its sector's floor. Cells can lie over another sector or below the floor, as with an open
	// trapdoor or a pillar hidden under one, so only DFAction.Place moves them.
	override void Tick() {}
}

class DFAction : DFDoorListener
{
	enum EState { AT_START, FORWARD, AT_END, REVERSE }
	enum ETrigger { TR_NONE = 0, TR_WALKON = 1, TR_DIRECT = 2, TR_WALKINTO = 3, TR_ATTACK = 5, TR_DIRECT6 = 6, TR_MULTI = 8, TR_COLLIDE9 = 9, TR_DOOR = 10 }
	enum ESource { FROM_ACTION, FROM_DIRECT, FROM_WALKON, FROM_WALKINTO, FROM_ATTACK, FROM_DOOR }

	int id, kind, flag, trigger, nextId, doorId, index, axis, magnitude, lockValue;
	int loadId;	// Daggerfall Unity's LoadID for this record (block file position + record position), 0 in older maps
	DFAction nextAction;
	DFDoor door;
	Actor visual;
	Array<DFActionCell> cells;
	vector3 pivot, travel, spin, center, boxMin, boxMax;
	double yaw, fraction, rate, cellHalf;
	bool forwardOnly, stalled, bodyInCells, freeSwing;
	int phase, activationCount, ruleRequests, touchCooldown;

	Default { +NOBLOCKMAP +NOSECTOR +NOGRAVITY +NOINTERACTION RenderStyle "None"; }
	States { Spawn: TNT1 A -1; Stop; }

	bool IsMover() { return flag >= 1 && flag <= 8 && kind != 0; }

	// Model space at Doom scale to world, at a given fraction of the move. Unity axes are (x, z, y) here.
	vector3 ToWorld(vector3 l, double f)
	{
		double ux = l.x, uy = l.z, uz = l.y, c, s, t;
		if (spin.z != 0) { c = cos(spin.z * f); s = sin(spin.z * f); t = ux * c - uy * s; uy = ux * s + uy * c; ux = t; }
		if (spin.x != 0) { c = cos(spin.x * f); s = sin(spin.x * f); t = uy * c - uz * s; uz = uy * s + uz * c; uy = t; }
		if (spin.y != 0) { c = cos(spin.y * f); s = sin(spin.y * f); t = ux * c + uz * s; uz = -ux * s + uz * c; ux = t; }
		c = cos(yaw); s = sin(yaw);
		return (pivot.x + travel.x * f + ux * c - uz * s, pivot.y + travel.y * f + ux * s + uz * c, pivot.z + travel.z * f + uy);
	}

	// The inverse of ToWorld at the current fraction.
	vector3 ToLocal(vector3 w)
	{
		double f = fraction, c = cos(yaw), s = sin(yaw), t;
		double dx = w.x - pivot.x - travel.x * f, dy = w.y - pivot.y - travel.y * f;
		double ux = dx * c + dy * s, uz = -dx * s + dy * c, uy = w.z - pivot.z - travel.z * f;
		if (spin.y != 0) { c = cos(-spin.y * f); s = sin(-spin.y * f); t = ux * c + uz * s; uz = -ux * s + uz * c; ux = t; }
		if (spin.x != 0) { c = cos(-spin.x * f); s = sin(-spin.x * f); t = uy * c - uz * s; uz = uy * s + uz * c; uy = t; }
		if (spin.z != 0) { c = cos(-spin.z * f); s = sin(-spin.z * f); t = ux * c - uy * s; uy = ux * s + uy * c; ux = t; }
		return (ux, uz, uy);
	}

	void Place(bool interpolate)
	{
		for (int i = 0; i < cells.Size(); i++)
		{
			let cell = cells[i];
			vector3 at = ToWorld((cell.lx, cell.ly, cell.lz), fraction);
			cell.SetOrigin((at.x, at.y, at.z - cell.height / 2), false);
		}
		if (!visual) return;
		visual.SetOrigin(ToWorld(center, fraction), interpolate);
		if (kind == 1)
		{
			visual.angle = yaw - spin.y * fraction;
			visual.pitch = -spin.z * fraction;
			visual.roll = -spin.x * fraction;
		}
		if (!interpolate) visual.ClearInterpolation();
	}

	// Tests the cells at the next fraction. Bodies standing on the object ride along; any other body stalls it.
	bool TryStep(double next)
	{
		Array<Actor> riders;
		Array<double> riderX, riderY, riderZ;
		for (int i = 0; i < cells.Size(); i++)
		{
			let cell = cells[i];
			vector3 was = cell.pos;
			vector3 at = ToWorld((cell.lx, cell.ly, cell.lz), next);
			double tall = cell.height;
			at.z -= tall / 2;
			double reach = cellHalf + 40;
			let it = BlockThingsIterator.CreateFromPos(at.x, at.y, at.z - 2, tall + 4, reach, false);
			while (it.Next())
			{
				Actor t = it.thing;
				if (!t.bSOLID || t is "DFActionCell" || t is "DFDoorBlocker") continue;
				bool onTop = abs(t.pos.z - (was.z + tall)) <= 2
					&& abs(t.pos.x - was.x) < t.radius + cellHalf && abs(t.pos.y - was.y) < t.radius + cellHalf;
				if (onTop)
				{
					if (riders.Find(t) == riders.Size())
					{
						riders.Push(t);
						riderX.Push(at.x - was.x); riderY.Push(at.y - was.y); riderZ.Push(at.z - was.z);
					}
					continue;
				}
				if (riders.Find(t) != riders.Size()) continue;
				if (abs(t.pos.x - at.x) >= t.radius + cellHalf || abs(t.pos.y - at.y) >= t.radius + cellHalf) continue;
				if (t.pos.z >= at.z + tall || t.pos.z + t.height <= at.z) continue;
				return false;
			}
		}
		for (int i = 0; i < riders.Size(); i++)
			if (riderZ[i] > 0 && riders[i].pos.z + riders[i].height + riderZ[i] > riders[i].ceilingz) return false;
		fraction = next;
		Place(true);
		for (int i = 0; i < riders.Size(); i++)
		{
			Actor r = riders[i];
			r.SetOrigin(r.pos + (riderX[i], riderY[i], riderZ[i]), true);
			r.FindFloorCeiling();
		}
		return true;
	}

	bool IsSpecialDoor() { return kind == 1 && (flag == 18 || flag == 20); }

	bool OverlapsBody(DFActionCell cell)
	{
		let it = BlockThingsIterator.CreateFromPos(cell.pos.x, cell.pos.y, cell.pos.z, cell.height, cell.radius, false);
		while (it.Next())
		{
			Actor t = it.thing;
			if (!t.bSOLID || (!t.player && !t.bISMONSTER)) continue;
			if (abs(t.pos.x - cell.pos.x) >= t.radius + cell.radius || abs(t.pos.y - cell.pos.y) >= t.radius + cell.radius) continue;
			if (t.pos.z >= cell.pos.z + cell.height || t.pos.z + t.height <= cell.pos.z) continue;
			return true;
		}
		return false;
	}

	// DaggerfallActionDoorSpecial never waits and never carries a body: its collider turns away and the character controller
	// is pushed clear. Doom has no push, so a cell inside a body stays non-solid until the body leaves.
	void TickSpecialDoor()
	{
		bool moving = phase == FORWARD || phase == REVERSE;
		if (!moving && !bodyInCells) return;
		if (moving)
		{
			fraction = clamp(fraction + (phase == FORWARD ? rate : -rate), 0.0, 1.0);
			Place(true);
			if (fraction >= 1 && phase == FORWARD) phase = AT_END;
			else if (fraction <= 0 && phase == REVERSE) phase = AT_START;
		}
		bodyInCells = false;
		foreach (cell : cells)
		{
			bool inside = OverlapsBody(cell);
			cell.bSOLID = !inside;
			bodyInCells = bodyInCells || inside;
		}
		// A body standing still does not notice a floor that swung away.
		let it = BlockThingsIterator.CreateFromPos(pivot.x, pivot.y, pivot.z + boxMin.z - 64, boxMax.z - boxMin.z + 128, 160, false);
		while (it.Next())
			if (it.thing.player || it.thing.bISMONSTER) it.thing.FindFloorCeiling();
	}

	override void Tick()
	{
		if (touchCooldown > 0) touchCooldown--;
		if (isFrozen()) return;
		// A hinged trapdoor drops out from under a body. It neither carries nor waits for one, as in Daggerfall.
		if (IsSpecialDoor() || freeSwing) { TickSpecialDoor(); return; }
		if (phase != FORWARD && phase != REVERSE) return;
		double next = clamp(fraction + (phase == FORWARD ? rate : -rate), 0.0, 1.0);
		if (!TryStep(next)) { stalled = true; return; }
		stalled = false;
		if (next >= 1 && phase == FORWARD) phase = AT_END;
		else if (next <= 0 && phase == REVERSE) phase = AT_START;
	}

	bool IsPlaying()
	{
		DFAction a = self;
		for (int depth = 0; a && depth < 64; depth++, a = a.nextAction)
			if (a.phase == FORWARD || a.phase == REVERSE) return true;
		return false;
	}

	void ActivateNext(DFAction from) { if (nextAction) nextAction.Receive(from, FROM_ACTION); }

	bool TriggerAccepts(int source)
	{
		if (source == FROM_ACTION) return true;
		switch (trigger)
		{
			case TR_WALKON: return source == FROM_WALKON;
			case TR_DIRECT: case TR_DIRECT6: return source == FROM_DIRECT;
			case TR_WALKINTO: return source == FROM_WALKINTO;
			case TR_ATTACK: return source == FROM_ATTACK;
			case TR_MULTI: return source == FROM_DIRECT || source == FROM_ATTACK || source == FROM_WALKINTO;
			case TR_COLLIDE9: return source == FROM_DIRECT || source == FROM_WALKINTO;
			case TR_DOOR: return source == FROM_DOOR;
		}
		return false;
	}

	void Receive(Actor from, int source)
	{
		if (IsPlaying() || !TriggerAccepts(source)) return;
		activationCount++;
		if (flag != 12) ActivateNext(self); // a riddle continues only through DFActionRules.AnswerAccepted
		Perform(from);
	}

	void Perform(Actor from)
	{
		Actor user = from;
		if (from is "DFAction") user = players[consoleplayer].mo;
		switch (flag)
		{
			case 1: case 2: case 3: case 4: case 5: case 6: case 7: case 8:
				if (phase == AT_START) { phase = FORWARD; A_StartSound("plats/pt1_strt", CHAN_BODY); }
				else if (phase == AT_END && !forwardOnly) { phase = REVERSE; A_StartSound("plats/pt1_strt", CHAN_BODY); }
				break;
			case 14: Teleport(user); break;
			// A model that is not a real door swings as DaggerfallActionDoorSpecial, once its converter record makes it a mover.
			case 18:
				if (door) door.RunAction(18);
				else if (kind == 1 && phase == AT_START) { phase = FORWARD; A_StartSound("doors/dr1_open", CHAN_BODY); }
				break;
			case 20:
				if (door) door.RunAction(20);
				else if (kind == 1 && phase == AT_END) { phase = REVERSE; A_StartSound("doors/dr1_clos", CHAN_BODY); }
				break;
			case 30: break;
			case 9: DFActionRules.Request(self, "spell", user); break;
			case 11: DFActionRules.Request(self, "text", user); break;
			case 12: DFActionRules.Request(self, "riddle", user); break;
			// Doom owns the live lock: a door record changes it here, with DaggerfallAction's rules (DFDoor.RunAction).
			case 16: if (door) door.RunAction(16); else DFActionRules.Request(self, "lock", user); break;
			case 17: if (door) door.RunAction(17); else DFActionRules.Request(self, "unlock", user); break;
			case 21: case 22: case 23: case 24: case 25: DFActionRules.Request(self, "damage", user); break;
			case 26: DFActionRules.Request(self, "poison", user); break;
			case 28: DFActionRules.Request(self, "magicka", user); break;
			case 29: DFActionRules.Request(self, "dialogue", user); break;
			case 31: DFActionRules.Request(self, "questvar", user); break;
			case 99: DFActionRules.Request(self, "doortext", user); break;
			default: DFActionRules.Request(self, "unknown", user); break;
		}
	}

	// Action 14 moves the player to the next object's position and facing.
	void Teleport(Actor user)
	{
		if (!nextAction || !user) return;
		user.SetOrigin(nextAction.pivot, false);
		user.angle = nextAction.yaw;
		user.vel = (0, 0, 0);
		user.FindFloorCeiling();
		if (user.pos.z < user.floorz) user.SetZ(user.floorz);
		user.ClearInterpolation();
	}

	// DFDoor.Toggle and TryUse call these in DaggerfallActionDoor's order (door trigger on the player's toggle, then
	// PlayerActivate's direct trigger). DaggerfallActionDoor.Open runs a first-activation DoorText record (with an
	// index and a Door, Direct or MultiTrigger trigger) before its lock check.
	override bool IsFirstDoorText() { return flag == 99 && index > 0 && activationCount == 0 && (trigger == TR_DOOR || trigger == TR_DIRECT || trigger == TR_MULTI); }
	override void DoorTrigger(Actor user) { Receive(user, FROM_DOOR); }
	override void DirectTrigger(Actor user) { Receive(user, FROM_DIRECT); }

	// Distance along a world ray to this object's box, or -1.
	double RayHit(vector3 origin, vector3 dir, double range)
	{
		vector3 a = ToLocal(origin), b = ToLocal(origin + dir * range), d = b - a;
		double t0 = 0, t1 = 1;
		for (int k = 0; k < 3; k++)
		{
			double o = k == 0 ? a.x : k == 1 ? a.y : a.z, v = k == 0 ? d.x : k == 1 ? d.y : d.z;
			double lo = (k == 0 ? boxMin.x : k == 1 ? boxMin.y : boxMin.z) - 2, hi = (k == 0 ? boxMax.x : k == 1 ? boxMax.y : boxMax.z) + 2;
			if (abs(v) < 1e-9) { if (o < lo || o > hi) return -1; continue; }
			double n = (lo - o) / v, f = (hi - o) / v;
			if (n > f) { double x = n; n = f; f = x; }
			t0 = max(t0, n); t1 = min(t1, f);
			if (t0 > t1) return -1;
		}
		return t0 * range;
	}

	// 0 no contact, FROM_WALKON standing on it, FROM_WALKINTO against its side.
	int Contact(Actor p)
	{
		// DaggerfallActionCollision counts walk-on only for a collider straight below the player's center, so a body beside a hung tile does not re-fire it.
		if (freeSwing)
		{
			foreach (c : cells)
				if (abs(p.pos.x - c.pos.x) <= c.radius && abs(p.pos.y - c.pos.y) <= c.radius && abs(p.pos.z - (c.pos.z + c.height)) <= 2)
					return FROM_WALKON;
			return 0;
		}
		vector3 l = ToLocal((p.pos.x, p.pos.y, p.pos.z + p.height / 2));
		double r = p.radius + 1, feet = l.z - p.height / 2, head = l.z + p.height / 2;
		if (l.x < boxMin.x - r || l.x > boxMax.x + r || l.y < boxMin.y - r || l.y > boxMax.y + r) return 0;
		if (feet > boxMax.z + 2 || head < boxMin.z - 1) return 0;
		bool over = l.x >= boxMin.x && l.x <= boxMax.x && l.y >= boxMin.y && l.y <= boxMax.y;
		// A static record can be a whole room model, so standing inside its box means walking on its floor.
		if (kind == 0 && over && p.pos.z <= p.floorz + 1) return FROM_WALKON;
		return over && feet >= boxMax.z - 2 ? FROM_WALKON : FROM_WALKINTO;
	}
}

class DFActionHandler : EventHandler
{
	Array<DFAction> actions;
	int lastButtons[MAXPLAYERS];

	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame || e.IsReopen || !DFDungeonData.OnDungeonMap()) return;
		SpawnFlats();
		SpawnLights();
		String body = DFDungeonData.Read("DFACTIONS");
		if (!body.Length()) return;

		Array<DFDoor> doors;
		let doorIt = ThinkerIterator.Create("DFDoor");
		DFDoor found;
		while (found = DFDoor(doorIt.Next())) doors.Push(found);

		Array<String> lines;
		body.Split(lines, "\n", TOK_SKIPEMPTY);
		double cellSize = 16;
		int cellCount = 0;
		foreach (text : lines)
		{
			Array<String> f;
			text.Split(f, " ", TOK_SKIPEMPTY);
			if (f[0] == "S") cellSize = f[1].ToDouble();
			else if (f[0] == "A" && f.Size() >= 34) actions.Push(Build(f, cellSize));
			else if (f[0] == "C")
			{
				let a = actions[f[1].ToInt()];
				let cell = DFActionCell(Actor.Spawn("DFActionCell", a.pivot, NO_REPLACE));
				cell.owner = a;
				cell.lx = f[2].ToDouble(); cell.ly = f[3].ToDouble(); cell.lz = f[4].ToDouble();
				// A thin panel gives its own half width. A flat trapdoor also gives its real thickness.
				cell.A_SetSize(f.Size() > 5 ? f[5].ToDouble() : cellSize / 2, f.Size() > 6 ? f[6].ToDouble() : cellSize, false);
				a.cells.Push(cell);
				cellCount++;
			}
		}
		int doorLinks = 0;
		foreach (a : actions)
		{
			if (a.nextId >= 0 && a.nextId < actions.Size()) a.nextAction = actions[a.nextId];
			if (a.doorId >= 0 && a.doorId < doors.Size())
			{
				a.door = doors[a.doorId];
				a.door.listener = a;
				doorLinks++;
			}
			a.Place(false);
		}
		{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFACTIONS loaded %d records, %d collision cells, %d door links", actions.Size(), cellCount, doorLinks); } // diagnostics: on screen only with dd_debugmessages
	}

	// DFDFLATS: texture x y z scaleX scaleY [npc id]. The center of the picture is on the position.
	void SpawnFlats()
	{
		String body = DFDungeonData.Read("DFDFLATS");
		if (!body.Length()) return;
		Array<String> rows;
		body.Split(rows, "\n", TOK_SKIPEMPTY);
		int spawned = 0, outside = 0, missing = 0;
		foreach (row : rows)
		{
			Array<String> f;
			row.Split(f, " ", TOK_SKIPEMPTY);
			if (f.Size() < 6) continue;
			vector3 at = (f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble());
			let flat = Actor.Spawn(f.Size() > 6 ? "DFDungeonNpc" : "DFDungeonFlat", at, NO_REPLACE);
			if (f.Size() > 6)
			{
				flat.args[1] = (f[6].Mid(0, 4).ToInt(16) << 16) | f[6].Mid(4, 4).ToInt(16);
				flat.args[0] = (f[6].Mid(8, 4).ToInt(16) << 16) | f[6].Mid(12, 4).ToInt(16);
			}
			flat.picnum = TexMan.CheckForTexture(f[0], TexMan.Type_Any);
			if (!flat.picnum.IsValid()) missing++;
			flat.scale = (f[4].ToDouble(), f[5].ToDouble());
			if (!level.IsPointInLevel(at))
			{
				outside++;
				let sec = level.PointInSector(at.xy);
				{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFFLATOUT %s %.0f %.0f %.0f sector %d floor %.0f ceiling %.0f", f[0], at.x, at.y, at.z, sec.Index(), sec.floorplane.ZAtPoint(at.xy), sec.ceilingplane.ZAtPoint(at.xy)); } // diagnostics: on screen only with dd_debugmessages
			}
			spawned++;
		}
		{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFDFLATS spawned %d billboards, %d outside a sector, %d missing textures", spawned, outside, missing); } // diagnostics: on screen only with dd_debugmessages
	}

	static double CVarOr(Name n, double fallback)
	{
		let v = CVar.FindCVar(n);
		return v ? v.GetFloat() : fallback;
	}

	// DFDLIGHTS: x y z range, one RDB light record each (RDBLayout.AddLight). The Dungeon light prefab is white at
	// intensity 0.8, and DaggerfallLight shrinks its range by up to one meter (75 map units) about 14 times a second.
	// dd_light_range turns Unity's steep falloff into Doom's linear one; dd_dungeon_light darkens the sectors so the
	// lights show, as Daggerfall Unity's dungeon ambient does. Both are engine cvars (dd_lights.cpp).
	void SpawnLights()
	{
		String body = DFDungeonData.Read("DFDLIGHTS");
		if (!body.Length() || CVarOr('dd_lights', 1) == 0) return;
		double scale = CVarOr('dd_light_range', 0.4);
		Array<String> rows;
		body.Split(rows, "\n", TOK_SKIPEMPTY);
		int spawned = 0;
		foreach (row : rows)
		{
			Array<String> f;
			row.Split(f, " ", TOK_SKIPEMPTY);
			if (f.Size() < 4) continue;
			let a = Actor.Spawn("DFDungeonLight", (f[0].ToDouble(), f[1].ToDouble(), f[2].ToDouble()), NO_REPLACE);
			double size = f[3].ToDouble() * scale / 2;	// a Doom light reaches twice its size
			a.A_AttachLight('ddlight', DynamicLight.RandomFlickerLight, Color(255, 255, 255), int(max(size - 75 * scale / 2, 1)), int(size),
				DynamicLight.LF_ATTENUATE, param: 3.0 / 360, intensity: 0.8);
			spawned++;
		}
		int ambient = int(CVarOr('dd_dungeon_light', 112));
		for (int i = 0; i < level.Sectors.Size(); i++) level.Sectors[i].SetLightLevel(ambient);
		{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "DFDLIGHTS spawned %d lights, sector light %d", spawned, ambient); } // diagnostics: on screen only with dd_debugmessages
	}

	DFAction Build(Array<String> f, double cellSize)
	{
		vector3 at = (f[8].ToDouble(), f[9].ToDouble(), f[10].ToDouble());
		let a = DFAction(Actor.Spawn("DFAction", at, NO_REPLACE));
		a.id = f[1].ToInt(); a.kind = f[2].ToInt(); a.flag = f[3].ToInt(); a.trigger = f[4].ToInt();
		a.nextId = f[5].ToInt(); a.doorId = f[6].ToInt();
		int visual = f[7].ToInt();
		String visualName = f[7].Left(1) == "_" ? f[7] : "";	// named by model or texture (runtime dungeons)
		a.pivot = at; a.yaw = f[11].ToDouble();
		a.travel = (f[12].ToDouble(), f[13].ToDouble(), f[14].ToDouble());
		a.spin = (f[15].ToDouble(), f[16].ToDouble(), f[17].ToDouble());
		int tics = f[18].ToInt();
		a.rate = tics > 0 ? 1.0 / tics : 1.0;
		a.forwardOnly = f[19].ToInt() != 0;
		a.center = (f[20].ToDouble(), f[21].ToDouble(), f[22].ToDouble());
		a.boxMin = (f[23].ToDouble(), f[25].ToDouble(), f[27].ToDouble());
		a.boxMax = (f[24].ToDouble(), f[26].ToDouble(), f[28].ToDouble());
		a.index = f[29].ToInt(); a.axis = f[30].ToInt(); a.magnitude = f[31].ToInt(); a.lockValue = f[32].ToInt();
		a.freeSwing = f[33].ToInt() != 0;
		if (f.Size() > 34) a.loadId = f[34].ToInt();
		a.cellHalf = cellSize / 2;
		if (visual >= 0)
		{
			class<Actor> type = visualName.Length() ? (a.kind == 2 ? "DFActionFlat" : "DFActionVisual") .. visualName : String.Format(a.kind == 2 ? "DFActionFlat%d" : "DFActionVisual%d", visual);
			if (type) a.visual = Actor.Spawn(type, at, NO_REPLACE);
		}
		return a;
	}

	// The nearest action object on the player's aim, not behind a wall.
	DFAction Aimed(PlayerPawn p, double range)
	{
		vector3 eye = (p.pos.x, p.pos.y, p.player.viewz);
		double cp = cos(p.pitch);
		vector3 dir = (cos(p.angle) * cp, sin(p.angle) * cp, -sin(p.pitch));
		FLineTraceData hit;
		p.LineTrace(p.angle, range, p.pitch, TRF_THRUACTORS, p.player.viewz - p.pos.z, 0, 0, hit);
		double limit = hit.HitType == TRACE_HitNone ? range : hit.Distance + 2;
		DFAction best = null;
		double bestAt = limit;
		foreach (a : actions)
		{
			if (a.door) continue; // doors take their use through DFDoor.TryUse
			double d = a.RayHit(eye, dir, range);
			if (d >= 0 && d <= bestAt) { best = a; bestAt = d; }
		}
		return best;
	}

	bool UseFrom(PlayerPawn p)
	{
		let a = Aimed(p, p.UseRange);
		if (!a) return false;
		a.Receive(p, DFAction.FROM_DIRECT);
		return true;
	}

	void TouchFrom(PlayerPawn p)
	{
		foreach (a : actions)
		{
			if (a.trigger != DFAction.TR_WALKON && a.trigger != DFAction.TR_WALKINTO && a.trigger != DFAction.TR_MULTI && a.trigger != DFAction.TR_COLLIDE9) continue;
			if (a.touchCooldown > 0) continue;
			int touch = a.Contact(p);
			if (touch == 0) continue;
			a.touchCooldown = 4; // DaggerfallActionCollision.Timeout, 0.12 s
			a.Receive(p, touch);
		}
	}

	override void WorldTick()
	{
		if (actions.Size() == 0) return;
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || !players[i].mo) continue;
			let p = players[i].mo;
			int buttons = players[i].cmd.buttons;
			int pressed = buttons & ~lastButtons[i];
			lastButtons[i] = buttons;
			if (pressed & BT_USE) UseFrom(p);
			if (pressed & BT_ATTACK)
			{
				let a = Aimed(p, p.UseRange);
				if (a) a.Receive(p, DFAction.FROM_ATTACK);
			}
			// As in Daggerfall, touching counts only while the player is actively moving.
			if (players[i].cmd.forwardmove != 0 || players[i].cmd.sidemove != 0 || p.vel.xy.Length() > 0.5) TouchFrom(p);
		}
	}
}
