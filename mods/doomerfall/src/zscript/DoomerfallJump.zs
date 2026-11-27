// Jumping on generated Daggerfall maps: Daggerfall's falling damage and the Jumping skill's effects
// (owner rules in work/backlog/skills-in-doom.md and the skillperks jumping card).
// In:  "dfi_rules:<0|1>" (dd_items.cpp: 1 on a generated Daggerfall map in a bridge session), the Jumping skill's
//      permanent value from Daggerfall's character sheet (Actor.DD_SheetSkillBase; perks follow the base value), and
//      the player's input and position.
// Out: the player's JumpZ, extra jumps in mid-air, and falling damage (a normal Doom hit, which the bridge reports to
//      Daggerfall, so Daggerfall applies it to its own HP).
// Falling damage is Daggerfall's rule (PlayerHealth.ApplyPlayerFallDamage and AcrobatMotor.CheckFallingDamage):
// the fall is measured from where the player left the ground to where they land, and every metre past 5 costs 5 HP.
// So a jump that lands where it started, double and triple jumps included, never hurts.
// Jumping skill: jump height +1% per point to +100% at 100, plus 25% from 25 on; one extra jump in mid-air at 50,
// two at 100; no falling damage from 75. Below 75 Jumping does not reduce falling damage (the owner has not chosen a
// curve yet). Nothing here runs unless the engine sends dfi_rules:1 and Daggerfall has a character, so Doom maps
// and Doom-only games are unchanged.
class DoomerfallJumpState
{
	bool airborne;
	double groundZ;    // height of the last ground the player stood on
	double fallStartZ; // where this fall is measured from
	int airJumpsLeft;
	bool wasNoGravity;
	Vector3 lastPos;
}

class DoomerfallJump : StaticEventHandler
{
	const JumpingSlot = 3;         // DFCareer.Skills.Jumping
	const UnitsPerMetre = 30.0;    // Doom maps are Daggerfall's layout at 75%, and Daggerfall has 40 units per metre
	const FallThreshold = 5.0;     // Daggerfall: metres of fall that do no damage
	const HPPerMetre = 5.0;        // Daggerfall: HP per metre past the threshold
	const SkillEvery = 8;          // tics between reads of the skill

	bool rules;
	int skill;                     // Jumping's permanent value, or -1 without a Daggerfall character
	int testSkill;                 // set only by tools/jumping (test probe, demo pk3); -1 means unused
	DoomerfallJumpState st[MAXPLAYERS];

	override void OnRegister() { skill = -1; testSkill = -1; }

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) == "dfi_rules:") rules = e.Name.Mid(10) == "1";
	}

	override void WorldLoaded(WorldEvent e)
	{
		for (int i = 0; i < MAXPLAYERS; i++) st[i] = null;
	}

	clearscope int JumpSkill() const { return testSkill >= 0 ? testSkill : skill; }
	clearscope bool Active() const { return rules && JumpSkill() >= 0; }

	// Jump height multiplier: linear to +100% at 100, plus a 25% spike from 25 on.
	clearscope static double HeightFactor(int s)
	{
		s = clamp(s, 0, 100);
		return 1.0 + s / 100.0 + (s >= 25 ? 0.25 : 0.0);
	}
	clearscope static int AirJumps(int s) { return s >= 100 ? 2 : s >= 50 ? 1 : 0; }
	clearscope static bool FallImmune(int s) { return s >= 75; }

	// Daggerfall's falling damage for a fall of this many Doom units, before the Jumping skill.
	clearscope static int FallDamage(double units)
	{
		double metres = units / UnitsPerMetre;
		return metres > FallThreshold ? int(HPPerMetre * (metres - FallThreshold)) : 0;
	}

	override void WorldTick()
	{
		if (level.maptime % SkillEvery == 0) skill = Actor.DD_SheetSkillBase(JumpingSlot);
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i]) continue;
			let mo = players[i].mo;
			if (!mo) continue;
			// Jump height is velocity squared, so the height factor's square root scales the jump velocity.
			double jumpZ = Active() ? mo.default.JumpZ * sqrt(HeightFactor(JumpSkill())) : mo.default.JumpZ;
			if (mo.JumpZ != jumpZ) mo.JumpZ = jumpZ;
			if (!Active()) { st[i] = null; continue; }
			if (!st[i]) { st[i] = new("DoomerfallJumpState"); Reset(mo, st[i]); }
			Think(players[i], mo, st[i]);
			st[i].wasNoGravity = mo.bNoGravity;
			st[i].lastPos = mo.pos;
		}
	}

	void Reset(PlayerPawn mo, DoomerfallJumpState s)
	{
		s.airborne = false;
		s.groundZ = mo.pos.z;
		s.fallStartZ = mo.pos.z;
		s.lastPos = mo.pos;
	}

	void Think(PlayerInfo p, PlayerPawn mo, DoomerfallJumpState s)
	{
		// A teleport or a map window shift moves the player farther in one tic than their speed allows. As in
		// Daggerfall's transitions, the fall starts over from the new place.
		double moved = (mo.pos - s.lastPos).Length();
		bool jumped = moved > mo.vel.Length() * 2 + 64;
		// Not falling: dead, flying, no-clipping, held on a climb (no gravity), or in water (Daggerfall: no falling
		// damage on landing in water).
		if (jumped || p.health <= 0 || p.playerstate != PST_LIVE || (p.cheats & CF_NOCLIP2) || mo.bFly || mo.bNoGravity ||
			mo.waterlevel > 0)
		{
			Reset(mo, s);
			if (jumped) s.airborne = mo.pos.z > mo.floorz && !mo.bOnMobj;
			return;
		}

		bool grounded = mo.pos.z <= mo.floorz || mo.bOnMobj;
		if (grounded)
		{
			if (s.airborne) Land(p, mo, s);
			s.airborne = false;
			s.groundZ = mo.pos.z;
			s.airJumpsLeft = AirJumps(JumpSkill());
			return;
		}
		if (!s.airborne)
		{
			s.airborne = true;
			s.fallStartZ = s.groundZ;
		}
		if ((p.cmd.buttons & BT_JUMP) && !(p.oldbuttons & BT_JUMP)) AirJump(p, mo, s);
	}

	void Land(PlayerInfo p, PlayerPawn mo, DoomerfallJumpState s)
	{
		double fell = s.fallStartZ - mo.pos.z;
		int damage = FallDamage(fell);
		if (damage > 0 && FallImmune(JumpSkill()))
		{
			DDLog.Debug(String.Format("DFJUMP land fell=%.1f damage=0 (immune, Jumping %d)", fell, JumpSkill()));
			return;
		}
		if (fell > UnitsPerMetre) DDLog.Debug(String.Format("DFJUMP land fell=%.1f damage=%d Jumping=%d", fell, damage, JumpSkill()));
		if (damage > 0) mo.DamageMobj(null, null, damage, 'Falling', DMG_NO_ARMOR | DMG_NO_FACTOR | DMG_NO_PROTECT | DMG_NO_ENHANCE);
	}

	// One more jump in mid-air, at the same strength as a jump from the ground.
	void AirJump(PlayerInfo p, PlayerPawn mo, DoomerfallJumpState s)
	{
		if (s.airJumpsLeft <= 0 || s.wasNoGravity || p.crouchoffset != 0 || mo.waterlevel >= 2 || !level.IsJumpingAllowed()) return;
		s.airJumpsLeft--;
		mo.vel.z = mo.JumpZ * 35 / TICRATE;
		mo.bOnMobj = false;
		mo.A_StartSound("*jump", CHAN_BODY);
		DDLog.Debug(String.Format("DFJUMP air jump z=%.1f left=%d", mo.pos.z, s.airJumpsLeft));
	}
}
