// The fire look for burning monsters (DoomerfallBurn.zs). Purely visual: the flames never deal damage or block.
// A light cut of the Schism mod's burn effect (its FlameTrails flame, sprites DDBF = Schism FRPR, art/README.md):
// short flames rise off the body, more on bigger monsters, sized to the monster. No flares, smoke, or damage
// actors. Chosen over engine particles (barely visible) and the Arch-vile flame (Doom II only, hides small monsters)
// with screenshots and frame times: work/notes/20261127-134921.md.
// Off with dd_burn_look 0; the burn damage keeps running.
class DoomerfallBurnFlame : Actor
{
	Default
	{
		+NOINTERACTION
		+NOBLOCKMAP
		+NOGRAVITY
		+NOTONAUTOMAP
		RenderStyle "Add";
		Scale 0.5;
	}
	States
	{
	Spawn:
		DDBF ABCDEFGH 3 Bright;
		Stop;
	}
}

class DoomerfallBurnLook play
{
	static bool Enabled()
	{
		let c = CVar.FindCVar("dd_burn_look");
		return !c || c.GetBool();
	}

	static void Draw(Actor v)
	{
		// Every 4 tics, staggered per monster so a pack does not pulse in step. Each flame lives 24 tics.
		if ((Level.maptime + v.SpawnTime) % 4 != 0) return;
		double r = v.radius * 0.7;
		double h = v.height;
		double s = 0.5 * clamp(h / 56.0, 0.6, 1.6);
		// One flame per ZombieMan-sized area (20 x 56), up to 4.
		int n = clamp(int(v.radius * h / 1120.0 + 0.5), 1, 4);
		for (int k = 0; k < n; k++)
		{
			let f = Actor.Spawn("DoomerfallBurnFlame",
				v.Vec3Offset(FRandom[DoomerfallBurnLook](-r, r), FRandom[DoomerfallBurnLook](-r, r), FRandom[DoomerfallBurnLook](h * 0.15, h * 0.75)), NO_REPLACE);
			if (!f) continue;
			f.scale = (s, s);
			f.vel = (v.vel.x + FRandom[DoomerfallBurnLook](-0.4, 0.4), v.vel.y + FRandom[DoomerfallBurnLook](-0.4, 0.4), FRandom[DoomerfallBurnLook](1.0, 2.0));
		}
	}
}
