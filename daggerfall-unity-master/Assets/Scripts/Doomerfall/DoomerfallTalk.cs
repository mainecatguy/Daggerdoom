// Doomerfall: Doom's Use on an NPC it draws. Runs only in a bridge session.
//
// Doom names the NPC and how far its view ray went to reach it. Daggerfall runs its own activation of that NPC, in
// Grab mode, or Steal while Doom's player crouches, once Doom has paused and opened the window target, so the talk
// window (or anything else Daggerfall opens for that NPC) appears inside Doom. A Use from too far away gets
// Daggerfall's own "too far away" message and no window.

using DaggerfallWorkshop.Game.UserInterface;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTalk : MonoBehaviour
    {
        const float AnswerSeconds = 5f; // Doom asks for the window right after the answer. An older answer is stale.
        const float MetersPerClassicUnit = PlayerActivate.StaticNPCActivationDistance / 256f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallInfo info;
        StaticNPC pending;
        ulong pendingId;
        uint pendingRequest;
        PlayerActivateModes pendingMode;
        float pendingDistance, answerBy;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallInfo messages)
        {
            bridge = owner;
            sync = positionSync;
            info = messages;
        }

        internal void OnUse(uint request, ulong id, uint mode, double distance)
        {
            uint status = Dfb.NPC_USE_REFUSED;
            float meters = (float)distance * MetersPerClassicUnit;
            PlayerActivateModes activateMode = mode == Dfb.TAKE_STEAL ? PlayerActivateModes.Steal : PlayerActivateModes.Grab;
            StaticNPC npc = null;
            if (!sync.LoadRunning && GameManager.HasInstance && sync.InGame && !GameManager.IsGamePaused)
            {
                npc = DoomerfallNpcs.FindNpc(id);
                if (!npc)
                {
                    status = Dfb.NPC_USE_GONE;
                }
                else if (meters > PlayerActivate.StaticNPCActivationDistance)
                {
                    // Daggerfall's own activation shows its "too far away" message and opens nothing.
                    StaticNPC far = npc;
                    info.Capture(request, () => GameManager.Instance.PlayerActivate.DoomerfallUseNpc(far, activateMode, meters),
                        string.Format("talk: use {0} on {1:x16} from {2:F2} m", request, id, meters));
                    status = Dfb.NPC_USE_DONE;
                }
                else
                {
                    pending = npc;
                    pendingId = id;
                    pendingRequest = request;
                    pendingMode = activateMode;
                    pendingDistance = meters;
                    answerBy = Time.unscaledTime + AnswerSeconds;
                    status = Dfb.NPC_USE_WINDOW;
                }
            }
            var e = new DfbEvent
            {
                kind = Dfb.KIND_NPC_USE_RESULT,
                tic = (uint)Time.frameCount,
                npcUseResult = new DfbNpcUseResult { id = id, request = request, status = status },
            };
            bridge.Send(ref e);
            bridge.LogLine(string.Format("talk: use {0} on {1:x16} ({2}, {3:F2} m): {4}, status {5}", request, id, activateMode,
                meters, npc ? npc.DisplayName : "none", status));
        }

        // DoomerfallUi calls this once Doom has asked for DFB_UI_TALK and the window target is in place.
        internal bool OpenWindow()
        {
            StaticNPC npc = pending;
            pending = null;
            if (!npc || Time.unscaledTime > answerBy)
                return false;
            info.Capture(pendingRequest, () => GameManager.Instance.PlayerActivate.DoomerfallUseNpc(npc, pendingMode, pendingDistance),
                string.Format("talk: activating {0:x16} {1} (faction {2}) in {3} mode", pendingId, npc.DisplayName,
                    npc.Data.factionID, pendingMode));
            bridge.LogLine("talk: top window after activation is " + TopWindowName());
            return true;
        }

        static string TopWindowName()
        {
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            return top == null ? "none" : top.GetType().Name;
        }
    }
}
