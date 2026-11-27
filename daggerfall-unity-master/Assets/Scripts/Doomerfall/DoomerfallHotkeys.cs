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
            public char kind;       // 'g' gun, 'a' armor, 'c' consumable (keeps its square when it runs out), 'f' the fist
            public string identity; // What a consumable square takes next: "doom:<class>" or "df:<group>:<template>:<recipe>"
        }

        // The fist is always on key 1, first plain square (owner, 2026-11-26). It is not a Daggerfall item: Doom keeps it,
        // so it never shows in the inventory. Its square cannot be assigned over or removed, and it is not saved.
        internal const int FistKey = 1, FistSquare = 0;
        internal const string FistName = "Fist";
        internal const string FistMessage = "The fist is always on hotkey 1.";
        static bool IsFist(int key, int square) { return key == FistKey && square == FistSquare; }
        static Square NewFist() { return new Square { uid = 0, kind = 'f', identity = null }; }

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
            table[FistKey, FistSquare] = NewFist();
            SaveLoadManager.DoomerfallSaveExtra = SaveText;
            SaveLoadManager.DoomerfallLoadExtra = LoadText;
            SaveLoadManager.OnStartLoad += OnStartLoad;
            StartGameBehaviour.OnNewGame += OnNewGame;
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfhotkeystest") >= 0)
                gameObject.AddComponent<DoomerfallHotkeysTest>().Init(this);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dffisttest") >= 0)
                gameObject.AddComponent<DoomerfallFistTest>().Init(this, owner);
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
            table[FistKey, FistSquare] = NewFist();
            activeKey = activeSquare = -1;
            activeItem = null;
            loadedActiveUid = 0;
            request = 0;
            stashLines.Clear();
            adopted.Clear();
            adoptWanted = true;
            pendingDraw = null;
        }

        // The gun Doom holds, or null. Its loaded ammo tier is DoomerfallAmmo's business.
        internal DoomerfallDoomItem ActiveGun { get { return activeItem as DoomerfallDoomItem; } }

        // The gun Doom held was dropped to the ground as its Doom pickup (DoomerfallDoomItems.DropToDoom): Doom's hands are empty.
        internal void ForgetActive(DaggerfallUnityItem item)
        {
            if (item == null || item != activeItem)
                return;
            activeItem = null;
            activeKey = activeSquare = -1;
            Log(string.Format("the active gun \"{0}\" was dropped; no gun is active", item.ItemName));
        }

        void OnNewGame() { ResetState(); DoomerfallAmmo.LoadTiers(null); Log("new game: table cleared, the starting gun will be adopted"); }
        void OnStartLoad(SaveData_v1 data) { request = 0; stashLines.Clear(); }

        // ---- Save ----

        internal string SaveText()
        {
            StringBuilder s = new StringBuilder("doomerfall-hotkeys 1\n");
            s.AppendFormat("active {0} {1} {2}\n", activeItem != null ? activeItem.UID : 0, activeKey, activeSquare);
            for (int k = 0; k < Keys; k++)
                for (int q = 0; q < Squares; q++)
                {
                    Square sq = table[k, q];
                    if (sq != null && sq.kind != 'f')
                        s.AppendFormat("square {0} {1} {2} {3} {4}\n", k, q, sq.uid, sq.kind, sq.identity ?? "-");
                }
            s.Append(DoomerfallAmmo.SaveTiers()).Append('\n'); // The tier Doom's counter of each ammo type stands for.
            return s.ToString();
        }

        internal void LoadText(string text)
        {
            ResetState();
            string[] tiers = null;
            List<Square> older = new List<Square>();
            if (!string.IsNullOrEmpty(text))
                foreach (string line in text.Split('\n'))
                {
                    string[] f = line.Trim().Split(' ');
                    try
                    {
                        if (f[0] == "ammotiers")
                            tiers = f;
                        else if (f[0] == "active" && f.Length >= 4)
                        {
                            loadedActiveUid = ulong.Parse(f[1]);
                            activeKey = int.Parse(f[2]);
                            activeSquare = int.Parse(f[3]);
                        }
                        else if (f[0] == "square" && f.Length >= 6 && f[4][0] != 'f')
                        {
                            int k = int.Parse(f[1]), q = int.Parse(f[2]);
                            Square sq = new Square { uid = ulong.Parse(f[3]), kind = f[4][0], identity = f[5] == "-" ? null : f[5] };
                            if (IsFist(k, q)) older.Add(sq); // A save from before the fist rule: placed after the other squares.
                            else table[k, q] = sq;
                        }
                    }
                    catch (Exception e) { Log("bad save line \"" + line + "\": " + e.Message); }
                }
            foreach (Square sq in older) MoveOffFist(sq);
            DropDuplicates();
            DoomerfallAmmo.LoadTiers(tiers); // An older save has none: every type loads Regular.
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            activeItem = loadedActiveUid != 0 ? items.GetItem(loadedActiveUid) : null;
            adoptWanted = activeItem == null; // An older save, or a lost gun: take what Doom holds.
            Log(string.Format("loaded: active {0} \"{1}\" key {2} square {3}, {4} squares: {5}; Doom items: {6}", loadedActiveUid,
                activeItem != null ? activeItem.ItemName : "none", activeKey, activeSquare, CountSquares(), Describe(), DoomItemList(items)));
        }

        // Every Doom gun and ammo stack the player carries, for the logs.
        internal static string DoomItemList(ItemCollection items)
        {
            StringBuilder s = new StringBuilder();
            int n = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (item is DoomerfallDoomItem || item is DoomerfallAmmoItem)
                {
                    s.AppendFormat("{0}[{1} x{2}]", n++ == 0 ? "" : " ", item.ItemName, item.stackCount);
                }
            }
            return n + " " + s;
        }

        // A save from before the fist rule held an item on the fist's square: it moves to the next free plain square of
        // key 1 (pressing 1 again reaches it), else it loses its hotkey and stays in the inventory.
        void MoveOffFist(Square sq)
        {
            bool wasActive = activeKey == FistKey && activeSquare == FistSquare;
            for (int q = 0; q < 3; q++)
                if (!IsFist(FistKey, q) && table[FistKey, q] == null)
                {
                    table[FistKey, q] = sq;
                    if (wasActive) activeSquare = q;
                    Log(string.Format("load: item {0} was on the fist's square; moved to key {1} square {2}", sq.uid, FistKey, q));
                    return;
                }
            if (wasActive) activeKey = activeSquare = -1;
            Log(string.Format("load: item {0} was on the fist's square and key {1} is full; it has no hotkey now", sq.uid, FistKey));
        }

        // Squares the player set. The fist does not count.
        int CountSquares()
        {
            int n = 0;
            foreach (Square sq in table) if (sq != null && sq.kind != 'f') n++;
            return n;
        }

        // True when no square of this key holds anything but the fist.
        bool KeyFree(int key)
        {
            for (int q = 0; q < Squares; q++)
                if (table[key, q] != null && table[key, q].kind != 'f') return false;
            return true;
        }

        // The first plain square of a key that is not the fist's.
        static int FirstSquare(int key) { return key == FistKey ? FistSquare + 1 : 0; }

        internal string Describe()
        {
            StringBuilder s = new StringBuilder();
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int k = 0; k < Keys; k++)
                for (int q = 0; q < Squares; q++)
                    if (table[k, q] != null)
                    {
                        DaggerfallUnityItem item = table[k, q].kind == 'f' ? null : items.GetItem(table[k, q].uid);
                        s.AppendFormat("[{0}.{1} {2}] ", k, q, table[k, q].kind == 'f' ? FistName : item != null ? item.ItemName : "missing");
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

        // One hotkey per item (owner, 2026-11-24): any other square holding this same inventory item (same UID) is
        // cleared, so assigning moves it. Other items of the same kind keep their squares.
        internal void Assign(int key, int square, DaggerfallUnityItem item)
        {
            if (IsFist(key, square))
            {
                Log(string.Format("refused \"{0}\" on key {1} square {2}: the fist's square", item.ItemName, key, square));
                return;
            }
            for (int k = 0; k < Keys; k++)
                for (int q = 0; q < Squares; q++)
                    if ((k != key || q != square) && table[k, q] != null && table[k, q].uid == item.UID)
                    {
                        Clear(k, q);
                        if (activeKey == k && activeSquare == q) { activeKey = key; activeSquare = square; } // The drawn gun moved.
                    }
            table[key, square] = new Square { uid = item.UID, kind = KindOf(item), identity = IdentityOf(item) };
            Log(string.Format("assigned \"{0}\" to key {1} square {2}", item.ItemName, key, square));
        }

        // An older save may hold one item on several squares. Keeps the first by hotkey order (keys 1-9, then 0).
        void DropDuplicates()
        {
            HashSet<ulong> seen = new HashSet<ulong>();
            for (int n = 0; n < Keys; n++)
            {
                int k = (n + 1) % Keys;
                for (int q = 0; q < Squares; q++)
                    if (table[k, q] != null && table[k, q].kind != 'f' && !seen.Add(table[k, q].uid))
                    {
                        Log(string.Format("load: item {0} is already on an earlier hotkey", table[k, q].uid));
                        Clear(k, q);
                        if (activeKey == k && activeSquare == q) activeKey = activeSquare = -1;
                    }
            }
        }

        internal void Clear(int key, int square)
        {
            if (IsFist(key, square))
                return; // The fist cannot be unbound.
            table[key, square] = null;
            Log(string.Format("cleared key {0} square {1}", key, square));
        }

        // The item a square uses now, or null. A consumable that ran out takes the next item of the same kind.
        internal DaggerfallUnityItem Resolve(Square sq)
        {
            if (sq == null || sq.kind == 'f') return null;
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
            if (!KeyFree(slot)) // The fist on key 1 does not count: a slot-1 melee gun goes on the next square.
            {
                Log(string.Format("took \"{0}\"; key {1} already has hotkeys, so it stays in the inventory", gun.DoomClass, slot));
                return;
            }
            Assign(slot, FirstSquare(slot), gun);
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
            int q = FirstSquare(pendingDrawKey);
            if (!GameManager.Instance.PlayerEntity.Items.Contains(gun.UID) || table[pendingDrawKey, q] == null || table[pendingDrawKey, q].uid != gun.UID)
                return;
            Log(string.Format("key {0} was free: drawing the new \"{1}\"", pendingDrawKey, gun.DoomClass));
            DrawGun(gun, pendingDrawKey, q);
        }

        // ---- Plain Daggerfall load (DoomerfallPlainLoad) ----

        DoomerfallDoomItem plainDraw; // Drawn once Doom has put its new game guns away.
        int plainKey = -1, plainSquare = -1;

        // Doom started its default class with that class's guns. The owner's rules (2026-11-24): Doom keeps only its fist,
        // then draws the first Doom gun by hotkey order (keys 1-9, then 0), else the first Doom gun in the inventory.
        // With none, the starter pistol and Regular (Iron) ammo of the class's start amount become real items, the pistol
        // goes on its weapon slot key by the auto-hotkey rule (OnGunTaken), and it is drawn.
        internal void BeginPlainStart(string pistolClass, int slot, int ammoType, int ammo)
        {
            activeItem = null; // Whatever the save's table called active, Doom does not hold it.
            activeKey = activeSquare = -1;
            adoptWanted = false; // Doom's new game guns are not the player's.
            pendingDraw = null;
            plainDraw = null;
            plainKey = plainSquare = -1;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            string how = null;
            for (int n = 0; n < Keys && plainDraw == null; n++)
            {
                int k = (n + 1) % Keys;
                for (int q = 0; q < Squares && plainDraw == null; q++)
                {
                    Square sq = table[k, q];
                    DoomerfallDoomItem gun = sq != null && sq.kind == 'g' ? Resolve(sq) as DoomerfallDoomItem : null;
                    if (gun != null && gun.IsGun) { plainDraw = gun; plainKey = k; plainSquare = q; how = string.Format("first by hotkey order, key {0} square {1}", k, q); }
                }
            }
            int guns = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem gun = items.GetItem(i) as DoomerfallDoomItem;
                if (gun == null || !gun.IsGun) continue;
                guns++;
                if (plainDraw == null) { plainDraw = gun; how = "first in the inventory, not hotkeyed"; }
            }
            if (plainDraw == null && !string.IsNullOrEmpty(pistolClass))
            {
                plainDraw = DoomerfallDoomItem.Create(pistolClass, Dfb.DOOM_ITEM_GUN, LootSeed.Of(LootSeed.DoomStarterGun, pistolClass));
                items.AddItem(plainDraw);
                if (ammoType >= 0 && ammoType < DoomerfallAmmo.Types.Length && ammo > 0)
                    items.AddItem(new DoomerfallAmmoItem(ammoType, DoomerfallAmmoTiers.Regular, ammo));
                how = string.Format("no Doom gun in the inventory: gave the starter \"{0}\" and {1} Regular {2}", pistolClass, ammo,
                    ammoType >= 0 && ammoType < DoomerfallAmmo.Types.Length ? DoomerfallAmmo.Types[ammoType].lowerName : "(no ammo type)");
                if (slot >= 0 && slot < Keys && KeyFree(slot)) { plainKey = slot; plainSquare = FirstSquare(slot); Assign(slot, plainSquare, plainDraw); }
            }
            Log(string.Format("plain load: {0} Doom gun(s) in the inventory; drawing \"{1}\" ({2}); Doom keeps only its fist first",
                guns, plainDraw != null ? plainDraw.ItemName : "nothing", how ?? "no starter pistol known"));
            Begin(Dfb.GUN_CLEAR, null, -1, -1);
            Send(Dfb.KIND_GUN_EQUIP, request, Dfb.GUN_CLEAR, "");
        }

        // A bridged New Game's starting guns (DoomerfallStartingGun), already in the inventory. Each goes on the first free
        // plain square of its weapon slot key. Doom keeps only its fist, then the first gun is drawn.
        internal void BeginStartKit(IList<DoomerfallDoomItem> guns, IList<int> slots)
        {
            ResetState(); // A new character: only the fist, and nothing adopted counts.
            adoptWanted = false; // Doom's new game guns are not the player's.
            plainDraw = null;
            plainKey = plainSquare = -1;
            for (int i = 0; i < guns.Count; i++)
            {
                int k = slots[i], q = FirstSquare(k >= 0 && k < Keys ? k : 0);
                while (k >= 0 && k < Keys && q < 3 && table[k, q] != null) q++;
                bool placed = k >= 0 && k < Keys && q < 3;
                if (placed) Assign(k, q, guns[i]);
                if (i == 0) { plainDraw = guns[i]; plainKey = placed ? k : -1; plainSquare = placed ? q : 0; }
            }
            Log(string.Format("new game: starting guns given, table {0}; Doom keeps only its fist first", Describe()));
            Begin(Dfb.GUN_CLEAR, null, -1, -1);
            Send(Dfb.KIND_GUN_EQUIP, request, Dfb.GUN_CLEAR, "");
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
                if (sq.kind == 'f') { RaiseFist(key, q); return; }
                DaggerfallUnityItem item = Resolve(sq);
                if (item == null) { grey = grey ?? sq; continue; }
                Use(key, q, item);
                return;
            }
            string what = grey != null ? "You have none left for that hotkey." : "Nothing is assigned to that hotkey.";
            DaggerfallUI.AddHUDText(what);
            Log(string.Format("press key {0} modifier {1}: {2}", key, mod, what));
        }

        internal void Use(int key, int square, DaggerfallUnityItem item)
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
            else if (DoomerfallShields.Banned(item) && !item.IsEquipped)
                DaggerfallUI.AddHUDText(DoomerfallShields.EquipMessage); // no shields for now
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
                    if (item.IsEquipped) player.UpdateEquippedArmorValues(item, true); // only what was really equipped
                }
                DaggerfallUI.AddHUDText(item.ItemName + (item.IsEquipped ? " equipped." : " removed."));
            }
        }

        // ---- Guns ----

        // Doom raises its fist. The active gun stays in Doom, lowered, so its key raises it again with GUN_SELECT.
        void RaiseFist(int key, int square)
        {
            if (request != 0)
                return; // One swap at a time, as DrawGun.
            activeKey = key;
            activeSquare = square;
            Log(string.Format("press key {0} square {1}: the fist", key, square));
            Send(Dfb.KIND_GUN_EQUIP, Begin(Dfb.GUN_FIST, null, key, square), Dfb.GUN_FIST, "");
        }

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

        // Counts gun requests, so DoomerfallAmmo knows which ready reports came after a swap began.
        internal int SwapCount { get; private set; }
        internal bool SwapInFlight { get { return request != 0; } }

        uint Begin(uint flags, DoomerfallDoomItem gun, int key, int square)
        {
            SwapCount++;
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
            else if (requestFlags == Dfb.GUN_CLEAR && plainDraw != null)
                Log(string.Format("plain load or New Game kit: Doom put away its new game gun \"{0}\"; not added", cls));
            else
                Log(string.Format("Doom held an unexpected gun \"{0}\" (state \"{1}\"); not added", cls, state));
        }

        DoomerfallDoomItem Adopt(string cls)
        {
            DoomerfallDoomItem item = DoomerfallDoomItem.Create(cls, Dfb.DOOM_ITEM_GUN, LootSeed.Of(LootSeed.DoomStarterGun, cls)); // the same for every new character
            GameManager.Instance.PlayerEntity.Items.AddItem(item);
            Log(string.Format("adopted Doom's \"{0}\" into Daggerfall's inventory, material {1}", cls, item.Material));
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
            if (flags == Dfb.GUN_CLEAR && plainDraw != null)
            {
                DoomerfallDoomItem gun = plainDraw;
                plainDraw = null;
                if (GameManager.Instance.PlayerEntity.Items.Contains(gun.UID))
                    DrawGun(gun, plainKey, plainSquare);
            }
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
                    if (sq != null && sq.kind != 'c' && sq.kind != 'f' && !items.Contains(sq.uid))
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
