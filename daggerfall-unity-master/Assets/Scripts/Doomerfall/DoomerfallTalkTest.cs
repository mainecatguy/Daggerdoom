// Doomerfall test only (-dftalktest): reports whom the talk window that Doom's Use opened is talking to, and what
// that NPC says, then closes it through the window's own code, so a minimized test can prove the whole route.

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
        bool acted;

        internal void Init(DoomerfallBridge owner)
        {
            bridge = owner;
        }

        void Update()
        {
            if (!DaggerfallUI.Instance || !DoomerfallInput.Active)
            {
                seen = null;
                return;
            }
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            if (top != seen)
            {
                seen = top;
                acted = false;
                actAt = Time.unscaledTime + ActSeconds;
                bridge.LogLine("talktest: window " + (top == null ? "none" : top.GetType().Name));
            }
            if (acted || Time.unscaledTime < actAt || !(top is UserInterfaceWindow) || top is DaggerfallHUD)
                return;
            acted = true;
            TalkManager talk = GameManager.Instance.TalkManager;
            if (top is DaggerfallTalkWindow)
            {
                StaticNPC npc = talk.StaticNPC;
                bridge.LogLine(string.Format("talktest: talking to \"{0}\" (static npc {1}, faction {2}, name seed {3}), greeting \"{4}\"",
                    talk.NameNPC, npc ? npc.DisplayName : "none", npc ? npc.Data.factionID : -1, npc ? npc.Data.nameSeed : -1, talk.NPCGreetingText));
            }
            ((UserInterfaceWindow)top).CloseWindow();
        }
    }
}
