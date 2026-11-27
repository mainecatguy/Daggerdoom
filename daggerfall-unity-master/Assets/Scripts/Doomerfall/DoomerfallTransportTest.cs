// Doomerfall test only (-dftransporttest <file> [none|large]): once the game runs, gives the player a horse, a cart and a
// small ship (a large ship with "large"; with "none", takes any away), and logs, each time it changes, the top window, the transport mode, what
// the player owns, the map pixel, and the transport window's panel in Daggerfall's 320x200 layout, so a test can follow
// the transport menu from Doom.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using System.Reflection;
using DaggerfallWorkshop.Game.Banking;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTransportTest : MonoBehaviour
    {
        static readonly FieldInfo PanelField = typeof(DaggerfallTransportWindow).GetField("mainPanel", BindingFlags.NonPublic | BindingFlags.Instance);

        string path, last;
        DoomerfallPositionSync sync;
        float readyAt;
        bool done, none, large;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dftransporttest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallTransportTest");
            DontDestroyOnLoad(host);
            DoomerfallTransportTest test = host.AddComponent<DoomerfallTransportTest>();
            test.path = args[at + 1];
            test.none = at + 2 < args.Length && args[at + 2] == "none";
            test.large = at + 2 < args.Length && args[at + 2] == "large";
            File.WriteAllText(test.path, "transport test: started\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Prepare(); }
            catch (Exception e) { Write("prepare error " + e.GetType().Name + " " + e.Message); done = true; }
            string line;
            try { line = Describe(); }
            catch (Exception e) { line = "error " + e.GetType().Name + " " + e.Message; }
            if (line == last)
                return;
            last = line;
            Write(line);
        }

        void Prepare()
        {
            if (done || !GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null)
            {
                readyAt = 0;
                return;
            }
            if (readyAt == 0)
                readyAt = Time.realtimeSinceStartup + 1f;
            if (Time.realtimeSinceStartup < readyAt)
                return;
            done = true;

            foreach (Transportation kind in new[] { Transportation.Horse, Transportation.Small_cart })
            {
                DaggerfallUnityItem item;
                while ((item = player.Items.GetItem(ItemGroups.Transportation, (int)kind)) != null)
                    player.Items.RemoveItem(item);
                if (!none)
                    player.Items.AddItem(ItemBuilder.CreateItem(ItemGroups.Transportation, (int)kind));
            }
            if (none)
                DaggerfallBankManager.ResetShip();
            else
                DaggerfallBankManager.AssignShipToPlayer(large ? ShipType.Large : ShipType.Small);
            Write(none ? "prepared: no horse, cart or ship" : large ? "prepared: horse, cart and large ship" : "prepared: horse, cart and small ship");
        }

        static string Describe()
        {
            if (!DaggerfallUI.Instance || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return "none";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            TransportManager t = GameManager.Instance.TransportManager;
            string panel = "-";
            var window = top as DaggerfallTransportWindow;
            if (window != null && PanelField != null)
            {
                var p = PanelField.GetValue(window) as Panel;
                if (p != null)
                    panel = string.Format("{0:F0},{1:F0} {2:F0}x{3:F0}", p.Position.x, p.Position.y, p.Size.x, p.Size.y);
            }
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            return string.Format("top {0} | mode {1} | horse {2} cart {3} ship {4} | pixel {5},{6} | panel {7}",
                top == null ? "none" : top.GetType().Name, t.TransportMode, t.HasHorse(), t.HasCart(), t.ShipAvailiable(),
                gps.CurrentMapPixel.X, gps.CurrentMapPixel.Y, panel);
        }
    }
}
