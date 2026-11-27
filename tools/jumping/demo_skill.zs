// Demo only (packed into the review folder's jump_demo.pk3 by make_demo.py): the console command
// "netevent jumpskill:<0-100>" makes DoomerfallJump use that Jumping value, and "netevent jumpskill:-1" goes back to
// the character's real skill. Daggerfall's character sheet is not changed.
class DoomerfallJumpDemo : StaticEventHandler
{
	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name.Left(10) != "jumpskill:") return;
		let j = DoomerfallJump(StaticEventHandler.Find("DoomerfallJump"));
		if (!j) return;
		j.testSkill = clamp(e.Name.Mid(10).ToInt(), -1, 100);
		if (j.testSkill >= 0) Console.Printf("Jumping set to %d for this demo", j.testSkill);
		else Console.Printf("Jumping follows your character again (%d)", j.skill);
	}
}
