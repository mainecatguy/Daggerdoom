// Jumping on generated Daggerfall maps: Daggerfall's falling damage and the Jumping skill's effects
// (owner rules in work/backlog/skills-in-doom.md and the skillperks jumping card).
// In:  "dfi_rules:<0|1>" (dd_items.cpp: 1 on a generated Daggerfall map in a bridge session), the Jumping skill's
//      permanent value from Daggerfall's character sheet (Actor.DD_SheetSkillBase; perks follow the base value), and
//      the player's input and position.
// Out: the player's JumpZ, extra jumps in mid-air, and falling damage (a normal Doom hit, which the bridge reports to
//      Daggerfall, so Daggerfall applies it to its own HP).
// The numbers are Doom's shared rules (DoomerfallRules.zs: FallDamage, JumpHeightFactor, AirJumps, FallImmune).
// Falling damage is Daggerfall's rule (PlayerHealth.ApplyPlayerFallDamage and AcrobatMotor.CheckFallingDamage):
// the fall is measured from where the player left the ground to where they land, and every metre past 5 costs 5 HP.
// So a jump that lands where it started, double and triple jumps included, never hurts. Daggerfall's two exemptions
// come over the bridge (Actor.DD_PlayerFlags, DoomerfallFallState.cs): while Slowfall is active the fall starts over
// every tic, and a landing outdoors on a water tile does no damage.
// Jumping skill: jump height +1% per point to +100% at 100, plus 25% from 25 on; one extra jump in mid-air at 50,
// two at 100; no falling damage from 75. Below 75 Jumping does not reduce falling damage (the owner has not chosen a
// curve yet). Nothing here runs unless the engine sends dfi_rules:1 and Daggerfall has a character, so Doom maps
// and Doom-only games are unchanged (JumpZ is not touched there).
class DoomerfallJumpState
{
	bool airborne;
	double groundZ;    // height of the last ground the player stood on
	double fallStartZ; // where this fall is measured from
	int airJumpsLeft;
	bool wasNoGravity;
	Vector3 lastPos;
	Vector3 lastVel;   // velocity at the end of the last tic, which the move since then used
}

class DoomerfallJump : StaticEventHandler
{
	const JumpingSlot = DoomerfallRules.SkillJumping;
	const UnitsPerMetre = DoomerfallRules.UnitsPerMetre;
	const SkillEvery = 8;          // tics between reads of the skill
	const FlagSlowfall = 1;        // DFB_PLF_SLOWFALL
	const FlagOutdoorWater = 2;    // DFB_PLF_OUTDOOR_WATER

	bool rules;
	int skill;                     // Jumping's permanent value, or -1 without a Daggerfall character
	int testSkill;                 // set only by tools/jumping (test probe, demo pk3); -1 means unused
	DoomerfallJumpState st[MAXPLAYERS];
	// JumpZ: this handler writes it only while active, and only scales what it found, so a map's or mod's own change
	// is kept. jumpZSet is the value it last wrote; anything else in JumpZ is someone else's base.
	bool jumpZScaled[MAXPLAYERS];
	double jumpZBase[MAXPLAYERS], jumpZSet[MAXPLAYERS];

	override void OnRegister() { skill = -1; testSkill = -1; }

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) == "dfi_rules:") rules = e.Name.Mid(10) == "1";
	}

	override void WorldLoaded(WorldEvent e)
	{
		// A loaded save or snapshot brings its own pawn and JumpZ: forget what was written to the old one.
		for (int i = 0; i < MAXPLAYERS; i++) { st[i] = null; jumpZScaled[i] = false; }
	}

	clearscope int JumpSkill() const { return testSkill >= 0 ? testSkill : skill; }
	clearscope bool Active() const { return rules && JumpSkill() >= 0; }

	override void WorldTick()
	{
		if (level.maptime % SkillEvery == 0) skill = Actor.DD_SheetSkillBase(JumpingSlot);
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i]) continue;
			let mo = players[i].mo;
			if (!mo) continue;
			ScaleJumpZ(i, mo);
			if (!Active()) { st[i] = null; continue; }
			if (!st[i]) { st[i] = new("DoomerfallJumpState"); Reset(mo, st[i]); }
			Think(players[i], mo, st[i]);
			st[i].wasNoGravity = mo.bNoGravity;
			st[i].lastPos = mo.pos;
			st[i].lastVel = mo.vel;
		}
	}

	// Jump height is velocity squared, so the height factor's square root scales the jump velocity.
	void ScaleJumpZ(int i, PlayerPawn mo)
	{
		if (!Active())
		{
			// Put back what was there, once, unless someone else has written JumpZ since.
			if (jumpZScaled[i] && mo.JumpZ == jumpZSet[i]) mo.JumpZ = jumpZBase[i];
			jumpZScaled[i] = false;
			return;
		}
		double scale = sqrt(DoomerfallRules.JumpHeightFactor(JumpSkill()));
		if (!jumpZScaled[i])
		{
			// A loaded save holds the value written at the Jumping level it was saved with, which may differ from
			// now: recognize the default scaled at any level so it is not scaled twice. Any other value is the base
			// (the default, or a map's or mod's own change).
			jumpZBase[i] = ScaledDefault(mo) ? mo.default.JumpZ : mo.JumpZ;
			jumpZScaled[i] = true;
		}
		else if (mo.JumpZ != jumpZSet[i]) jumpZBase[i] = mo.JumpZ; // someone else wrote JumpZ: that is the new base
		jumpZSet[i] = jumpZBase[i] * scale;
		if (mo.JumpZ != jumpZSet[i]) mo.JumpZ = jumpZSet[i];
	}

	static bool ScaledDefault(PlayerPawn mo)
	{
		for (int k = 0; k <= 100; k++)
			if (abs(mo.JumpZ - mo.default.JumpZ * sqrt(DoomerfallRules.JumpHeightFactor(k))) < 1e-6) return true;
		return false;
	}

	void Reset(PlayerPawn mo, DoomerfallJumpState s)
	{
		s.airborne = false;
		s.groundZ = mo.pos.z;
		s.fallStartZ = mo.pos.z;
		s.lastPos = mo.pos;
		s.lastVel = mo.vel;
	}

	void Think(PlayerInfo p, PlayerPawn mo, DoomerfallJumpState s)
	{
		// A teleport or a map window shift moves the player farther in one tic than their speed allows. As in
		// Daggerfall's transitions, the fall starts over from the new place.
		double moved = (mo.pos - s.lastPos).Length();
		// The move used last tic's velocity (a landing has already zeroed vel.z), plus gravity.
		bool jumped = moved > max(s.lastVel.Length(), mo.vel.Length()) * 2 + 64;
		// Not falling: dead, flying, no-clipping, held on a climb (no gravity), or in water (Daggerfall: no falling
		// damage on landing in water). Daggerfall's outdoor sea and lakes have no water volume in Doom's maps; Daggerfall's
		// outdoor water flag covers them in Land.
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
			s.airJumpsLeft = DoomerfallRules.AirJumps(JumpSkill());
			return;
		}
		if (!s.airborne)
		{
			s.airborne = true;
			s.fallStartZ = s.groundZ;
		}
		// Daggerfall: Slowfall restarts the fall every frame, so only the part after it ends can hurt.
		if (Actor.DD_PlayerFlags() & FlagSlowfall) s.fallStartZ = mo.pos.z;
		if ((p.cmd.buttons & BT_JUMP) && !(p.oldbuttons & BT_JUMP)) AirJump(p, mo, s);
	}

	void Land(PlayerInfo p, PlayerPawn mo, DoomerfallJumpState s)
	{
		double fell = s.fallStartZ - mo.pos.z;
		int damage = DoomerfallRules.FallDamage(fell);
		if (damage > 0 && DoomerfallRules.FallImmune(JumpSkill()))
		{
			DDLog.Debug(String.Format("DFJUMP land fell=%.1f damage=0 (immune, Jumping %d)", fell, JumpSkill()));
			return;
		}
		if (damage > 0 && (Actor.DD_PlayerFlags() & FlagOutdoorWater))
		{
			DDLog.Debug(String.Format("DFJUMP land fell=%.1f damage=0 (outdoor water)", fell));
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
