// Doomerfall test only (-dfhotkeyuniquetest <dir>): checks the one-hotkey-per-item rule on the real DoomerfallHotkeys,
// with no bridge session, then quits. Writes report.txt into <dir>; its last line is "PASS" or "FAIL <count>".
//
// Cases: moving an item to another key and to another square of the same key; two separate items of one kind keep
// their own squares; a potion stack moves as one item; the taken-gun rule (OnGunTaken) moves a gun already on a key;
// the table survives the save text round trip; an older save with one item on two squares keeps the first by key order.

using System;
using System.Collections;
using System.IO;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHotkeyUniqueTest : MonoBehaviour
    {
        string dir;
        string report = "";
        int failures;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfhotkeyuniquetest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallHotkeyUniqueTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallHotkeyUniqueTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            // Same scene start as DoomerfallHotkeyShotsTest.
            float giveUp = Time.realtimeSinceStartup + 60;
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            Application.runInBackground = true;
            if (GameObject.FindWithTag("Player") == null)
                yield return SceneManager.LoadSceneAsync(1);
            while ((GameObject.FindWithTag("Player") == null || DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady
                || DaggerfallUI.Instance == null || !GameManager.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            StartGameBehaviour start = FindObjectOfType<StartGameBehaviour>();
            if (start != null)
                start.EnableVideos = false;
            if (DaggerfallUI.Instance != null)
                DaggerfallUI.Instance.enableVideos = false;
            for (int i = 0; i < 5; i++)
                yield return null;
            Directory.CreateDirectory(dir);
            if (GameObject.FindWithTag("Player") == null)
                Check(false, "the game scene loaded (is the Arena2 path set?)");
            else
                try { Run(); }
                catch (Exception e) { Check(false, "no exception: " + e); }
            report += failures == 0 ? "PASS\n" : "FAIL " + failures + "\n";
            File.WriteAllText(Path.Combine(dir, "report.txt"), report);
            Application.Quit();
        }

        void Check(bool ok, string what)
        {
            if (!ok) failures++;
            report += (ok ? "ok   " : "FAIL ") + what + "\n";
        }

        static int Count(DoomerfallHotkeys h, ulong uid)
        {
            int n = 0;
            foreach (DoomerfallHotkeys.Square sq in h.table)
                if (sq != null && sq.uid == uid) n++;
            return n;
        }

        static bool Holds(DoomerfallHotkeys h, int k, int q, DaggerfallUnityItem item)
        {
            return h.table[k, q] != null && h.table[k, q].uid == item.UID;
        }

        void Run()
        {
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            DaggerfallUnityItem mace = ItemBuilder.CreateWeapon(Weapons.Mace, WeaponMaterialTypes.Ebony);
            DaggerfallUnityItem daggerA = ItemBuilder.CreateWeapon(Weapons.Dagger, WeaponMaterialTypes.Iron);
            DaggerfallUnityItem daggerB = ItemBuilder.CreateWeapon(Weapons.Dagger, WeaponMaterialTypes.Iron);
            DaggerfallUnityItem potions = ItemBuilder.CreatePotion(ItemBuilder.CreateRandomPotion().PotionRecipeKey);
            potions.stackCount = 5;
            DoomerfallDoomItem gun = new DoomerfallDoomItem("RLShotgunPickup", true);
            foreach (DaggerfallUnityItem item in new[] { mace, daggerA, daggerB, potions, gun })
                items.AddItem(item);

            DoomerfallHotkeys h = gameObject.AddComponent<DoomerfallHotkeys>();
            h.InitForShots();

            h.Assign(3, 0, mace);
            h.Assign(5, 2, mace);
            Check(h.table[3, 0] == null && Holds(h, 5, 2, mace) && Count(h, mace.UID) == 1, "mace moved from key 3 square 0 to key 5 square 2");
            h.Assign(5, 4, mace);
            Check(h.table[5, 2] == null && Holds(h, 5, 4, mace) && Count(h, mace.UID) == 1, "mace moved to another square of the same key");
            h.Assign(5, 4, mace);
            Check(Holds(h, 5, 4, mace) && Count(h, mace.UID) == 1, "assigning the same square again keeps it");

            h.Assign(6, 0, daggerA);
            h.Assign(6, 1, daggerB);
            Check(Holds(h, 6, 0, daggerA) && Holds(h, 6, 1, daggerB), "two separate daggers keep their own squares");

            h.Assign(7, 0, potions);
            h.Assign(8, 3, potions);
            Check(h.table[7, 0] == null && Holds(h, 8, 3, potions) && Count(h, potions.UID) == 1, "a potion stack moves as one item");

            h.Assign(4, 0, gun);
            h.OnGunTaken(gun, 2); // Key 2 has no hotkeys, so the automatic rule assigns it there.
            Check(h.table[4, 0] == null && Holds(h, 2, 0, gun) && Count(h, gun.UID) == 1, "the taken-gun rule moved the gun from key 4 to key 2");

            string saved = h.SaveText();
            report += "table before save: " + h.Describe() + "\n";
            h.Assign(9, 0, mace); // Change the table, then load the saved text over it.
            h.LoadText(saved);
            report += "table after load:  " + h.Describe() + "\n";
            Check(Holds(h, 5, 4, mace) && h.table[9, 0] == null && Count(h, mace.UID) == 1, "after load the mace is only on key 5 square 4");
            Check(Holds(h, 2, 0, gun) && Count(h, gun.UID) == 1 && Holds(h, 8, 3, potions) && Count(h, potions.UID) == 1
                && Holds(h, 6, 0, daggerA) && Holds(h, 6, 1, daggerB), "after load every other square is as saved");

            // An older save with the mace on key 0 and key 1: key 1 comes first in hotkey order.
            string old = string.Format("doomerfall-hotkeys 1\nactive 0 -1 -1\nsquare 0 0 {0} c df:x\nsquare 1 2 {0} c df:x\n", mace.UID);
            h.LoadText(old);
            Check(Holds(h, 1, 2, mace) && h.table[0, 0] == null && Count(h, mace.UID) == 1, "an older save's duplicate keeps the first by key order (key 1)");
            report += "table after old save: " + h.Describe() + "\n";
        }
    }
}
