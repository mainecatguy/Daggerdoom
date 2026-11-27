// Doomerfall test only (-dffisttest): checks that the fist is always on hotkey 1. Runs once both games are playing
// with a gun drawn, and again after every load. Writes "fisttest:" lines to the bridge log; tools/fist/run_fist.py reads them.
//
//   1. Key 1 square 0 is the fist, and nothing else names it.
//   2. Assigning the active gun to key 1 square 0 and removing that square both leave the fist there.
//   3. No inventory item is a fist, and the save text has no fist line.
//   4. Pressing 1 raises a melee weapon in Doom (Doom's own ready report), and the gun stays Daggerfall's active gun.
//   5. Pressing the gun's key raises the gun again.

using System;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallFistTest : MonoBehaviour
    {
        DoomerfallHotkeys hotkeys;
        DoomerfallAmmo ammo;
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        int step, gunKey, runs, fails;
        float wait, deadline;
        DoomerfallDoomItem gun;

        internal void Init(DoomerfallHotkeys owner, DoomerfallBridge bridgeOwner)
        {
            hotkeys = owner;
            bridge = bridgeOwner;
            ammo = GetComponent<DoomerfallAmmo>();
            SaveLoadManager.OnLoad += OnLoad;
        }

        void OnDestroy() { SaveLoadManager.OnLoad -= OnLoad; }
        void OnLoad(SaveData_v1 data) { step = 0; wait = Time.unscaledTime + 1f; Log("a save loaded; checking again"); }

        void Log(string text) { bridge.LogLine("fisttest: " + text); }

        void Check(bool ok, string what)
        {
            if (!ok) fails++;
            Log((ok ? "PASS " : "FAIL ") + what);
        }

        void Update()
        {
            if (step < 0 || hotkeys == null || Time.unscaledTime < wait || !GameManager.HasInstance || !GameManager.Instance.IsPlayingGame()
                || SaveLoadManager.Instance.LoadInProgress || hotkeys.SwapInFlight)
                return;
            if (ammo == null) ammo = GetComponent<DoomerfallAmmo>();
            switch (step)
            {
                case 0: // Wait for a drawn gun on a key.
                    gun = hotkeys.ActiveGun;
                    gunKey = KeyOf(gun);
                    if (gun == null || gunKey < 0 || ammo == null || ammo.ReadyMelee) return; // Doom must report the gun raised first.
                    if (sync == null) sync = GetComponent<DoomerfallPositionSync>();
                    if (sync == null || !sync.Engaged || sync.LoadRunning) return; // Both games in the area, not mid-transition, as a player pressing 1.
                    Static();
                    hotkeys.Press(DoomerfallHotkeys.FistKey, Dfb.HOTKEY_PLAIN);
                    Next(1);
                    break;
                case 1:
                    if (!ammo.ReadyMelee && Time.unscaledTime < deadline) return;
                    Check(ammo.ReadyMelee, "pressing 1 raised a melee weapon in Doom (Doom's ready report)");
                    Check(hotkeys.ActiveGun == gun, "the gun stays Daggerfall's active gun while the fist is up: " + (hotkeys.ActiveGun != null ? hotkeys.ActiveGun.ItemName : "none"));
                    Check(FistOnly(), "the fist is still on key 1 square 0 and in no inventory");
                    hotkeys.Press(gunKey, Dfb.HOTKEY_PLAIN);
                    Next(2);
                    break;
                case 2:
                    if (ammo.ReadyMelee && Time.unscaledTime < deadline) return;
                    Check(!ammo.ReadyMelee && hotkeys.ActiveGun == gun, "pressing key " + gunKey + " raised the gun again");
                    runs++;
                    Log(string.Format("done run {0}: {1}", runs, fails == 0 ? "PASS" : fails + " FAIL"));
                    step = -1;
                    break;
            }
        }

        void Next(int s) { step = s; deadline = Time.unscaledTime + 6f; }

        void Static()
        {
            Log(string.Format("checking with \"{0}\" drawn on key {1}; table {2}", gun.ItemName, gunKey, hotkeys.Describe()));
            Check(FistOnly(), "key 1 square 0 is the fist, and no item is a fist");
            hotkeys.Assign(DoomerfallHotkeys.FistKey, DoomerfallHotkeys.FistSquare, gun);
            Check(FistOnly() && KeyOf(gun) == gunKey, "assigning the gun to key 1 square 0 is refused; the gun keeps key " + gunKey);
            hotkeys.Clear(DoomerfallHotkeys.FistKey, DoomerfallHotkeys.FistSquare);
            Check(FistOnly(), "removing key 1 square 0 leaves the fist");
            Check(hotkeys.SaveText().IndexOf(" f ", StringComparison.Ordinal) < 0, "the save text has no fist line");
        }

        bool FistOnly()
        {
            DoomerfallHotkeys.Square fist = hotkeys.table[DoomerfallHotkeys.FistKey, DoomerfallHotkeys.FistSquare];
            if (fist == null || fist.kind != 'f') return false;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                DoomerfallDoomItem doom = item as DoomerfallDoomItem;
                if (item.ItemName.IndexOf("fist", StringComparison.OrdinalIgnoreCase) >= 0 || (doom != null && doom.DoomClass.IndexOf("Fist", StringComparison.Ordinal) >= 0))
                    return false;
            }
            return true;
        }

        int KeyOf(DaggerfallUnityItem item)
        {
            if (item == null) return -1;
            for (int k = 0; k < DoomerfallHotkeys.Keys; k++)
                for (int q = 0; q < DoomerfallHotkeys.Squares; q++)
                    if (hotkeys.table[k, q] != null && hotkeys.table[k, q].kind != 'f' && hotkeys.table[k, q].uid == item.UID)
                        return k;
            return -1;
        }
    }
}
