// Doomerfall: Doom's Use on an NPC it draws. Runs only in a bridge session.
//
// Doom names the NPC and how far its view ray went to reach it. Daggerfall runs its own activation of that NPC, in
// Grab mode, or Steal while Doom's player crouches, once Doom has paused and opened the window target, so the talk
// window (or anything else Daggerfall opens for that NPC) appears inside Doom. A Use from too far away gets
// Daggerfall's own "too far away" message and no window.
//
// A townsperson (DoomerfallTownspeople) is not a Daggerfall object, so Daggerfall talks to an inactive stand-in
// MobilePersonNPC that carries the person's race, gender, name and face, as its wanderers do. Being inactive, the
// stand-in never registers as a civilian or runs any behaviour. One stand-in is kept per person, so talking to the
// same person again continues Daggerfall's "same talk partner" rules and its rolls for that person.

using System.Collections.Generic;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.UserInterface;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTalk : MonoBehaviour
    {
        const float AnswerSeconds = 5f; // Doom asks for the window right after the answer. An older answer is stale.
        const float MetersPerClassicUnit = PlayerActivate.StaticNPCActivationDistance / 256f;
        const int MaxStandIns = 64;

        // MobilePersonNPC's portrait records per outfit variant (its SetPerson), indexed the same way.
        static readonly int[] MaleRedguardFaces = { 336, 312, 336, 312 }, FemaleRedguardFaces = { 144, 144, 120, 96 };
        static readonly int[] MaleNordFaces = { 240, 264, 168, 192 }, FemaleNordFaces = { 72, 0, 48, 0 };
        static readonly int[] MaleBretonFaces = { 192, 216, 288, 240 }, FemaleBretonFaces = { 72, 72, 24, 72 };

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallInfo info;
        StaticNPC pending;
        MobilePersonNPC pendingMobile;
        ulong pendingId;
        uint pendingRequest;
        PlayerActivateModes pendingMode;
        float pendingDistance, answerBy;
        readonly Dictionary<ulong, MobilePersonNPC> standIns = new Dictionary<ulong, MobilePersonNPC>();

        internal DoomerfallTownspeople Townspeople { get; set; }

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
            MobilePersonNPC mobile = null;
            string name = "none";
            if (!sync.LoadRunning && GameManager.HasInstance && sync.InGame && !GameManager.IsGamePaused)
            {
                if ((id >> 61) == Dfb.TOWNSPERSON_TAG)
                    mobile = StandIn(id);
                else
                    npc = DoomerfallNpcs.FindNpc(id);
                name = npc ? npc.DisplayName : mobile ? mobile.NameNPC : "none";
                if (!npc && !mobile)
                {
                    status = Dfb.NPC_USE_GONE;
                }
                else if (meters > (npc ? PlayerActivate.StaticNPCActivationDistance : PlayerActivate.MobileNPCActivationDistance))
                {
                    // Daggerfall's own activation shows its "too far away" message and opens nothing.
                    StaticNPC far = npc;
                    MobilePersonNPC farMobile = mobile;
                    info.Capture(request, () => Activate(far, farMobile, activateMode, meters),
                        string.Format("talk: use {0} on {1:x16} from {2:F2} m", request, id, meters));
                    status = Dfb.NPC_USE_DONE;
                }
                else
                {
                    pending = npc;
                    pendingMobile = mobile;
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
            bridge.LogLine(string.Format("talk: use {0} on {1:x16} ({2}, {3:F2} m): {4}{5}, status {6}{7}", request, id, activateMode,
                meters, name, mobile ? " (townsperson)" : "", status, status == Dfb.NPC_USE_REFUSED ? RefusedBecause() : ""));
        }

        static void Activate(StaticNPC npc, MobilePersonNPC mobile, PlayerActivateModes mode, float meters)
        {
            if (npc)
                GameManager.Instance.PlayerActivate.DoomerfallUseNpc(npc, mode, meters);
            else
                GameManager.Instance.PlayerActivate.DoomerfallUseMobileNpc(mobile, mode, meters);
        }

        // The stand-in for a living townsperson of the current town, or null.
        MobilePersonNPC StandIn(ulong id)
        {
            TownPerson person = Townspeople ? Townspeople.FindPerson(id) : null;
            if (person == null)
                return null;
            MobilePersonNPC standIn;
            if (standIns.TryGetValue(id, out standIn) && standIn)
                return standIn;
            if (standIns.Count >= MaxStandIns)
            {
                foreach (MobilePersonNPC old in standIns.Values)
                    if (old) Destroy(old.gameObject);
                standIns.Clear();
            }
            GameObject go = new GameObject("DoomerfallTownsperson " + id.ToString("x16"));
            go.SetActive(false); // before AddComponent, so MobilePersonNPC.Awake never registers it as a civilian
            go.transform.SetParent(transform, false);
            standIn = go.AddComponent<MobilePersonNPC>();
            standIn.Race = person.race;
            standIn.Gender = person.gender;
            standIn.PersonOutfitVariant = person.outfit;
            standIn.IsGuard = person.guard;
            standIn.NameNPC = person.Name;
            standIn.PersonFaceRecordId = Faces(person.race, person.gender)[person.outfit] + person.face;
            standIns[id] = standIn;
            return standIn;
        }

        static int[] Faces(Races race, Genders gender)
        {
            bool male = gender == Genders.Male;
            switch (race)
            {
                case Races.Redguard: return male ? MaleRedguardFaces : FemaleRedguardFaces;
                case Races.Nord: return male ? MaleNordFaces : FemaleNordFaces;
                default: return male ? MaleBretonFaces : FemaleBretonFaces;
            }
        }

        string RefusedBecause()
        {
            if (sync.LoadRunning) return ", a load is running";
            if (!GameManager.HasInstance || !sync.InGame) return ", no game in progress";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            return ", Daggerfall is paused, top window " + (top == null ? "none" : top.GetType().Name);
        }

        // DoomerfallUi calls this once Doom has asked for DFB_UI_TALK and the window target is in place.
        internal bool OpenWindow()
        {
            StaticNPC npc = pending;
            MobilePersonNPC mobile = pendingMobile;
            pending = null;
            pendingMobile = null;
            if ((!npc && !mobile) || Time.unscaledTime > answerBy)
                return false;
            info.Capture(pendingRequest, () => Activate(npc, mobile, pendingMode, pendingDistance),
                npc ? string.Format("talk: activating {0:x16} {1} (faction {2}) in {3} mode", pendingId, npc.DisplayName,
                    npc.Data.factionID, pendingMode)
                    : string.Format("talk: activating townsperson {0:x16} {1} ({2} {3}, face {4}) in {5} mode", pendingId,
                    mobile.NameNPC, mobile.Race, mobile.Gender, mobile.PersonFaceRecordId, pendingMode));
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
