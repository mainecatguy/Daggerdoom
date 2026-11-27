// Doomerfall: Doom reserve ammo held in Daggerfall's inventory. Runs only in a bridge session.
//
// Daggerfall holds each ammo type as a stack (one round per unit) that weighs and is priced per round. Doom's ammo
// inventory is the live counter that guns spend, so Doom reports its counts (DFB_KIND_AMMO) and Daggerfall mirrors
// them. Changes made on Daggerfall's side (dropping, trading, taking from a pile) go to Doom as numbered deltas
// (DFB_KIND_AMMO_ADD). Each report carries the last delta Doom applied, so a delta still in flight is never counted twice.
// Doom's ammo is in its own save and Daggerfall's stacks in its own, both in the bundled save. After a load Doom
// reports again and its count wins any difference.
//
// Loaded ammo. Doom's counter for an ammo type stands for the stacks of that type that are loaded (IsLoaded). Doom
// reports which ammo type its ready gun uses (DFB_KIND_AMMO_READY) whenever a gun is equipped or raised. Daggerfall
// then tells Doom how many loaded rounds it holds, and the damage bonus (DoomerfallDamageBonus) takes that ammo's
// material. Only the stacks of the type's loaded tier are loaded (DoomerfallAmmoTiers); changing the loaded tier
// (SetLoadedTier) calls Reload, and Update sends Doom the difference through the same delta path.
//
// Tiered pickups. Doom's tiered ammo pickups (DoomerfallAmmo.zs) do not add to Doom's counter. Doom reports each one
// (DFB_KIND_AMMO_TAKE) and it becomes a stack here; a loaded-tier stack then reaches Doom as a delta. Doom rolls each
// pickup's tier with the area level Daggerfall answers for a map pixel (DFB_KIND_AREA_LEVEL).

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // One stack of one ammo type and material tier (DoomerfallAmmoTiers). The template index names both.
    public class DoomerfallAmmoItem : DaggerfallUnityItem, ICustomItemImage, ICustomItemInfo
    {
        public DoomerfallAmmoItem() : base(ItemGroups.MiscItems, DoomerfallAmmo.Types[0].template)
        {
        }

        public DoomerfallAmmoItem(int type, int count) : this(type, DoomerfallAmmoTiers.Regular, count)
        {
        }

        // Daggerfall reloads its item templates after the bridge registers custom ones, so the custom templates are gone by
        // play time. The item carries its own weight and value, saved with it, and its group index names its type and tier.
        public DoomerfallAmmoItem(int type, int tier, int count) : base(ItemGroups.MiscItems, DoomerfallAmmoTiers.Template(type, tier))
        {
            stackCount = Math.Max(1, count);
            shortName = DoomerfallAmmoTiers.Name(type, tier);
            weightInKg = DoomerfallAmmoTiers.Weight(type, tier);
            value = DoomerfallAmmoTiers.Price(type, tier);
            nativeMaterialValue = (int)DoomerfallAmmoTiers.Tiers[tier].material;
        }

        // -1 for an item that is not ammo.
        public int AmmoType { get { int type, tier; DoomerfallAmmoTiers.FromTemplate(GroupIndex, out type, out tier); return type; } }
        public int Tier { get { int type, tier; DoomerfallAmmoTiers.FromTemplate(GroupIndex, out type, out tier); return tier; } }
        public string DoomClass { get { int t = AmmoType; return t < 0 ? "" : DoomerfallAmmo.Types[t].doomClass; } }
        public override string ItemName { get { int t = AmmoType; return t < 0 ? base.ItemName : DoomerfallAmmoTiers.Name(t, Tier); } }
        public override string LongName { get { return ItemName; } }
        public override bool IsStackable() { return true; }
        // Daggerfall's split would build the part from the template, which is gone at play time, or registered only for bullets.
        public override DaggerfallUnityItem CreateStackPart() { int t = AmmoType; return t < 0 ? base.CreateStackPart() : new DoomerfallAmmoItem(t, Tier, 1); }
        public override bool UseItem(ItemCollection collection)
        {
            DaggerfallUI.MessageBox("Your guns load this ammo by themselves.");
            return true;
        }
        public bool TryGetImage(out ImageData image)
        {
            if (!DoomerfallDoomItems.TryGetImage(DoomClass, out image))
                return false;
            Texture2D tint = DoomerfallAmmoTiers.Tinted(image.texture, AmmoType, Tier);
            if (tint)
                image.texture = tint;
            return true;
        }
        public TextFile.Token[] GetInfoTokens() { int t = AmmoType; return t < 0 ? null : DoomerfallAmmoTiers.Info(t, Tier, stackCount); }

        public override ItemData_v1 GetSaveData()
        {
            ItemData_v1 data = base.GetSaveData();
            data.className = typeof(DoomerfallAmmoItem).ToString();
            return data;
        }
    }

    internal sealed class DoomerfallAmmo : MonoBehaviour
    {
        internal struct AmmoType
        {
            public int template; // The Regular tier's template; DoomerfallAmmoTiers.Template gives the others.
            public string doomClass, lowerName;
            public float baseWeightKg;
            public int basePrice;
        }

        // The owner's base weights and prices per round (2026-11-24); each tier multiplies them. Doom's class names match dd_items.cpp AmmoClasses.
        internal static readonly AmmoType[] Types =
        {
            new AmmoType { template = 9101, doomClass = "Clip", lowerName = "bullets", baseWeightKg = 0.02f, basePrice = 1 },
            new AmmoType { template = 9102, doomClass = "Shell", lowerName = "shotgun shells", baseWeightKg = 0.1f, basePrice = 3 },
            new AmmoType { template = 9103, doomClass = "RocketAmmo", lowerName = "rockets", baseWeightKg = 0.2f, basePrice = 10 },
            new AmmoType { template = 9104, doomClass = "Cell", lowerName = "energy cells", baseWeightKg = 0.02f, basePrice = 5 },
        };

        internal static bool IsRegistered { get { return registered; } }

        // The tier Doom's counter of each ammo type stands for (an index into DoomerfallAmmoTiers.Tiers). Each gun remembers
        // its own tier (DoomerfallDoomItem.TryGetAmmoTier), which becomes its type's loaded tier while Doom holds it.
        // Saved in DoomerfallHotkeys.txt, so a load restores it before Doom's restored counts are mirrored.
        static readonly int[] loadedTier = new int[4];

        internal static string SaveTiers() { return "ammotiers " + string.Join(" ", Array.ConvertAll(loadedTier, t => t.ToString())); }

        // From the save's "ammotiers" line, or null (an older save, or a new game): Regular.
        internal static void LoadTiers(string[] fields)
        {
            for (int i = 0; i < loadedTier.Length; i++)
            {
                int tier;
                loadedTier[i] = fields != null && fields.Length > i + 1 && int.TryParse(fields[i + 1], out tier)
                    && tier >= 0 && tier < DoomerfallAmmoTiers.Tiers.Length ? tier : DoomerfallAmmoTiers.Regular;
            }
        }

        // The loaded ammo's tags, a kind of player state (owner, 2026-11-24). Empty with no gun ready. None exist yet.
        internal static string[] LoadedTags = new string[0];

        // The change ammo key (card ammotiers/05). One magazine unload in flight at a time.
        const float UnloadTimeout = 5f, AutoInterval = 0.5f;
        bool changeWanted;
        uint nextUnload = 1, unloadRequest, unloadedRounds;
        bool unloadAuto, unloadedArrived;
        int unloadType, unloadFrom, unloadTo;
        float unloadDeadline, nextAuto;
        int readySeq;                      // Counts AMMO_READY reports.
        DoomerfallDoomItem boundGun;       // The active gun last seen, and whether Doom has reported it ready since.
        int boundSeq, seenSwap, swapSeq;
        bool boundReady;
        int gunType = -1;                  // The ammo type of the bound gun, kept while Doom lowers it to fists.
        string sentLoaded;                 // What Doom's HUD shows, so it is sent only on a change.

        // Tiered pickups Doom reported before Daggerfall was in a game, and area level questions not yet answered.
        readonly List<KeyValuePair<int, KeyValuePair<int, int>>> takes = new List<KeyValuePair<int, KeyValuePair<int, int>>>();
        readonly List<uint> levelRequests = new List<uint>();

        sealed class Track
        {
            public int report = -1;  // Doom's last reported count, or -1 before any report.
            public uint reportAck;   // The last AMMO_ADD Doom had applied when it sent that report.
            public int synced;       // Daggerfall's inventory total as of the last time both sides agreed.
            public readonly List<KeyValuePair<uint, int>> pending = new List<KeyValuePair<uint, int>>(); // Deltas sent, not yet applied.
        }

        static bool registered;
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly Track[] tracks = new Track[Types.Length];
        bool ready;
        uint nextAdd = 1;
        int readyType = -2;  // The ammo type Doom's ready gun uses: -1 none (fists), -2 not reported yet.
        bool tellWanted;     // The ready gun or its loaded ammo changed: tell Doom the loaded count.

        // Test only (DoomerfallAmmoTest.ApplyBonusTest): a material bonus per ammo type in place of the loaded ammo's.
        internal static double[] TestBonus;

        static int TypeOfClass(string cls)
        {
            for (int i = 0; i < Types.Length; i++)
                if (Types[i].doomClass == cls)
                    return i;
            return -1;
        }

        // Before any save can load, so Daggerfall can rebuild ammo stacks from it.
        internal static void Register()
        {
            if (registered)
                return;
            registered = true;
            AddTemplates();
            // A class registers for loading only once. A save names the class, and the item's own data names its type.
            DaggerfallUnity.Instance.ItemHelper.RegisterCustomItem(Types[0].template, ItemGroups.None, typeof(DoomerfallAmmoItem));
        }

        // Adds any ammo template Daggerfall does not hold. Its template list is rebuilt after Register runs.
        static void AddTemplates()
        {
            ItemHelper helper = DaggerfallUnity.Instance.ItemHelper;
            ItemTemplate placeholder = helper.GetItemTemplate((int)MiscItems.Letter_of_credit); // Shown until Doom sends the sprite.
            for (int type = 0; type < Types.Length; type++)
            {
                for (int tier = 0; tier < DoomerfallAmmoTiers.Tiers.Length; tier++)
                {
                    helper.AddCustomItemTemplate(new ItemTemplate
                    {
                        index = DoomerfallAmmoTiers.Template(type, tier),
                        name = DoomerfallAmmoTiers.Name(type, tier),
                        baseWeight = DoomerfallAmmoTiers.Weight(type, tier),
                        basePrice = DoomerfallAmmoTiers.Price(type, tier),
                        isNotRepairable = true,
                        worldTextureArchive = placeholder.worldTextureArchive,
                        worldTextureRecord = placeholder.worldTextureRecord,
                        playerTextureArchive = placeholder.playerTextureArchive,
                        playerTextureRecord = placeholder.playerTextureRecord,
                    });
                }
            }
        }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            for (int i = 0; i < tracks.Length; i++)
                tracks[i] = new Track();
            SaveLoadManager.OnLoad += OnLoad;
        }

        void OnDestroy()
        {
            SaveLoadManager.OnLoad -= OnLoad;
        }

        // Reports from before the load describe the old game. Doom reports its restored counts once both games resume.
        void OnLoad(SaveData_v1 saveData)
        {
            foreach (Track t in tracks)
            {
                t.report = -1;
                t.pending.Clear();
            }
            ready = false;
            readyType = -2; // Doom reports its ready gun again after the load.
            tellWanted = false;
            takes.Clear(); // Pickups from the game being replaced.
            changeWanted = unloadedArrived = false;
            unloadRequest = 0;
            boundGun = null;
            boundReady = false;
            gunType = -1;
            sentLoaded = null; // Doom shows the loaded ammo again once it reports its ready gun.
            bridge.LogLine("ammo: after load Daggerfall holds" + Totals() + "; " + SaveTiers());
        }

        // DFB_KIND_AMMO_READY: Doom's ready weapon changed and uses this reserve ammo ("" for none).
        internal void OnReady(string cls)
        {
            readyType = string.IsNullOrEmpty(cls) ? -1 : TypeOfClass(cls);
            readySeq++;
            tellWanted = true;
            bridge.LogLine(string.Format("ammo: Doom's ready gun uses {0}", readyType >= 0 ? Types[readyType].doomClass : "no reserve ammo"));
        }

        // The loaded ammo changed (a later change ammo key): tell Doom the new loaded count. Same path as equipping a gun.
        internal void Reload()
        {
            tellWanted = true;
        }

        internal int ReadyType { get { return readyType; } }

        // DFB_KIND_AMMO_CHANGE: the change ammo key.
        internal void OnChangeKey() { changeWanted = true; }

        // DFB_KIND_AMMO_UNLOADED: Doom emptied the gun's magazine (or refused an automatic change).
        internal void OnUnloaded(uint request, uint rounds)
        {
            if (request != unloadRequest || request == 0)
                return;
            unloadedArrived = true;
            unloadedRounds = rounds;
        }

        static int TierTotal(ItemCollection items, int type, int tier)
        {
            int total = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null && item.AmmoType == type && item.Tier == tier)
                    total += item.stackCount;
            }
            return total;
        }

        // The next tier after this one, in the owner's tier order and wrapping round, that the inventory holds; -1 for none.
        static int NextTier(ItemCollection items, int type, int from)
        {
            for (int k = 1; k < DoomerfallAmmoTiers.Tiers.Length; k++)
            {
                int tier = (from + k) % DoomerfallAmmoTiers.Tiers.Length;
                if (TierTotal(items, type, tier) > 0)
                    return tier;
            }
            return -1;
        }

        // Each gun loads its own tier. Once Doom reports the active gun ready, its recorded tier becomes its ammo type's
        // loaded tier; a gun with no record (or one for another ammo type) records the type's current tier. Until then
        // Doom may still hold the gun being put away, so nothing changes.
        void SyncGunTier()
        {
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            DoomerfallDoomItem gun = hotkeys != null ? hotkeys.ActiveGun : null;
            // Doom can report the new gun ready before its swap is confirmed, so the reports that count are those after
            // the swap request began.
            if (hotkeys != null && hotkeys.SwapCount != seenSwap)
            {
                seenSwap = hotkeys.SwapCount;
                swapSeq = readySeq;
            }
            // Mid-swap, Doom may already hold the new gun while the active gun is still the old one.
            if (hotkeys != null && hotkeys.SwapInFlight)
                return;
            if (gun != boundGun)
            {
                boundReady = boundGun == null && gun != null; // With no gun before there is nothing to wait for.
                boundGun = gun;
                boundSeq = swapSeq;
                gunType = -1;
            }
            if (!boundReady && readySeq > boundSeq)
                boundReady = true;
            if (gun == null || !boundReady || readyType < 0)
                return;
            gunType = readyType;
            int type, tier;
            if (!gun.TryGetAmmoTier(out type, out tier) || type != readyType || tier >= DoomerfallAmmoTiers.Tiers.Length)
            {
                gun.SetAmmoTier(readyType, loadedTier[readyType]);
                bridge.LogLine(string.Format("ammo: \"{0}\" now remembers {1}", gun.ItemName, DoomerfallAmmoTiers.Name(readyType, loadedTier[readyType])));
            }
            else if (tier != loadedTier[readyType])
                SetLoadedTier(readyType, tier);
        }

        // The change ammo key, and the automatic change when the loaded tier runs out with the gun's magazine empty. Either
        // asks Doom to empty the magazine first (AMMO_UNLOAD); ApplyUnloaded makes the change.
        void HandleChange(ItemCollection items)
        {
            if (unloadRequest != 0)
            {
                if (Time.unscaledTime > unloadDeadline)
                {
                    bridge.LogLine("ammo: change: Doom never answered unload " + unloadRequest);
                    unloadRequest = 0;
                }
                return;
            }
            if (changeWanted)
            {
                changeWanted = false;
                if (readyType < 0)
                {
                    Hud("This weapon has no ammo to change.");
                    return;
                }
                int next = NextTier(items, readyType, loadedTier[readyType]);
                if (next < 0)
                {
                    Hud(string.Format("You have no other {0}.", Types[readyType].lowerName));
                    return;
                }
                BeginUnload(readyType, next, false);
                return;
            }
            // Doom may have lowered an empty stock gun to fists already, so the bound gun's type is used then.
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            int auto = readyType >= 0 ? readyType : boundGun != null && hotkeys != null && hotkeys.ActiveGun == boundGun ? gunType : -1;
            if (auto < 0 || Time.unscaledTime < nextAuto)
                return;
            Track t = tracks[auto];
            if (t.report != 0 || t.pending.Count > 0 || t.synced != 0 || LoadedTotal(items, auto) != 0)
                return;
            int other = NextTier(items, auto, loadedTier[auto]);
            if (other < 0)
                return;
            nextAuto = Time.unscaledTime + AutoInterval;
            BeginUnload(auto, other, true);
        }

        void BeginUnload(int type, int to, bool automatic)
        {
            unloadRequest = nextUnload++;
            unloadType = type;
            unloadFrom = loadedTier[type];
            unloadTo = to;
            unloadAuto = automatic;
            unloadDeadline = Time.unscaledTime + UnloadTimeout;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_AMMO_UNLOAD;
            e.tic = (uint)Time.frameCount;
            e.doomItem.request = unloadRequest;
            e.doomItem.status = automatic ? 1u : 0u;
            byte[] name = System.Text.Encoding.UTF8.GetBytes(Types[type].doomClass);
            e.doomItem.SetCls(name, Math.Min(name.Length, 39));
            bridge.Send(ref e);
            if (!automatic) // The automatic one repeats while the magazine still holds rounds, so only its result is logged.
                bridge.LogLine(string.Format("ammo: change: {0} to {1}, unload {2}", DoomerfallAmmoTiers.Name(type, unloadFrom), DoomerfallAmmoTiers.Tiers[to].name, unloadRequest));
        }

        // Doom answered the unload: the magazine's rounds go back as the tier they were loaded as, then the new tier loads.
        // Runs after Doom's counts are mirrored and before Daggerfall's changes are sent, so the delta loop sends Doom the
        // new tier's rounds in place of the old ones.
        void ApplyUnloaded(ItemCollection items)
        {
            if (!unloadedArrived)
                return;
            unloadedArrived = false;
            uint request = unloadRequest;
            unloadRequest = 0;
            int type = unloadType;
            if (unloadedRounds == 0xFFFFFFFFu)
                return; // An automatic change waits until the magazine is empty too.
            if (unloadedRounds > 0 && unloadedRounds < 100000)
                items.AddItem(new DoomerfallAmmoItem(type, unloadFrom, (int)unloadedRounds));
            int to = TierTotal(items, type, unloadTo) > 0 ? unloadTo : NextTier(items, type, loadedTier[type]);
            if (to >= 0)
            {
                SetLoadedTier(type, to);
                DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
                DoomerfallDoomItem gun = hotkeys != null ? hotkeys.ActiveGun : null;
                if (gun != null && gun == boundGun && boundReady && gunType == type)
                    gun.SetAmmoTier(type, to);
                Hud(string.Format("{0} {1}.", unloadAuto ? "Out of ammo: loading" : "Loading", DoomerfallAmmoTiers.Name(type, to)));
            }
            bridge.LogLine(string.Format("ammo: change{0}: unload {1} gave back {2} rounds of {3}; the gun loads {4}; Daggerfall holds{5}",
                unloadAuto ? " (automatic)" : "", request, unloadedRounds, DoomerfallAmmoTiers.Name(type, unloadFrom),
                DoomerfallAmmoTiers.Name(type, loadedTier[type]), Totals()));
        }

        // Doom's HUD shows the loaded ammo and its tags; both clear when the ready weapon uses no reserve ammo.
        void PublishLoaded()
        {
            int tier = readyType >= 0 ? loadedTier[readyType] : -1;
            string key = readyType + ":" + tier;
            if (key == sentLoaded)
                return;
            sentLoaded = key;
            LoadedTags = readyType >= 0 ? DoomerfallAmmoTiers.Tags(readyType, tier) : new string[0];
            string tags = string.Join(",", LoadedTags);
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_AMMO_LOADED;
            e.tic = (uint)Time.frameCount;
            e.doomItem.request = tier >= 0 ? (uint)tier : 0xFFFFFFFFu;
            e.doomItem.status = readyType >= 0 ? (uint)readyType : 0u;
            byte[] name = System.Text.Encoding.UTF8.GetBytes(tags);
            e.doomItem.SetCls(name, Math.Min(name.Length, 39));
            bridge.Send(ref e);
            bridge.LogLine(string.Format("ammo: loaded ammo shown: {0}; tags: {1}", tier >= 0 ? DoomerfallAmmoTiers.Name(readyType, tier) : "none",
                tags.Length > 0 ? tags : "none"));
        }

        static void Hud(string text) { DaggerfallUI.AddHUDText(text); }

        // True for a stack Doom's counter of this type stands for: the type's loaded tier.
        internal static bool IsLoaded(DoomerfallAmmoItem item, int type)
        {
            return item.AmmoType == type && item.Tier == loadedTier[type];
        }

        // A new stack of the loaded ammo, for rounds Doom gained (plain Doom ammo, such as a backpack or a gun's own ammo).
        static DoomerfallAmmoItem NewLoaded(int type, int count)
        {
            return new DoomerfallAmmoItem(type, loadedTier[type], count);
        }

        internal static int LoadedTier(int type) { return loadedTier[type]; }

        // Changes the tier this type's guns load. The next Update sends Doom the difference in loaded rounds.
        internal void SetLoadedTier(int type, int tier)
        {
            if (type < 0 || type >= Types.Length || tier < 0 || tier >= DoomerfallAmmoTiers.Tiers.Length || loadedTier[type] == tier)
                return;
            loadedTier[type] = tier;
            bridge.LogLine(string.Format("ammo: {0} guns now load {1}", Types[type].doomClass, DoomerfallAmmoTiers.Tiers[tier].name));
            Reload();
        }

        // The material bonus of the ammo loaded in Doom's ready gun, as a fraction (0.5 is +50%). 0 for no ready gun.
        internal double LoadedMaterialBonus()
        {
            if (readyType < 0)
                return 0.0;
            if (TestBonus != null && readyType < TestBonus.Length)
                return TestBonus[readyType];
            return DoomerfallAmmoTiers.Tiers[loadedTier[readyType]].bonus;
        }

        // DFB_KIND_AMMO_TAKE: the player touched a tiered pickup in Doom. Its rounds become a stack in Daggerfall's
        // inventory. If that tier is loaded, Update sends Doom the rounds as a delta like any other inventory change.
        internal void OnTake(string cls, int tier, uint rounds)
        {
            int type = TypeOfClass(cls);
            if (type < 0 || tier < 0 || tier >= DoomerfallAmmoTiers.Tiers.Length || rounds == 0 || rounds > 100000)
            {
                bridge.LogLine(string.Format("ammo: ignored a pickup of {0} tier {1} x{2}", cls, tier, rounds));
                return;
            }
            takes.Add(new KeyValuePair<int, KeyValuePair<int, int>>(type, new KeyValuePair<int, int>(tier, (int)rounds)));
        }

        // DFB_KIND_AREA_LEVEL_REQUEST: Doom rolls ammo drop tiers with the area level of this map pixel. A pixel past one
        // million is inside a dungeon there.
        internal void OnAreaLevelRequest(uint key)
        {
            if (!levelRequests.Contains(key))
                levelRequests.Add(key);
        }

        void AnswerLevels()
        {
            if (levelRequests.Count == 0)
                return;
            int test = DoomerfallDrops.TestAreaLevel();
            if (test < 0 && !DoomerfallAreaLevels.IsFinished)
                return;
            foreach (uint key in levelRequests)
            {
                bool dungeon = key >= 1000000 && key < 2000000;
                int pixel = (int)(key % 1000000), x = pixel % 1000, y = pixel / 1000;
                int level = test;
                if (level < 0 && key == 2000000)
                    level = DoomerfallAreaLevels.ForCurrentDanger(); // Doom does not know the pixel yet: where Daggerfall's player is.
                else if (level < 0)
                {
                    level = 0;
                    DaggerfallWorkshop.Utility.ContentReader.MapSummary summary;
                    DFLocation location;
                    DoomerfallAreaLevels.Level l;
                    if (dungeon && DaggerfallUnity.Instance.ContentReader.HasLocation(x, y, out summary)
                        && DaggerfallUnity.Instance.ContentReader.GetLocation(summary.RegionIndex, summary.MapIndex, out location)
                        && DoomerfallAreaLevels.ForLocation(location, out l) && l.dungeon > 0)
                        level = l.dungeon;
                    else
                        level = DoomerfallAreaLevels.ForMapPixel(x, y);
                }
                level = Mathf.Clamp(level, 1, DoomerfallDrops.MaxAreaLevel);
                DfbEvent e = default(DfbEvent);
                e.kind = Dfb.KIND_AREA_LEVEL;
                e.tic = (uint)Time.frameCount;
                e.doomItem.request = key;
                e.doomItem.status = (uint)level;
                bridge.Send(ref e);
                bridge.LogLine(string.Format("ammo: area level at map pixel ({0}, {1}){2} is {3}", x, y, dungeon ? " in the dungeon" : "", level));
            }
            levelRequests.Clear();
        }

        void ApplyTakes(ItemCollection items)
        {
            if (takes.Count == 0)
                return;
            foreach (KeyValuePair<int, KeyValuePair<int, int>> take in takes)
            {
                int type = take.Key, tier = take.Value.Key, rounds = take.Value.Value;
                items.AddItem(new DoomerfallAmmoItem(type, tier, rounds));
                bridge.LogLine(string.Format("ammo: picked up {0} x{1}{2}", DoomerfallAmmoTiers.Name(type, tier), rounds,
                    tier == loadedTier[type] ? " (loaded tier, goes to Doom)" : ""));
            }
            takes.Clear();
            bridge.LogLine("ammo: after tiered pickups Daggerfall holds" + Totals());
            DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallInventoryWindow window =
                DaggerfallUI.UIManager.TopWindow as DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallInventoryWindow;
            if (window != null)
                window.Refresh(false);
        }

        internal static int LoadedTotal(ItemCollection items, int type)
        {
            int total = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null && IsLoaded(item, type))
                    total += item.stackCount;
            }
            return total;
        }

        // One DFB_KIND_AMMO report. Applied in Update, once Daggerfall is in a game.
        internal void OnReport(uint ack, uint count, string cls)
        {
            int type = TypeOfClass(cls);
            if (type < 0)
                return;
            tracks[type].report = (int)Math.Min(count, (uint)int.MaxValue);
            tracks[type].reportAck = ack;
        }

        internal bool Ready { get { return ready; } }

        // Both sides agree: every type has a report, no delta is in flight, and the inventory matches.
        internal bool Settled
        {
            get
            {
                if (!ready)
                    return false;
                PlayerEntity player = GameManager.Instance.PlayerEntity;
                for (int i = 0; i < tracks.Length; i++)
                    if (tracks[i].report < 0 || tracks[i].pending.Count > 0 || tracks[i].report != tracks[i].synced || LoadedTotal(player.Items, i) != tracks[i].synced)
                        return false;
                return !tellWanted;
            }
        }

        internal static int Total(ItemCollection items, int type)
        {
            int total = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null && item.AmmoType == type)
                    total += item.stackCount;
            }
            return total;
        }

        internal string Totals()
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null)
                return " (no player)";
            string text = "";
            for (int i = 0; i < Types.Length; i++)
                text += string.Format(" {0} {1};", Types[i].doomClass, LoadedTotal(player.Items, i)); // What Doom's counter mirrors.
            text += string.Format(" carried {0:F2} kg; stacks", player.CarriedWeight);
            for (int i = 0; i < player.Items.Count; i++)
            {
                DoomerfallAmmoItem item = player.Items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null)
                    text += string.Format(" [{0} x{1} {2} kg {3} gold each]", item.ItemName, item.stackCount, item.weightInKg, item.value);
            }
            return text;
        }

        // Adds (or removes, for a negative change) loaded rounds of one type in the player's inventory.
        internal static void Change(ItemCollection items, int type, int change)
        {
            if (change > 0)
            {
                items.AddItem(NewLoaded(type, change));
                return;
            }
            for (int i = items.Count - 1; i >= 0 && change < 0; i--)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item == null || !IsLoaded(item, type))
                    continue;
                int take = Math.Min(item.stackCount, -change);
                change += take;
                if (take >= item.stackCount)
                    items.RemoveItem(item);
                else
                    item.stackCount -= take;
            }
        }

        void Update()
        {
            AnswerLevels();
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null || !sync.InGame || sync.LoadRunning)
            {
                ready = false;
                return;
            }
            ItemCollection items = player.Items;
            if (!ready)
            {
                AddTemplates();
                // Whatever Daggerfall holds now is its side; the next report brings Doom's side.
                for (int i = 0; i < tracks.Length; i++)
                {
                    tracks[i].synced = LoadedTotal(items, i);
                    tracks[i].pending.Clear();
                }
                ready = true;
            }
            ApplyTakes(items);
            bool changed = false;
            for (int i = 0; i < tracks.Length; i++)
            {
                Track t = tracks[i];
                if (t.report >= 0)
                {
                    t.pending.RemoveAll(p => p.Key <= t.reportAck);
                    int believed = t.report;
                    foreach (KeyValuePair<uint, int> p in t.pending)
                        believed += p.Value;
                    believed = Math.Max(0, believed);
                    if (believed != t.synced)
                    {
                        // Doom picked up or spent ammo.
                        Change(items, i, believed - t.synced);
                        t.synced = believed;
                        changed = true;
                    }
                }
            }
            SyncGunTier();
            ApplyUnloaded(items);
            for (int i = 0; i < tracks.Length; i++)
            {
                Track t = tracks[i];
                int total = LoadedTotal(items, i);
                if (total != t.synced && t.report >= 0)
                {
                    // Daggerfall's side changed: a drop, a trade, a pile, a stack that could not go below zero, or a
                    // change of the loaded ammo.
                    SendDelta(t, i, total - t.synced, "sent to Doom");
                    t.synced = total;
                }
            }
            HandleChange(items);
            if (tellWanted)
                Tell(items);
            PublishLoaded();
            if (changed)
            {
                DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallInventoryWindow window =
                    DaggerfallUI.UIManager.TopWindow as DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallInventoryWindow;
                if (window != null)
                    window.Refresh(false);
                bridge.LogLine("ammo: Doom changed the count, Daggerfall holds" + Totals());
            }
        }

        // Doom's ready gun was equipped or raised, or its loaded ammo changed: Daggerfall tells Doom how many loaded rounds
        // of the gun's ammo type it holds, and the damage bonus follows the loaded ammo (DoomerfallDamageBonus reads
        // LoadedMaterialBonus every frame). Doom's counter is set to Daggerfall's count with a delta from what Doom is
        // believed to hold, so a round Doom spends meanwhile is still counted once. Waits for Doom's first count report.
        void Tell(ItemCollection items)
        {
            if (readyType == -2)
                return;
            double bonus = LoadedMaterialBonus();
            if (readyType < 0)
            {
                tellWanted = false;
                bridge.LogLine(string.Format("ammo: equip: the ready weapon uses no reserve ammo; ammo damage bonus {0:+0.##%;-0.##%;0%}", bonus));
                return;
            }
            Track t = tracks[readyType];
            if (t.report < 0)
                return;
            tellWanted = false;
            int believed = t.report;
            foreach (KeyValuePair<uint, int> p in t.pending)
                believed += p.Value;
            believed = Math.Max(0, believed);
            int loaded = LoadedTotal(items, readyType);
            if (loaded != believed)
                SendDelta(t, readyType, loaded - believed, "to load the gun");
            t.synced = loaded;
            bridge.LogLine(string.Format("ammo: equip: the ready gun loads {0}; Daggerfall holds {1}, Doom held {2}; ammo damage bonus {3:+0.##%;-0.##%;0%}",
                Types[readyType].doomClass, loaded, believed, bonus));
        }

        void SendDelta(Track t, int type, int delta, string why)
        {
            uint id = nextAdd++;
            t.pending.Add(new KeyValuePair<uint, int>(id, delta));
            Send(id, delta, Types[type].doomClass);
            bridge.LogLine(string.Format("ammo: add {0} {1} {2:+0;-0} {3}, Daggerfall holds {4}", id, Types[type].doomClass, delta, why, LoadedTotal(GameManager.Instance.PlayerEntity.Items, type)));
        }

        void Send(uint request, int delta, string cls)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_AMMO_ADD;
            e.tic = (uint)Time.frameCount;
            e.doomItem.request = request;
            e.doomItem.status = unchecked((uint)delta);
            byte[] name = System.Text.Encoding.UTF8.GetBytes(cls);
            e.doomItem.SetCls(name, Math.Min(name.Length, 39));
            bridge.Send(ref e);
        }
    }
}
