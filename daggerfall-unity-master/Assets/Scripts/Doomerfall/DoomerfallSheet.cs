// Doomerfall: publishes the character sheet to Doom. Daggerfall stays the authority and Doom only reads.
// The sheet is rebuilt each frame and written to its bulk slot only when a value changed, so level-ups, training,
// equipment, and effects need no hooks of their own. Loads and new characters withdraw it before the player changes.

using System;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSheet : IDisposable
    {
        readonly DoomerfallBridge bridge;
        readonly DoomerfallPositionSync sync;
        readonly int[] values = new int[Dfb.SHEET_INTS];
        readonly int[] published = new int[Dfb.SHEET_INTS];
        readonly byte[] bytes = new byte[Dfb.SHEET_INTS * sizeof(int)];
        readonly bool flow;
        int epoch = 1;
        bool written, hasCharacter, creating, loading;

        public DoomerfallSheet(DoomerfallBridge owner, DoomerfallPositionSync positionSync, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            flow = DoomerfallNewGame.IsFlow(args);
            hasCharacter = !flow; // A flow session waits at Doom's title with only Daggerfall's blank default player.
            SaveLoadManager.OnStartLoad += OnStartLoad;
            SaveLoadManager.OnLoad += OnLoad;
            StartGameBehaviour.OnStartGame += OnStartGame;
        }

        public void Dispose()
        {
            SaveLoadManager.OnStartLoad -= OnStartLoad;
            SaveLoadManager.OnLoad -= OnLoad;
            StartGameBehaviour.OnStartGame -= OnStartGame;
        }

        void OnStartLoad(SaveData_v1 data)
        {
            loading = true;
            epoch++;
            Publish(); // Before Daggerfall restores the player.
        }

        void OnLoad(SaveData_v1 data)
        {
            loading = false;
            hasCharacter = true;
            Publish();
        }

        void OnStartGame(object sender, EventArgs e)
        {
            // A flow character was already handled by CharacterPlaced, and a load by OnLoad.
            if (flow || (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress))
                return;
            epoch++;
            Publish();
        }

        /// <summary>Character creation opened, so the current character is about to be replaced.</summary>
        internal void CreationStarted()
        {
            creating = true;
            epoch++;
            Publish();
        }

        /// <summary>The wizard closed without a character, so the existing one (if any) is still in place.</summary>
        internal void CreationCancelled()
        {
            creating = false;
            Publish();
        }

        internal void CharacterPlaced()
        {
            creating = false;
            loading = false;
            hasCharacter = true;
            epoch++;
            Publish();
        }

        internal void CharacterDropped()
        {
            hasCharacter = false;
            epoch++;
            Publish();
        }

        /// <summary>Writes the sheet if it changed. Runs every frame and allocates nothing.</summary>
        internal void Publish()
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            SaveLoadManager saves = SaveLoadManager.Instance;
            bool valid = player != null && hasCharacter && !creating && !loading && sync.InGame &&
                (saves == null || !saves.LoadInProgress);

            Array.Clear(values, 0, values.Length);
            values[Dfb.SHEET_FORMAT] = Dfb.SHEET_FORMAT_VERSION;
            values[Dfb.SHEET_EPOCH] = epoch;
            if (valid)
            {
                values[Dfb.SHEET_VALID] = 1;
                Fill(player);
            }

            if (written && Same())
                return;
            Buffer.BlockCopy(values, 0, bytes, 0, bytes.Length);
            uint version;
            if (DfbNative.dfb_bulk_write(bridge.Session, Dfb.SHEET_SLOT, bytes, (uint)bytes.Length, out version) != Dfb.OK)
                return; // Retried next frame, because published is unchanged.
            bool log = bridge.LogEnabled && (!written || !OnlyVitalsChanged());
            Array.Copy(values, published, values.Length);
            written = true;
            if (log)
                bridge.LogLine(Describe("sheet: published", version));
        }

        bool Same()
        {
            for (int i = 0; i < values.Length; i++)
                if (values[i] != published[i])
                    return false;
            return true;
        }

        // Fatigue and magicka change constantly, so they alone do not earn a log line.
        bool OnlyVitalsChanged()
        {
            for (int i = 0; i < values.Length; i++)
                if (values[i] != published[i] && (i < Dfb.SHEET_FATIGUE_CURRENT || i > Dfb.SHEET_MAGICKA_MAX))
                    return false;
            return true;
        }

        void Fill(PlayerEntity player)
        {
            values[Dfb.SHEET_LEVEL] = player.Level;
            values[Dfb.SHEET_FATIGUE_CURRENT] = player.CurrentFatigue;
            values[Dfb.SHEET_FATIGUE_MAX] = player.MaxFatigue;
            values[Dfb.SHEET_MAGICKA_CURRENT] = player.CurrentMagicka;
            values[Dfb.SHEET_MAGICKA_MAX] = player.MaxMagicka;
            values[Dfb.SHEET_MAGIC_RESIST] = player.MagicResist;
            values[Dfb.SHEET_ARMOR_INCREASE] = player.IncreasedArmorValueModifier;
            values[Dfb.SHEET_ARMOR_DECREASE] = player.DecreasedArmorValueModifier;

            for (int i = 0; i < DaggerfallStats.Count; i++)
            {
                values[Dfb.SHEET_STATS_BASE + i] = player.Stats.GetPermanentStatValue(i);
                values[Dfb.SHEET_STATS_LIVE + i] = player.Stats.GetLiveStatValue(i);
            }
            for (int i = 0; i < DaggerfallSkills.Count; i++)
            {
                values[Dfb.SHEET_SKILLS_BASE + i] = player.Skills.GetPermanentSkillValue(i);
                values[Dfb.SHEET_SKILLS_LIVE + i] = player.Skills.GetLiveSkillValue(i);
            }
            sbyte[] armor = player.ArmorValues;
            for (int i = 0; armor != null && i < armor.Length && i < 7; i++)
            {
                values[Dfb.SHEET_ARMOR_BASE + i] = armor[i];
                values[Dfb.SHEET_ARMOR_LIVE + i] = armor[i] + player.IncreasedArmorValueModifier + player.DecreasedArmorValueModifier;
            }
            for (int i = 0; i < DaggerfallResistances.Count; i++)
            {
                var element = (DFCareer.Elements)i;
                values[Dfb.SHEET_RESIST_BASE + i] = player.Resistances.GetPermanentResistanceValue(i);
                values[Dfb.SHEET_RESIST_LIVE + i] = player.Resistances.GetLiveResistanceValue(i);
                values[Dfb.SHEET_RESIST_ACTIVE + i] = player.HasResistanceFlag(element) ? 1 : 0;
                values[Dfb.SHEET_RESIST_CHANCE + i] = player.GetResistanceChance(element);
            }

            DFCareer career = player.Career;
            if (career != null)
            {
                values[Dfb.SHEET_TOLERANCE] = (int)career.Paralysis;
                values[Dfb.SHEET_TOLERANCE + 1] = (int)career.Magic;
                values[Dfb.SHEET_TOLERANCE + 2] = (int)career.Poison;
                values[Dfb.SHEET_TOLERANCE + 3] = (int)career.Fire;
                values[Dfb.SHEET_TOLERANCE + 4] = (int)career.Frost;
                values[Dfb.SHEET_TOLERANCE + 5] = (int)career.Shock;
                values[Dfb.SHEET_TOLERANCE + 6] = (int)career.Disease;
            }
            RaceTemplate race = player.GetLiveRaceTemplate();
            if (race != null)
            {
                values[Dfb.SHEET_RACE_RESIST] = (int)race.ResistanceFlags;
                values[Dfb.SHEET_RACE_IMMUNE] = (int)race.ImmunityFlags;
                values[Dfb.SHEET_RACE_LOW] = (int)race.LowToleranceFlags;
                values[Dfb.SHEET_RACE_CRITICAL] = (int)race.CriticalWeaknessFlags;
            }
            values[Dfb.SHEET_BIO_MAGIC] = player.BiographyResistMagicMod;
            values[Dfb.SHEET_BIO_POISON] = player.BiographyResistPoisonMod;
            values[Dfb.SHEET_BIO_DISEASE] = player.BiographyResistDiseaseMod;

            // Daggerfall's own formula, so race, effects, luck, and formula mods stay Daggerfall's (ClimbingMotor bases).
            values[Dfb.SHEET_CLIMB_CHANCE + Dfb.CLIMB_START] = FormulaHelper.CalculateClimbingChance(player, 70);
            values[Dfb.SHEET_CLIMB_CHANCE + Dfb.CLIMB_GRASP] = FormulaHelper.CalculateClimbingChance(player, 40);
            values[Dfb.SHEET_CLIMB_CHANCE + Dfb.CLIMB_CONTINUE] = FormulaHelper.CalculateClimbingChance(player, 50);
            values[Dfb.SHEET_CLIMB_CHANCE + Dfb.CLIMB_REGAIN] = FormulaHelper.CalculateClimbingChance(player, 20);
            values[Dfb.SHEET_CLIMB_ENHANCED] = player.IsEnhancedClimbing ? 1 : 0;
            DoomerfallAutomaticsRules.Fill(values, player);
            DoomerfallExplosivesRules.Fill(values, player);
            DoomerfallShotgunsRules.Fill(values, player);
            DoomerfallEnergyRules.Fill(values, player);
            DoomerfallPistolsRules.Fill(values, player);
        }

        // The checksum lets a test compare this line with Doom's copy of the same version.
        string Describe(string what, uint version)
        {
            uint sum = 2166136261;
            for (int i = 0; i < values.Length; i++)
                sum = (sum ^ (uint)values[i]) * 16777619;
            return string.Format("{0} v{1} epoch {2} valid {3} level {4} str {5}/{6} archery {7}/{8} armor0 {9}/{10} fire {11}/{12} sum {13:x8}" +
                " shotguns {14}/{15} automatics {16}/{17} explosives {18}/{19} pistols {20}/{21} rifles {22}/{23} energy {24}/{25} melee {26}/{27}",
                what, version, values[Dfb.SHEET_EPOCH], values[Dfb.SHEET_VALID], values[Dfb.SHEET_LEVEL],
                values[Dfb.SHEET_STATS_BASE], values[Dfb.SHEET_STATS_LIVE],
                values[Dfb.SHEET_SKILLS_BASE + (int)DFCareer.Skills.Archery], values[Dfb.SHEET_SKILLS_LIVE + (int)DFCareer.Skills.Archery],
                values[Dfb.SHEET_ARMOR_BASE], values[Dfb.SHEET_ARMOR_LIVE], values[Dfb.SHEET_RESIST_ACTIVE], values[Dfb.SHEET_RESIST_CHANCE], sum,
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_SHOTGUNS], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_SHOTGUNS],
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_AUTOMATICS], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_AUTOMATICS],
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_EXPLOSIVES], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_EXPLOSIVES],
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_PISTOLS], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_PISTOLS],
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_RIFLES], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_RIFLES],
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_ENERGY], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_ENERGY],
                values[Dfb.SHEET_SKILLS_BASE + Dfb.SKILL_MELEE], values[Dfb.SHEET_SKILLS_LIVE + Dfb.SKILL_MELEE]);
        }
    }
}
