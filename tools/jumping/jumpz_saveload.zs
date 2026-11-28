// Save/load check for DoomerfallJump's jump height (run by jumpz_saveload.py). It turns the handler on the way a
// Daggerfall map in a bridge session does (rules, plus a Jumping value through the testSkill hook), logs the player's
// JumpZ, and in the save run makes an autosave. The runner then loads that save in new launches at other Jumping
// values: JumpZ must be the default scaled for the new value, never scaled twice. Mode "oldsave" makes the save the way
// an older jump formula would have: the handler is turned off and JumpZ set to a value no current Jumping level gives
// (the default x @OLDFACTOR@); a load must still recalculate JumpZ from the Jumping value (jumpfollowup 01, Q&A item 71).
class DoomerfallJumpZSaveLoad : StaticEventHandler
{
	int count;

	override void WorldTick()
	{
		count++;
		let j = DoomerfallJump(StaticEventHandler.Find("DoomerfallJump"));
		let mo = players[consoleplayer].mo;
		if (!j || !mo) return;
		if (count == 5) { j.rules = true; j.testSkill = @SKILL@; }
		if (count == 40)
			Console.Printf("JZTEST mode=@MODE@ skill=%d jumpz=%.4f default=%.4f class=%s", j.testSkill, mo.JumpZ,
				mo.default.JumpZ, mo.GetClassName());
		if (count == 41 && "@MODE@" == "oldsave") { j.rules = false; j.testSkill = -1; }
		if (count == 43 && "@MODE@" == "oldsave")
		{
			mo.JumpZ = mo.default.JumpZ * @OLDFACTOR@;
			Console.Printf("JZTEST oldsave wrote jumpz=%.4f", mo.JumpZ);
		}
		if (count == 45 && ("@MODE@" == "save" || "@MODE@" == "oldsave")) level.MakeAutoSave();
		if (count == 90) Console.Printf("JZDONE");
	}
}
