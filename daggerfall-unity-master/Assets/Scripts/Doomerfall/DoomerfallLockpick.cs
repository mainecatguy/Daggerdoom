// Doomerfall: the Lockpick, a Daggerfall item Doom's lockpicking minigame spends (owner, 2026-11-25). Runs only in a
// bridge session: Register is called by DoomerfallBridge, and every hook below does nothing until it has run.
//
// 25 gold, 0.1 kg, stackable. Daggerfall owns the item and the count. Sources (owner's rules, my counts and odds):
// - Shops (owner, 2026-11-27: "Pawn shops, general goods traders, occasionally other traders"). In a bridge session
//   the shop ledger tops up a lockpick stack every day, like Doom ammo and outside the stock target, so picks never
//   crowd out other goods (DailyStock, called from DoomerfallShopLedger). Pawn shops and general stores carry them on
//   most visits, weapon smiths and armorers (metalworkers, the fitting other traders) now and then. The classic shop
//   delivery (StockShop) only adds them outside the ledger.
// - Daggerfall-engine loot: treasure piles, human class enemies, and monsters whose Daggerfall loot table carries gold
//   may hold a few (AddLoot, called from LootTables.GenerateLoot and EnemyEntity). Animals and other monsters with no
//   gold in their table never do. Every roll is seeded from the seeded state it runs in and leaves that state as it
//   was, so it never shifts or correlates with a seeded roll.
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

        // My numbers within the owner's rules. Shop chances are per day before the quality scale (0.55x at quality 1 to
        // 1.5x at 20, at most 95%). A stack sells off at 50% a day (DoomerfallShopLedger.SellChance), so a shop with a
        // daily chance p has picks on about 2p/(1+p) of visits: about 82% of mid-quality general stores, 89% of pawn
        // shops, and 15% of weapon smiths and armorers.
        internal const int StartCount = 3, BurglarCount = 8;
        const int GeneralStoreChance = 70, PawnShopChance = 80, MetalworkerChance = 8;
        const int LootChance = 8;                                 // percent per enemy or treasure pile that may hold them
        const int LootMax = 3;                                    // a find holds 1 to LootMax picks
        const long LootSalt = 0x4c50434b;                         // "LPCK": the lockpick rolls' own seed stream

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

        // Daily percent chance for a shop type at a quality; 0 for shops that never carry picks.
        internal static int ShopChance(DFLocation.BuildingTypes buildingType, int quality)
        {
            int chance;
            switch (buildingType)
            {
                case DFLocation.BuildingTypes.GeneralStore: chance = GeneralStoreChance; break;
                case DFLocation.BuildingTypes.PawnShop: chance = PawnShopChance; break;
                case DFLocation.BuildingTypes.WeaponSmith:
                case DFLocation.BuildingTypes.Armorer: chance = MetalworkerChance; break;
                default: return 0;
            }
            return Mathf.Min(95, Mathf.RoundToInt(chance * (0.5f + Mathf.Clamp(quality, 1, 20) / 20f)));
        }

        // A full stack for the shop type: general stores and pawn shops 5-15, metalworkers 1-5.
        static int StackSize(DFLocation.BuildingTypes buildingType)
        {
            bool main = buildingType == DFLocation.BuildingTypes.GeneralStore || buildingType == DFLocation.BuildingTypes.PawnShop;
            return main ? UnityEngine.Random.Range(5, 16) : UnityEngine.Random.Range(1, 6);
        }

        // A classic shop delivery outside the shop ledger. In a ledger session DailyStock stocks picks instead, so they
        // never enter the delivery pool the ledger picks the stocked goods from.
        internal static void StockShop(DFLocation.BuildingTypes buildingType, int quality, ItemCollection items)
        {
            if (!registered || items == null || WorldLevel.ShopProvider != null)
                return;
            if (UnityEngine.Random.Range(0, 100) < ShopChance(buildingType, quality))
                items.AddItem(new DoomerfallLockpickItem(StackSize(buildingType)));
        }

        // One shop day in the ledger (its first shelf). Seeded from the shop and the day only, on its own stream, and
        // Unity's generator is left as it was, so the ledger's own rolls are unchanged. The day's stack tops up a stack
        // already there rather than adding to it, as Doom ammo does.
        internal static void DailyStock(ItemCollection items, PlayerGPS.DiscoveredBuilding building, int location, int day)
        {
            if (!registered || items == null)
                return;
            int chance = ShopChance(building.buildingType, building.quality);
            if (chance <= 0)
                return;
            UnityEngine.Random.State saved = UnityEngine.Random.state;
            int count = 0;
            try
            {
                UnityEngine.Random.InitState(LootSeed.Of(LootSalt, null, location, building.buildingKey, day));
                if (UnityEngine.Random.Range(0, 100) < chance)
                    count = StackSize(building.buildingType);
            }
            finally
            {
                UnityEngine.Random.state = saved;
            }
            if (count <= 0)
                return;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem stack = items.GetItem(i);
                if (stack is DoomerfallLockpickItem)
                {
                    stack.stackCount = Mathf.Max(stack.stackCount, count);
                    return;
                }
            }
            items.AddItem(new DoomerfallLockpickItem(count));
        }

        // True for an enemy that may carry picks: a human class enemy, or a monster whose Daggerfall loot table carries
        // gold (orcs, centaurs, giants, undead, daedra and the like; not rats, spiders, or other animals).
        internal static bool CarriesPicks(EntityTypes entityType, string lootTableKey)
        {
            if (entityType == EntityTypes.EnemyClass)
                return true;
            if (entityType != EntityTypes.EnemyMonster || string.IsNullOrEmpty(lootTableKey))
                return false;
            LootChanceMatrix matrix = LootTables.GetMatrix(lootTableKey);
            return matrix.key == lootTableKey && matrix.MaxGold > 0;
        }

        // An enemy (EnemyEntity) just rolled its loot.
        internal static void AddEnemyLoot(EntityTypes entityType, string lootTableKey, ItemCollection items)
        {
            if (registered && CarriesPicks(entityType, lootTableKey))
                AddLoot(items);
        }

        // A treasure pile (LootTables.GenerateLoot) or an enemy (AddEnemyLoot) just rolled its loot. The roll seeds its
        // own stream from the current generator state (the place's loot seed during a seeded roll) and then puts that
        // state back, so seeded rolls that follow stay the same and are not correlated with this one.
        internal static void AddLoot(ItemCollection items)
        {
            if (!registered || items == null)
                return;
            UnityEngine.Random.State state = UnityEngine.Random.state;
            bool add;
            int count;
            try
            {
                // The next value the seeded roll would draw, hashed: a fixed fact of the seed that the hash decorrelates.
                int next = UnityEngine.Random.Range(0, 1 << 30);
                UnityEngine.Random.InitState(LootSeed.Of(LootSalt, null, next));
                add = Dice100.SuccessRoll(LootChance);
                count = UnityEngine.Random.Range(1, LootMax + 1);
            }
            finally
            {
                UnityEngine.Random.state = state;
            }
            if (add)
                items.AddItem(new DoomerfallLockpickItem(count));
        }
    }
}
