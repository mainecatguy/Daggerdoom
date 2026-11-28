// Doomerfall test only.
// -dfquestnpctest: once a Daggerfall window (talk, or a quest message) has opened while a quest Person placed at a
// quest marker is present, and then closed, runs the quest's own "hide npc" action on that Person, and some seconds later its "restore npc" action, so a
// minimized test can watch Doom remove the Person's billboard and bring it back (DoomerfallNpcs relays both).

using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Game.Questing.Actions;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallQuestNpcTest : MonoBehaviour
    {
        const float HideAfter = 3f, RestoreAfter = 6f, ArmAfter = 3f;

        DoomerfallBridge bridge;
        Quest quest;
        Symbol symbol;
        float at, hudSince = -1;
        int step;
        bool armed;

        internal void Init(DoomerfallBridge owner)
        {
            bridge = owner;
        }

        void Update()
        {
            if (!GameManager.HasInstance || !DaggerfallUI.Instance || step > 3)
                return;
            // Using a quest Person may open the talk window, or a quest message box when the Person is a turn-in.
            bool talking = !(DaggerfallUI.UIManager.TopWindow is DaggerfallHUD);
            // Armed only after the HUD has shown for a while, so a load's own windows do not count as a talk.
            if (!armed)
            {
                if (talking)
                    hudSince = -1;
                else if (hudSince < 0)
                    hudSince = Time.unscaledTime;
                armed = hudSince >= 0 && Time.unscaledTime - hudSince >= ArmAfter;
                return;
            }
            if (step == 0)
            {
                StaticNPC npc = talking ? PlacedNpc() : null;
                QuestResourceBehaviour behaviour = npc ? npc.GetComponent<QuestResourceBehaviour>() : null;
                if (!behaviour)
                    return;
                quest = GameManager.Instance.QuestMachine.GetQuest(behaviour.QuestUID);
                symbol = behaviour.TargetSymbol;
                bridge.LogLine(string.Format("questnpctest: talking to quest npc {0:x16} {1}, quest {2} symbol {3}",
                    DoomerfallNpcs.QuestIdOf(npc), npc.DisplayName, quest != null ? quest.QuestName : "none", symbol.Name));
                step = quest != null ? 1 : 4;
            }
            else if (step == 1 && !talking)
            {
                at = Time.unscaledTime + HideAfter;
                step = 2;
            }
            else if (step == 2 && Time.unscaledTime > at)
            {
                Run(new HideNpc(quest).CreateNew("hide npc " + symbol.Name, quest));
                at = Time.unscaledTime + RestoreAfter;
                step = 3;
            }
            else if (step == 3 && Time.unscaledTime > at)
            {
                Run(new RestoreNpc(quest).CreateNew("restore npc " + symbol.Name, quest));
                step = 4;
            }
        }

        // The first active quest Person placed at a marker, the one Doom's Use just reached in the test save.
        static StaticNPC PlacedNpc()
        {
            foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs())
                if (npc.gameObject.activeSelf && DoomerfallNpcs.QuestIdOf(npc) != 0)
                    return npc;
            return null;
        }

        void Run(IQuestAction action)
        {
            action.Update(null);
            Person person = quest.GetPerson(symbol);
            bridge.LogLine(string.Format("questnpctest: ran {0} on {1}, hidden {2}", action.GetType().Name, symbol.Name, person != null && person.IsHidden));
        }
    }
}
