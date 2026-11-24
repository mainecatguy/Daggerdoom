// Doomerfall: weapon and item hotkeys. Runs only in a bridge session.
//
// Hover over an item in Daggerfall's inventory and press 1-0 to open a popup of five squares for that key: three
// for the plain key (pressing it again cycles), one for Ctrl+key, one for Alt+key. A square is a reference only.
// In Doom, a weapon slot key on a generated map sends the press here (DFB_KIND_HOTKEY).
//
// Daggerfall holds every gun. Doom holds only the active one. Drawing a gun sends its saved Doom state and asks Doom to
// take the current gun, whose state comes back and is stored on its Daggerfall item (DoomerfallDoomItem.GunState).
// The table, the active gun, and the active square are saved in DoomerfallHotkeys.txt beside Daggerfall's save.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHotkeys : MonoBehaviour
    {
        internal const string EquipMessage = "Press # over an item to assign hotkeys. Equip doom weapons through their hotkey.";
        internal const int Keys = 10, Squares = 5; // Squares 0-2 plain, 3 Ctrl, 4 Alt.
        const float RequestTimeout = 10f;

        internal sealed class Square
        {
            public ulong uid;
            public char kind;       // 'g' gun, 'a' armor, 'c' consumable (keeps its square when it runs out)
            public string identity; // What a consumable square takes next: "doom:<class>" or "df:<group>:<template>:<recipe>"
        }

        internal static DoomerfallHotkeys Instance { get; private set; }
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        internal readonly Square[,] table = new Square[Keys, Squares];
        int activeKey = -1, activeSquare = -1;
        DaggerfallUnityItem activeItem; // The gun Doom holds. Kept as an object so a dropped gun's state still finds it.
        ulong loadedActiveUid;

        // The one gun request in flight.
        uint request, nextRequest = 1;
        uint requestFlags;
        DoomerfallDoomItem requestItem;
        int requestKey = -1, requestSquare = -1;
        float requestDeadline;
        bool activeStored;
        readonly List<string> stashLines = new List<string>();
        readonly List<DoomerfallDoomItem> adopted = new List<DoomerfallDoomItem>();
        bool adoptWanted = true;
        float nextCheck;
        DoomerfallDoomItem pendingDraw; // A taken gun put on its free slot key, drawn once no swap is in flight.
        int pendingDrawKey;

        // Inventory window hover.
        DaggerfallInventoryWindow hoverWindow;
        DaggerfallUnityItem hovered;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            Instance = this;
            bridge = owner;
            sync = positionSync;
            SaveLoadManager.DoomerfallSaveExtra = SaveText;
            SaveLoadManager.DoomerfallLoadExtra = LoadText;
            SaveLoadManager.OnStartLoad += OnStartLoad;
            StartGameBehaviour.OnNewGame += OnNewGame;
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfhotkeystest") >= 0)
                gameObject.AddComponent<DoomerfallHotkeysTest>().Init(this);
        }

        void OnDestroy()
        {
            SaveLoadManager.OnStartLoad -= OnStartLoad;
            StartGameBehaviour.OnNewGame -= OnNewGame;
            if (SaveLoadManager.DoomerfallSaveExtra == SaveText) SaveLoadManager.DoomerfallSaveExtra = null;
            if (SaveLoadManager.DoomerfallLoadExtra == LoadText) SaveLoadManager.DoomerfallLoadExtra = null;
            if (Instance == this) Instance = null;
        }

        internal void InitForShots() { Instance = this; enabled = false; } // Test only: DoomerfallHotkeyShotsTest, no bridge.

        void Log(string text) { if (bridge != null) bridge.LogLine("hotkeys: " + text); }

        void ResetState()
        {
            Array.Clear(table, 0, table.Length);
            activeKey = activeSquare = -1;
            activeItem = null;
            loadedActiveUid = 0;
            request = 0;
            stashLines.Clear();
            adopted.Clear();
            adoptWanted = true;
            pendingDraw = null;
        }

        void OnNewGame() { ResetState(); Log("new game: table cleared, the starting gun will be adopted"); }
        void OnStartLoad(SaveData_v1 data) { request = 0; stashLines.Clear(); }

        // ---- Save ----

        string SaveText()
        {
            StringBuilder s = new StringBuilder("doomerfall-hotkeys 1\n");
            s.AppendFormat("active {0} {1} {2}\n", activeItem != null ? activeItem.UID : 0, activeKey, activeSquare);
            for (int k = 0; k < Keys; k++)
                for (int q = 0; q < Squares; q++)
                {
                    Square sq = table[k, q];
                    if (sq != null)
                        s.AppendFormat("square {0} {1} {2} {3} {4}\n", k, q, sq.uid, sq.kind, sq.identity ?? "-");
                }
            return s.ToString();
        }

        void LoadText(string text)
        {
            ResetState();
            if (!string.IsNullOrEmpty(text))
                foreach (string line in text.Split('\n'))
                {
                    string[] f = line.Trim().Split(' ');
                    try
                    {
                        if (f[0] == "active" && f.Length >= 4)
                        {
                            loadedActiveUid = ulong.Parse(f[1]);
                            activeKey = int.Parse(f[2]);
                            activeSquare = int.Parse(f[3]);
                        }
                        else if (f[0] == "square" && f.Length >= 6)
                            table[int.Parse(f[1]), int.Parse(f[2])] = new Square { uid = ulong.Parse(f[3]), kind = f[4][0], identity = f[5] == "-" ? null : f[5] };
                    }
                    catch (Exception e) { Log("bad save line \"" + line + "\": " + e.Message); }
                }
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            activeItem = loadedActiveUid != 0 ? items.GetItem(loadedActiveUid) : null;
            adoptWanted = activeItem == null; // An older save, or a lost gun: take what Doom holds.
            Log(string.Format("loaded: active {0} \"{1}\" key {2} square {3}, {4} squares: {5}", loadedActiveUid,
                activeItem != null ? activeItem.ItemName : "none", activeKey, activeSquare, CountSquares(), Describe()));
        }

        int CountSquares()
        {
            int n = 0;
            foreach (Square sq in table) if (sq != null) n++;
            return n;
        }

        internal string Describe()
        {
            StringBuilder s = new StringBuilder();
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int k = 0; k < Keys; k++)
                for (int q = 0; q < Squares; q++)
                    if (table[k, q] != null)
                    {
                        DaggerfallUnityItem item = items.GetItem(table[k, q].uid);
                        s.AppendFormat("[{0}.{1} {2}] ", k, q, item != null ? item.ItemName : "missing");
                    }
            return s.ToString();
        }

        // ---- Which items can be hotkeyed ----

        internal static string Refusal(DaggerfallUnityItem item)
        {
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            if (doom != null && doom.IsWearable) return DoomerfallDoomItem.WearMessage;
            if (doom != null || item.IsPotion || item.ItemGroup == ItemGroups.Armor) return null;
            if (item.ItemGroup == ItemGroups.MensClothing || item.ItemGroup == ItemGroups.WomensClothing) return "Clothing cannot be hotkeyed.";
            return "That cannot be hotkeyed.";
        }

        static string IdentityOf(DaggerfallUnityItem item)
        {
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            if (doom != null) return "doom:" + doom.DoomClass;
            return string.Format("df:{0}:{1}:{2}", (int)item.ItemGroup, item.TemplateIndex, item.PotionRecipeKey);
        }

        static char KindOf(DaggerfallUnityItem item)
        {
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            if (doom != null && doom.IsGun) return 'g';
            if (item.ItemGroup == ItemGroups.Armor) return 'a';
            return 'c';
        }

        internal void Assign(int key, int square, DaggerfallUnityItem item)
        {
            table[key, square] = new Square { uid = item.UID, kind = KindOf(item), identity = IdentityOf(item) };
            Log(string.Format("assigned \"{0}\" to key {1} square {2}", item.ItemName, key, square));
        }

        internal void Clear(int key, int square)
        {
            table[key, square] = null;
            Log(string.Format("cleared key {0} square {1}", key, square));
        }

        // The item a square uses now, or null. A consumable that ran out takes the next item of the same kind.
        internal DaggerfallUnityItem Resolve(Square sq)
        {
            if (sq == null) return null;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            DaggerfallUnityItem item = items.GetItem(sq.uid);
            if (item != null || sq.kind != 'c') return item;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem other = items.GetItem(i);
                if (IdentityOf(other) == sq.identity)
                {
                    sq.uid = other.UID;
                    return other;
                }
            }
            return null;
        }

        // ---- Inventory window ----

        // From DaggerfallInventoryWindow.Update. A number key over an item opens its hotkey popup.
        internal static void InventoryUpdate(DaggerfallInventoryWindow window, BaseScreenComponent list)
        {
            if (Instance == null || !DoomerfallInput.Active)
                return;
            if (Instance.hoverWindow != window)
            {
                if (Instance.hoverWindow != null) Instance.hoverWindow.OnItemHover -= Instance.OnHover;
                Instance.hoverWindow = window;
                Instance.hovered = null;
                window.OnItemHover += Instance.OnHover;
            }
            for (int k = 0; k < Keys; k++)
                if (DoomerfallInput.PollDown(KeyCode.Alpha0 + k) && Instance.hovered != null && list.MouseOverComponent)
                {
                    string refusal = Refusal(Instance.hovered);
                    if (refusal != null)
                        DaggerfallUI.MessageBox(refusal);
                    else
                        DaggerfallUI.UIManager.PushWindow(new DoomerfallHotkeyPopup(DaggerfallUI.UIManager, window, Instance.hovered, k));
                    return;
                }
        }

        void OnHover(DaggerfallUnityItem item, DaggerfallInventoryWindow.ItemHoverLocation loc)
        {
            hovered = loc == DaggerfallInventoryWindow.ItemHoverLocation.LocalList ? item : null;
        }

        // From DaggerfallInventoryWindow.EquipItem. True when Daggerfall must not equip this item.
        internal static bool BlockEquip(DaggerfallUnityItem item)
        {
            if (item is DoomerfallAmmoItem) return true; // Nothing to equip, and its zero condition would read as "broken".
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            if (doom == null) return false;
            DaggerfallUI.MessageBox(doom.IsWearable ? DoomerfallDoomItem.WearMessage : EquipMessage);
            return true;
        }

        // ---- Taking a gun ----

        // A gun the player just took with Use. When the key of its Doom weapon slot has no hotkeys yet, the gun goes on
        // that key and is drawn at once (the owner's interim rule, 2026-11-24).
        internal void OnGunTaken(DoomerfallDoomItem gun, int slot)
        {
            if (slot < 0 || slot >= Keys)
            {
                Log(string.Format("took \"{0}\", which has no Doom weapon slot; left in the inventory", gun.DoomClass));
                return;
            }
            for (int q = 0; q < Squares; q++)
                if (table[slot, q] != null)
                {
                    Log(string.Format("took \"{0}\"; key {1} already has hotkeys, so it stays in the inventory", gun.DoomClass, slot));
                    return;
                }
            Assign(slot, 0, gun);
            pendingDraw = gun;
            pendingDrawKey = slot;
            TryPendingDraw();
        }

        // Waits for the starting gun to be adopted and for any swap in flight, so neither loses a gun.
        void TryPendingDraw()
        {
            if (pendingDraw == null || request != 0 || adoptWanted || !Playing())
                return;
            DoomerfallDoomItem gun = pendingDraw;
            pendingDraw = null;
            if (!GameManager.Instance.PlayerEntity.Items.Contains(gun.UID) || table[pendingDrawKey, 0] == null || table[pendingDrawKey, 0].uid != gun.UID)
                return;
            Log(string.Format("key {0} was free: drawing the new \"{1}\"", pendingDrawKey, gun.DoomClass));
            DrawGun(gun, pendingDrawKey, 0);
        }

        // ---- Presses ----

        internal void OnEvent(ushort kind, uint req, uint status, string cls)
        {
            switch (kind)
            {
                case Dfb.KIND_HOTKEY: Press((int)req, status); break;
                case Dfb.KIND_GUN_STATE:
                    if (req == request) stashLines.Add(cls + "=" + status);
                    break;
                case Dfb.KIND_GUN_STASHED: OnStashed(req, cls); break;
                case Dfb.KIND_GUN_KEPT: OnKept(req, cls); break;
                case Dfb.KIND_GUN_EQUIPPED: OnEquipped(req, status, cls); break;
            }
        }

        bool Playing()
        {
            return GameManager.HasInstance && GameManager.Instance.IsPlayingGame() && !sync.LoadRunning && !SaveLoadManager.Instance.LoadInProgress;
        }

        internal void Press(int key, uint mod)
        {
            if (key < 0 || key >= Keys || !Playing())
                return;
            int first = mod == Dfb.HOTKEY_CTRL ? 3 : mod == Dfb.HOTKEY_ALT ? 4 : 0;
            int count = first == 0 ? 3 : 1;
            // Pressing the plain key of the active square again moves to the next filled square.
            int start = first == 0 && activeKey == key && activeSquare >= 0 && activeSquare < 3 ? activeSquare + 1 : first;
            Square grey = null;
            for (int n = 0; n < count; n++)
            {
                int q = first + (start - first + n) % count;
                Square sq = table[key, q];
                if (sq == null) continue;
                DaggerfallUnityItem item = Resolve(sq);
                if (item == null) { grey = grey ?? sq; continue; }
                Use(key, q, item);
                return;
            }
            string what = grey != null ? "You have none left for that hotkey." : "Nothing is assigned to that hotkey.";
            DaggerfallUI.AddHUDText(what);
            Log(string.Format("press key {0} modifier {1}: {2}", key, mod, what));
        }

        void Use(int key, int square, DaggerfallUnityItem item)
        {
            Log(string.Format("press key {0} square {1}: \"{2}\"", key, square, item.ItemName));
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            if (doom != null && doom.IsGun)
                DrawGun(doom, key, square);
            else if (doom != null)
                DoomerfallDoomItems.Use(doom);
            else if (item.IsPotion)
            {
                GameManager.Instance.PlayerEffectManager.DrinkPotion(item);
                player.Items.RemoveOne(item);
            }
            else if (item.ItemGroup == ItemGroups.Armor)
            {
                if (item.IsEquipped)
                {
                    player.ItemEquipTable.UnequipItem(item);
                    player.UpdateEquippedArmorValues(item, false);
                }
                else
                {
                    List<DaggerfallUnityItem> off = player.ItemEquipTable.EquipItem(item, true, false);
                    if (off != null) foreach (DaggerfallUnityItem o in off) player.UpdateEquippedArmorValues(o, false);
                    player.UpdateEquippedArmorValues(item, true);
                }
                DaggerfallUI.AddHUDText(item.ItemName + (item.IsEquipped ? " equipped." : " removed."));
            }
        }

        // ---- Guns ----

        void DrawGun(DoomerfallDoomItem gun, int key, int square)
        {
            if (request != 0)
                return; // One swap at a time. The press is dropped, as Doom drops a slot key during a weapon change.
            if (gun == activeItem)
            {
                activeKey = key;
                activeSquare = square;
                Send(Dfb.KIND_GUN_EQUIP, Begin(Dfb.GUN_SELECT, gun, key, square), Dfb.GUN_SELECT, gun.DoomClass);
                return;
            }
            uint req = Begin(Dfb.GUN_GIVE, gun, key, square);
            string state = gun.GunState;
            foreach (string line in state.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
            {
                int eq = line.LastIndexOf('=');
                int amount;
                if (eq > 0 && int.TryParse(line.Substring(eq + 1), out amount))
                    Send(Dfb.KIND_GUN_STATE, req, (uint)amount, line.Substring(0, eq));
            }
            Send(Dfb.KIND_GUN_EQUIP, req, Dfb.GUN_GIVE, gun.DoomClass);
            Log(string.Format("draw \"{0}\" with state \"{1}\" (request {2}), putting away \"{3}\"", gun.ItemName, state, req, activeItem != null ? activeItem.ItemName : "nothing"));
        }

        uint Begin(uint flags, DoomerfallDoomItem gun, int key, int square)
        {
            request = nextRequest++;
            requestFlags = flags;
            requestItem = gun;
            requestKey = key;
            requestSquare = square;
            requestDeadline = Time.unscaledTime + RequestTimeout;
            activeStored = false;
            stashLines.Clear();
            adopted.Clear();
            return request;
        }

        void OnStashed(uint req, string cls)
        {
            if (req != request)
                return;
            string state = string.Join(";", stashLines.ToArray());
            stashLines.Clear();
            DoomerfallDoomItem active = activeItem as DoomerfallDoomItem;
            // Doom names a put-away gun by its plain pickup, so a gun taken from DRLA's RL<Weapon>PickupModded comes back as RL<Weapon>Pickup.
            if (active != null && !activeStored && (active.DoomClass == cls || active.DoomClass == cls + "Modded"))
            {
                active.GunState = state;
                activeStored = true;
                Log(string.Format("put away \"{0}\" with state \"{1}\"", active.ItemName, state));
            }
            else if (requestFlags == Dfb.GUN_ADOPT)
            {
                DoomerfallDoomItem item = Adopt(cls);
                item.GunState = state;
                adopted.Add(item);
            }
            else
                Log(string.Format("Doom held an unexpected gun \"{0}\" (state \"{1}\"); not added", cls, state));
        }

        DoomerfallDoomItem Adopt(string cls)
        {
            DoomerfallDoomItem item = new DoomerfallDoomItem(cls, true);
            GameManager.Instance.PlayerEntity.Items.AddItem(item);
            Log(string.Format("adopted Doom's \"{0}\" into Daggerfall's inventory", cls));
            return item;
        }

        void OnKept(uint req, string cls)
        {
            if (req != request || requestFlags != Dfb.GUN_ADOPT)
                return;
            activeItem = Adopt(cls);
        }

        void OnEquipped(uint req, uint status, string cls)
        {
            if (req != request)
                return;
            request = 0;
            uint flags = requestFlags;
            if (flags == Dfb.GUN_GIVE && status == Dfb.ITEM_TAKEN)
            {
                activeItem = requestItem;
                requestItem.GunState = ""; // Doom holds it now.
                activeKey = requestKey;
                activeSquare = requestSquare;
            }
            else if (flags == Dfb.GUN_CLEAR || (flags == Dfb.GUN_GIVE && activeStored))
                activeItem = null;
            if (flags == Dfb.GUN_ADOPT)
            {
                adoptWanted = false;
                DoomerfallDoomItem start = activeItem as DoomerfallDoomItem ?? (adopted.Count > 0 ? adopted[0] : null);
                if (start != null && CountSquares() == 0)
                {
                    Assign(2, 0, start); // The player starts with a gun on a hotkey. Key 2 is Doom's pistol slot.
                    if (activeItem == start) { activeKey = 2; activeSquare = 0; }
                }
                if (activeItem == null && start != null)
                    DrawGun(start, CountSquares() > 0 && table[2, 0] != null && table[2, 0].uid == start.UID ? 2 : -1, 0);
            }
            Log(string.Format("request {0} flags {1} done, status {2}: active \"{3}\" key {4} square {5}; table {6}", req, flags, status,
                activeItem != null ? activeItem.ItemName : "none", activeKey, activeSquare, Describe()));
            RefreshInventory();
        }

        void Update()
        {
            if (request != 0 && Time.unscaledTime > requestDeadline)
            {
                Log("request " + request + " timed out");
                request = 0;
            }
            if (Time.unscaledTime < nextCheck || !Playing())
                return;
            nextCheck = Time.unscaledTime + 0.25f;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            // A gun or armor that left the inventory loses its squares. A consumable keeps its square, greyed.
            for (int k = 0; k < Keys; k++)
                for (int q = 0; q < Squares; q++)
                {
                    Square sq = table[k, q];
                    if (sq != null && sq.kind != 'c' && !items.Contains(sq.uid))
                        Clear(k, q);
                }
            if (request != 0 || GameManager.IsGamePaused)
                return;
            if (activeItem != null && !items.Contains(activeItem.UID))
            {
                Log("the active gun \"" + activeItem.ItemName + "\" left the inventory; Doom puts it away");
                Begin(Dfb.GUN_CLEAR, null, -1, -1);
                activeKey = activeSquare = -1;
                Send(Dfb.KIND_GUN_EQUIP, request, Dfb.GUN_CLEAR, "");
            }
            else if (activeItem == null && adoptWanted)
            {
                Begin(Dfb.GUN_ADOPT, null, -1, -1);
                Send(Dfb.KIND_GUN_EQUIP, request, Dfb.GUN_ADOPT, "");
                Log("asking Doom for the guns it holds (request " + request + ")");
            }
            else
                TryPendingDraw();
        }

        static void RefreshInventory()
        {
            DaggerfallInventoryWindow window = DaggerfallUI.UIManager.TopWindow as DaggerfallInventoryWindow;
            if (window != null)
                window.Refresh(false);
        }

        void Send(ushort kind, uint req, uint status, string cls)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = kind;
            e.tic = (uint)Time.frameCount;
            e.doomItem.request = req;
            e.doomItem.status = status;
            byte[] name = Encoding.UTF8.GetBytes(cls);
            e.doomItem.SetCls(name, Math.Min(name.Length, 39));
            bridge.Send(ref e);
        }
    }
}
