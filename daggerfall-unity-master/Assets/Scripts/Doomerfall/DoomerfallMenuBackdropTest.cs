// Doomerfall test only (-dfmenubackdroptest <folder>): in a bridge session, once Doom's test has opened the inventory,
// shows small and full-screen Daggerfall windows over it in turn (merchant Talk/Sell popup, message boxes, pause
// options, spellbook, automap, travel map), and for each saves Daggerfall Unity's own render with its alpha channel
// (the UI render target Doom is sent) as <folder>/dfu-<name>.png, logging the pixel alpha counts to
// <folder>/dfu-steps.txt. Doom's test screenshots each window meanwhile, so the backdrop Doom shows can be checked.
// Starts itself; no hook in game classes. Used by tools/menu_text/menu_text.py --backdrop.

using System;
using System.Collections;
using System.IO;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMenuBackdropTest : MonoBehaviour
    {
        string folder;
        StaticNPC merchant;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfmenubackdroptest");
            if (at < 0 || at + 1 >= args.Length || Array.IndexOf(args, "-dfbridge") < 0)
                return;
            GameObject host = new GameObject("DoomerfallMenuBackdropTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallMenuBackdropTest>().folder = args[at + 1];
        }

        IEnumerator Start()
        {
            Directory.CreateDirectory(folder);
            Step("started");
            // The popup reads only the faction of the NPC it serves. Inactive, so it never registers as a world NPC.
            var stand = new GameObject("DoomerfallMenuBackdropTestNpc");
            stand.SetActive(false);
            stand.transform.SetParent(transform, false);
            merchant = stand.AddComponent<StaticNPC>();
            while (GameObject.FindWithTag("Player") == null || DaggerfallUI.Instance == null || DaggerfallUI.UIManager == null
                || !(DaggerfallUI.UIManager.TopWindow is DaggerfallInventoryWindow))
                yield return null;
            IUserInterfaceManager ui = DaggerfallUI.UIManager;
            yield return Show("inventory", null);
            yield return Show("merchant", () => ui.PushWindow(new DaggerfallMerchantServicePopupWindow(ui, merchant, DaggerfallMerchantServicePopupWindow.Services.Sell)));
            yield return Show("messagebox", () => ui.PushWindow(Box(ui, null)));
            yield return Show("messagebox-dimmed", () => ui.PushWindow(Box(ui, DaggerfallUI.Instance.DaggerfallHUD)));
            yield return Show("pause", () => DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenPauseOptionsDialog));
            yield return Show("spellbook", () => DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenSpellBookWindow));
            yield return Show("automap", () => DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenAutomap));
            yield return Show("travelmap", () => DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenTravelMapWindow));
            Step("done");
        }

        static DaggerfallMessageBox Box(IUserInterfaceManager ui, IUserInterfaceWindow previous)
        {
            var box = new DaggerfallMessageBox(ui, previous);
            box.SetText("The Doom view should show around this box.");
            box.ClickAnywhereToClose = true;
            return box;
        }

        IEnumerator Show(string name, Action open)
        {
            if (open != null)
            {
                try
                {
                    open();
                }
                catch (Exception e)
                {
                    Step(name + " failed to open: " + e.Message);
                    yield break;
                }
            }
            yield return new WaitForSecondsRealtime(2f);
            yield return new WaitForEndOfFrame();
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            Step(string.Format("{0} {1:HH:mm:ss.fff} top {2} {3}", name, DateTime.Now, top == null ? "none" : top.GetType().Name, Save(name)));
            yield return new WaitForSecondsRealtime(2.5f); // Doom screenshots once a second
            while (!(DaggerfallUI.UIManager.TopWindow is DaggerfallInventoryWindow) && DaggerfallUI.UIManager.TopWindow != null)
                DaggerfallUI.UIManager.PopWindow();
            yield return new WaitForSecondsRealtime(1f);
        }

        string Save(string name)
        {
            UserInterfaceRenderTarget target = DaggerfallUI.Instance.CustomRenderTarget;
            RenderTexture texture = target ? target.TargetTexture : null;
            if (!texture)
                return "no render";
            RenderTexture previous = RenderTexture.active;
            RenderTexture.active = texture;
            var image = new Texture2D(texture.width, texture.height, TextureFormat.RGBA32, false);
            image.ReadPixels(new Rect(0, 0, texture.width, texture.height), 0, 0);
            RenderTexture.active = previous;
            File.WriteAllBytes(Path.Combine(folder, "dfu-" + name + ".png"), image.EncodeToPNG());
            int clear = 0, opaque = 0, partial = 0;
            foreach (Color32 c in image.GetPixels32())
            {
                if (c.a == 0) clear++;
                else if (c.a == 255) opaque++;
                else partial++;
            }
            Destroy(image);
            return string.Format("render {0}x{1} alpha: clear {2} opaque {3} partial {4}", texture.width, texture.height, clear, opaque, partial);
        }

        void Step(string line)
        {
            File.AppendAllText(Path.Combine(folder, "dfu-steps.txt"), line + Environment.NewLine);
        }
    }
}
