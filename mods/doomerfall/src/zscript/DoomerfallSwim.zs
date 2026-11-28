// Daggerfall's outdoor swimming in Doom (owner, 2026-11-27, Q&A item 59: "implement them as daggerfall").
// Daggerfall owns the rule and the shoreline: it reports the water tile under the player (DFB_PLF_OUTDOOR_WATER, its
// own tilemap, towns included) and Water Walking. dd_bridge.cpp decides from those whether the player swims
// (Actor.DD_OutdoorSwimming: on the open ground over a water tile, not flying, no Water Walking). While swimming, as in
// Daggerfall Unity:
//   - movement speed is multiplied by 1/4 + Swimming / 200 (PlayerSpeedChanger.GetSwimSpeed: 25% at Swimming 0, 75%
//     at 100), on top of every other speed factor;
//   - the eye drops to Daggerfall's swimming eye height, 0.21 m of the standing 1.71 m (PlayerHeightChanger:
//     controllerSwimHeight 0.30 m, eye 0.09 m below the top), over Daggerfall's 0.1 s;
//   - jumping and resting are refused (AcrobatMotor.HandleJumpInput, DaggerfallUI's rest check); transport is not.
// Daggerfall tallies Swimming and charges its swimming fatigue from the swim state Doom reports
// (dfb_uz_state.player_motion -> DoomerfallSwimState.cs). Breath never runs down outdoors, as in Daggerfall, whose
// outdoor water is a surface. The collision height is unchanged, so swimming does not change how shots hit the player.
// Without a Daggerfall character the item is never given, so stock Doom and plain WADs are unchanged.

class DoomerfallSwimEffects : Inventory
{
	const SwimmingSkill = 17;            // DFCareer.Skills.Swimming
	const EyeRatio = 0.21 / 1.71;        // Daggerfall's swimming eye height over its standing eye height
	const EyeStep = (1 - EyeRatio) / 3;  // about Daggerfall's 0.1 s camera move

	bool swimming;
	double eye;                          // the share of the standing eye height in use; 0 until first set

	Default
	{
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
		Inventory.MaxAmount 1;
	}

	override double GetSpeedFactor()
	{
		if (!swimming) return 1;
		int skill = max(0, Actor.DD_SheetSkill(SwimmingSkill));
		return 0.25 + skill / 200.0;
	}

	// Once per tic, before the players move.
	void Update(PlayerInfo p, PlayerPawn mo)
	{
		bool now = Actor.DD_OutdoorSwimming();
		if (now != swimming)
			DDLog.Debug(String.Format("DFSWIM %s Swimming=%d speed=%.3f", now ? "start" : "stop", Actor.DD_SheetSkill(SwimmingSkill),
				now ? 0.25 + max(0, Actor.DD_SheetSkill(SwimmingSkill)) / 200.0 : 1.0));
		swimming = now;
		if (swimming) p.cmd.buttons &= ~BT_JUMP;

		if (p.health <= 0 || p.playerstate != PST_LIVE) return; // leave Doom's death view alone
		if (eye <= 0) eye = 1;
		double target = swimming ? EyeRatio : 1.0;
		if (eye == target) return;
		eye = eye < target ? min(target, eye + EyeStep) : max(target, eye - EyeStep);
		mo.ViewHeight = mo.Default.ViewHeight * eye;
		// Doom's view only snaps down to ViewHeight by itself (PlayerPawn.CalcHeight), so it is set both ways here.
		p.viewheight = mo.ViewHeight * p.crouchfactor;
		p.crouchviewdelta = p.viewheight - mo.ViewHeight;
		p.deltaviewheight = 0;
	}
}

class DoomerfallSwim : EventHandler
{
	// Its WorldTick runs after the other handlers' (they are called in Order), so a jump another handler adds is refused too.
	override void OnRegister() { SetOrder(1000); }

	override void WorldTick()
	{
		if (Actor.DD_SheetStat(0) < 0 || !playeringame[consoleplayer]) return;
		let mo = players[consoleplayer].mo;
		if (!mo) return;
		let fx = DoomerfallSwimEffects(mo.FindInventory("DoomerfallSwimEffects"));
		if (!fx)
		{
			mo.GiveInventory("DoomerfallSwimEffects", 1);
			fx = DoomerfallSwimEffects(mo.FindInventory("DoomerfallSwimEffects"));
		}
		if (fx) fx.Update(players[consoleplayer], mo);
	}
}
