// Doomerfall test only (-dfmenutexttest <dir>): shows item info text in Daggerfall's inventory, to compare text sharpness
// between Daggerfall Unity and the same window shown in Doom. Gives the player Casual Pants (the item in the owner's
// screenshot), and whenever the inventory is the top window, fills its info panel with that item, as hovering would.
// Without a bridge session it also opens the inventory itself, saves <dir>/dfu-inventory.png, and quits.
// Starts itself; no hook in game classes.

using System;
using System.Collections;
using System.IO;
using System.Reflection;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMenuTextTest : MonoBehaviour
    {
        static readonly MethodInfo UpdateInfo = typeof(DaggerfallInventoryWindow).GetMethod("UpdateItemInfoPanel",
            BindingFlags.Instance | BindingFlags.NonPublic, null, new[] { typeof(DaggerfallUnityItem) }, null);

        string dir;
        DaggerfallUnityItem pants;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfmenutexttest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallMenuTextTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallMenuTextTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            bool paired = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfbridge") >= 0;
            float giveUp = Time.realtimeSinceStartup + 60;
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            Application.runInBackground = true;
            if (!paired && GameObject.FindWithTag("Player") == null)
                yield return SceneManager.LoadSceneAsync(1);
            while ((GameObject.FindWithTag("Player") == null || DaggerfallUI.Instance == null || !GameManager.HasInstance
                || !GameManager.Instance.IsReady) && Time.realtimeSinceStartup < giveUp + (paired ? 600 : 0))
                yield return null;
            if (!paired)
            {
                StartGameBehaviour start = FindObjectOfType<StartGameBehaviour>();
                if (start != null)
                    start.EnableVideos = false;
                DaggerfallUI.Instance.enableVideos = false;
                yield return new WaitForSecondsRealtime(2f);
                DaggerfallUI.Instance.PopToHUD();
            }
            else
            {
                yield return new WaitForSecondsRealtime(3f); // the paired test character is given after the scene is ready
            }
            pants = ItemBuilder.CreateItem(ItemGroups.MensClothing, (int)MensClothing.Casual_pants);
            GameManager.Instance.PlayerEntity.Items.AddItem(pants);
            if (paired)
                yield break; // Update fills the panel whenever Doom opens the inventory.

            // settings.ini's fullscreen mode wins over -screen-width/-height at start, and a fullscreen window on a
            // private desktop captures black, so take the asked size as a plain window.
            string[] args = Environment.GetCommandLineArgs();
            int w = Array.IndexOf(args, "-screen-width"), h = Array.IndexOf(args, "-screen-height");
            if (w >= 0 && h >= 0 && w + 1 < args.Length && h + 1 < args.Length)
                Screen.SetResolution(int.Parse(args[w + 1]), int.Parse(args[h + 1]), FullScreenMode.Windowed);
            Directory.CreateDirectory(dir);
            DaggerfallUI.Instance.UserInterfaceManager.PushWindow(new DaggerfallInventoryWindow(DaggerfallUI.Instance.UserInterfaceManager));
            yield return new WaitForSecondsRealtime(2f);
            File.WriteAllText(Path.Combine(dir, "dfu-report.txt"), string.Format("screen {0}x{1}, top window {2}, player scene loaded {3}\n",
                Screen.width, Screen.height, DaggerfallUI.UIManager.TopWindow, GameObject.FindWithTag("Player") != null));
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, "dfu-inventory.png"));
            yield return new WaitForSecondsRealtime(1f);
            Application.Quit();
        }

        void Update()
        {
            if (pants == null || !DaggerfallUI.Instance)
                return;
            var inventory = DaggerfallUI.UIManager.TopWindow as DaggerfallInventoryWindow;
            if (inventory != null && UpdateInfo != null)
                UpdateInfo.Invoke(inventory, new object[] { pants });
        }
    }
}
