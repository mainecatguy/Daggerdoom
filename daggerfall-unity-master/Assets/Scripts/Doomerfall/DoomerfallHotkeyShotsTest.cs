// Doomerfall test only (-dfhotkeyshots <dir>): opens Daggerfall's inventory with the real hotkey popup on top and saves
// screenshots, then quits. Needs no bridge session, so the squares hold Daggerfall items (Doom item art comes from Doom).
//
// Key 3 gets: square 1 a mace, square 2 a potion, Ctrl a cuirass, Alt a dagger that then leaves the inventory, so the
// popup shows a filled, an empty, and a used-up square. Writes popup.png, inventory.png, and report.txt into <dir>.

using System;
using System.Collections;
using System.IO;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHotkeyShotsTest : MonoBehaviour
    {
        string dir;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfhotkeyshots");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallHotkeyShotsTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallHotkeyShotsTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            // Same scene start as DoomerfallTravelHintTest.
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
            if (DaggerfallUI.Instance != null)
                DaggerfallUI.Instance.PopToHUD();
            Directory.CreateDirectory(dir);
            string report;
            if (GameObject.FindWithTag("Player") == null)
                report = "error: the game scene never loaded (is the Arena2 path set?)\n";
            else
            {
                yield return new WaitForSecondsRealtime(2f);
                report = "";
                IEnumerator run = Run(r => report += r + "\n");
                while (true)
                {
                    bool more;
                    try { more = run.MoveNext(); }
                    catch (Exception e) { report += "error " + e + "\n"; more = false; }
                    if (!more) break;
                    yield return run.Current;
                }
            }
            File.WriteAllText(Path.Combine(dir, "report.txt"), report);
            Application.Quit();
        }

        IEnumerator Run(Action<string> report)
        {
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            DaggerfallUnityItem mace = ItemBuilder.CreateWeapon(Weapons.Mace, WeaponMaterialTypes.Ebony);
            DaggerfallUnityItem potion = ItemBuilder.CreatePotion(ItemBuilder.CreateRandomPotion().PotionRecipeKey);
            DaggerfallUnityItem cuirass = ItemBuilder.CreateArmor(Genders.Male, Races.Breton, Armor.Cuirass, ArmorMaterialTypes.Steel);
            DaggerfallUnityItem dagger = ItemBuilder.CreateWeapon(Weapons.Dagger, WeaponMaterialTypes.Iron);
            foreach (DaggerfallUnityItem item in new[] { mace, potion, cuirass, dagger })
                items.AddItem(item);

            DoomerfallHotkeys hotkeys = gameObject.AddComponent<DoomerfallHotkeys>();
            hotkeys.InitForShots();
            hotkeys.Assign(3, 0, mace);
            hotkeys.Assign(3, 1, potion);
            hotkeys.Assign(3, 3, cuirass);
            hotkeys.Assign(3, 4, dagger); // A consumable square: it stays, greyed, once no dagger is left.
            items.RemoveItem(dagger);
            report("table: " + hotkeys.Describe());

            IUserInterfaceManager ui = DaggerfallUI.Instance.UserInterfaceManager;
            DaggerfallInventoryWindow inventory = new DaggerfallInventoryWindow(ui);
            ui.PushWindow(inventory);
            for (int i = 0; i < 10; i++)
                yield return null;
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, "inventory.png"));
            yield return new WaitForEndOfFrame();
            yield return null;

            ui.PushWindow(new DoomerfallHotkeyPopup(ui, inventory, mace, 3));
            for (int i = 0; i < 10; i++)
                yield return null;
            report("top window: " + ui.TopWindow.GetType().Name);
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, "popup.png"));
            yield return new WaitForEndOfFrame();
            yield return null;
            report("done");
        }
    }
}
