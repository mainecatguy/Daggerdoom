// Doomerfall test only (-dfjournaltest <file>): once the game runs, starts two real quests and adds notebook, finished
// quest and message entries, so the journal has content on every tab. Then logs, each time it changes, the top window
// and, while the quest journal is open, its tab, page and entry count, so a test can see Doom open, page and close it.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using System.Reflection;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallJournalTest : MonoBehaviour
    {
        const BindingFlags Field = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        static readonly string[] Quests = { "A0C00Y00", "A0C00Y11" }; // Both log at start and need no local site, which the test town may lack.

        string path, last;
        DoomerfallPositionSync sync;
        float readyAt;
        bool seeded;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfjournaltest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallJournalTest");
            DontDestroyOnLoad(host);
            DoomerfallJournalTest test = host.AddComponent<DoomerfallJournalTest>();
            test.path = args[at + 1];
            File.WriteAllText(test.path, "journal: started\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Seed(); }
            catch (Exception e) { Write("seed error " + e.GetType().Name + " " + e.Message); seeded = true; }
            string line;
            try { line = Describe(); }
            catch (Exception e) { line = "error " + e.GetType().Name + " " + e.Message; }
            if (line == last)
                return;
            last = line;
            Write(line);
        }

        void Seed()
        {
            if (seeded || !GameManager.HasInstance || QuestMachine.Instance == null)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || GameManager.Instance.PlayerEntity == null)
            {
                readyAt = 0;
                return;
            }
            if (readyAt == 0)
                readyAt = Time.realtimeSinceStartup + 3f; // Let the test start's placement settle first.
            if (Time.realtimeSinceStartup < readyAt)
                return;
            seeded = true;
            foreach (string name in Quests)
                QuestMachine.Instance.StartQuest(name);
            var book =GameManager.Instance.PlayerEntity.Notebook;
            for (int i = 1; i <= 3; i++)
                book.AddNote("Test note " + i + ": the journal test wrote this.");
            book.AddMessage("Test message: the journal test wrote this.");
            book.AddFinishedQuest(new[] { TextFile.CreateTextToken("Test finished quest: the journal test wrote this.") });
            Write(string.Format("seeded quests {0} log_messages {1} notes {2} messages {3} finished {4}", QuestMachine.Instance.QuestCount,
                QuestMachine.Instance.GetAllQuestLogMessages().Count, book.GetNotes().Count, book.GetMessages().Count, book.GetFinishedQuests().Count));
        }

        static string Describe()
        {
            if (!DaggerfallUI.Instance || !GameManager.HasInstance)
                return "none";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            string view = "";
            var journal = top as DaggerfallQuestJournalWindow;
            if (journal != null)
            {
                Type t = typeof(DaggerfallQuestJournalWindow);
                var title = (TextLabel)t.GetField("titleLabel", Field).GetValue(journal);
                view = string.Format("mode {0} page {1} of {2} title {3}", journal.DisplayMode, t.GetField("currentMessageIndex", Field).GetValue(journal),
                    t.GetField("messageCount", Field).GetValue(journal), title == null ? "" : title.Text);
            }
            else if (top is DaggerfallTravelMapWindow)
            {
                Type t = typeof(DaggerfallTravelMapWindow);
                view = string.Format("region {0} finding {1}", t.GetField("selectedRegion", Field).GetValue(top), t.GetField("findingLocation", Field).GetValue(top));
            }
            else if (top is DaggerfallMessageBox)
            {
                view = "message box";
            }
            Vector2 mouse = InputManager.Instance.MousePosition;
            return string.Format("top {0} view {1} | mouse {2:F0},{3:F0} button {4}", top == null ? "none" : top.GetType().Name, view, mouse.x, mouse.y,
                DoomerfallInput.GetKey(KeyCode.Mouse0));
        }
    }
}
