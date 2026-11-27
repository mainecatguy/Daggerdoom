// Save/load check for DoomerfallJump's jump height (run by jumpz_saveload.py). It turns the handler on the way a
// Daggerfall map in a bridge session does (rules, plus a Jumping value through the testSkill hook), logs the player's
// JumpZ, and in the save run makes an autosave. The runner then loads that save in new launches at other Jumping
// values: JumpZ must be the default scaled for the new value, never scaled twice.
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
		if (count == 45 && "@MODE@" == "save") level.MakeAutoSave();
		if (count == 90) Console.Printf("JZDONE");
	}
}
