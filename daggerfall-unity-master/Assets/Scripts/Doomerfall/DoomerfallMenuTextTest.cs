// Doomerfall test only (-dfmenutexttest [folder]): in a bridge session, shows item info text in Daggerfall's inventory so
// the text Doom shows can be compared with Daggerfall Unity's. Gives the player Casual Pants (the item in the owner's
// screenshot), and whenever the inventory is the top window, fills its info panel with that item, as hovering would.
// With a folder, once the inventory is open it also shows the character sheet, a shop (trade) window and the talk
// window, then the merchant, guild, repair and witches' coven popups in turn, and saves Daggerfall Unity's own render of each (the UI render target Doom is sent) to
// <folder>/dfu-<name>.png, logging each step to <folder>/dfu-steps.txt.
// Starts itself; no hook in game classes. Used by tools/menu_text/menu_text.py --menutext.

using System;
using System.Collections;
using System.IO;
using System.Reflection;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Guilds;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMenuTextTest : MonoBehaviour
    {
        static readonly MethodInfo UpdateInfo = typeof(DaggerfallInventoryWindow).GetMethod("UpdateItemInfoPanel",
            BindingFlags.Instance | BindingFlags.NonPublic, null, new[] { typeof(DaggerfallUnityItem) }, null);

        DaggerfallUnityItem pants;
        string folder;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfmenutexttest");
            if (at < 0 || Array.IndexOf(args, "-dfbridge") < 0)
                return;
            GameObject host = new GameObject("DoomerfallMenuTextTest");
            DontDestroyOnLoad(host);
            var test = host.AddComponent<DoomerfallMenuTextTest>();
            if (at + 1 < args.Length && !args[at + 1].StartsWith("-"))
                test.folder = args[at + 1];
        }

        IEnumerator Start()
        {
            while (GameObject.FindWithTag("Player") == null || DaggerfallUI.Instance == null || !GameManager.HasInstance || !GameManager.Instance.IsReady)
                yield return null;
            yield return new WaitForSecondsRealtime(3f); // the paired test character is given after the scene is ready
            pants = ItemBuilder.CreateItem(ItemGroups.MensClothing, (int)MensClothing.Casual_pants);
            GameManager.Instance.PlayerEntity.Items.AddItem(pants);
            if (folder == null)
                yield break;
            Directory.CreateDirectory(folder);
            while (!(DaggerfallUI.UIManager.TopWindow is DaggerfallInventoryWindow))
                yield return null;
            yield return Show("inventory", null);
            yield return Show("charactersheet", () => new DaggerfallCharacterSheetWindow(DaggerfallUI.UIManager));
            yield return Show("shop", () => new DaggerfallTradeWindow(DaggerfallUI.UIManager, null, DaggerfallTradeWindow.WindowModes.Buy));
            yield return Show("talk", () => new DaggerfallTalkWindow(DaggerfallUI.UIManager));
            // The NPC popups whose painted words DoomerfallPopupText redraws, each alone over the inventory.
            DaggerfallUI.UIManager.PopWindow();
            yield return Popup("merchant", () => new DaggerfallMerchantServicePopupWindow(DaggerfallUI.UIManager, Npc(0),
                DaggerfallMerchantServicePopupWindow.Services.Sell));
            yield return Popup("guild", () => new DaggerfallGuildServicePopupWindow(DaggerfallUI.UIManager,
                Npc((int)GuildNpcServices.MG_Training), FactionFile.GuildGroups.MagesGuild, MagesGuildFaction));
            yield return Popup("repair", () => new DaggerfallMerchantRepairPopupWindow(DaggerfallUI.UIManager, Npc(0)));
            yield return Popup("coven", () => new DaggerfallWitchesCovenPopupWindow(DaggerfallUI.UIManager, Npc(0)));
            Step("done");
        }

        const int MagesGuildFaction = 40;

        IEnumerator Popup(string name, Func<IUserInterfaceWindow> make)
        {
            yield return Show(name, make);
            if (!(DaggerfallUI.UIManager.TopWindow is DaggerfallInventoryWindow))
                DaggerfallUI.UIManager.PopWindow();
        }

        StaticNPC Npc(int factionId)
        {
            var npc = new GameObject("DoomerfallMenuTextTestNpc").AddComponent<StaticNPC>();
            FieldInfo field = typeof(StaticNPC).GetField("npcData", BindingFlags.Instance | BindingFlags.NonPublic);
            object data = field.GetValue(npc);
            typeof(StaticNPC.NPCData).GetField("factionID").SetValue(data, factionId);
            field.SetValue(npc, data);
            return npc;
        }

        IEnumerator Show(string name, Func<IUserInterfaceWindow> make)
        {
            if (make != null)
            {
                try
                {
                    DaggerfallUI.UIManager.PushWindow(make());
                }
                catch (Exception e)
                {
                    Step(name + " failed to open: " + e.Message);
                    yield break;
                }
            }
            yield return new WaitForSecondsRealtime(0.5f);
            if (DaggerfallUI.UIManager.TopWindow is DaggerfallMessageBox) // the shop outdoors says "no trade" first
                DaggerfallUI.UIManager.PopWindow();
            yield return new WaitForSecondsRealtime(2f);
            yield return new WaitForEndOfFrame();
            UserInterfaceRenderTarget target = DaggerfallUI.Instance.CustomRenderTarget;
            RenderTexture texture = target ? target.TargetTexture : null;
            if (texture)
            {
                RenderTexture previous = RenderTexture.active;
                RenderTexture.active = texture;
                var image = new Texture2D(texture.width, texture.height, TextureFormat.RGB24, false);
                image.ReadPixels(new Rect(0, 0, texture.width, texture.height), 0, 0);
                RenderTexture.active = previous;
                File.WriteAllBytes(Path.Combine(folder, "dfu-" + name + ".png"), image.EncodeToPNG());
                Destroy(image);
            }
            Step(string.Format("{0} {1:HH:mm:ss.fff} top {2} render {3}", name, DateTime.Now,
                DaggerfallUI.UIManager.TopWindow == null ? "none" : DaggerfallUI.UIManager.TopWindow.GetType().Name,
                texture ? texture.width + "x" + texture.height : "none"));
            yield return new WaitForSecondsRealtime(2.5f); // Doom screenshots once a second; keep the window up for a few
        }

        void Step(string line)
        {
            File.AppendAllText(Path.Combine(folder, "dfu-steps.txt"), line + Environment.NewLine);
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
