// Doomerfall: how much Regular Doom ammo a shop stocks at each restock (shop ammo card, owner 2026-11-26). Shops are
// the main source of Doom ammo. A general store holds on average about 300 bullets, 120 shells, 30 rockets and 300 cells
// (Doom's pickup ratio: a clip is 10 bullets, shells come 4 at a time, a rocket 1 at a time). Each shop varies by its
// own fixed seed (gamedesign.md, Randomness): some lean hard toward one ammo type, an occasional one is a specialist, a
// few are big depots or near empty. Nothing adapts to the player. Restocking follows Daggerfall's normal shop restock;
// each restock varies a little around the shop's fixed amounts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShopAmmo
    {
        // The average stock of a general store, per ammo type (bullets, shells, rockets, cells).
        internal static readonly int[] Average = { 300, 120, 30, 300 };

        // Doom's small pickup per type. Stock is a whole number of these, at least one: leans, never bans.
        static readonly int[] Unit = { 10, 4, 1, 20 };

        // Which shops sell ammo, and how much of the general store's amounts. My call within the owner's "general stores,
        // weaponsmiths and maybe others that are appropriate sounding": an armorer outfits fighters, so it carries half.
        // Pawn shops wait on the open question about them.
        internal static float Sells(DFLocation.BuildingTypes type)
        {
            switch (type)
            {
                case DFLocation.BuildingTypes.GeneralStore: return 1f;
                case DFLocation.BuildingTypes.WeaponSmith: return 1f;
                case DFLocation.BuildingTypes.Armorer: return 0.5f;
                default: return 0f;
            }
        }

        // The amounts for one restock, or null for a shop that sells no ammo.
        internal static int[] Restock(DFLocation.BuildingTypes type, int quality, int mapID, int buildingKey)
        {
            float[] fixedAmounts = Expected(type, quality, mapID, buildingKey);
            if (fixedAmounts == null)
                return null;
            int[] amounts = new int[fixedAmounts.Length];
            for (int t = 0; t < amounts.Length; t++)
                amounts[t] = Round(t, fixedAmounts[t] * Random.Range(0.85f, 1.15f));
            return amounts;
        }

        // The shop's fixed average amounts, before a restock's small variation.
        internal static float[] Expected(DFLocation.BuildingTypes type, int quality, int mapID, int buildingKey)
        {
            float scale = Sells(type);
            if (scale <= 0)
                return null;
            float[] weights = Genome(Seed(mapID, buildingKey));
            float[] norm = Norm;
            // Better shops hold more: quality 1 is 0.7x, quality 20 is 1.3x, the average of 1-20 is 1x.
            scale *= 0.7f + 0.6f * (Mathf.Clamp(quality, 1, 20) - 1) / 19f;
            float[] result = new float[Average.Length];
            for (int t = 0; t < result.Length; t++)
                result[t] = Average[t] * scale * weights[t] / norm[t];
            return result;
        }

        // A trade window's price for a basket or sale item. Daggerfall prices one unit, rounding down after the regional
        // price adjustment, then multiplies by the stack: a 1-gold bullet would cost nothing in any region priced under
        // 100%. Doom ammo is priced as the whole stack's value instead, so the regional price applies without rounding
        // each round away. Every other item keeps Daggerfall's formula.
        internal static int StackCost(DaggerfallUnityItem item, int quality, int conditionPercentage = -1)
        {
            if (item is DoomerfallAmmoItem)
                return FormulaHelper.CalculateCost(item.value * item.stackCount, quality, conditionPercentage);
            return FormulaHelper.CalculateCost(item.value, quality, conditionPercentage) * item.stackCount;
        }

        internal static int Round(int type, float amount)
        {
            return Mathf.Max(1, Mathf.RoundToInt(amount / Unit[type])) * Unit[type];
        }

        // The shop's ammo identity: its size and its lean, as a weight per type. Normalised by Norm so the average over
        // all shops is 1 for each type.
        internal static float[] Genome(uint seed)
        {
            System.Random rng = new System.Random((int)(seed & 0x7fffffff));
            int n = Average.Length;
            float[] w = new float[n];
            // Size: mostly about the average, sometimes a near-empty shop, sometimes a big depot (U-shaped tails).
            double r = rng.NextDouble();
            float size = r < 0.12 ? 0.35f : r < 0.85 ? 0.75f + 0.5f * (float)rng.NextDouble() : 2f + (float)rng.NextDouble();
            // Lean: balanced, leaning hard toward one type, or (the exception) a specialist in one type.
            double s = rng.NextDouble();
            int favourite = rng.Next(n);
            for (int t = 0; t < n; t++)
            {
                float jitter = 0.8f + 0.4f * (float)rng.NextDouble();
                if (s < 0.40)
                    w[t] = jitter;
                else if (s < 0.85)
                    w[t] = t == favourite ? 2.5f * jitter : 0.7f * jitter;
                else
                    w[t] = t == favourite ? 4f * jitter : 0.25f * jitter;
                w[t] *= size;
            }
            return w;
        }

        // A shop's seed from its town and building, mixed so neighbouring keys differ. Separate from other seeds by its salt.
        internal static uint Seed(int mapID, int buildingKey)
        {
            uint h = 0x9E3779B9u ^ 0xA3307u; // Salt: shop ammo.
            h = Mix(h ^ (uint)mapID);
            h = Mix(h ^ (uint)buildingKey);
            return h;
        }

        static uint Mix(uint x)
        {
            x ^= x >> 16; x *= 0x7feb352du;
            x ^= x >> 15; x *= 0x846ca68bu;
            x ^= x >> 16;
            return x;
        }

        // The mean weight per type over many seeds, computed once, so each type averages exactly its Average.
        static float[] norm;
        static float[] Norm
        {
            get
            {
                if (norm != null)
                    return norm;
                const int samples = 4000; // About 1% error per type; a one-time cost of a few ms.
                float[] sum = new float[Average.Length];
                for (int i = 0; i < samples; i++)
                {
                    float[] w = Genome(Mix((uint)i * 2654435761u + 12345u));
                    for (int t = 0; t < sum.Length; t++)
                        sum[t] += w[t];
                }
                for (int t = 0; t < sum.Length; t++)
                    sum[t] /= samples;
                norm = sum;
                return norm;
            }
        }
    }
}
