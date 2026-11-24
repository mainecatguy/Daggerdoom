// Doomerfall test only (-dffacetest): adds and drops quest follower faces through Daggerfall's own HUD panel
// (EscortingFaces), as a quest's "add face" and "drop face" would, so a paired run can watch Doom's HUD follow.
// Doom's side of the run (-dffacetest on UZDoom, dd_faces.cpp) saves, loads, and takes the screenshots.
//   1. In game: add face A (a noble).
//   2. After Daggerfall's half of a save: add face B (a child), which the save does not have.
//   3. After a load: the panel holds only A again. Three seconds later, drop A.

using System.Collections;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterface;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallFaceTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        Person a, b;
        bool saved, loaded;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            SaveLoadManager.OnSave += OnSave;
            SaveLoadManager.OnLoad += OnLoad;
            StartCoroutine(Run());
        }

        void OnDestroy()
        {
            SaveLoadManager.OnSave -= OnSave;
            SaveLoadManager.OnLoad -= OnLoad;
        }

        static EscortingNPCFacePanel Panel { get { return DaggerfallUI.Instance.DaggerfallHUD.EscortingFaces; } }

        void Log(string what)
        {
            bridge.LogLine(string.Format("face test: {0}; panel holds {1} face(s)", what, Panel.GetSaveData().Length));
        }

        void OnSave(SaveData_v1 data) { saved = true; }
        void OnLoad(SaveData_v1 data) { loaded = true; }

        IEnumerator Run()
        {
            while (!sync.InGame || DaggerfallUI.Instance == null || DaggerfallUI.Instance.DaggerfallHUD == null)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            Quest quest = new Quest(); // Never started: only its UID ties the faces together, as a quest's would.
            a = new Person(quest, "Person _dffacea_ face 5 group Noble male");
            b = new Person(quest, "Person _dffaceb_ face 1 faction Children");
            Panel.AddFace(a);
            Log("added A, " + a.DisplayName);

            while (!saved)
                yield return null;
            yield return null;
            Panel.AddFace(b);
            Log("saved, added B, " + b.DisplayName);

            while (!loaded)
                yield return null;
            yield return null;
            Log("loaded");
            yield return new WaitForSecondsRealtime(3f);
            Panel.DropFace(a);
            Log("dropped A");
        }
    }
}
