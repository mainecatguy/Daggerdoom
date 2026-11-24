// Doomerfall: Doom items held in Daggerfall's inventory. Runs only in a bridge session.
//
// Daggerfall is the record. A Doom item the player takes with Use becomes a DoomerfallDoomItem in the
// player's inventory and is saved with it. The item is named by the Doom world pickup class, kept in
// shortName. Doom supplies the sprite and display name at runtime, so no game data is stored here.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // One Doom item. Plain for now: no material, condition, enchantments, or value.
    public class DoomerfallDoomItem : DaggerfallUnityItem, ICustomItemImage
    {
        internal const int DoomTemplate = 9100;
        internal const float DefaultWeightKg = 2f; // Every Doom item until real weights are chosen.

        public DoomerfallDoomItem() : base(ItemGroups.MiscItems, DoomTemplate)
        {
        }

        public DoomerfallDoomItem(string doomClass, bool gun = false) : this()
        {
            shortName = doomClass + (gun ? "|gun|" : "");
            weightInKg = DefaultWeightKg;
        }

        // shortName is "<class>" or, for a gun, "<class>|gun|<state>", where state is the gun's Doom per-class
        // inventory while Doom does not hold it ("RLPistolClip=5;RLPistolModLimit=1"). Saved with the item.
        public string DoomClass { get { int bar = shortName.IndexOf('|'); return bar < 0 ? shortName : shortName.Substring(0, bar); } }
        public bool IsGun { get { return shortName.Contains("|gun|"); } }
        public string GunState
        {
            get { int at = shortName.IndexOf("|gun|"); return at < 0 ? "" : shortName.Substring(at + 5); }
            set { shortName = DoomClass + "|gun|" + (value ?? ""); }
        }
        public override string ItemName { get { return DoomerfallDoomItems.NameFor(DoomClass); } }
        public override string LongName { get { return ItemName; } }
        public override bool IsStackable() { return false; }
        public override bool UseItem(ItemCollection collection)
        {
            if (IsGun)
            {
                DaggerfallUI.MessageBox(DoomerfallHotkeys.EquipMessage);
                return true;
            }
            return DoomerfallDoomItems.Use(this);
        }
        public bool TryGetImage(out ImageData image) { return DoomerfallDoomItems.TryGetImage(DoomClass, out image); }

        public override ItemData_v1 GetSaveData()
        {
            ItemData_v1 data = base.GetSaveData();
            data.className = typeof(DoomerfallDoomItem).ToString();
            return data;
        }
    }

    internal sealed class DoomerfallDoomItems : MonoBehaviour
    {
        const float ArtTimeoutSeconds = 2f;
        const int MaxIconSize = 48; // Daggerfall's inventory icons are about this size in its native pixels.

        sealed class Art
        {
            public Texture2D texture;
            public string tag;
            public int width, height;
            public bool requested;
        }

        static DoomerfallDoomItems instance;
        static bool registered;
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly Dictionary<string, Art> art = new Dictionary<string, Art>();
        readonly Queue<string> artQueue = new Queue<string>();
        readonly Dictionary<uint, ulong> pendingUses = new Dictionary<uint, ulong>();
        readonly byte[] slot = new byte[Dfb.BULK_BYTES];
        uint nextRequest = 1, artRequest;
        string testFolder; // -dfdoomitemstest FOLDER: writes each inventory picture there and uses a taken RLBlurSphere at once.
        DoomerfallDoomItem testUse;
        string artClass;
        float artDeadline;

        // Before any save can load, so Daggerfall can rebuild Doom items from it.
        internal static void Register()
        {
            if (registered)
                return;
            registered = true;
            ItemHelper helper = DaggerfallUnity.Instance.ItemHelper;
            // Shown only until Doom sends the item's sprite.
            ItemTemplate placeholder = helper.GetItemTemplate((int)MiscItems.Letter_of_credit);
            helper.AddCustomItemTemplate(new ItemTemplate
            {
                index = DoomerfallDoomItem.DoomTemplate,
                name = "Doom item",
                baseWeight = DoomerfallDoomItem.DefaultWeightKg,
                isNotRepairable = true,
                worldTextureArchive = placeholder.worldTextureArchive,
                worldTextureRecord = placeholder.worldTextureRecord,
                playerTextureArchive = placeholder.playerTextureArchive,
                playerTextureRecord = placeholder.playerTextureRecord,
            });
            helper.RegisterCustomItem(DoomerfallDoomItem.DoomTemplate, ItemGroups.None, typeof(DoomerfallDoomItem));
        }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            instance = this;
            bridge = owner;
            sync = positionSync;
            SaveLoadManager.OnStartLoad += OnStartLoad;
            SaveLoadManager.OnLoad += OnLoad;
            string[] args = Environment.GetCommandLineArgs();
            int test = Array.IndexOf(args, "-dfdoomitemstest");
            if (test >= 0 && test + 1 < args.Length)
                testFolder = args[test + 1];
        }

        void OnLoad(SaveData_v1 saveData)
        {
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            StringBuilder list = new StringBuilder();
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem item = items.GetItem(i) as DoomerfallDoomItem;
                if (item == null)
                    continue;
                list.AppendFormat(" \"{0}\" {1} kg;", item.DoomClass, item.weightInKg);
                if (testFolder != null)
                    RequestArt(item.DoomClass); // As the inventory window would on opening.
            }
            bridge.LogLine(string.Format("doomitems: after load the inventory holds {0} Doom items:{1} carried {2:F2} kg", Count(items), list, GameManager.Instance.PlayerEntity.CarriedWeight));
        }

        void OnDestroy()
        {
            SaveLoadManager.OnStartLoad -= OnStartLoad;
            SaveLoadManager.OnLoad -= OnLoad;
            if (instance == this)
                instance = null;
        }

        void OnStartLoad(SaveData_v1 saveData)
        {
            pendingUses.Clear();
        }

        // The same rounding as DaggerfallInventoryWindow.ComputeCanHoldAmount.
        static int CanHold(int available, float unitKg, float capacityKg, float loadKg)
        {
            int unit = Mathf.RoundToInt(unitKg * 400f);
            if (unit <= 0)
                return available;
            return Math.Min(available, (Mathf.RoundToInt(capacityKg * 400f) - Mathf.RoundToInt(loadKg * 400f)) / unit);
        }

        // The player pressed Use on a Doom item. Daggerfall's weight rule decides.
        internal void OnTake(uint request, uint flags, string cls)
        {
            uint status = Dfb.ITEM_TAKEN;
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null || sync.LoadRunning || GameManager.IsGamePaused || cls.Length == 0)
                status = Dfb.ITEM_REFUSED;
            else if (CanHold(1, DoomerfallDoomItem.DefaultWeightKg, player.MaxEncumbrance, player.CarriedWeight) <= 0)
                status = Dfb.ITEM_TOO_HEAVY;
            else
            {
                DoomerfallDoomItem item = new DoomerfallDoomItem(cls, (flags & Dfb.DOOM_ITEM_GUN) != 0);
                player.Items.AddItem(item);
                RequestArt(cls);
                if (testFolder != null && cls == "RLBlurSphere")
                    testUse = item;
            }
            Send(Dfb.KIND_DOOM_ITEM_RESULT, request, status, cls);
            bridge.LogLine(string.Format("doomitems: take {0} \"{1}\": status {2}, carried {3:F2}/{4} kg, doom items {5}",
                request, cls, status, player != null ? player.CarriedWeight : 0, player != null ? player.MaxEncumbrance : 0, player != null ? Count(player.Items) : 0));
        }

        static int Count(ItemCollection items)
        {
            int n = 0;
            for (int i = 0; i < items.Count; i++)
                if (items.GetItem(i) is DoomerfallDoomItem)
                    n++;
            return n;
        }

        // Using a Doom item in Daggerfall's inventory hands it to Doom, which applies it as its own pickup.
        // The record goes only when Doom reports it was taken, so a refused item stays.
        internal static bool Use(DoomerfallDoomItem item)
        {
            if (instance == null)
                return false;
            if (instance.pendingUses.ContainsValue(item.UID))
                return true;
            uint request = instance.nextRequest++;
            instance.pendingUses[request] = item.UID;
            instance.Send(Dfb.KIND_DOOM_ITEM_USE, request, 0, item.DoomClass);
            instance.bridge.LogLine(string.Format("doomitems: use {0} \"{1}\" sent to Doom", request, item.DoomClass));
            if (instance.testFolder == null)
                DaggerfallUI.MessageBox("You ready the " + item.ItemName + ".");
            return true;
        }

        internal void OnUsed(uint request, uint status, string cls)
        {
            ulong uid;
            if (!pendingUses.TryGetValue(request, out uid))
                return;
            pendingUses.Remove(request);
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            DaggerfallUnityItem item = player.Items.GetItem(uid);
            bool removed = status == Dfb.ITEM_TAKEN && item != null;
            if (removed)
                player.Items.RemoveItem(item);
            bridge.LogLine(string.Format("doomitems: used {0} \"{1}\": status {2}, record {3}", request, cls, status, removed ? "removed" : "kept"));
            RefreshInventory();
        }

        internal static string NameFor(string cls)
        {
            Art known;
            if (instance != null && instance.art.TryGetValue(cls, out known) && !string.IsNullOrEmpty(known.tag))
                return known.tag;
            return cls;
        }

        internal static bool TryGetImage(string cls, out ImageData image)
        {
            image = default(ImageData);
            if (instance == null || string.IsNullOrEmpty(cls))
                return false;
            Art known;
            if (!instance.art.TryGetValue(cls, out known) || !known.texture)
            {
                instance.RequestArt(cls);
                return false;
            }
            image.type = ImageTypes.TEXTURE;
            image.texture = known.texture;
            image.width = known.width;
            image.height = known.height;
            image.size = new DaggerfallConnect.Utility.DFSize(known.width, known.height);
            return true;
        }

        void RequestArt(string cls)
        {
            Art known;
            if (!art.TryGetValue(cls, out known))
                art[cls] = known = new Art();
            if (known.requested)
                return;
            known.requested = true;
            artQueue.Enqueue(cls);
        }

        // One art request at a time, because Doom answers through a single bulk slot.
        void Update()
        {
            if (testUse != null)
            {
                Use(testUse);
                testUse = null;
            }
            if (artClass != null && Time.unscaledTime > artDeadline)
            {
                bridge.LogLine("doomitems: no art for \"" + artClass + "\" in time");
                artClass = null;
            }
            if (artClass != null || artQueue.Count == 0)
                return;
            artClass = artQueue.Dequeue();
            artRequest = nextRequest++;
            artDeadline = Time.unscaledTime + ArtTimeoutSeconds;
            Send(Dfb.KIND_DOOM_ITEM_ART_REQUEST, artRequest, 0, artClass);
        }

        internal void OnArt(uint request, uint status, string cls)
        {
            if (request != artRequest || artClass == null)
                return;
            artClass = null;
            Art known;
            if (!art.TryGetValue(cls, out known))
                return;
            uint size, version;
            if (status != Dfb.ITEM_TAKEN || DfbNative.dfb_bulk_read(bridge.Session, Dfb.ITEM_ART_SLOT, slot, (uint)slot.Length, out size, out version) != Dfb.GOT || size < Dfb.ITEM_ART_HEADER)
            {
                bridge.LogLine(string.Format("doomitems: art for \"{0}\" unavailable, status {1}", cls, status));
                return;
            }
            uint got = BitConverter.ToUInt32(slot, 0);
            int width = BitConverter.ToInt32(slot, 4), height = BitConverter.ToInt32(slot, 8);
            if (got != request || width <= 0 || height <= 0 || Dfb.ITEM_ART_HEADER + (long)width * height * 4 > size)
            {
                bridge.LogLine("doomitems: art slot did not match request " + request);
                known.requested = false; // Asked again the next time it is drawn.
                return;
            }
            // Doom sends BGRA with the top row first. Unity wants RGBA with the bottom row first.
            byte[] rgba = new byte[width * height * 4];
            for (int y = 0; y < height; y++)
            {
                int src = (int)Dfb.ITEM_ART_HEADER + y * width * 4, dst = (height - 1 - y) * width * 4;
                for (int x = 0; x < width; x++, src += 4, dst += 4)
                {
                    rgba[dst] = slot[src + 2];
                    rgba[dst + 1] = slot[src + 1];
                    rgba[dst + 2] = slot[src];
                    rgba[dst + 3] = slot[src + 3];
                }
            }
            Texture2D texture = new Texture2D(width, height, TextureFormat.RGBA32, false);
            texture.filterMode = FilterMode.Point;
            texture.wrapMode = TextureWrapMode.Clamp;
            texture.LoadRawTextureData(rgba);
            texture.Apply(false, testFolder == null);
            known.texture = texture;
            known.tag = Text(slot, 80, 64);
            float scale = Mathf.Min(1f, (float)MaxIconSize / Mathf.Max(width, height));
            known.width = Mathf.Max(1, Mathf.RoundToInt(width * scale));
            known.height = Mathf.Max(1, Mathf.RoundToInt(height * scale));
            bridge.LogLine(string.Format("doomitems: art for \"{0}\" is {1}x{2}, shown {3}x{4}, name \"{5}\"", cls, width, height, known.width, known.height, known.tag));
            RefreshInventory();
            if (testFolder != null)
                WriteTestPicture(cls);
        }

        // Test only: the picture Daggerfall's inventory would draw for a carried item of this class.
        void WriteTestPicture(string cls)
        {
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem item = items.GetItem(i) as DoomerfallDoomItem;
                if (item == null || item.DoomClass != cls)
                    continue;
                ImageData image = DaggerfallUnity.Instance.ItemHelper.GetInventoryImage(item);
                bool doom = image.texture == art[cls].texture;
                System.IO.Directory.CreateDirectory(testFolder);
                System.IO.File.WriteAllBytes(System.IO.Path.Combine(testFolder, cls + ".png"), image.texture.EncodeToPNG());
                bridge.LogLine(string.Format("doomitems: inventory picture for \"{0}\" named \"{1}\" weighs {2} kg: {3}x{4} texture, doom sprite {5}", cls, item.ItemName, item.weightInKg, image.width, image.height, doom));
                return;
            }
        }

        static void RefreshInventory()
        {
            DaggerfallInventoryWindow window = DaggerfallUI.UIManager.TopWindow as DaggerfallInventoryWindow;
            if (window != null)
                window.Refresh(false);
        }

        internal static string Text(byte[] bytes, int offset, int length)
        {
            int end = offset;
            while (end < offset + length && end < bytes.Length && bytes[end] != 0)
                end++;
            return Encoding.UTF8.GetString(bytes, offset, end - offset);
        }

        internal static string ClassOf(DfbDoomItem item)
        {
            byte[] bytes = new byte[40];
            item.CopyCls(bytes);
            return Text(bytes, 0, bytes.Length);
        }

        void Send(ushort kind, uint request, uint status, string cls)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = kind;
            e.tic = (uint)Time.frameCount;
            e.doomItem.request = request;
            e.doomItem.status = status;
            byte[] name = Encoding.UTF8.GetBytes(cls);
            e.doomItem.SetCls(name, Math.Min(name.Length, 39));
            bridge.Send(ref e);
        }
    }
}
