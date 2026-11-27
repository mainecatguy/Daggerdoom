// Doomerfall: the character sheet's attribute popup (left-click an attribute) explains what the attribute does in
// Doomerfall, with its formula and the player's own result, under Daggerfall's own text (owner, 2026-11-26).
// Only in a bridge session, where the rules apply; elsewhere the popup is Daggerfall's alone.
//
// The text mirrors the rules where they are built. Keep it in step when a rule changes:
//   Strength   mods/doomerfall/src/zscript/DoomerfallAttributes.zs   melee damage x (1 + STR / 100)
//   Willpower  UZDoom/src/dd_bridge.cpp DD_BridgeWillpowerDamage      damage taken x (300 - WIL) / 250, applied last
//   Agility    mods/doomerfall/src/zscript/DoomerfallAgility.zs      reload/switch x (1 + 0.4 AGI / 100), evade 15% AGI / 100
//   Endurance  DoomerfallEndurance.MaxHealth                         50 + END + (level - 1) x END / 15
//   Speed      mods/doomerfall/src/zscript/DoomerfallAttributes.zs   move speed x (0.75 + SPD / 200)
//   Luck       mods/doomerfall/src/zscript/DoomerfallAmmo.zs LuckDrop each monster ammo drop: Luck in 100 for a second one
// All use the live value (fortify and drain count). Every one but Endurance counts values above 100 as 100.

using System;
using System.Collections.Generic;
using System.Globalization;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallAttributeHelp
    {
        /// <summary>Test only: show the Doomerfall lines without a bridge session (DoomerfallAttributeHelpTest).</summary>
        internal static bool ShowWithoutSession;

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        /// <summary>
        /// Fills the attribute popup with Daggerfall's text for textId followed by the Doomerfall lines. Returns false,
        /// changing nothing, outside a bridge session or for an id that is no attribute's, so the caller shows
        /// Daggerfall's text as before.
        /// </summary>
        internal static bool SetText(DaggerfallMessageBox box, int textId, PlayerEntity player)
        {
            if ((!DoomerfallBridge.SessionActive && !ShowWithoutSession) || box == null || player == null)
                return false;
            TextFile.Token[] tokens = Build(textId, player);
            if (tokens == null)
                return false;
            box.SetTextTokens(tokens, null, false); // already expanded: the Doomerfall lines hold '%' signs
            return true;
        }

        /// <summary>Daggerfall's expanded text for the attribute's popup with the Doomerfall lines added, or null.</summary>
        internal static TextFile.Token[] Build(int textId, PlayerEntity player)
        {
            DFCareer.Stats stat;
            if (!StatFor(textId, out stat))
                return null;
            TextFile.Token[] tokens = DaggerfallUnity.Instance.TextProvider.GetRSCTokens(textId);
            if (tokens == null)
                return null;
            MacroHelper.ExpandMacros(ref tokens, player.Stats);

            var list = new List<TextFile.Token>(tokens);
            int last = list.Count - 1;
            while (last >= 0 && list[last].formatting == TextFile.Formatting.EndOfRecord)
                list.RemoveAt(last--);
            // Classic text ends each line with a justify token; the new lines reuse it so they line up with the rest.
            TextFile.Formatting lineEnd = TextFile.Formatting.JustifyCenter;
            if (last >= 0 && (list[last].formatting == TextFile.Formatting.JustifyCenter || list[last].formatting == TextFile.Formatting.JustifyLeft))
                lineEnd = list[last].formatting;
            else if (last >= 0)
                list.Add(new TextFile.Token(lineEnd));

            list.Add(new TextFile.Token(lineEnd)); // a blank line between Daggerfall's text and Doomerfall's
            foreach (string line in Lines(stat, player))
            {
                list.Add(new TextFile.Token(TextFile.Formatting.Text, line));
                list.Add(new TextFile.Token(lineEnd));
            }
            list.Add(new TextFile.Token(TextFile.Formatting.EndOfRecord));
            return list.ToArray();
        }

        static bool StatFor(int textId, out DFCareer.Stats stat)
        {
            for (int i = 0; i < DaggerfallStats.Count; i++)
            {
                stat = (DFCareer.Stats)i;
                if (DaggerfallUnity.Instance.TextProvider.GetStatDescriptionTextID(stat) == textId)
                    return true;
            }
            stat = DFCareer.Stats.None;
            return false;
        }

        static string N(double v) { return v.ToString("0.##", Inv); }
        static string Signed(double v) { return v.ToString("+0.##;-0.##;0", Inv); }

        /// <summary>The Doomerfall lines for one attribute, each short enough for the popup's width.</summary>
        internal static string[] Lines(DFCareer.Stats stat, PlayerEntity player)
        {
            int live = player.Stats.GetLiveStatValue(stat);
            int v = Math.Max(0, Math.Min(live, 100)); // the value the rule uses, where above 100 counts as 100
            string yours = "Yours (" + live.ToString(Inv) + "): ";
            const string Over100 = "Above 100 counts as 100.";
            switch (stat)
            {
                case DFCareer.Stats.Strength:
                    return new[] {
                        "In Doomerfall, Strength raises melee damage:",
                        "damage x (1 + Strength / 100), double at 100.",
                        "Melee is your fists and Melee-skill weapons;",
                        "shots fired from a gun never get it. " + Over100,
                        yours + Signed(v) + "% melee damage.",
                    };
                case DFCareer.Stats.Intelligence:
                    return new[] {
                        "In Doomerfall, Intelligence works as in Daggerfall.",
                        "It has no extra effect in Doom's combat.",
                    };
                case DFCareer.Stats.Willpower:
                    return new[] {
                        "In Doomerfall, Willpower changes all damage you take:",
                        "damage x (300 - Willpower) / 250, applied last,",
                        "after armor and resistances. x1.2 at 0, x1 at 50,",
                        "x0.8 at 100. " + Over100,
                        yours + Signed((50 - v) * 0.4) + "% damage taken.",
                    };
                case DFCareer.Stats.Agility:
                    return new[] {
                        "In Doomerfall, Agility speeds reloads and weapon",
                        "switches: speed x (1 + 0.4 x Agility / 100).",
                        "Chance to dodge any hit: 15% x Agility / 100.",
                        Over100,
                        yours + Signed(0.4 * v) + "% handling, " + N(0.15 * v) + "% dodge.",
                    };
                case DFCareer.Stats.Endurance:
                    return new[] {
                        "In Doomerfall, Endurance sets your maximum HP:",
                        "50 + Endurance + (level - 1) x Endurance / 15.",
                        "This replaces Daggerfall's hit points per level.",
                        yours + DoomerfallEndurance.MaxHealth(player.Level, live).ToString(Inv) +
                            " max HP at level " + player.Level.ToString(Inv) + ".",
                    };
                case DFCareer.Stats.Personality:
                    return new[] {
                        "In Doomerfall, Personality works as in Daggerfall.",
                        "It has no extra effect in Doom's combat.",
                    };
                case DFCareer.Stats.Speed:
                    return new[] {
                        "In Doomerfall, Speed sets how fast you walk and run:",
                        "speed x (0.75 + Speed / 200). x0.75 at 0, x1 at 50,",
                        "x1.25 at 100. Not climbing or jumping. " + Over100,
                        yours + Signed((v - 50) * 0.5) + "% move speed.",
                    };
                case DFCareer.Stats.Luck:
                    return new[] {
                        "In Doomerfall, each ammo drop from a monster has a",
                        "Luck in 100 chance to come with a second one.",
                        "Luck keeps its Daggerfall effects. " + Over100,
                        yours + N(v) + "% chance of a second drop.",
                    };
                default:
                    return new string[0];
            }
        }
    }
}
