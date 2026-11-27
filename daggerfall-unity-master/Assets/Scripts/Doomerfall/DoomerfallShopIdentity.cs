// Doomerfall: a shop's fixed identity (Shops 6), rolled from its location and building key only, so each shop is the
// same in every game and never adapts to the player. Used by DoomerfallShopLedger's deliveries.
//
//   Breadth  U-shaped (arcsine) in [0, 1]: 0 is a deep specialist, 1 a thin generalist. Kinds the shop does not favour
//            keep a weight of 0.03 (specialist) up to 1 (generalist): leans, never bans.
//   Lean     1 to 5 favoured kinds (item group and template) from the shop type's own table, picked in proportion to
//            the table's chance for that group, so a weapon smith mostly favours weapons. Specialists favour fewer.
//   Rhythm   U-shaped: half the shops get a trickle every 2-4 days, half a big delivery every 7, 14 or 30 days on a
//            fixed day. Nobody delivers every 5-6 days.
//   Suppliers two or three regulars share 85% of deliveries; the other 15% go to newcomers drawn from a Pitman-Yor
//            stick-breaking tail (discount 0.5, concentration 1), so new names keep appearing now and then and a few
//            of them come back. Each supplier favours one kind of its own (weight x3).
// Nothing here looks at an item's material or value: weights depend only on the kind, so the approved material odds
// are untouched.

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopIdentity
    {
        internal const float RegularShare = 0.85f;
        const float TailDiscount = 0.5f, TailConcentration = 1f, SupplierBoost = 3f;
        const int TailSuppliers = 24;

        internal readonly float Breadth;
        internal readonly bool Big;
        internal readonly int Interval, Phase, Regulars;
        internal readonly int[] Favoured;           // kind keys
        internal readonly float[] SupplierShare;    // regulars first, then the newcomer tail; sums to at most 1
        internal readonly int[] SupplierKind;       // kind key each supplier favours
        readonly float floor;

        static readonly Dictionary<long, DoomerfallShopIdentity> cache = new Dictionary<long, DoomerfallShopIdentity>();

        internal static DoomerfallShopIdentity For(int location, PlayerGPS.DiscoveredBuilding building)
        {
            long key = ((long)location << 32) ^ (uint)building.buildingKey ^ ((long)building.buildingType << 24) ^ ((long)building.quality << 18);
            DoomerfallShopIdentity id;
            if (!cache.TryGetValue(key, out id))
                cache[key] = id = new DoomerfallShopIdentity(location, building);
            return id;
        }

        DoomerfallShopIdentity(int location, PlayerGPS.DiscoveredBuilding building)
        {
            Rng rng = new Rng(DoomerfallShopLedger.Seed(location, building.buildingKey, 0x1D, 0x5A0F));
            float u = rng.Next();
            Breadth = Mathf.Sin(u * Mathf.PI / 2) * Mathf.Sin(u * Mathf.PI / 2);   // arcsine: U-shaped
            floor = 0.03f + 0.97f * Breadth;

            Big = rng.Next() < 0.5f;
            float r = rng.Next();
            Interval = Big ? (r < 0.6f ? 7 : r < 0.85f ? 14 : 30) : 2 + Mathf.Min(2, (int)(r * 3));
            Phase = Mathf.Min(Interval - 1, (int)(rng.Next() * Interval));

            List<int> kinds = new List<int>();
            List<float> odds = new List<float>();
            Kinds(building, kinds, odds);
            int count = Mathf.Min(kinds.Count, 1 + Mathf.RoundToInt(Breadth * 4));
            Favoured = new int[count];
            for (int i = 0; i < count; i++)
            {
                int pick = rng.Pick(odds);
                Favoured[i] = kinds[pick];
                odds[pick] = 0;
            }

            Regulars = rng.Next() < 0.5f ? 2 : 3;
            SupplierShare = new float[Regulars + TailSuppliers];
            float sum = 0;
            for (int i = 0; i < Regulars; i++)
                sum += SupplierShare[i] = 1 + rng.Next();   // regulars within a factor of two of each other
            for (int i = 0; i < Regulars; i++)
                SupplierShare[i] *= RegularShare / sum;
            float rest = 1 - RegularShare;
            for (int k = 0; k < TailSuppliers; k++)   // Pitman-Yor stick-breaking: V_k ~ Beta(1 - d, theta + (k + 1) d)
            {
                float v = rng.Beta(1 - TailDiscount, TailConcentration + (k + 1) * TailDiscount);
                SupplierShare[Regulars + k] = rest * v;
                rest *= 1 - v;
            }
            SupplierKind = new int[SupplierShare.Length];
            List<float> all = new List<float>(kinds.Count);
            Kinds(building, new List<int>(), all);
            for (int i = 0; i < SupplierKind.Length; i++)
                SupplierKind[i] = kinds.Count > 0 ? kinds[rng.Pick(all)] : -1;
        }

        /// <summary>True when the shop receives goods on this day number.</summary>
        internal bool DeliversOn(int day)
        {
            return ((day - Phase) % Interval + Interval) % Interval == 0;
        }

        /// <summary>The supplier of the delivery on this day (an index into SupplierShare), the same for every shelf.
        /// Returns SupplierShare.Length for the rare draw past the simulated tail (an unnamed one-off).</summary>
        internal int Supplier(int location, int buildingKey, int day)
        {
            float u = new Rng(DoomerfallShopLedger.Seed(location, buildingKey, day, 0x50F)).Next(), acc = 0;
            for (int i = 0; i < SupplierShare.Length; i++)
                if (u < (acc += SupplierShare[i]))
                    return i;
            return SupplierShare.Length;
        }

        /// <summary>Delivery weight of an item from this supplier: from its kind only.</summary>
        internal float Weight(DaggerfallUnityItem item, int supplier)
        {
            int kind = Kind(item);
            float w = System.Array.IndexOf(Favoured, kind) >= 0 ? 1f : floor;
            if (supplier < SupplierKind.Length && SupplierKind[supplier] == kind)
                w *= SupplierBoost;
            return w;
        }

        internal static int Kind(DaggerfallUnityItem item)
        {
            return Kind(item.ItemGroup, item.ItemGroup == ItemGroups.Books ? 0 : item.GroupIndex);
        }

        static int Kind(ItemGroups group, int index)
        {
            if (group == ItemGroups.WomensClothing)
                group = ItemGroups.MensClothing;   // classic swaps clothing to the player's gender; the lean must not
            return (int)group * 1000 + index;
        }

        internal static string KindName(int kind)
        {
            ItemGroups group = (ItemGroups)(kind / 1000);
            if (group == ItemGroups.Books || !DaggerfallUnity.Instance)
                return group.ToString();
            try { return DaggerfallUnity.Instance.ItemHelper.GetItemTemplate(group, kind % 1000).name; }
            catch { return group + "#" + kind % 1000; }
        }

        /// <summary>The kinds a shop type's classic table can stock at this quality, with the table's chance for each.</summary>
        static void Kinds(PlayerGPS.DiscoveredBuilding building, List<int> kinds, List<float> odds)
        {
            byte[] table = Table(building.buildingType);
            ItemHelper helper = DaggerfallUnity.Instance ? DaggerfallUnity.Instance.ItemHelper : null;
            for (int i = 0; table != null && i < table.Length; i += 2)
            {
                ItemGroups group = (ItemGroups)table[i];
                int chance = table[i + 1];
                if (chance == 0 || group == ItemGroups.Furniture || group == ItemGroups.UselessItems1 || group == ItemGroups.Transportation)
                    continue;
                if (group == ItemGroups.Books || helper == null)
                {
                    kinds.Add(Kind(group, 0));
                    odds.Add(chance);
                    continue;
                }
                System.Array values = helper.GetEnumArray(group);
                for (int j = 0; j < values.Length; j++)
                    if (helper.GetItemTemplate(group, j).rarity <= building.quality)
                    {
                        kinds.Add(Kind(group, j));
                        odds.Add((float)chance / values.Length);
                    }
            }
        }

        static byte[] Table(DFLocation.BuildingTypes type)
        {
            switch (type)
            {
                case DFLocation.BuildingTypes.Alchemist: return DaggerfallLootDataTables.itemGroupsAlchemist;
                case DFLocation.BuildingTypes.Armorer: return DaggerfallLootDataTables.itemGroupsArmorer;
                case DFLocation.BuildingTypes.Bookseller: return DaggerfallLootDataTables.itemGroupsBookseller;
                case DFLocation.BuildingTypes.ClothingStore: return DaggerfallLootDataTables.itemGroupsClothingStore;
                case DFLocation.BuildingTypes.GemStore: return DaggerfallLootDataTables.itemGroupsGemStore;
                case DFLocation.BuildingTypes.GeneralStore: return DaggerfallLootDataTables.itemGroupsGeneralStore;
                case DFLocation.BuildingTypes.PawnShop: return DaggerfallLootDataTables.itemGroupsPawnShop;
                case DFLocation.BuildingTypes.WeaponSmith: return DaggerfallLootDataTables.itemGroupsWeaponSmith;
            }
            return null;
        }

        internal string Describe()
        {
            string fav = "";
            foreach (int k in Favoured)
                fav += (fav.Length > 0 ? ", " : "") + KindName(k);
            string sup = "";
            for (int i = 0; i < Regulars; i++)
                sup += string.Format("{0}{1:P0} (favours {2})", i > 0 ? ", " : "", SupplierShare[i], KindName(SupplierKind[i]));
            return string.Format("breadth {0:F2} ({1}), favours {2}; {3} every {4} days (day {5} of the cycle); {6} regular suppliers: {7}; newcomers {8:P0}",
                Breadth, Breadth < 0.5f ? "specialist" : "generalist", fav, Big ? "big delivery" : "trickle", Interval, Phase, Regulars, sup, 1 - RegularShare);
        }

        /// <summary>Small deterministic generator (xorshift32), independent of Unity's global generator and of the runtime.</summary>
        sealed class Rng
        {
            uint s;
            internal Rng(int seed) { s = (uint)seed; if (s == 0) s = 0x9E3779B9; for (int i = 0; i < 4; i++) Step(); }
            uint Step() { s ^= s << 13; s ^= s >> 17; s ^= s << 5; return s; }
            internal float Next() { return (Step() >> 8) * (1f / 16777216f); }

            internal int Pick(List<float> weights)
            {
                float total = 0;
                foreach (float w in weights) total += w;
                float x = Next() * total;
                for (int i = 0; i < weights.Count; i++)
                    if (weights[i] > 0 && (x -= weights[i]) < 0)
                        return i;
                for (int i = weights.Count - 1; i >= 0; i--)
                    if (weights[i] > 0) return i;
                return 0;
            }

            internal float Beta(float a, float b) { float x = Gamma(a), y = Gamma(b); return x / (x + y); }

            float Gamma(float shape)   // Marsaglia-Tsang; shape < 1 via the u^(1/shape) boost
            {
                if (shape < 1)
                    return Gamma(shape + 1) * Mathf.Pow(Mathf.Max(Next(), 1e-7f), 1 / shape);
                float d = shape - 1f / 3, c = 1 / Mathf.Sqrt(9 * d);
                while (true)
                {
                    float x, v;
                    do { x = Normal(); v = 1 + c * x; } while (v <= 0);
                    v = v * v * v;
                    float u = Mathf.Max(Next(), 1e-7f);
                    if (Mathf.Log(u) < 0.5f * x * x + d - d * v + d * Mathf.Log(v))
                        return d * v;
                }
            }

            float Normal() { return Mathf.Sqrt(-2 * Mathf.Log(Mathf.Max(Next(), 1e-7f))) * Mathf.Cos(2 * Mathf.PI * Next()); }
        }
    }
}
