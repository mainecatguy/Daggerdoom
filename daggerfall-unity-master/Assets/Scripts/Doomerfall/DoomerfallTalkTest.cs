// Doomerfall test only.
// -dftalktest: reports whom the talk window that Doom's Use opened is talking to, and what that NPC says, then closes it
// through the window's own code, so a minimized test can prove the whole route. A message box (an NPC that will not
// talk) is reported with its text.
// -dftalkrefuse: once the first talk window has closed, the player's social group reputations drop to -100, so
// Daggerfall's own reaction check makes every later NPC refuse (TalkManager.TalkToNpc: a reaction below -20 gives
// "You get no response"). Works alone too, for a hand demo where the windows stay open.

using System;
using System.Text;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTalkTest : MonoBehaviour
    {
        const float ActSeconds = 2.0f;

        DoomerfallBridge bridge;
        IUserInterfaceWindow seen;
        float actAt;
        bool acted, closes, refuse;

        internal void Init(DoomerfallBridge owner)
        {
            bridge = owner;
            string[] args = Environment.GetCommandLineArgs();
            closes = Array.IndexOf(args, "-dftalktest") >= 0;
            refuse = Array.IndexOf(args, "-dftalkrefuse") >= 0;
        }

        void Update()
        {
            if (!DaggerfallUI.Instance || !DoomerfallInput.Active)
            {
                Lower(null);
                seen = null;
                return;
            }
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            if (top != seen)
            {
                Lower(top);
                seen = top;
                acted = false;
                actAt = Time.unscaledTime + ActSeconds;
                if (closes)
                    bridge.LogLine("talktest: window " + (top == null ? "none" : top.GetType().Name));
            }
            if (!closes || acted || Time.unscaledTime < actAt || !(top is UserInterfaceWindow) || top is DaggerfallHUD)
                return;
            acted = true;
            TalkManager talk = GameManager.Instance.TalkManager;
            if (top is DaggerfallTalkWindow)
            {
                StaticNPC npc = talk.StaticNPC;
                bridge.LogLine(string.Format("talktest: talking to \"{0}\" (static npc {1}, faction {2}, name seed {3}), greeting \"{4}\"",
                    talk.NameNPC, npc ? npc.DisplayName : "none", npc ? npc.Data.factionID : -1, npc ? npc.Data.nameSeed : -1, talk.NPCGreetingText));
            }
            else if (top is DaggerfallMessageBox)
            {
                var text = new StringBuilder();
                Collect(((DaggerfallMessageBox)top).ParentPanel, text);
                bridge.LogLine("talktest: message box \"" + text.ToString().Trim() + "\"");
            }
            ((UserInterfaceWindow)top).CloseWindow();
        }

        // After the first talk window gives way to anything else, every later NPC dislikes the player.
        void Lower(IUserInterfaceWindow next)
        {
            if (!refuse || !(seen is DaggerfallTalkWindow) || next == seen || !GameManager.HasInstance)
                return;
            refuse = false;
            short[] reps = GameManager.Instance.PlayerEntity.SGroupReputations;
            for (int i = 0; i < reps.Length; i++)
                reps[i] = -100;
            bridge.LogLine("talktest: social group reputations set to -100, later NPCs should refuse");
        }

        static void Collect(BaseScreenComponent component, StringBuilder text)
        {
            TextLabel label = component as TextLabel;
            if (label != null && !string.IsNullOrEmpty(label.Text))
                text.Append(label.Text).Append(' ');
            MultiFormatTextLabel multi = component as MultiFormatTextLabel;
            if (multi != null)
                foreach (TextLabel line in multi.TextLabels)
                    Collect(line, text);
            Panel panel = component as Panel;
            if (panel != null)
                foreach (BaseScreenComponent child in panel.Components)
                    Collect(child, text);
        }
    }
}
