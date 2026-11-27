// Doomerfall: Skill XP (owner, 2026-11-26; work/backlog/skills-in-doom.md). Daggerfall owns the pool, the prices and
// the skills; Doom only reports damage (DFB_KIND_SKILL_XP, from mods/doomerfall/src/zscript/DoomerfallSkillXp.zs).
//
//   Earning   1 Skill XP per 100 HP of damage the player deals (Doom counts and keeps the remainder). The pool is
//             PlayerEntity.SkillXp and goes into Daggerfall's save with the player.
//   Use       1 use of a weapon skill per 250 HP dealt with that skill's guns, tallied through Daggerfall's own
//             TallySkill, so RaiseSkills, its 6-hour check and its level-up stay Daggerfall's.
//   Buying    the next point of a skill costs Daggerfall's uses for that point (CalculateSkillUsesForAdvancement with
//             the class and character level) with one flat skill multiplier, times XpPerUse. A bought point is a
//             permanent point like one from use: it counts for level-ups, and keeps the 95 cap once a primary skill
//             is at 100. Every playable skill can be bought; Critical Strike and the removed language slots cannot.

using System;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public static class DoomerfallSkillXp
    {
        /// <summary>The one tunable price setting: Skill XP per Daggerfall skill use (owner, 2026-11-26).</summary>
        public const float XpPerUse = 7.5f;

        /// <summary>The skill multiplier for every bought point, in place of Daggerfall's per-skill multipliers, which
        /// offset how often uses happen and do not apply to buying (owner: 2, as for weapon skills).</summary>
        public const int BuyMultiplier = 2;

        static DoomerfallBridge bridge;
        static int logged;

        internal static void Begin(DoomerfallBridge owner) { bridge = owner; }
        internal static void End() { bridge = null; }

        /// <summary>False for skills that cannot be bought (or shown in the menu).</summary>
        public static bool Buyable(DFCareer.Skills skill)
        {
            return skill >= 0 && skill < DFCareer.Skills.Count && skill != DFCareer.Skills.CriticalStrike && !DFCareer.IsRemovedSkill(skill);
        }

        /// <summary>Skill XP for the player's next point of this skill.</summary>
        public static int Price(PlayerEntity player, DFCareer.Skills skill)
        {
            int uses = FormulaHelper.CalculateSkillUsesForAdvancement(player.Skills.GetPermanentSkillValue(skill), BuyMultiplier,
                player.Career.AdvancementMultiplier, player.Level);
            return (int)Math.Ceiling(uses * XpPerUse);
        }

        /// <summary>Null when the skill can take another point, else why not (for the menu).</summary>
        public static string Capped(PlayerEntity player, DFCareer.Skills skill)
        {
            int value = player.Skills.GetPermanentSkillValue(skill);
            if (value >= 100)
                return "Mastered";
            if (value >= 95 && player.AlreadyMasteredASkill())
                return "Capped at 95";
            return null;
        }

        /// <summary>Buys one point. True when bought; the menu checks Capped and the pool first.</summary>
        public static bool Buy(PlayerEntity player, DFCareer.Skills skill)
        {
            if (player == null || !Buyable(skill) || Capped(player, skill) != null)
                return false;
            int price = Price(player, skill);
            if (player.SkillXp < price)
                return false;
            player.SkillXp -= price;
            int i = (int)skill;
            short value = (short)(player.Skills.GetPermanentSkillValue(i) + 1);
            player.Skills.SetPermanentSkillValue(i, value);
            player.SetSkillRecentlyIncreased(i);
            player.SetCurrentLevelUpSkillSum();
            if (value == 100 && player.GetPrimarySkills().Contains(skill)) // as RaiseSkills: "You are now a master of..."
            {
                TextFile.Token[] tokens = DaggerfallUnity.Instance.TextProvider.GetRSCTokens(4020);
                if (tokens != null && tokens.Length > 0)
                {
                    var box = new DaggerfallMessageBox(DaggerfallUI.UIManager);
                    box.SetTextTokens(tokens);
                    box.ClickAnywhereToClose = true;
                    box.Show();
                }
                DaggerfallUI.Instance.PlayOneShot(SoundClips.ArenaFanfareLevelUp);
            }
            bool levelUp = player.CheckForLevelUp();
            if (bridge != null)
                bridge.LogLine(string.Format("skillxp: bought {0} {1} for {2} XP, pool {3}, level-up {4}", skill, value, price, player.SkillXp, levelUp));
            return true;
        }

        /// <summary>DFB_KIND_SKILL_XP from Doom.</summary>
        internal static void OnEvent(DoomerfallBridge owner, uint xp, int skill, uint uses)
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null || DoomerfallNewGame.HoldsNewCharacter)
                return;
            if (xp > 0)
                player.SkillXp = (int)Math.Min((long)player.SkillXp + Math.Min(xp, 1000000u), int.MaxValue);
            if (uses > 0 && skill >= 0 && skill < (int)DFCareer.Skills.Count && Buyable((DFCareer.Skills)skill))
                player.TallySkill((DFCareer.Skills)skill, (short)Math.Min(uses, 1000u));
            if (owner.LogEnabled && logged < 500)
            {
                logged++;
                owner.LogLine(string.Format("skillxp: +{0} XP, pool {1}; {2} uses of skill {3}, tally {4}", xp, player.SkillXp, uses, skill,
                    skill >= 0 && skill < player.SkillUses.Length ? player.SkillUses[skill] : 0));
            }
        }
    }
}
