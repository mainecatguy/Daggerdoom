// Doomerfall: the player's max HP from Endurance and level, and the class Endurance bonus (gamedesign/hp.md).
// Daggerfall owns HP; Doom mirrors the max HP that DoomerfallHp publishes. Active in a bridge session only.
//
// Max HP = 50 + Endurance + (level - 1) x Endurance / 15, from the permanent Endurance, recomputed whenever level or
// permanent Endurance changes. A rise in max HP raises current HP by the same amount; a fall clamps it.
// Class bonus = class HP per level - 8. It is real Endurance: added once to the permanent value (at the character
// creation roll, or on the first load of a character made without it) and to Endurance's maximum (100 + bonus).

using System;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.Utility.ModSupport;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public sealed class DoomerfallEndurance : MonoBehaviour
    {
        /// <summary>The class HP per level that gives no Endurance bonus.</summary>
        public const int NeutralHpPerLevel = 8;

        static DoomerfallEndurance instance;
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        int logged;

        /// <summary>True in a bridge session, where Doomerfall's HP rules replace Daggerfall's.</summary>
        public static bool Active { get { return instance != null; } }

        public static int ClassBonus(DFCareer career)
        {
            return career == null ? 0 : career.HitPointsPerLevel - NeutralHpPerLevel;
        }

        /// <summary>Max HP for a level and permanent Endurance, rounded to the nearest whole HP.</summary>
        public static int MaxHealth(int level, int endurance)
        {
            return (int)Math.Round(50 + endurance + Math.Max(0, level - 1) * endurance / 15.0, MidpointRounding.AwayFromZero);
        }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            instance = this;
            // Doomerfall wins over any formula mod. Level-up gives no rolled HP: Apply recomputes max HP instead,
            // so current HP rises with it.
            var provider = new Mod { LoadPriority = int.MaxValue };
            FormulaHelper.RegisterOverride<Func<PlayerEntity, int>>(provider, "RollMaxHealth",
                player => MaxHealth(player.Level, player.Stats.PermanentEndurance));
            FormulaHelper.RegisterOverride<Func<PlayerEntity, int>>(provider, "CalculateHitPointsPerLevelUp", player => 0);
            SaveLoadManager.OnLoad += OnLoaded;
        }

        void OnDestroy()
        {
            SaveLoadManager.OnLoad -= OnLoaded;
            if (instance == this)
                instance = null;
        }

        void OnLoaded(SaveData_v1 data)
        {
            if (GameManager.HasInstance && GameManager.Instance.PlayerEntity != null)
                Apply(GameManager.Instance.PlayerEntity);
        }

        void Update()
        {
            // Not mid-load: the load passes through a blank default character first. OnLoaded covers the end.
            if (sync.InGame && GameManager.Instance.PlayerEntity != null && !GameManager.Instance.SaveLoadManager.LoadInProgress)
                Apply(GameManager.Instance.PlayerEntity);
        }

        /// <summary>The creation roll: adds the class bonus to Endurance and its maximum. Nothing outside a session.</summary>
        public static void AddCreationBonus(DaggerfallStats stats, DFCareer career)
        {
            if (!Active || career == null)
                return;
            int bonus = ClassBonus(career);
            stats.DoomerfallEnduranceMaxBonus = bonus;
            stats.SetPermanentStatValue(DFCareer.Stats.Endurance, Mathf.Max(1, stats.PermanentEndurance + bonus));
            stats.DoomerfallEnduranceBonus = true;
        }

        /// <summary>Brings the player in line with the rules. Cheap; runs every frame in game.</summary>
        internal void Apply(PlayerEntity player)
        {
            if (player.Career == null)
                return;
            DaggerfallStats stats = player.Stats;
            int bonus = ClassBonus(player.Career);
            stats.DoomerfallEnduranceMaxBonus = bonus;
            if (!stats.DoomerfallEnduranceBonus)
            {
                // A character made without the bonus (an older save, a classic import): add it once.
                int before = stats.PermanentEndurance;
                int after = Mathf.Clamp(before + bonus, 1, stats.GetMaxPermanentValue(DFCareer.Stats.Endurance));
                stats.SetPermanentStatValue(DFCareer.Stats.Endurance, after);
                stats.DoomerfallEnduranceBonus = true;
                bridge.LogLine(string.Format("endurance: class bonus {0:+0;-0;0} added to {1}, endurance {2} -> {3} (max {4})",
                    bonus, player.Name, before, after, stats.GetMaxPermanentValue(DFCareer.Stats.Endurance)));
            }

            int max = MaxHealth(player.Level, stats.PermanentEndurance);
            int oldMax = player.RawMaxHealth;
            if (max == oldMax)
                return;
            int oldCurrent = player.CurrentHealth;
            player.MaxHealth = max;
            if (oldCurrent > 0) // Never revives the dead.
                player.SetHealth(Mathf.Min(oldCurrent + Mathf.Max(0, max - oldMax), max));
            if (logged++ < 200)
                bridge.LogLine(string.Format("endurance: max hp {0} -> {1} (level {2}, endurance {3}), hp {4} -> {5}",
                    oldMax, max, player.Level, stats.PermanentEndurance, oldCurrent, player.CurrentHealth));
        }

        /// <summary>The custom class editor's HP per level value, shown as the Endurance bonus in a session.</summary>
        public static string HpControlText(int hpPerLevel)
        {
            if (!Active)
                return hpPerLevel.ToString();
            int bonus = hpPerLevel - NeutralHpPerLevel;
            return bonus > 0 ? "+" + bonus : bonus.ToString();
        }

        /// <summary>Covers the editor's painted "hit points per level" label with the Endurance bonus label.</summary>
        public static void RelabelHpControl(Panel nativePanel, Texture2D background)
        {
            if (!Active || background == null)
                return;
            // The painted text spans x 260-306, y 22-41 of CUST00I0.IMG. Rows 42-44 are plain panel, stretched over it.
            var cover = new Panel
            {
                Position = new Vector2(251, 21),
                Size = new Vector2(63, 23),
                BackgroundTexture = background,
                BackgroundTextureLayout = BackgroundLayout.Cropped,
                BackgroundCroppedRect = new Rect(251, background.height - 45, 63, 3),
            };
            nativePanel.Components.Add(cover);
            string[] lines = { "ENDURANCE", "(AND MAX END)", "BONUS" };
            for (int i = 0; i < lines.Length; i++)
            {
                TextLabel label = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(0, 1 + 7 * i), lines[i], cover);
                label.HorizontalAlignment = HorizontalAlignment.Center;
            }
        }
    }
}
