// Doomerfall test only (-dfskillbasicstest <file> [prime]): follows Daggerfall's use tallies of the six interaction skills
// (Lockpicking, Pickpocket, Mercantile, Etiquette, Streetwise, Medical) in a paired run, writing each change to <file>.
// - When a talk window opens, it asks "Where am I?" once in the polite tone and once in the blunt tone through Daggerfall's
//   own TalkManager calls (what the talk window's question button does), so Etiquette and Streetwise get their tallies.
//   Any other test component may close the window afterwards.
// - When a rest window opens, it takes the player to a quarter of their health, so the rest has hours to heal, and presses
//   Rest Until Healed (the window's own handler). It clicks away the rest's closing message box.
// - With "prime", each of the six skills starts one use short of Daggerfall's advancement threshold, and after each tally
//   Daggerfall's own skill check (PlayerEntity.RaiseSkills) runs, so one real use shows the skill rising.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSkillBasicsTest : MonoBehaviour
    {
        static readonly DFCareer.Skills[] Watched = { DFCareer.Skills.Lockpicking, DFCareer.Skills.Pickpocket,
            DFCareer.Skills.Mercantile, DFCareer.Skills.Etiquette, DFCareer.Skills.Streetwise, DFCareer.Skills.Medical };

        string path;
        bool prime, ready, rested, gaveWares;
        float readyAt;
        readonly short[] uses = new short[Watched.Length];
        readonly short[] values = new short[Watched.Length];
        IUserInterfaceWindow seen;
        DoomerfallPositionSync sync;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfskillbasicstest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallSkillBasicsTest");
            DontDestroyOnLoad(host);
            DoomerfallSkillBasicsTest test = host.AddComponent<DoomerfallSkillBasicsTest>();
            test.path = args[at + 1];
            test.prime = at + 2 < args.Length && args[at + 2] == "prime";
            File.WriteAllText(test.path, "skillbasics: started" + (test.prime ? " (prime)" : "") + "\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Step(); }
            catch (Exception e) { Write("error " + e.GetType().Name + " " + e.Message); }
        }

        void Step()
        {
            if (!GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null)
            {
                readyAt = 0;
                return;
            }
            if (!ready)
            {
                if (readyAt == 0)
                    readyAt = Time.realtimeSinceStartup + 1f;
                if (Time.realtimeSinceStartup < readyAt)
                    return;
                Begin(player);
            }
            Watch(player);
            Act(player);
        }

        void Begin(PlayerEntity player)
        {
            ready = true;
            for (int i = 0; i < Watched.Length; i++)
            {
                if (prime)
                    player.SkillUses[(int)Watched[i]] = (short)Math.Max(0, UsesToAdvance(player, Watched[i]) - 1);
                uses[i] = player.SkillUses[(int)Watched[i]];
                values[i] = player.Skills.GetPermanentSkillValue(Watched[i]);
                Write(string.Format("start {0}: skill {1}, uses {2} of {3} needed", Watched[i], values[i], uses[i], UsesToAdvance(player, Watched[i])));
            }
        }

        // The raw tally at which PlayerEntity.RaiseSkills raises this skill (its reflexes scaling undone).
        internal static int UsesToAdvance(PlayerEntity player, DFCareer.Skills skill)
        {
            int needed = FormulaHelper.CalculateSkillUsesForAdvancement(player.Skills.GetPermanentSkillValue(skill),
                DaggerfallSkills.GetAdvancementMultiplier(skill), player.Career.AdvancementMultiplier, player.Level);
            int mod = 0x10000 - (((int)player.Reflexes - 2) << 13);
            int raw = 0;
            while (((raw * mod) >> 16) < needed && raw < 20000)
                raw++;
            return raw;
        }

        void Watch(PlayerEntity player)
        {
            bool tallied = false;
            for (int i = 0; i < Watched.Length; i++)
            {
                short now = player.SkillUses[(int)Watched[i]];
                if (now != uses[i])
                {
                    Write(string.Format("tally {0}: uses {1} -> {2}", Watched[i], uses[i], now));
                    tallied |= now > uses[i];
                    uses[i] = now;
                }
            }
            if (tallied && prime)
            {
                player.TimeOfLastSkillIncreaseCheck = 0;
                player.RaiseSkills();
                Write("ran Daggerfall's skill check");
            }
            for (int i = 0; i < Watched.Length; i++)
            {
                short value = player.Skills.GetPermanentSkillValue(Watched[i]);
                if (value != values[i])
                {
                    Write(string.Format("advance {0}: skill {1} -> {2}, uses now {3}", Watched[i], values[i], value, player.SkillUses[(int)Watched[i]]));
                    values[i] = value;
                }
                uses[i] = player.SkillUses[(int)Watched[i]];
            }
        }

        void Act(PlayerEntity player)
        {
            if (!DaggerfallUI.Instance)
                return;
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            if (top == seen)
                return;
            seen = top;
            Write("window " + (top == null ? "none" : top.GetType().Name));
            if (top is DaggerfallTalkWindow)
            {
                TalkManager talk = GameManager.Instance.TalkManager;
                var question = new TalkManager.ListItem { type = TalkManager.ListItemType.Item, questionType = TalkManager.QuestionType.WhereAmI };
                foreach (DaggerfallTalkWindow.TalkTone tone in new[] { DaggerfallTalkWindow.TalkTone.Polite, DaggerfallTalkWindow.TalkTone.Blunt })
                {
                    string asked = talk.GetQuestionText(question, tone);
                    Write(string.Format("talk to \"{0}\", {1}: \"{2}\" -> \"{3}\"", talk.NameNPC, tone, asked, talk.GetAnswerText(question)));
                }
            }
            else if ((top is DaggerfallMerchantServicePopupWindow || top is DaggerfallMerchantRepairPopupWindow) && !gaveWares)
            {
                // The test character carries nothing a shop buys: one ordinary item to sell.
                gaveWares = true;
                player.Items.AddItem(Items.ItemBuilder.CreateMensClothing(Items.MensClothing.Casual_cloak, player.Race));
                Write("merchant menu: gave the player a cloak to sell");
            }
            else if (top is DaggerfallRestWindow)
            {
                player.CurrentHealth = Math.Max(1, player.MaxHealth / 4);
                Write(string.Format("rest: pressing Rest Until Healed at hp {0}/{1}", player.CurrentHealth, player.MaxHealth));
                MethodInfo healed = typeof(DaggerfallRestWindow).GetMethod("HealedButton_OnMouseClick", BindingFlags.Instance | BindingFlags.NonPublic);
                healed.Invoke(top, new object[] { null, Vector2.zero });
                rested = true;
            }
            else if (top is DaggerfallMessageBox && rested)
            {
                // The rest's closing message ("You are healed", or why it stopped): click it away as a player would.
                rested = false;
                Write(string.Format("rest: closing its message box at hp {0}/{1}", player.CurrentHealth, player.MaxHealth));
                ((DaggerfallMessageBox)top).CloseWindow();
            }
        }
    }
}
