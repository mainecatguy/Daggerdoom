version "4.10"

// Harness for rules_test.py: prints every value of Doom's shared rules (mods/doomerfall/src/zscript/DoomerfallRules.zs)
// over the whole input range, so the script can compare them with the formulas they replaced.
class RulesTest : EventHandler
{
	override void WorldLoaded(WorldEvent e)
	{
		for (int r = 0; r < DoomerfallRules.RuleCount; r++)
			for (int s = -5; s <= 105; s++)
				Console.Printf("RULESTEST perk %d %d %d", r, s, DoomerfallRules.Compute(r, s));
		for (int r = 0; r < DoomerfallRules.RuleCount; r++)
			Console.Printf("RULESTEST get %d %d", r, DoomerfallRules.Get(r)); // no bridge: every rule off
		for (int v = -1; v <= 100; v++)
			Console.Printf("RULESTEST attr %d %.6f %.6f %.6f %.6f %.6f %.6f %.6f", v, DoomerfallRules.StrengthMeleeFactor(v), DoomerfallRules.SpeedFactor(v),
				DoomerfallRules.AgilityHandlingBonus(v), DoomerfallRules.StrengthGunFactor(v), DoomerfallRules.AgilityGunFactor(v, false),
				DoomerfallRules.AgilityGunFactor(v, true), DoomerfallRules.LuckCritChance(v));
		for (int s = -5; s <= 105; s++)
			Console.Printf("RULESTEST jump %d %.6f %d %.6f", s, DoomerfallRules.JumpHeightFactor(s), DoomerfallRules.AirJumps(s),
				DoomerfallRules.SafeFall(DoomerfallRules.JumpHeight(8 * sqrt(DoomerfallRules.JumpHeightFactor(s)), 1)));
		for (int u = 0; u <= 1200; u += 3)
			Console.Printf("RULESTEST fall %d %d %d", u, DoomerfallRules.FallDamage(u, 54), DoomerfallRules.FallDamage(u, 117));
		static const double hj[] = { 8, 9.5, 12, 0, 8 };
		static const double hg[] = { 1, 1, 1, 1, 0.5 };
		for (int i = 0; i < hj.Size(); i++)
			Console.Printf("RULESTEST height %.2f %.2f %.6f", hj[i], hg[i], DoomerfallRules.JumpHeight(hj[i], hg[i]));
		static const int lucks[] = { -1, 0, 1, 25, 50, 99, 100, 101, 150 };
		for (int i = 0; i < lucks.Size(); i++)
		{
			String bits = "";
			for (int k = 0; k <= 600; k++) bits = bits .. (DoomerfallRules.LuckAmmoDrop(lucks[i], k / 1000.0) ? "1" : "0");
			Console.Printf("RULESTEST luck %d %s", lucks[i], bits);
		}
		Console.Printf("RULESTEST stat %d %d", DoomerfallRules.Stat(DoomerfallRules.StatAgility), DoomerfallRules.HasCharacter());
		Console.Printf("RULESTEST done");
	}
}
