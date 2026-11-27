// Doomerfall: shop deliveries arrive as lots that tell a story (Shops 7). Called by DoomerfallShopLedger.Deliver, so
// it runs only in a bridge session, inside the ledger's seeded generator and approved material odds.
//
// A lot is a small coherent bundle from a template in Resources/Doomerfall/ShopLots.txt, rolled with Daggerfall's own
// item and material code: regular supply (Daggerfall's classic delivery for the shop, plus Doom guns when guns are
// enabled), estate sale (one dead adventurer's kit, one material roll, worn), salvage (mixed gear, worn), caravan
// (another province's goods by item kind), bulk (many identical items) and townsfolk (one odd item). Pawn shops take
// only estate, salvage and townsfolk lots. An ordinary lot arrives only when the shelf has room for its core (the items
// that make it read as itself); items past the room are dropped. Only a rare exception shipment may go over the share.
//
// Rare exceptions: each building's days are cut into windows; a window is an exception window with a small fixed
// chance computed from (location, building, window) alone, so it is the same in every game and never depends on the
// player. Exceptions: a pawn shop's estate lot with a Doom gun, a general store's siege window (weapons only), and a
// village weapon smith whose deliveries for the window are all one weapon kind. An exception lot arrives even on a full
// shelf, going over the share by at most its core. Exceptions never remove anything from the shelf.
//
// Doom gun values and tiers come from Resources/Doomerfall/WeaponValues.txt (weaponvalues 01). Without the file, no
// Doom guns are stocked.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShopLots
    {
        /// <summary>Guns mode: Doom guns are for sale. Always on today (owner: "currently they always are"); a guns-off option is backlog.</summary>
        internal static bool GunsEnabled = true;
        /// <summary>The Doom weapon set the loaded mods use, as WeaponValues.txt names it. Only DRLA is stocked: other sets
        /// need a tier from DPS (owner), which is not built (owner question), so they get no guns for sale.</summary>
        internal static string GunSet = "DRLA";
        /// <summary>False only in the ledger's stock-size test, which measures ordinary deliveries.</summary>
        internal static bool ExceptionsEnabled = true;
        /// <summary>Sees every lot put on a shelf (null in play).</summary>
        internal static Action<Lot> Observer;

        internal sealed class Lot
        {
            public string template, detail = "";
            public bool exception;
            public int core = 1, day, shelf, added;
            public DFLocation.BuildingTypes shop;
            public readonly List<DaggerfallUnityItem> items = new List<DaggerfallUnityItem>();
        }

        /// <summary>Where the shop is: its region (for caravans) and whether the town is a village or hamlet.</summary>
        internal sealed class Place
        {
            public string region = "";
            public bool village;

            internal static Place Here()
            {
                Place p = new Place();
                PlayerGPS gps = GameManager.HasInstance ? GameManager.Instance.PlayerGPS : null;
                if (gps != null)
                {
                    p.region = gps.CurrentRegionName ?? "";
                    p.village = gps.CurrentLocationType == DFRegion.LocationTypes.TownVillage || gps.CurrentLocationType == DFRegion.LocationTypes.TownHamlet;
                }
                return p;
            }
        }

        internal sealed class Rec
        {
            public string kind, name;
            public readonly Dictionary<string, string> kv = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            public string Get(string key, string fallback = "") { string v; return kv.TryGetValue(key, out v) ? v : fallback; }
            public int Int(string key, int fallback = 0) { int v; return int.TryParse(Get(key), NumberStyles.Integer, CultureInfo.InvariantCulture, out v) ? v : fallback; }
            public string[] List(string key) { string v = Get(key); return v.Length == 0 ? new string[0] : v.Split(','); }
            public bool ForShop(DFLocation.BuildingTypes type) { return Array.IndexOf(List("shops"), type.ToString()) >= 0; }
        }

        internal sealed class Gun
        {
            public string pickup, tier;
            public float weightKg;
            public int value;
        }

        static List<Rec> recs;
        static readonly Dictionary<string, string> settings = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        static Dictionary<string, List<Gun>> gunsBySet;
        static readonly Dictionary<string, int> gunRarity = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        static readonly Armor[] BodyPieces = { Armor.Helm, Armor.Gauntlets, Armor.Greaves, Armor.Boots, Armor.Left_Pauldron, Armor.Right_Pauldron };
        static readonly Armor[] Shields = { Armor.Buckler, Armor.Round_Shield, Armor.Kite_Shield, Armor.Tower_Shield };

        internal static int LotsPerDelivery { get { return Setting("lots_per_delivery", 8); } }
        internal static float ExceptionShare { get { return SettingFloat("exception_share", 0.04f); } }
        internal static int WindowDays { get { return Mathf.Max(1, Setting("exception_window_days", 7)); } }

        // ---------------------------------------------------------------- delivery

        /// <summary>
        /// Fills one shelf for one day. classic is the shop's classic Daggerfall delivery without Doom ammo and the horse
        /// and cart (the regular-supply lot draws from it). room is the shelf's free share. Returns a one-line summary.
        /// </summary>
        internal static string Fill(ItemCollection shelf, PlayerGPS.DiscoveredBuilding building, List<DaggerfallUnityItem> classic,
            int room, int shelfIndex, int location, int day, int level, Place place)
        {
            Load();
            StringBuilder summary = new StringBuilder();
            Shuffle(classic);
            int classicNext = 0;
            bool gunsRolled = false;
            Rec ex = ExceptionFor(location, building.buildingKey, building.buildingType, day, place);
            bool firstDay = Mod(day, WindowDays) == 0;
            if (ex != null && (ex.Get("mode") == "window" || (firstDay && shelfIndex == 0)))
            {
                Lot lot = MakeException(ex, building, level, Mathf.Max(1, room), location, day);
                if (lot != null)
                {
                    room -= Add(shelf, lot, room, building, day, shelfIndex, summary);
                    if (ex.Get("mode") == "window")
                        return summary.ToString();
                }
            }
            for (int n = 0; n < LotsPerDelivery && room > 0; n++)
            {
                string template = PickTemplate(building.buildingType);
                Lot lot;
                if (template == "regular")
                {
                    lot = new Lot { template = template };
                    if (!gunsRolled)
                    {
                        gunsRolled = true;
                        RollDoomGuns(building, lot.items);
                        if (lot.items.Count > 0)
                            lot.detail = lot.items.Count + " Doom gun" + (lot.items.Count > 1 ? "s" : "");
                    }
                    while (lot.items.Count < room && classicNext < classic.Count)
                        lot.items.Add(classic[classicNext++]);
                    Shuffle(lot.items);
                }
                else
                    lot = Make(template, building, level, place);
                if (lot == null)
                    continue;
                room -= Add(shelf, lot, room, building, day, shelfIndex, summary);
            }
            return summary.ToString();
        }

        static int Add(ItemCollection shelf, Lot lot, int room, PlayerGPS.DiscoveredBuilding building, int day, int shelfIndex, StringBuilder summary)
        {
            // An ordinary lot arrives only when its core fits; items past the room are dropped. An exception shipment
            // arrives whole up to its core even on a full shelf (a rare, visible break; sell-off brings it back down).
            if (lot.items.Count == 0 || (!lot.exception && (room <= 0 || room < Mathf.Min(lot.core, lot.items.Count))))
                return 0;
            int n = Mathf.Min(lot.items.Count, Mathf.Max(room, lot.core));
            lot.items.RemoveRange(n, lot.items.Count - n);
            foreach (DaggerfallUnityItem item in lot.items)
                shelf.AddItem(item, ItemCollection.AddPosition.Back, true);
            lot.added = n; lot.day = day; lot.shelf = shelfIndex; lot.shop = building.buildingType;
            summary.AppendFormat(" {0}{1}({2}{3})", lot.exception ? "EXCEPTION " : "", lot.template, n, lot.detail.Length > 0 ? ", " + lot.detail : "");
            if (Observer != null) Observer(lot);
            return n;
        }

        static string PickTemplate(DFLocation.BuildingTypes type)
        {
            int total = 0;
            foreach (Rec r in recs)
                if (r.kind == "lot")
                    total += r.Int(type.ToString());
            if (total <= 0)
                return "regular";
            int roll = UnityEngine.Random.Range(0, total);
            foreach (Rec r in recs)
                if (r.kind == "lot")
                {
                    roll -= r.Int(type.ToString());
                    if (roll < 0)
                        return r.name;
                }
            return "regular";
        }

        static int CoreOf(string template)
        {
            foreach (Rec r in recs)
                if (r.kind == "lot" && r.name == template)
                    return r.Int("core", 1);
            return 1;
        }

        static Lot Make(string template, PlayerGPS.DiscoveredBuilding building, int level, Place place)
        {
            Lot lot = new Lot { template = template, core = CoreOf(template) };
            switch (template)
            {
                case "estate": Estate(lot, level); break;
                case "salvage": Salvage(lot, level); break;
                case "caravan": Caravan(lot, building.buildingType, level, place); break;
                case "bulk": Bulk(lot, building.buildingType, level); break;
                case "townsfolk": Townsfolk(lot, level); break;
            }
            return lot;
        }

        // ---------------------------------------------------------------- templates

        static void Estate(Lot lot, int level)
        {
            List<Rec> kits = Records("estate");
            if (kits.Count == 0)
                return;
            Rec kit = kits[UnityEngine.Random.Range(0, kits.Count)];
            WeaponMaterialTypes material = FormulaHelper.RandomMaterial(level);
            string armor = kit.Get("armor", "none");
            ArmorMaterialTypes armorMaterial = armor == "plate" ? (ArmorMaterialTypes)(0x0200 + (int)material)
                : armor == "chain" ? ArmorMaterialTypes.Chain : ArmorMaterialTypes.Leather;
            lot.detail = kit.name + ", " + material + (armor == "none" ? "" : ", " + armor);
            lot.items.Add(ItemBuilder.CreateWeapon(PickWeapon(kit.List("weapons")), material));
            if (armor != "none")
            {
                int pieces = Range(kit.Get("pieces", "1-2"));
                List<Armor> body = new List<Armor>(BodyPieces);
                Shuffle(body);
                for (int i = 0; i < pieces; i++)
                    lot.items.Add(MakeArmor(i == 0 ? Armor.Cuirass : body[(i - 1) % body.Count], armorMaterial));
                if (Dice100.SuccessRoll(kit.Int("shield")))
                    lot.items.Add(MakeArmor(Shields[UnityEngine.Random.Range(0, Shields.Length)], armorMaterial));
            }
            if (kit.Get("arrows").Length > 0)
            {
                DaggerfallUnityItem arrows = ItemBuilder.CreateWeapon(Weapons.Arrow, material);
                arrows.stackCount = Range(kit.Get("arrows"));
                lot.items.Add(arrows);
            }
            if (kit.Get("sides").Length > 0 && Dice100.SuccessRoll(kit.Int("side")))
                lot.items.Add(ItemBuilder.CreateWeapon(PickWeapon(kit.List("sides")), material));
            Worn(lot.items, Setting("worn_estate", "55-90"));
            for (int i = Range(kit.Get("magic", "0")); i > 0; i--)
                lot.items.Add(ItemBuilder.CreateRandomMagicItem(level, Player.Gender, Player.Race));
            for (int i = Range(kit.Get("clothes", "0")); i > 0; i--)
                lot.items.Add(ItemBuilder.CreateRandomClothing(Player.Gender, Player.Race));
            for (int i = Range(kit.Get("books", "0")); i > 0; i--)
                lot.items.Add(ItemBuilder.CreateRandomBook());
            for (int i = Range(Setting("estate_potions", "0-2")); i > 0; i--)
                lot.items.Add(ItemBuilder.CreateRandomPotion());
            if (Dice100.SuccessRoll(Setting("estate_book", 40)))
                lot.items.Add(ItemBuilder.CreateRandomBook());
            if (Dice100.SuccessRoll(Setting("estate_jewellery", 35)))
                lot.items.Add(ItemBuilder.CreateItem(ItemGroups.Jewellery, UnityEngine.Random.Range(0, 2) == 0 ? (int)Jewellery.Ring : (int)Jewellery.Amulet));
        }

        static void Salvage(Lot lot, int level)
        {
            for (int i = Range(Setting("salvage_items", "2-4")); i > 0; i--)
            {
                if (Dice100.SuccessRoll(50))
                    lot.items.Add(ItemBuilder.CreateWeapon(RandomWeapon(), FormulaHelper.RandomMaterial(level)));
                else
                {
                    Armor piece = (Armor)UnityEngine.Random.Range((int)Armor.Cuirass, (int)Armor.Tower_Shield + 1);
                    lot.items.Add(MakeArmor(piece, FormulaHelper.RandomArmorMaterial(level)));
                }
            }
            Worn(lot.items, Setting("worn_salvage", "35-80"));
        }

        static void Caravan(Lot lot, DFLocation.BuildingTypes type, int level, Place place)
        {
            string province = ProvinceOf(place.region);
            List<Rec> options = new List<Rec>();
            foreach (Rec r in Records("caravan"))
                if (r.ForShop(type) && (province == null || r.Get("home") != province))
                    options.Add(r);
            if (options.Count == 0)
                return;
            Rec caravan = options[UnityEngine.Random.Range(0, options.Count)];
            lot.detail = caravan.name.Replace('_', ' ');
            string[] items = caravan.List("items");
            for (int i = Range(caravan.Get("count", "3-5")); i > 0; i--)
            {
                DaggerfallUnityItem item = MakeSpec(items[UnityEngine.Random.Range(0, items.Length)], level);
                if (item != null)
                    lot.items.Add(item);
            }
        }

        static void Bulk(Lot lot, DFLocation.BuildingTypes type, int level)
        {
            List<Rec> options = new List<Rec>();
            foreach (Rec r in Records("bulk"))
                if (r.ForShop(type))
                    options.Add(r);
            if (options.Count == 0)
                return;
            Rec bulk = options[UnityEngine.Random.Range(0, options.Count)];
            string[] specs = bulk.List("items");
            string spec = specs[UnityEngine.Random.Range(0, specs.Length)];
            int count = Range(bulk.Get("count", "6-10"));
            // One template and one material roll for the whole lot: resolve the spec once and copy it.
            DaggerfallUnityItem first = MakeSpec(spec, level);
            if (first == null)
                return;
            lot.detail = bulk.name + ": " + first.LongName;
            if (bulk.Int("stack") == 1)
            {
                first.stackCount = count;
                lot.items.Add(first);
                lot.core = 1;
                return;
            }
            lot.items.Add(first);
            for (int i = 1; i < count; i++)
                lot.items.Add(Copy(first));
            lot.core = Mathf.Min(lot.core, count);
        }

        static void Townsfolk(Lot lot, int level)
        {
            List<Rec> list = Records("townsfolk");
            if (list.Count == 0)
                return;
            string[] specs = list[0].List("items");
            DaggerfallUnityItem item = MakeSpec(specs[UnityEngine.Random.Range(0, specs.Length)], level);
            if (item != null)
            {
                lot.items.Add(item);
                lot.detail = item.LongName;
            }
        }

        // ---------------------------------------------------------------- exceptions

        /// <summary>The exception that applies to this building on this day, or null. Depends only on location, building and day.</summary>
        internal static Rec ExceptionFor(int location, int buildingKey, DFLocation.BuildingTypes type, int day, Place place)
        {
            Load();
            if (!ExceptionsEnabled)
                return null;
            int window = Floor(day, WindowDays);
            uint h = Hash(location, buildingKey, window, 0x5EED);
            if ((h & 0xFFFF) / 65536f >= ExceptionShare)
                return null;
            List<Rec> eligible = new List<Rec>();
            foreach (Rec r in Records("exception"))
                if (r.ForShop(type) && (r.Int("village") == 0 || place.village) && (r.Int("guns") == 0 || (GunsEnabled && Guns().Count > 0)))
                    eligible.Add(r);
            if (eligible.Count == 0)
                return null;
            return eligible[(int)((h >> 16) % (uint)eligible.Count)];
        }

        static Lot MakeException(Rec ex, PlayerGPS.DiscoveredBuilding building, int level, int room, int location, int day)
        {
            Lot lot = new Lot { template = ex.name, exception = true, core = ex.Int("core", 1) };
            switch (ex.name)
            {
                case "pawngun":
                {
                    DaggerfallUnityItem gun = null;
                    for (int t = 0; t < 30 && gun == null; t++)
                        gun = PickGun(building.quality, 70);
                    if (gun == null)
                        return null;
                    Lot estate = new Lot();
                    Estate(estate, level);
                    lot.items.Add(gun);
                    lot.items.AddRange(estate.items);
                    lot.detail = "estate with " + ((DoomerfallDoomItem)gun).DoomClass + (estate.detail.Length > 0 ? ", " + estate.detail : "");
                    break;
                }
                case "siege":
                    for (int i = 0; i < room; i++)
                        lot.items.Add(ItemBuilder.CreateWeapon(RandomWeapon(), FormulaHelper.RandomMaterial(level)));
                    lot.detail = "weapons only";
                    break;
                case "onekind":
                {
                    Weapons kind = (Weapons)((int)Weapons.Dagger + (int)(Hash(location, building.buildingKey, Floor(day, WindowDays), 0x0E1D) % (uint)((int)Weapons.Long_Bow - (int)Weapons.Dagger + 1)));
                    for (int i = 0; i < room; i++)
                        lot.items.Add(ItemBuilder.CreateWeapon(kind, FormulaHelper.RandomMaterial(level)));
                    lot.detail = "all " + kind;
                    break;
                }
            }
            return lot;
        }

        // ---------------------------------------------------------------- Doom guns

        /// <summary>The loaded set's Doom guns for sale (no fists), or an empty list without WeaponValues.txt.</summary>
        internal static List<Gun> Guns()
        {
            LoadGuns();
            List<Gun> list;
            return GunSet == "DRLA" && gunsBySet.TryGetValue(GunSet, out list) ? list : new List<Gun>();
        }

        internal static int RarityOf(string tier) { int r; return gunRarity.TryGetValue(tier, out r) ? r : 20; }

        /// <summary>Daggerfall's weapon stock chance for this shop type (DaggerfallLootDataTables), 0 if it stocks no weapons.</summary>
        internal static int WeaponChance(DFLocation.BuildingTypes type)
        {
            byte[] groups;
            switch (type)
            {
                case DFLocation.BuildingTypes.WeaponSmith: groups = DaggerfallLootDataTables.itemGroupsWeaponSmith; break;
                case DFLocation.BuildingTypes.Armorer: groups = DaggerfallLootDataTables.itemGroupsArmorer; break;
                case DFLocation.BuildingTypes.GeneralStore: groups = DaggerfallLootDataTables.itemGroupsGeneralStore; break;
                default: return 0;   // pawn shops get Doom guns only from a rare estate exception
            }
            for (int i = 0; i + 1 < groups.Length; i += 2)
                if (groups[i] == (byte)ItemGroups.Weapons)
                    return groups[i + 1];
            return 0;
        }

        static void RollDoomGuns(PlayerGPS.DiscoveredBuilding building, List<DaggerfallUnityItem> into)
        {
            int chance = WeaponChance(building.buildingType);
            if (!GunsEnabled || chance <= 0)
                return;
            for (int i = Setting("gun_rolls", 3); i > 0; i--)
            {
                DaggerfallUnityItem gun = PickGun(building.quality, chance);
                if (gun != null)
                    into.Add(gun);
            }
        }

        /// <summary>The tiers in order, common first.</summary>
        internal static readonly string[] Tiers = { "common", "uncommon", "rare", "veryrare", "legendary" };

        /// <summary>
        /// One Doom gun roll: the tier is rolled first, with weights that fall by tier (gun_tier_weights; only tiers whose
        /// rarity the shop's quality allows and that have guns), then a gun within the tier is picked evenly, and it is
        /// kept with Daggerfall's stock chance for the tier's rarity, which also falls by tier. Null when nothing is kept.
        /// </summary>
        static DaggerfallUnityItem PickGun(int quality, int weaponChance)
        {
            List<Gun> guns = Guns();
            string[] w = Setting("gun_tier_weights", "60,30,20,10,6").Split(',');
            float total = 0;
            float[] weight = new float[Tiers.Length];
            for (int k = 0; k < Tiers.Length; k++)
            {
                int wk;
                string tierName = Tiers[k];
                bool any = guns.Exists(g => g.tier == tierName);
                weight[k] = any && RarityOf(tierName) <= quality && k < w.Length && int.TryParse(w[k], out wk) ? wk : 0;
                total += weight[k];
            }
            if (total <= 0)
                return null;
            float roll = UnityEngine.Random.value * total;
            int tier = 0;
            while (tier < Tiers.Length - 1 && (roll -= weight[tier]) >= 0)
                tier++;
            while (weight[tier] <= 0)
                tier--;
            string chosen = Tiers[tier];
            List<Gun> inTier = guns.FindAll(g => g.tier == chosen);
            Gun pick = inTier[UnityEngine.Random.Range(0, inTier.Count)];
            if (!Dice100.SuccessRoll(weaponChance * 5 * (21 - RarityOf(chosen)) / 100))
                return null;
            DoomerfallDoomItem item = new DoomerfallDoomItem(pick.pickup, true);
            item.value = pick.value;
            item.weightInKg = pick.weightKg;
            return item;
        }

        static void LoadGuns()
        {
            if (gunsBySet != null)
                return;
            Load();
            gunsBySet = new Dictionary<string, List<Gun>>(StringComparer.OrdinalIgnoreCase);
            TextAsset text = Resources.Load<TextAsset>("Doomerfall/WeaponValues");
            if (text == null)
            {
                Debug.LogWarning("Doomerfall: Resources/Doomerfall/WeaponValues.txt is missing; shops stock no Doom guns.");
                return;
            }
            // Value as weaponvalues 01 (DoomerfallWeaponValues): the role's Daggerfall weapon at Iron x tier multiplier x share.
            Dictionary<string, Weapons> roles = new Dictionary<string, Weapons>();
            Dictionary<string, int> tiers = new Dictionary<string, int>();
            foreach (string raw in text.text.Split('\n'))
            {
                string[] f = raw.Trim().Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (f.Length == 0 || f[0].StartsWith("#"))
                    continue;
                try
                {
                    if (f[0] == "role" && f.Length >= 3)
                        roles[f[1]] = (Weapons)Enum.Parse(typeof(Weapons), f[2]);
                    else if (f[0] == "tier" && f.Length >= 3)
                        tiers[f[1]] = int.Parse(f[2], CultureInfo.InvariantCulture);
                    else if (f[0] == "weapon" && f.Length >= 9 && f[4] != "unarmed")
                    {
                        float share = float.Parse(f[7], CultureInfo.InvariantCulture);
                        Gun g = new Gun
                        {
                            pickup = f[8].Split(',')[0], tier = f[5],
                            weightKg = float.Parse(f[6], CultureInfo.InvariantCulture),
                            value = Mathf.Max(1, Mathf.RoundToInt(ItemBuilder.CreateWeapon(roles[f[4]], WeaponMaterialTypes.Iron).value * tiers[f[5]] * share)),
                        };
                        List<Gun> list;
                        if (!gunsBySet.TryGetValue(f[2], out list))
                            gunsBySet[f[2]] = list = new List<Gun>();
                        list.Add(g);
                    }
                }
                catch (Exception e)
                {
                    Debug.LogWarning("Doomerfall: skipped WeaponValues.txt line \"" + raw.Trim() + "\": " + e.Message);
                }
            }
        }

        // ---------------------------------------------------------------- items

        static PlayerEntity Player { get { return GameManager.Instance.PlayerEntity; } }

        static DaggerfallUnityItem MakeArmor(Armor piece, ArmorMaterialTypes material)
        {
            return ItemBuilder.CreateArmor(Player.Gender, Player.Race, piece, material);
        }

        static Weapons RandomWeapon() { return (Weapons)UnityEngine.Random.Range((int)Weapons.Dagger, (int)Weapons.Long_Bow + 1); }

        static Weapons PickWeapon(string[] names)
        {
            if (names.Length == 0)
                return RandomWeapon();
            return (Weapons)Enum.Parse(typeof(Weapons), names[UnityEngine.Random.Range(0, names.Length)]);
        }

        /// <summary>One item from a spec "Group:Name", "Group:*" or "Clothing:*". Weapons and armor take a material roll.</summary>
        static DaggerfallUnityItem MakeSpec(string spec, int level)
        {
            int colon = spec.IndexOf(':');
            string groupName = colon < 0 ? spec : spec.Substring(0, colon), name = colon < 0 ? "*" : spec.Substring(colon + 1);
            if (groupName == "Clothing")
                return ItemBuilder.CreateRandomClothing(Player.Gender, Player.Race);
            ItemGroups group = (ItemGroups)Enum.Parse(typeof(ItemGroups), groupName);
            if (group == ItemGroups.Weapons)
                return ItemBuilder.CreateWeapon(name == "*" ? RandomWeapon() : (Weapons)Enum.Parse(typeof(Weapons), name), FormulaHelper.RandomMaterial(level));
            if (group == ItemGroups.Armor)
                return MakeArmor(name == "*" ? (Armor)UnityEngine.Random.Range((int)Armor.Cuirass, (int)Armor.Tower_Shield + 1) : (Armor)Enum.Parse(typeof(Armor), name), FormulaHelper.RandomArmorMaterial(level));
            if (name == "*")
            {
                switch (group)
                {
                    case ItemGroups.Books: return ItemBuilder.CreateRandomBook();
                    case ItemGroups.Gems: return ItemBuilder.CreateRandomGem();
                    case ItemGroups.Jewellery: return ItemBuilder.CreateRandomJewellery();
                    case ItemGroups.ReligiousItems: return ItemBuilder.CreateRandomReligiousItem();
                }
                Array values = DaggerfallUnity.Instance.ItemHelper.GetEnumArray(group);
                return values.Length == 0 ? null : new DaggerfallUnityItem(group, UnityEngine.Random.Range(0, values.Length));
            }
            Array all = DaggerfallUnity.Instance.ItemHelper.GetEnumArray(group);
            foreach (object v in all)
                if (v.ToString() == name)
                    return ItemBuilder.CreateItem(group, Convert.ToInt32(v));
            return null;
        }

        static DaggerfallUnityItem Copy(DaggerfallUnityItem item)
        {
            if (item.ItemGroup == ItemGroups.Weapons)
                return ItemBuilder.CreateWeapon((Weapons)item.TemplateIndex, (WeaponMaterialTypes)item.nativeMaterialValue);
            if (item.ItemGroup == ItemGroups.Armor)
                return MakeArmor((Armor)item.TemplateIndex, (ArmorMaterialTypes)item.nativeMaterialValue);
            return ItemBuilder.CreateItem(item.ItemGroup, item.TemplateIndex);
        }

        /// <summary>Weapons and armor in the list arrive worn: condition and value fall to a random percentage in range.</summary>
        static void Worn(List<DaggerfallUnityItem> items, string range)
        {
            foreach (DaggerfallUnityItem item in items)
            {
                if (item.ItemGroup != ItemGroups.Weapons && item.ItemGroup != ItemGroups.Armor)
                    continue;
                if (item.IsOfTemplate(ItemGroups.Weapons, (int)Weapons.Arrow))
                    continue;
                int pct = Range(range);
                item.currentCondition = Mathf.Max(1, item.maxCondition * pct / 100);
                item.value = Mathf.Max(1, item.value * pct / 100);
            }
        }

        // ---------------------------------------------------------------- data

        static List<Rec> Records(string kind)
        {
            Load();
            List<Rec> list = new List<Rec>();
            foreach (Rec r in recs)
                if (r.kind == kind)
                    list.Add(r);
            return list;
        }

        static string ProvinceOf(string region)
        {
            string name = (region ?? "").Replace(' ', '_');
            foreach (Rec r in Records("province"))
                if (Array.IndexOf(r.List("regions"), name) >= 0)
                    return r.name;
            return null;
        }

        static string Setting(string key, string fallback) { Load(); string v; return settings.TryGetValue(key, out v) ? v : fallback; }
        static int Setting(string key, int fallback) { int v; return int.TryParse(Setting(key, ""), NumberStyles.Integer, CultureInfo.InvariantCulture, out v) ? v : fallback; }
        static float SettingFloat(string key, float fallback) { float v; return float.TryParse(Setting(key, ""), NumberStyles.Float, CultureInfo.InvariantCulture, out v) ? v : fallback; }

        static void Load()
        {
            if (recs != null)
                return;
            recs = new List<Rec>();
            TextAsset text = Resources.Load<TextAsset>("Doomerfall/ShopLots");
            if (text == null)
            {
                Debug.LogError("Doomerfall: Resources/Doomerfall/ShopLots.txt is missing; shops get regular supply only.");
                return;
            }
            foreach (string raw in text.text.Split('\n'))
            {
                string[] f = raw.Trim().Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (f.Length < 2 || f[0].StartsWith("#"))
                    continue;
                if (f[0] == "setting")
                {
                    settings[f[1]] = f.Length > 2 ? f[2] : "";
                    continue;
                }
                Rec r = new Rec { kind = f[0], name = f[1] };
                for (int i = 1; i < f.Length; i++)
                {
                    int eq = f[i].IndexOf('=');
                    if (eq > 0)
                        r.kv[f[i].Substring(0, eq)] = f[i].Substring(eq + 1);
                }
                if (r.kind == "gunrarity")
                {
                    foreach (KeyValuePair<string, string> kv in r.kv)
                        gunRarity[kv.Key] = int.Parse(kv.Value, CultureInfo.InvariantCulture);
                    continue;
                }
                recs.Add(r);
            }
        }

        // ---------------------------------------------------------------- helpers

        static int Range(string range)
        {
            int dash = range.IndexOf('-');
            int lo, hi;
            if (dash < 0)
            {
                int.TryParse(range, NumberStyles.Integer, CultureInfo.InvariantCulture, out lo);
                return lo;
            }
            int.TryParse(range.Substring(0, dash), NumberStyles.Integer, CultureInfo.InvariantCulture, out lo);
            int.TryParse(range.Substring(dash + 1), NumberStyles.Integer, CultureInfo.InvariantCulture, out hi);
            return UnityEngine.Random.Range(lo, Mathf.Max(lo, hi) + 1);
        }

        static void Shuffle<T>(List<T> list)
        {
            for (int i = list.Count - 1; i > 0; i--)
            {
                int j = UnityEngine.Random.Range(0, i + 1);
                T t = list[i]; list[i] = list[j]; list[j] = t;
            }
        }

        static int Floor(int a, int b) { return a >= 0 ? a / b : -((-a + b - 1) / b); }
        static int Mod(int a, int b) { return a - Floor(a, b) * b; }

        static uint Hash(int a, int b, int c, int d)
        {
            unchecked
            {
                uint h = 2166136261;
                foreach (int v in new[] { a, b, c, d })
                    for (int s = 0; s < 32; s += 8)
                        h = (h ^ (uint)((v >> s) & 0xFF)) * 16777619;
                h ^= h >> 15; h *= 0x2C1B3C6D; h ^= h >> 12;
                return h;
            }
        }
    }
}
