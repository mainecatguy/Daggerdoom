// Doomerfall: Doom items held in Daggerfall's inventory. Runs only in a bridge session.
//
// Daggerfall is the record. A Doom item the player takes with Use becomes a DoomerfallDoomItem in the
// player's inventory and is saved with it. The item is named by the Doom world pickup class, kept in
// shortName. Doom supplies the sprite and display name at runtime, so no game data is stored here.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // One Doom item. A gun has a Daggerfall material; a weapon has the weight and value of DoomerfallWeaponValues; no Doom
    // item has condition or enchantments yet.
    public class DoomerfallDoomItem : DaggerfallUnityItem, ICustomItemImage, ICustomItemInfo
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

        // From the DFB_DOOM_ITEM_* flags Doom sends when the player takes the item.
        public DoomerfallDoomItem(string doomClass, uint flags) : this(doomClass, (flags & Dfb.DOOM_ITEM_GUN) != 0)
        {
            if ((flags & Dfb.DOOM_ITEM_GUN) == 0 && (flags & Dfb.DOOM_ITEM_WEARABLE) != 0)
                shortName = doomClass + "|wear|";
            else if ((flags & Dfb.DOOM_ITEM_GUN) == 0 && (flags & Dfb.DOOM_ITEM_ARMOR) != 0)
                shortName = doomClass + "|armor|";
        }

        // shortName is "<class>", "<class>|armor|" (Doom armor, used up when used), "<class>|wear|" (DRLA armor or boots,
        // which cannot be worn yet), or, for a gun, "<class>|gun|<state>", where state is the gun's Doom per-class
        // inventory while Doom does not hold it ("RLPistolClip=5;RLPistolModLimit=1"). Saved with the item.
        public string DoomClass { get { int bar = shortName.IndexOf('|'); return bar < 0 ? shortName : shortName.Substring(0, bar); } }
        public bool IsGun { get { return shortName.Contains("|gun|"); } }
        public bool IsWearable { get { return shortName.EndsWith("|wear|"); } }
        public bool IsArmor { get { return IsWearable || shortName.EndsWith("|armor|"); } }
        internal const string WearMessage = "Doom armor and boots cannot be worn yet.";

        // Doom guns and armor are listed with Daggerfall's weapons and armor, and so is Doom ammo, next to the guns that
        // fire it, as Daggerfall lists arrows. In Clothing & Misc the owner could not find it (play test, 2026-11-24).
        public static bool InWeaponsAndArmorTab(DaggerfallUnityItem item)
        {
            if (item is DoomerfallAmmoItem)
                return true;
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            return doom != null && (doom.IsGun || doom.IsArmor);
        }
        public string GunState
        {
            get { int at = shortName.IndexOf("|gun|"); return at < 0 ? "" : shortName.Substring(at + 5); }
            set { shortName = DoomClass + "|gun|" + (value ?? ""); }
        }
        // The ammo tier this gun loads (card ammotiers/05: each gun remembers its own), with the reserve ammo type it was
        // recorded for, or false when the gun has none yet. Kept in typeDependentData (saved; Daggerfall uses it only for
        // potions and arrows) as (type + 1) * 16 + tier.
        internal bool TryGetAmmoTier(out int type, out int tier)
        {
            type = typeDependentData / 16 - 1;
            tier = typeDependentData % 16;
            return IsGun && type >= 0;
        }
        internal void SetAmmoTier(int type, int tier) { typeDependentData = (byte)((type + 1) * 16 + tier); }

        // A gun's Daggerfall weapon material (owner, 2026-11-24). Kept in nativeMaterialValue, where Daggerfall weapons keep
        // theirs, so Daggerfall's own rules read it (GetWeaponMaterialModifier; price later), and saved with the item. It never
        // changes which Doom weapon this is. A gun saved before guns had materials reads as Iron (0).
        public WeaponMaterialTypes Material
        {
            get { return (WeaponMaterialTypes)Mathf.Clamp(nativeMaterialValue, 0, (int)WeaponMaterialTypes.Daedric); }
            set { nativeMaterialValue = (int)value; }
        }

        // Every Doom item Daggerfall creates comes from here. A gun gets a material rolled with the approved odds
        // (DoomerfallDrops.RollMaterial) at the area level where it is created, like any other loot. A nonzero lootSeed
        // (LootSeed.Of, from the floor item's lasting id) makes the roll the same in every game. A gun that already has
        // a material (carried, from a drop out of the inventory; -1 for none) keeps it and rolls nothing.
        internal static DoomerfallDoomItem Create(string doomClass, uint flags, int lootSeed = 0, int carried = -1)
        {
            DoomerfallDoomItem item = new DoomerfallDoomItem(doomClass, flags);
            if (item.IsGun)
                item.Material = carried >= 0 ? (WeaponMaterialTypes)carried : RollMaterial(lootSeed);
            DoomerfallWeaponValues.Apply(item); // weight and gold value from WeaponValues.txt
            return item;
        }

        // A starter Doom gun: a new character's kit, the pistol a converted save gets, or a gun Doom's new game gave. Fixed at
        // Iron, like Daggerfall's starting gear (owner, 2026-11-27).
        internal static DoomerfallDoomItem CreateStarter(string doomClass)
        {
            return Create(doomClass, Dfb.DOOM_ITEM_GUN, 0, (int)WeaponMaterialTypes.Iron);
        }

        // The material roll of a new gun. Seeded (lootSeed nonzero), it leaves Unity's shared generator as it was.
        internal static WeaponMaterialTypes RollMaterial(int lootSeed)
        {
            if (lootSeed == 0)
                return DoomerfallDrops.RollMaterial(WorldLevel.Current);
            using (new LootSeed.Scope(lootSeed))
                return DoomerfallDrops.RollMaterial(WorldLevel.Current);
        }

        // A gun's inventory name: "<material> <Doom name>", except that an Iron one has the plain Doom name: "Pistol", not
        // "Iron Pistol" (owner, 2026-11-27). The info box still says "Material: Iron".
        internal static string GunName(WeaponMaterialTypes material, string doomClass)
        {
            if (material == WeaponMaterialTypes.Iron)
                return DoomerfallDoomItems.NameFor(doomClass);
            return DaggerfallUnity.Instance.TextProvider.GetWeaponMaterialName(material) + " " + DoomerfallDoomItems.NameFor(doomClass);
        }

        string MaterialName { get { return DaggerfallUnity.Instance.TextProvider.GetWeaponMaterialName(Material); } }
        public override string ItemName
        {
            get { return IsGun ? GunName(Material, DoomClass) : DoomerfallDoomItems.NameFor(DoomClass); }
        }

        // Daggerfall's misc item text for most Doom items. A gun's info starts with its Doom name and the weapon skills it
        // counts as, then a brief description where the gun's mod has one (todo: weapontypes 01), then its material.
        // Doom sends the types and description with the gun's sprite; until they arrive the info starts with the name.
        public TextFile.Token[] GetInfoTokens()
        {
            if (!IsGun)
                return DaggerfallUnity.Instance.TextProvider.GetRSCTokens(1003); // ItemHelper.GetItemInfo's miscTextId
            List<string> lines = new List<string>();
            string types, brief;
            if (DoomerfallDoomItems.TryGetWeaponText(DoomClass, out types, out brief))
            {
                lines.Add(TypesLine(DoomerfallDoomItems.NameFor(DoomClass), types));
                lines.AddRange(Wrap(brief, InfoLineChars));
            }
            else
                lines.Add(ItemName);
            lines.Add(string.Format("Material: {0}", MaterialName));
            lines.Add(string.Format("Weight: {0:0.##} kilograms", weightInKg));
            return DaggerfallUnity.Instance.TextProvider.CreateTokens(TextFile.Formatting.JustifyCenter, lines.ToArray());
        }

        const int InfoLineChars = 44; // Keeps the info box inside Daggerfall's 320-pixel screen.

        // "Plasma Rifle. Type: Energy", "Laser Shotgun. Types: Energy, Shotgun", or "Types: none" for a gun in no
        // weapon skill. Doom sends the types comma-separated.
        internal static string TypesLine(string doomName, string types)
        {
            if (string.IsNullOrEmpty(types))
                return string.Format("{0}. Types: none", doomName);
            return string.Format("{0}. {1}: {2}", doomName, types.Contains(",") ? "Types" : "Type", types);
        }

        // Words in lines of at most width characters (a longer word gets a line of its own).
        internal static List<string> Wrap(string text, int width)
        {
            List<string> lines = new List<string>();
            if (string.IsNullOrEmpty(text))
                return lines;
            StringBuilder line = new StringBuilder();
            foreach (string word in text.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries))
            {
                if (line.Length > 0 && line.Length + 1 + word.Length > width)
                {
                    lines.Add(line.ToString());
                    line.Length = 0;
                }
                if (line.Length > 0)
                    line.Append(' ');
                line.Append(word);
            }
            if (line.Length > 0)
                lines.Add(line.ToString());
            return lines;
        }
        public override string LongName { get { return ItemName; } }
        public override bool IsStackable() { return false; }
        public override bool UseItem(ItemCollection collection)
        {
            if (IsGun)
            {
                DaggerfallUI.MessageBox(DoomerfallHotkeys.EquipMessage);
                return true;
            }
            if (IsWearable)
            {
                DaggerfallUI.MessageBox(WearMessage);
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
            public string types, brief; // A weapon's, for its item description; empty for other items.
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
        readonly List<string> takeState = new List<string>();
        uint takeStateRequest;
        uint takeIdRequest;
        ulong takeId;
        string testFolder; // -dfdoomitemstest FOLDER: writes each inventory picture there and uses a taken RLBlurSphere at once.
        DoomerfallDoomItem testUse;
        string artClass;
        float artDeadline;
        readonly HashSet<uint> lateArt = new HashSet<uint>(); // Art requests that timed out; a late answer is still used.

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
            // Doom items in the wagon or left for repair get their weight and value too (saves from before values).
            foreach (ItemCollection other in new[] { GameManager.Instance.PlayerEntity.WagonItems, GameManager.Instance.PlayerEntity.OtherItems })
                for (int i = 0; other != null && i < other.Count; i++)
                    if (other.GetItem(i) is DoomerfallDoomItem)
                        DoomerfallWeaponValues.Apply((DoomerfallDoomItem)other.GetItem(i));
            StringBuilder list = new StringBuilder();
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem item = items.GetItem(i) as DoomerfallDoomItem;
                if (item == null)
                    continue;
                DoomerfallWeaponValues.Apply(item); // a save from before values, or after the table changed
                list.AppendFormat(" \"{0}\" {1} kg named \"{2}\" material {3} value {4};", item.DoomClass, item.weightInKg, item.ItemName, item.IsGun ? item.Material.ToString() : "none", item.value);
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

        // One state line of the gun in the next take request (DFB_KIND_DOOM_ITEM_GUN_STATE). The material line of a gun
        // dropped from the inventory is not gun state: it gives the taken gun its material back.
        internal void OnTakeState(uint request, uint amount, string cls)
        {
            if (request != takeStateRequest)
            {
                takeState.Clear();
                takeStateRequest = request;
                takeMaterial = -1;
            }
            if (cls == GunMaterialClass)
                takeMaterial = CarriedMaterial((int)amount);
            else
                takeState.Add(cls + "=" + amount);
        }

        // The token that carries a dropped gun's material on Doom's floor (DoomerfallGuns.zs), as material + 1.
        internal const string GunMaterialClass = "DoomerfallGunMaterial";
        int takeMaterial = -1;

        static int CarriedMaterial(int amount)
        {
            return amount >= 1 && amount <= (int)WeaponMaterialTypes.Daedric + 1 ? amount - 1 : -1;
        }

        // The seed of a floor gun's material roll: the same floor item rolls the same material in every game. 0 (no
        // lasting id) rolls freely.
        static int FloorSeed(string cls, ulong floorId)
        {
            return floorId != 0 ? LootSeed.Of(LootSeed.DoomFloorItem, cls, (long)floorId) : 0;
        }

        // The look label of a Doom gun on Doom's floor (UZDoom/src/dd_look.cpp): the name OnTake would give it now, by
        // the same material rule. "" when its material is not fixed yet (no lasting id and none carried) or Doom has not
        // sent its name yet (asked for here, so the next look has it). Changes nothing.
        internal static string FloorGunLabel(string cls, ulong floorId, int carriedAmount)
        {
            int carried = CarriedMaterial(carriedAmount);
            if (instance == null || string.IsNullOrEmpty(cls) || (floorId == 0 && carried < 0))
                return "";
            Art known;
            if (!instance.art.TryGetValue(cls, out known) || string.IsNullOrEmpty(known.tag))
            {
                instance.RequestArt(cls);
                return "";
            }
            WeaponMaterialTypes material = carried >= 0 ? (WeaponMaterialTypes)carried : DoomerfallDoomItem.RollMaterial(FloorSeed(cls, floorId));
            return DoomerfallDoomItem.GunName(material, cls);
        }

        // The floor item's lasting id, sent just before its take request (DFB_KIND_DOOM_ITEM_ID).
        internal void OnTakeId(uint request, ulong id)
        {
            takeIdRequest = request;
            takeId = id;
        }

        // The player pressed Use on a Doom item. Daggerfall's weight rule decides.
        internal void OnTake(uint request, uint flags, string cls)
        {
            // The same floor item rolls the same material in every game; an item without a lasting id rolls freely.
            ulong floorId = takeIdRequest == request ? takeId : 0;
            int lootSeed = FloorSeed(cls, floorId);
            int carried = takeStateRequest == request ? takeMaterial : -1;
            takeMaterial = -1;
            takeIdRequest = 0;
            takeId = 0;
            uint status = Dfb.ITEM_TAKEN;
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null || sync.LoadRunning || GameManager.IsGamePaused || cls.Length == 0)
                status = Dfb.ITEM_REFUSED;
            // The weight check uses the item's own weight, which for a gun depends on its material, so it is made first.
            DoomerfallDoomItem taken = status == Dfb.ITEM_TAKEN ? DoomerfallDoomItem.Create(cls, flags, lootSeed, carried) : null;
            if (taken != null && CanHold(1, taken.weightInKg, player.MaxEncumbrance, player.CarriedWeight) <= 0)
            {
                status = Dfb.ITEM_TOO_HEAVY;
                taken = null;
            }
            if (status == Dfb.ITEM_TAKEN)
            {
                if (taken.IsGun && takeStateRequest == request)
                    taken.GunState = string.Join(";", takeState.ToArray()); // A DRLA modded pickup's mods.
                player.Items.AddItem(taken);
                RequestArt(cls);
                if (testFolder != null && cls == "RLBlurSphere")
                    testUse = taken;
            }
            takeState.Clear();
            takeStateRequest = 0;
            Send(Dfb.KIND_DOOM_ITEM_RESULT, request, status, cls);
            if (taken != null && taken.IsGun && DoomerfallHotkeys.Instance != null)
                DoomerfallHotkeys.Instance.OnGunTaken(taken, (int)((flags & Dfb.DOOM_ITEM_SLOT_MASK) >> (int)Dfb.DOOM_ITEM_SLOT_SHIFT) - 1);
            bridge.LogLine(string.Format("doomitems: take {0} \"{1}\" flags 0x{6:x}: status {2}, carried {3:F2}/{4} kg, doom items {5}{7}",
                request, cls, status, player != null ? player.CarriedWeight : 0, player != null ? player.MaxEncumbrance : 0, player != null ? Count(player.Items) : 0,
                flags, taken != null ? ", stored as \"" + taken.shortName + "\" named \"" + taken.ItemName + "\"" + (taken.IsGun ? " material " + taken.Material + " at area level " + WorldLevel.Current : "") + string.Format(", value {0}, {1} kg", taken.value, taken.weightInKg) : "")
                + string.Format(", floor id {0:x16}{1}", floorId, carried >= 0 ? ", material carried from a drop" : ""));
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
            bool drop = (request & DropRequest) != 0;
            if (removed)
            {
                if (drop && DoomerfallHotkeys.Instance != null)
                    DoomerfallHotkeys.Instance.ForgetActive(item);   // the gun Doom held went down with its pickup
                player.Items.RemoveItem(item);
            }
            bridge.LogLine(string.Format("doomitems: {0} {1} \"{2}\": status {3}, record {4}", drop ? "dropped" : "used", request, cls, status, removed ? "removed" : "kept"));
            RefreshInventory();
        }

        // Owner rule (2026-11-24): a Doom item dropped from Daggerfall's inventory window becomes its own Doom pickup, not a
        // Daggerfall pile. The window calls this with the items it is about to pile (DaggerfallInventoryWindow, on close).
        // Each Doom item goes back to the player's inventory and Doom is asked to spawn it, a gun carrying its stored state
        // (its magazine and DRLA mods); the item leaves Daggerfall's inventory only when Doom confirms (OnUsed), so a
        // failed spawn loses nothing. The pickup is then a Doom ground item in the location record like any other.
        const uint DropRequest = 0x40000000;   // keeps these requests apart from hotkey swaps in DoomerfallGuns.zs
        const uint DropOnGround = 0x100, DropHeld = 0x200;   // DOOM_ITEM_USE status bits (dd_items.cpp)

        internal static void DropToDoom(ItemCollection dropped)
        {
            if (instance == null || dropped == null)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            List<DoomerfallDoomItem> doom = new List<DoomerfallDoomItem>();
            for (int i = 0; i < dropped.Count; i++)
            {
                DoomerfallDoomItem item = dropped.GetItem(i) as DoomerfallDoomItem;
                if (item != null)
                    doom.Add(item);
            }
            foreach (DoomerfallDoomItem item in doom)
            {
                player.Items.Transfer(item, dropped);
                uint request = (instance.nextRequest++) | DropRequest;
                instance.pendingUses[request] = item.UID;
                int lines = 0;
                if (item.IsGun)
                {
                    // Its material goes with it, so the floor shows it and taking it back gives the same gun.
                    instance.Send(Dfb.KIND_GUN_STATE, request, (uint)item.Material + 1, GunMaterialClass);
                    lines++;
                }
                if (item.IsGun)
                    foreach (string line in item.GunState.Split(';'))
                    {
                        int eq = line.IndexOf('=');
                        int amount;
                        if (eq <= 0 || !int.TryParse(line.Substring(eq + 1), out amount))
                            continue;
                        instance.Send(Dfb.KIND_GUN_STATE, request, (uint)amount, line.Substring(0, eq));
                        lines++;
                    }
                bool held = DoomerfallHotkeys.Instance != null && DoomerfallHotkeys.Instance.ActiveGun == item;
                instance.Send(Dfb.KIND_DOOM_ITEM_USE, request, DropOnGround | (held ? DropHeld : 0), item.DoomClass);
                instance.bridge.LogLine(string.Format("doomitems: drop {0} \"{1}\" sent to Doom with {2} state lines{3}", request, item.shortName, lines, held ? ", the gun Doom holds" : ""));
            }
        }

        internal static string NameFor(string cls)
        {
            Art known;
            if (instance != null && instance.art.TryGetValue(cls, out known) && !string.IsNullOrEmpty(known.tag))
                return known.tag;
            return cls;
        }

        // A gun's weapon types and brief description, false until Doom has sent them with its sprite.
        internal static bool TryGetWeaponText(string cls, out string types, out string brief)
        {
            types = brief = null;
            Art known;
            if (instance == null || !instance.art.TryGetValue(cls, out known) || string.IsNullOrEmpty(known.tag))
                return false;
            types = known.types;
            brief = known.brief;
            return true;
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
                Art late;
                if (art.TryGetValue(artClass, out late))
                    late.requested = false; // Asked again the next time it is drawn or looked at.
                lateArt.Add(artRequest);
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
            if (request == artRequest && artClass != null)
                artClass = null;
            else if (!lateArt.Remove(request)) // A late answer to a timed-out request (Doom slow to answer) still counts.
                return;
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
            texture.Apply(false, false); // Kept readable: tiered ammo tints a copy (DoomerfallAmmoTiers.Tinted). Icons are small.
            known.texture = texture;
            known.tag = Text(slot, 80, 64);
            known.types = Text(slot, 144, 64); // dfb_item_art.types
            known.brief = Text(slot, 208, 256); // dfb_item_art.brief
            float scale = Mathf.Min(1f, (float)MaxIconSize / Mathf.Max(width, height));
            known.width = Mathf.Max(1, Mathf.RoundToInt(width * scale));
            known.height = Mathf.Max(1, Mathf.RoundToInt(height * scale));
            bridge.LogLine(string.Format("doomitems: art for \"{0}\" is {1}x{2}, shown {3}x{4}, name \"{5}\", types \"{6}\", brief {7} chars", cls, width, height, known.width, known.height, known.tag, known.types, known.brief.Length));
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
                bridge.LogLine(string.Format("doomitems: inventory picture for \"{0}\" named \"{1}\" weighs {2} kg: {3}x{4} texture, doom sprite {5}, info \"{6}\"", cls, item.ItemName, item.weightInKg, image.width, image.height, doom,
                    string.Join(" / ", Array.FindAll(Array.ConvertAll(item.GetInfoTokens(), t => t.text), t => !string.IsNullOrEmpty(t)))));
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
