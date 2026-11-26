// Doomerfall: the Lockpick, a Daggerfall item Doom's lockpicking minigame spends (owner, 2026-11-25). Runs only in a
// bridge session: Register is called by DoomerfallBridge, and every hook below does nothing until it has run.
//
// 25 gold, 0.1 kg, stackable. Daggerfall owns the item and the count. Sources (owner's rules, my counts and odds):
// - General stores and pawn shops stock a stack at most restocks (StockShop, called from DaggerfallLoot.StockShopShelf).
// - Treasure piles and human class enemies may hold a few (AddLoot, called from LootTables.GenerateLoot and from
//   EnemyEntity for EntityTypes.EnemyClass only). Monsters never do, whatever their loot table. The roll restores the
//   random state, so it never shifts a seeded roll.
// - Every new character starts with StartCount picks, and a class with Lockpicking among its primary or major skills
//   (the burglar types) with BurglarCount.
// No Thieves Guild sales (owner, 2026-11-25).
//
// The picture is the owner's 42x42 pixel art, mods/doomerfall/src/sprites/LPCKA0.png, copied byte for byte to
// Resources/Doomerfall/LPCKA0.png.bytes and decoded with point filtering, so its pixels are never resampled.

using System;
using DaggerfallConnect;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public class DoomerfallLockpickItem : DaggerfallUnityItem, ICustomItemImage
    {
        public DoomerfallLockpickItem() : this(1)
        {
        }

        // Daggerfall rebuilds its template list after the bridge registers custom ones (see DoomerfallAmmoItem), so the
        // item carries its own name, weight and value, saved with it.
        public DoomerfallLockpickItem(int count) : base(ItemGroups.MiscItems, DoomerfallLockpick.Template)
        {
            stackCount = Math.Max(1, count);
            shortName = DoomerfallLockpick.Name;
            weightInKg = DoomerfallLockpick.WeightKg;
            value = DoomerfallLockpick.Price;
        }

        public override string ItemName { get { return DoomerfallLockpick.Name; } }
        public override string LongName { get { return DoomerfallLockpick.Name; } }
        public override bool IsStackable() { return true; }
        public override DaggerfallUnityItem CreateStackPart() { return new DoomerfallLockpickItem(1); }
        public override bool UseItem(ItemCollection collection)
        {
            DaggerfallUI.MessageBox("Use a locked door to pick its lock.");
            return true;
        }
        public bool TryGetImage(out ImageData image) { return DoomerfallLockpick.TryGetImage(out image); }

        public override ItemData_v1 GetSaveData()
        {
            ItemData_v1 data = base.GetSaveData();
            data.className = typeof(DoomerfallLockpickItem).ToString();
            return data;
        }
    }

    internal static class DoomerfallLockpick
    {
        internal const int Template = 9300;
        internal const string Name = "Lockpick";
        internal const float WeightKg = 0.1f;
        internal const int Price = 25;

        // My numbers within the owner's rules.
        internal const int StartCount = 3, BurglarCount = 8;
        const int GeneralStoreChance = 70, PawnShopChance = 80;  // percent per restock, before the quality scale
        const int LootChance = 8;                                 // percent per loot roll that carries gold
        const int LootMax = 3;                                    // a find holds 1 to LootMax picks

        static bool registered;
        static Texture2D texture;
        internal static bool IsRegistered { get { return registered; } }

        // Before any save can load, so Daggerfall can rebuild lockpick stacks from it.
        internal static void Register()
        {
            if (registered)
                return;
            registered = true;
            ItemHelper helper = DaggerfallUnity.Instance.ItemHelper;
            ItemTemplate placeholder = helper.GetItemTemplate((int)MiscItems.Letter_of_credit);
            helper.AddCustomItemTemplate(new ItemTemplate
            {
                index = Template,
                name = Name,
                baseWeight = WeightKg,
                basePrice = Price,
                isNotRepairable = true,
                worldTextureArchive = placeholder.worldTextureArchive,
                worldTextureRecord = placeholder.worldTextureRecord,
                playerTextureArchive = placeholder.playerTextureArchive,
                playerTextureRecord = placeholder.playerTextureRecord,
            });
            helper.RegisterCustomItem(Template, ItemGroups.None, typeof(DoomerfallLockpickItem));
            StartGameBehaviour.OnStartGame += OnStartGame;
        }

        internal static bool TryGetImage(out ImageData image)
        {
            image = default(ImageData);
            if (!texture)
            {
                TextAsset png = Resources.Load<TextAsset>("Doomerfall/LPCKA0.png");
                if (!png)
                    return false;
                texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!texture.LoadImage(png.bytes, false)) // stays readable, as Daggerfall's UI may read icon pixels
                {
                    texture = null;
                    return false;
                }
                texture.filterMode = FilterMode.Point;
                texture.wrapMode = TextureWrapMode.Clamp;
            }
            image.type = ImageTypes.TEXTURE;
            image.texture = texture;
            image.width = texture.width;
            image.height = texture.height;
            image.size = new DaggerfallConnect.Utility.DFSize(texture.width, texture.height);
            return true;
        }

        // The number of lockpicks in a collection.
        internal static int Count(ItemCollection items)
        {
            int n = 0;
            if (items == null)
                return 0;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (item is DoomerfallLockpickItem)
                    n += item.stackCount;
            }
            return n;
        }

        // Removes one lockpick (a broken pick). False when there was none.
        internal static bool BreakOne(ItemCollection items)
        {
            if (items == null)
                return false;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (item is DoomerfallLockpickItem)
                {
                    items.RemoveOne(item);
                    return true;
                }
            }
            return false;
        }

        // A new character: a load or a held character from Doom's New Game flow also fires OnStartGame, so only a
        // character that holds no picks yet gets them.
        static void OnStartGame(object sender, EventArgs e)
        {
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (player == null || Count(player.Items) > 0)
                return;
            int count = IsBurglar(player.Career) ? BurglarCount : StartCount;
            player.Items.AddItem(new DoomerfallLockpickItem(count));
            Debug.LogFormat("lockpick: new character starts with {0}", count);
        }

        static bool IsBurglar(DFCareer career)
        {
            if (career == null)
                return false;
            DFCareer.Skills l = DFCareer.Skills.Lockpicking;
            return career.PrimarySkill1 == l || career.PrimarySkill2 == l || career.PrimarySkill3 == l
                || career.MajorSkill1 == l || career.MajorSkill2 == l || career.MajorSkill3 == l;
        }

        // A shop shelf being restocked.
        internal static void StockShop(DFLocation.BuildingTypes buildingType, int quality, ItemCollection items)
        {
            if (!registered || items == null)
                return;
            int chance = buildingType == DFLocation.BuildingTypes.GeneralStore ? GeneralStoreChance
                : buildingType == DFLocation.BuildingTypes.PawnShop ? PawnShopChance : 0;
            if (chance <= 0)
                return;
            chance = Mathf.Min(95, Mathf.RoundToInt(chance * (0.5f + Mathf.Clamp(quality, 1, 20) / 20f)));
            if (UnityEngine.Random.Range(0, 100) < chance)
                items.AddItem(new DoomerfallLockpickItem(UnityEngine.Random.Range(5, 16)));
        }

        // A treasure pile (LootTables.GenerateLoot) or a human class enemy (EnemyEntity) just rolled its loot. Monsters
        // never call this. The random state is restored afterwards, so seeded rolls that follow stay the same.
        internal static void AddLoot(ItemCollection items)
        {
            if (!registered || items == null)
                return;
            UnityEngine.Random.State state = UnityEngine.Random.state;
            bool add = Dice100.SuccessRoll(LootChance);
            int count = UnityEngine.Random.Range(1, LootMax + 1);
            UnityEngine.Random.state = state;
            if (add)
                items.AddItem(new DoomerfallLockpickItem(count));
        }
    }
}
