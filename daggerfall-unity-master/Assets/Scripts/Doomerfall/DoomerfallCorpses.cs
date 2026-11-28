// Doomerfall: the corpses of Daggerfall guards killed in Doom, and of Daggerfall creatures (townspeople leave none, as in Daggerfall Unity). Runs only in a bridge session.
//
// Daggerfall keeps each corpse where the body fell, with the billboard image Daggerfall gives it, in the townspeople
// ledger, so it is still there after leaving and returning and after a save and load. DoomerfallTownspeople lists
// the ones in sight inside its townsfolk lists, and Doom draws them (UZDoom/src/dd_townsfolk.cpp).

using System;
using System.Collections.Generic;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    [Serializable]
    public sealed class DoomerfallCorpse
    {
        public string id;
        public int mapId;           // the town
        public int building;        // 0 on the streets, else the building key
        public double x, y;         // streets: Daggerfall world units (x east, y north); inside: Doom map units
        public float z;             // inside: the Doom floor height
        public int archive, record;
    }

    internal static class DoomerfallCorpses
    {
        // A Daggerfall creature's corpse image, as EnemyDeath picks it (its male texture's corpse). False if no such type.
        internal static bool CreatureCorpse(int mobileType, out int archive, out int record)
        {
            archive = record = 0;
            foreach (MobileEnemy e in EnemyBasics.Enemies)
                if (e.ID == mobileType)
                {
                    EnemyBasics.ReverseCorpseTexture(e.CorpseTexture, out archive, out record);
                    return true;
                }
            return false;
        }

        internal static bool Has(List<DoomerfallCorpse> corpses, string id)
        {
            foreach (DoomerfallCorpse c in corpses)
                if (c.id == id)
                    return true;
            return false;
        }

        // The corpses on these streets within range of (px, pz), relative to the origin, or in this building.
        internal static void Select(List<DoomerfallCorpse> corpses, int mapId, int building, double originX, double originZ, double px, double pz, double range, List<DoomerfallCorpse> into)
        {
            into.Clear();
            foreach (DoomerfallCorpse c in corpses)
            {
                if (c.mapId != mapId || c.building != building)
                    continue;
                if (building == 0)
                {
                    double dx = c.x - originX - px, dz = c.y - originZ - pz;
                    if (dx * dx + dz * dz > range * range)
                        continue;
                }
                into.Add(c);
            }
        }
    }
}
