// Doomerfall: ammo material tiers (owner, 2026-11-24, card ammotiers/04). Each tier is a Daggerfall material with
// its own name, damage bonus, price and weight, as multiples of each ammo type's base values. Runs only
// in a bridge session.
//
// A tiered stack is told apart by its template index, which Daggerfall saves and stacks by: Regular keeps the plain
// ammo templates 9101-9104, so old saves load as Regular, and tier k of ammo type t is 9200 + 10t + k.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallAmmoTiers
    {
        internal struct Tier
        {
            public string name;
            public WeaponMaterialTypes material; // The Daggerfall material this tier maps to.
            public double bonus;                 // Damage bonus as a fraction, 0.2 is +20%.
            public int priceMul;                 // Price per round, as a multiple of the base price.
            public float weightMul;
            public Color32 dark, light;          // The material's colour ramp (Daggerfall's metal dye), darkest and lightest.
        }

        internal const int Regular = 0, Daedric = 9;

        // The owner's table, in its order. Tint ramps are the darkest and lightest colours of each material's metal dye
        // table (ImageProcessing.GetMetalColorTable) in ART_PAL.COL, the palette of Daggerfall's item pictures.
        internal static readonly Tier[] Tiers =
        {
            T("Regular",    WeaponMaterialTypes.Iron,       0.00,  3, 1.0f,  44,  44,  45, 119, 119, 119),
            T("Steel",      WeaponMaterialTypes.Steel,      0.20,  5, 1.0f,  44,  44,  44, 220, 220, 220),
            T("Silver",     WeaponMaterialTypes.Silver,     0.10,  7, 1.0f,  94,  94, 109, 254, 255, 199),
            T("Moonstone",  WeaponMaterialTypes.Elven,      0.35, 14, 0.5f, 110, 110, 110, 254, 255, 199),
            T("Dwemer",     WeaponMaterialTypes.Dwarven,    0.50, 15, 2.0f,  58,  51,  25, 255, 246, 103),
            T("Adamantium", WeaponMaterialTypes.Adamantium, 0.60, 28, 1.0f,  19,  19,  19,  75,  75,  85),
            T("Orichalcum", WeaponMaterialTypes.Orcish,     0.70, 32, 1.0f,  23,  23,  23,  92, 127,  54),
            T("Mithril",    WeaponMaterialTypes.Mithril,    0.40, 40, 0.1f,  19,  19,  19,  62, 105, 167),
            T("Ebony",      WeaponMaterialTypes.Ebony,      1.00, 45, 2.0f,  19,  19,  19, 119, 119, 119),
            T("Daedric",    WeaponMaterialTypes.Daedric,    1.00, 75, 1.0f,  83,  32,  10, 198,  95,  31),
        };

        static Tier T(string name, WeaponMaterialTypes material, double bonus, int price, float weight,
            byte dr, byte dg, byte db, byte lr, byte lg, byte lb)
        {
            return new Tier { name = name, material = material, bonus = bonus, priceMul = price, weightMul = weight,
                dark = new Color32(dr, dg, db, 255), light = new Color32(lr, lg, lb, 255) };
        }

        // Rounds in one vendor pack. Every tier's pack holds the same as Regular's: higher tiers are rarer, not smaller
        // (owner, 2026-11-26). Shop stock only: pickups and drops in Doom give stock Doom's amounts, which
        // DoomerfallAmmoPickup.Rounds (DoomerfallAmmo.zs) decides and sends here with each take.
        internal static readonly int[] ShopPack = { 80, 20, 8, 100 };

        internal static int Template(int type, int tier)
        {
            return tier == Regular ? DoomerfallAmmo.Types[type].template : 9200 + type * 10 + tier;
        }

        // Splits a template index into its ammo type and tier. False for anything that is not ammo.
        internal static bool FromTemplate(int template, out int type, out int tier)
        {
            type = tier = -1;
            for (int t = 0; t < DoomerfallAmmo.Types.Length; t++)
            {
                if (template == DoomerfallAmmo.Types[t].template) { type = t; tier = Regular; return true; }
                int k = template - (9200 + t * 10);
                if (k > Regular && k < Tiers.Length) { type = t; tier = k; return true; }
            }
            return false;
        }

        internal static string Name(int type, int tier) { return Tiers[tier].name + " " + DoomerfallAmmo.Types[type].lowerName; }
        internal static int Price(int type, int tier) { return DoomerfallAmmo.Types[type].basePrice * Tiers[tier].priceMul; }
        internal static float Weight(int type, int tier) { return DoomerfallAmmo.Types[type].baseWeightKg * Tiers[tier].weightMul; }
        internal static int Stack(int type) { return ShopPack[type]; }

        // An ammo's tags (such as reduced_noise), shown as player state while it is loaded (owner, 2026-11-24). None exist
        // yet: Silver's creature bonus and the quiet tag are backlog items. They show under Doom's loaded ammo icon.
        static readonly string[] NoTags = new string[0];
        internal static string[] Tags(int type, int tier) { return NoTags; }

        internal static string BonusText(int tier)
        {
            double b = Tiers[tier].bonus;
            return b <= 0 ? "no damage bonus" : string.Format("+{0:0}% damage", b * 100);
        }

        // The info popup: what the ammo does, including its bonus (owner, 2026-11-24).
        internal static TextFile.Token[] Info(int type, int tier, int count)
        {
            DoomerfallAmmo.AmmoType a = DoomerfallAmmo.Types[type];
            string what = tier == Regular
                ? string.Format("Plain {0}: {1}.", a.lowerName, BonusText(tier))
                : string.Format("{0} {1}: {2} with every gun that fires {1}.", Tiers[tier].name, a.lowerName, BonusText(tier));
            return DaggerfallUnity.Instance.TextProvider.CreateTokens(TextFile.Formatting.JustifyCenter,
                string.Format("{0} ({1})", Name(type, tier), count),
                what,
                string.Format("Each round weighs {0:0.###} kg and is worth {1} gold.", Weight(type, tier), Price(type, tier)),
                string.Format("One pack holds {0}.", Stack(type)));
        }

        // ---- Colour tints ------------------------------------------------------------------------------------------

        static readonly Dictionary<long, Texture2D> tinted = new Dictionary<long, Texture2D>();

        // Doom's sprite recoloured along the material's ramp by brightness, as Daggerfall dyes metal items.
        internal static Texture2D Tinted(Texture2D source, int type, int tier)
        {
            if (!source || !source.isReadable)
                return null; // The untinted picture is shown instead.
            long key = ((long)source.GetInstanceID() << 8) | (long)(type * 16 + tier);
            Texture2D cached;
            if (tinted.TryGetValue(key, out cached) && cached)
                return cached;
            Color32[] pixels = source.GetPixels32();
            Color32 dark = Tiers[tier].dark, light = Tiers[tier].light;
            for (int i = 0; i < pixels.Length; i++)
            {
                Color32 p = pixels[i];
                float lum = (0.3f * p.r + 0.59f * p.g + 0.11f * p.b) / 255f;
                Color32 c = Color32.Lerp(dark, light, lum);
                c.a = p.a;
                pixels[i] = c;
            }
            Texture2D result = new Texture2D(source.width, source.height, TextureFormat.ARGB32, false);
            result.filterMode = source.filterMode;
            result.SetPixels32(pixels);
            result.Apply(false, false);
            tinted[key] = result;
            return result;
        }

        // ---- Shop stock --------------------------------------------------------------------------------------------

        // My numbers: percent chance per ammo type at each restock of a weapon smith of quality 10, in tier order. The
        // owner's "where you get it" column decides the order: Regular is common, Adamantium uncommon, Orichalcum rare
        // except in the Orsinium Area, and Daedric rare.
        static readonly int[] SmithChance = { 85, 50, 45, 35, 35, 12, 6, 25, 25, 10 };
        const int OrsiniumOrichalcumChance = 50, GeneralStoreRegularChance = 60;

        // Adds ammo to a shop shelf being restocked (DaggerfallLoot.StockShopShelf). Weapon smiths stock every tier;
        // general stores stock only Regular. Other shops stock none.
        internal static void StockShop(DFLocation.BuildingTypes buildingType, int quality, ItemCollection items)
        {
            if (!DoomerfallAmmo.IsRegistered || items == null)
                return;
            bool smith = buildingType == DFLocation.BuildingTypes.WeaponSmith;
            if (!smith && buildingType != DFLocation.BuildingTypes.GeneralStore)
                return;
            bool orsinium = GameManager.HasInstance && GameManager.Instance.PlayerGPS != null
                && GameManager.Instance.PlayerGPS.CurrentRegionName == "Orsinium Area";
            float qualityScale = 0.5f + Mathf.Clamp(quality, 1, 20) / 20f;
            for (int type = 0; type < DoomerfallAmmo.Types.Length; type++)
            {
                for (int tier = 0; tier < Tiers.Length; tier++)
                {
                    int chance;
                    if (!smith)
                        chance = tier == Regular ? GeneralStoreRegularChance : 0;
                    else if (tier == 6 && orsinium)
                        chance = OrsiniumOrichalcumChance;
                    else
                        chance = SmithChance[tier];
                    chance = Mathf.Min(95, Mathf.RoundToInt(chance * qualityScale));
                    if (chance <= 0 || UnityEngine.Random.Range(0, 100) >= chance)
                        continue;
                    int stacks = tier == Regular ? UnityEngine.Random.Range(2, 5) : UnityEngine.Random.Range(1, 3);
                    items.AddItem(new DoomerfallAmmoItem(type, tier, stacks * Stack(type)));
                }
            }
        }
    }
}
