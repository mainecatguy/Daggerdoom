// Doomerfall test only (-dfdamagetest <multiplier>): forces the published damage bonus, for example 2 for +100%,
// so a Doom harness can show that a non-zero bonus changes the damage the player deals.

using System;
using System.Globalization;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallDamageBonusTest
    {
        public static void Apply(DoomerfallBridge bridge, DoomerfallDamageBonus bonus, string[] args)
        {
            int i = Array.IndexOf(args, "-dfdamagetest");
            double m;
            if (i < 0 || i + 1 >= args.Length ||
                !double.TryParse(args[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out m))
                return;
            bonus.TestMultiplier = m;
            bridge.LogLine(string.Format(CultureInfo.InvariantCulture, "damage test: multiplier forced to {0}", m));
        }
    }
}
