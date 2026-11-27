// The fire look for burning monsters (DoomerfallBurn.zs). Purely visual: no damage, no actors, no thinkers.
// Particles (A_SpawnParticle) in fire colours rise over the monster's body: they work on any monster, need no mod
// sprites (works without DRLA), and cost far less than one flame actor per monster, so hundreds can burn at once.
// Off with dd_burn_look 0; the burn damage keeps running.
class DoomerfallBurnLook play
{
	static bool Enabled()
	{
		let c = CVar.FindCVar("dd_burn_look");
		return !c || c.GetBool();
	}

	static void Draw(Actor v)
	{
		// One particle every 3 tics (about 7 alive per monster), staggered per monster so a pack does not pulse in step.
		if ((Level.maptime + v.SpawnTime) % 3 != 0) return;
		double r = v.radius * 0.8;
		double h = v.height;
		{
			int colour = Random[DoomerfallBurnLook](0, 2);
			Color c = colour == 0 ? Color(255, 255, 160, 0) : (colour == 1 ? Color(255, 255, 80, 0) : Color(255, 255, 220, 60));
			v.A_SpawnParticle(c, SPF_FULLBRIGHT | SPF_RELATIVE, Random[DoomerfallBurnLook](18, 30),
				FRandom[DoomerfallBurnLook](3, 6),
				0,
				FRandom[DoomerfallBurnLook](-r, r), FRandom[DoomerfallBurnLook](-r, r), FRandom[DoomerfallBurnLook](0, h * 0.8),
				FRandom[DoomerfallBurnLook](-0.3, 0.3), FRandom[DoomerfallBurnLook](-0.3, 0.3), FRandom[DoomerfallBurnLook](0.8, 1.6),
				0, 0, 0.02, 1.0, -1, -0.1);
		}
	}
}
