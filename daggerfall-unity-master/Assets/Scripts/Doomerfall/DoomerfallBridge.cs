// Doomerfall: Daggerfall Unity's side of the bridge. Does nothing unless the game is started with
// -dfbridge <session>; without it the native DLL is never loaded and no object is created.
// After startup the per-frame path uses preallocated blittable structs and allocates nothing.
// Only the two-second log line allocates.

using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using DaggerfallWorkshop.Game.Formulas;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // The structs, constants, and native imports are generated from bridge/doomerfall_bridge.h: see DoomerfallBridge.g.cs.

    public sealed class DoomerfallBridge : MonoBehaviour
    {
        const long PingIntervalNs = 50000000, LogIntervalNs = 2000000000, StaleNs = 1000000000;
        const int SampleCount = 1024;

        internal sealed class Samples
        {
            readonly long[] values = new long[SampleCount];
            readonly long[] sorted = new long[SampleCount];
            int count, next;

            public void Add(long v)
            {
                values[next] = v;
                next = (next + 1) % SampleCount;
                if (count < SampleCount) count++;
            }

            public string Summary()
            {
                if (count == 0) return "n=0";
                Array.Copy(values, sorted, count);
                Array.Sort(sorted, 0, count);
                string summary = string.Format("n={0} p50={1:F2}ms p99={2:F2}ms max={3:F2}ms", count,
                    sorted[count / 2] / 1e6, sorted[count * 99 / 100] / 1e6, sorted[count - 1] / 1e6);
                count = next = 0; // each line covers one window
                return summary;
            }
        }

        static string pendingSession, pendingLog;

        // True in a working bridge session. Doom's death screen then replaces Daggerfall's automatic restart.
        public static bool SessionActive { get; private set; }

        IntPtr session;
        StreamWriter log;
        DfbEvent ev;
        DfbDfState own;
        DfbUzState peer;
        DfbStats stats;
        DoomerfallPositionSync sync;
        internal DoomerfallPositionSync PositionSync { get { return sync; } }
        DoomerfallUi ui;
        DoomerfallHp hp;
        DoomerfallDamageBonus damageBonus;
        DoomerfallFallState fallState;
        DoomerfallSave save;
        DoomerfallItems items;
        DoomerfallDoomItems doomItems;
        DoomerfallHotkeys hotkeys;
        DoomerfallAmmo ammo;
        DoomerfallNewGame newGame;
        DoomerfallPlainLoad plainLoad;
        DoomerfallMonsters monsters;
        DoomerfallLocations locations;
        DoomerfallNpcs npcs;
        DoomerfallInfo info;
        DoomerfallDoors doors;
        DoomerfallSheet sheet;
        DoomerfallFaces faces;
        internal DoomerfallSheet Sheet { get { return sheet; } }
        DoomerfallTownspeople townspeople;
        DoomerfallGuards guards;
        DoomerfallLoadingPause loadingPause;
        bool textFrame;
        uint ownSize, peerSize, nextPing = 1;
        ulong pingsAnswered, pongsReceived, unknownKinds;
        long nextPingNs, nextLogNs;
        bool peerSeen, peerStale, peerStateChangedLog;
        long measuredFrames, allocatingFrames, allocatedBytes;
        readonly Samples rtt = new Samples(), oneWayOut = new Samples(), oneWayIn = new Samples(), stateAge = new Samples();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; i++)
            {
                if (args[i] == "-dfbridge") pendingSession = args[i + 1];
                else if (args[i] == "-dfbridgelog") pendingLog = args[i + 1];
            }
            if (pendingSession == null) return;

            var host = new GameObject("DoomerfallBridge");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallBridge>();
        }

        void Awake()
        {
            if (pendingLog != null)
                log = new StreamWriter(pendingLog, true, new UTF8Encoding(false)) { AutoFlush = true };

            try
            {
                string mismatch = DefinitionMismatch();
                if (mismatch != null)
                {
                    Fail("bridge DLL does not match this build: " + mismatch);
                    return;
                }
                int rc = DfbNative.dfb_attach(pendingSession, Dfb.SIDE_DF, out session);
                if (rc != 0)
                {
                    session = IntPtr.Zero;
                    Fail("could not attach to session " + pendingSession + " (error " + rc + ")");
                    return;
                }
            }
            catch (DllNotFoundException e)
            {
                Fail("bridge DLL not found: " + e.Message);
                return;
            }
            catch (EntryPointNotFoundException e)
            {
                Fail("bridge DLL does not match this build (it is older): " + e.Message);
                return;
            }

            SessionActive = true;
            WorldLevel.CurrentPlaceProvider = DoomerfallDrops.CurrentWorldLevel;   // the world scales to area level, never the player
            WorldLevel.BuildingProvider = building => DoomerfallShopShelves.LayoutLevel(building, Log);   // interior loot piles roll at the building's level
            WorldLevel.DangerProvider = DoomerfallDrops.CurrentDangerLevel;   // enemies indoors keep the place's danger, not the building's wealth
            WorldLevel.DungeonProvider = DoomerfallDrops.DungeonWorldLevel;
            FormulaHelper.DoomerfallMaterialRoll = DoomerfallDrops.RollMaterial;   // approved material odds for all loot
            WorldLevel.ShopProvider = building => DoomerfallShopShelves.Level(building, Log);   // shelves roll at the shop's level
            ownSize = (uint)Marshal.SizeOf(typeof(DfbDfState));
            peerSize = (uint)Marshal.SizeOf(typeof(DfbUzState));
            Log(string.Format("attached to session {0}, protocol {1}, layout {2:x16}", pendingSession,
                DfbNative.dfb_protocol_version(), DfbNative.dfb_layout_hash()));

            ev = new DfbEvent { kind = Dfb.KIND_HELLO };
            DfbNative.dfb_send(session, ref ev);
            SendText("hello from Daggerfall Unity");

            sync = gameObject.AddComponent<DoomerfallPositionSync>();
            sync.Init(this, Environment.GetCommandLineArgs());
            hp = new DoomerfallHp(this, sync, Environment.GetCommandLineArgs());
            gameObject.AddComponent<DoomerfallEndurance>().Init(this, sync);  // max HP from Endurance and level
            DoomerfallHpFormulaTest.Attach(this, sync); // test only: -dfhpformulatest
            DoomerfallAttributesTest.Attach(this, sync); // test only: -dfattrtest
            sheet = new DoomerfallSheet(this, sync, Environment.GetCommandLineArgs());
            DoomerfallAgilityTest.Attach(this, sync); // test only: -dfagilitytest
            DoomerfallWillpowerTest.Attach(this, sync); // test only: -dfwillpowertest
            DoomerfallLuckTest.Attach(this, sync); // test only: -dflucktest
            faces = new DoomerfallFaces(this);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dffacetest") >= 0)
                gameObject.AddComponent<DoomerfallFaceTest>().Init(this, sync); // Test only
            damageBonus = new DoomerfallDamageBonus(this, sync);
            fallState = new DoomerfallFallState(this, sync);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dffalltest") >= 0)
                gameObject.AddComponent<DoomerfallFallStateTest>().Init(this); // Test only
            DoomerfallDamageBonusTest.Apply(this, damageBonus, Environment.GetCommandLineArgs()); // Test only, does nothing without -dfdamagetest
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfsheettest") >= 0)
                gameObject.AddComponent<DoomerfallSheetTest>().Init(this, sync);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfclasscardtest") >= 0)
                gameObject.AddComponent<DoomerfallClassCardTest>().Init(this, sync); // Test only
            DoomerfallLookTest.Apply(this, sync); // Test only, does nothing without -dflooktest
            DoomerfallWorldLookTest.Apply(this, sync); // Test only, does nothing without -dfworldlooktest
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfloottest") >= 0)
                gameObject.AddComponent<DoomerfallLootTest>().Init(this);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dftalktest") >= 0 || Array.IndexOf(Environment.GetCommandLineArgs(), "-dftalkrefuse") >= 0)
                gameObject.AddComponent<DoomerfallTalkTest>().Init(this);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshoptest") >= 0)
                gameObject.AddComponent<DoomerfallShopTest>().Init(this);
            ui =gameObject.AddComponent<DoomerfallUi>();
            ui.Init(this);
            DoomerfallRest.Begin(this);
            save = gameObject.AddComponent<DoomerfallSave>();
            save.Init(this, sync, hp, Environment.GetCommandLineArgs());
            items = gameObject.AddComponent<DoomerfallItems>();
            items.Init(this, sync);
            save.Items = items;
            ui.Items = items;
            DoomerfallDoomItems.Register();
            doomItems = gameObject.AddComponent<DoomerfallDoomItems>();
            doomItems.Init(this, sync);
            hotkeys = gameObject.AddComponent<DoomerfallHotkeys>();
            hotkeys.Init(this, sync);
            DoomerfallAmmo.Register();
            DoomerfallLockpick.Register();
            DoomerfallShields.Register(this); // no shields for now
            ammo =gameObject.AddComponent<DoomerfallAmmo>();
            ammo.Init(this, sync);
            damageBonus.Ammo = ammo;
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfequiptest") >= 0)
                gameObject.AddComponent<DoomerfallEquipAmmoTest>().Init(this, ammo);
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfammotest") >= 0)
                gameObject.AddComponent<DoomerfallAmmoTest>().Init(this, ammo);
            DoomerfallShopStockTest.Attach(this); // test only: -dfshoptest
            DoomerfallShieldsTest.Attach(this, sync); // test only: -dfshieldtest
            DoomerfallShopAmmoTest.Attach(this, ammo); // test only: -dfshopammotest
            DoomerfallWorldLevelTest.Attach(this); // test only: -dfworldleveltest N
            DoomerfallChangeAmmoTest.Attach(this, ammo); // test only: -dfchangeammotest
            DoomerfallMaterialDamageTest.Attach(this, ammo); // test only: -dfmaterialtest
            DoomerfallAmmoPileTest.Attach(this, ammo); // test only: -dfammopiletest
            DoomerfallStartingGunTest.Attach(this); // test only: -dfstartguntest <skills>
            newGame = gameObject.AddComponent<DoomerfallNewGame>();
            newGame.Init(this, sync, Environment.GetCommandLineArgs());
            newGame.Items = items;
            newGame.Hotkeys = hotkeys;
            newGame.Ammo = ammo;
            ui.NewGame = newGame;
            monsters = gameObject.AddComponent<DoomerfallMonsters>();
            monsters.Init(this, sync);
            save.Monsters = monsters;
            newGame.Monsters = monsters;
            locations = gameObject.AddComponent<DoomerfallLocations>();
            locations.Init(this, monsters);
            gameObject.AddComponent<DoomerfallPiles>().Init(this, sync, locations);
            DoomerfallPilesTest.Attach(this, sync, locations); // test only: -dfpilestest
            DoomerfallGunDropTest.Attach(this, sync); // test only: -dfgundroptest
            save.Locations = locations;
            newGame.Locations = locations;
            npcs = gameObject.AddComponent<DoomerfallNpcs>();
            npcs.Init(this, sync);
            info = gameObject.AddComponent<DoomerfallInfo>();
            info.Init(this, sync);
            DoomerfallHudMessages.Install(this); // Daggerfall's HUD messages go to Doom's HUD
            DoomerfallHudMessagesTest.Attach(this, sync); // test only: -dfhudtest
            doors = gameObject.AddComponent<DoomerfallDoors>();
            doors.Init(this, sync, info);
            save.Doors = doors;
            newGame.Doors = doors;
            DoomerfallLockTest.Attach(this); // test only: -dflocktest
            DoomerfallTalk talk = gameObject.AddComponent<DoomerfallTalk>();
            talk.Init(this, sync, info);
            ui.Talk = talk;
            townspeople = gameObject.AddComponent<DoomerfallTownspeople>();
            townspeople.Init(this, sync);
            talk.Townspeople = townspeople;
            ui.Townspeople = townspeople;
            ui.Npcs = npcs;
            info.Items = items;
            info.Townspeople = townspeople;
            save.Townspeople = townspeople;
            newGame.Townspeople = townspeople;
            plainLoad = gameObject.AddComponent<DoomerfallPlainLoad>();
            plainLoad.Init(this, sync, Environment.GetCommandLineArgs());
            plainLoad.Items = items;
            plainLoad.Monsters = monsters;
            plainLoad.Townspeople = townspeople;
            plainLoad.Doors = doors;
            plainLoad.Hotkeys = hotkeys;
            plainLoad.Ammo = ammo;
            ui.PlainLoad = plainLoad;
            guards = gameObject.AddComponent<DoomerfallGuards>();
            guards.Init(this, sync);
            gameObject.AddComponent<DoomerfallCityLights>().Init(this);
            gameObject.AddComponent<DoomerfallWorldLook>().Init(this);
            gameObject.AddComponent<DoomerfallPerks>().Init(this, sync);
            DoomerfallPerksTest.Attach(this, sync); // test only: -dfperktest <skill>
            gameObject.AddComponent<DoomerfallHiddenWorld>().Init(this, sync, Environment.GetCommandLineArgs());
            DoomerfallWorldCost.Attach(this, sync, Environment.GetCommandLineArgs()); // measurement only: -dfworldcost
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfguardtest") >= 0)
                gameObject.AddComponent<DoomerfallGuardsTest>().Init(this, sync);
        }

        // The schema hash covers every constant, struct field, and function in the header.
        static string DefinitionMismatch()
        {
            uint version = DfbNative.dfb_protocol_version();
            if (version != Dfb.PROTOCOL_VERSION)
                return "protocol " + version + ", expected " + Dfb.PROTOCOL_VERSION;
            ulong schema = DfbNative.dfb_schema_hash();
            if (schema != Dfb.SchemaHash)
                return string.Format("schema {0:x16}, expected {1:x16}", schema, Dfb.SchemaHash);
            for (int i = 0; i < Dfb.StructTypes.Length; i++)
                if (Marshal.SizeOf(Dfb.StructTypes[i]) != Dfb.StructSizes[i])
                    return Dfb.StructTypes[i].Name + " has the wrong managed size";
            if (DfbNative.dfb_struct_size(0) != Marshal.SizeOf(typeof(DfbEvent)) ||
                DfbNative.dfb_struct_size(1) != Marshal.SizeOf(typeof(DfbDfState)) ||
                DfbNative.dfb_struct_size(2) != Marshal.SizeOf(typeof(DfbUzState)) ||
                DfbNative.dfb_struct_size(3) != Marshal.SizeOf(typeof(DfbStats)))
                return "struct sizes differ";
            return null;
        }

        // The newest Doom state, for the save handshake. Doom published it before sending the request.
        internal void ReadPeerState(out DfbUzState state)
        {
            DfbNative.dfb_read_state(session, ref peer, peerSize);
            state = peer;
        }

        // Publishes now, so Doom sees Daggerfall's restored HP before it reads the load's answer.
        internal void PublishNow()
        {
            own.dfPhase = sync.Phase;
            own.dfHeartbeat++;
            hp.Fill(ref own);
            damageBonus.Fill(ref own);
            fallState.Fill(ref own);
            sheet.Publish();
            faces.Publish();
            DfbNative.dfb_publish_state(session, ref own, ownSize);
        }

        internal IntPtr Session { get { return session; } }
        internal void Send(ref DfbEvent e) { DfbNative.dfb_send(session, ref e); }
        internal bool LogEnabled { get { return log != null; } }
        internal void LogLine(string line) { Log(line); }

        void Fail(string message)
        {
            Log("error: " + message);
            Debug.LogError("[bridge] " + message);
            enabled = false;
        }

        void Log(string line)
        {
            if (log == null) return;
            // The clock comes from the DLL, so a failed attach must still be able to log without it.
            log.WriteLine((session != IntPtr.Zero ? (DfbNative.dfb_now_ns() / 1e9).ToString("F3") : "-") + " " + line);
        }

        internal void SendText(string text)
        {
            byte[] bytes = new byte[48];
            Encoding.UTF8.GetBytes(text, 0, Math.Min(text.Length, 48), bytes, 0);
            ev = new DfbEvent { kind = Dfb.KIND_TEXT };
            ev.SetPayload(bytes, bytes.Length);
            DfbNative.dfb_send(session, ref ev);
        }

        // The payload from byte `start` up to its terminator or end.
        string ReadText(int start = 0)
        {
            byte[] bytes = new byte[48];
            ev.CopyPayload(bytes);
            int length = Array.IndexOf(bytes, (byte)0, start);
            return Encoding.UTF8.GetString(bytes, start, (length < 0 ? 48 : length) - start);
        }

        void Update()
        {
            if (session == IntPtr.Zero) return;
            DoomerfallAreaLevels.Warm(); // ranks every place once, on a worker thread

            long memoryBefore = GC.GetTotalMemory(false);
            int collectionsBefore = GC.CollectionCount(0);

            // DoomerfallUi drained the event ring earlier this frame, before InputManager polled.
            FinishFrame(memoryBefore, collectionsBefore);
        }

        // Runs first in the frame, so input from Doom is in place before anything reads it.
        internal void DrainEvents()
        {
            if (session == IntPtr.Zero) return;
            textFrame = false;
            while (DfbNative.dfb_receive(session, ref ev) == Dfb.GOT)
            {
                long received = DfbNative.dfb_now_ns();
                if (ev.kind == Dfb.KIND_TEXT || ev.kind == Dfb.KIND_HELLO) textFrame = true;
                switch (ev.kind)
                {
                    case Dfb.KIND_PING:
                        ev.ping.replierNs = received;
                        ev.kind = Dfb.KIND_PONG;
                        ev.tic = (uint)Time.frameCount;
                        DfbNative.dfb_send(session, ref ev);
                        pingsAnswered++;
                        break;
                    case Dfb.KIND_PONG:
                        long sent = ev.ping.sentNs, replied = ev.ping.replierNs;
                        rtt.Add(received - sent);
                        oneWayOut.Add(replied - sent);
                        oneWayIn.Add(received - replied);
                        pongsReceived++;
                        break;
                    case Dfb.KIND_TEXT:
                    {
                        string text = ReadText();
                        Log("message from UZDoom: \"" + text + "\" (seq " + ev.seq + ")");
                        hp.OnText(text);
                        break;
                    }
                    case Dfb.KIND_HP:
                        hp.OnEvent(ev.hpEvent.eventNo, ev.hpEvent.type, ev.hpEvent.amount);
                        break;
                    case Dfb.KIND_SAVE_REQUEST:
                        save.OnRequest(ev.saveRequest.txn, ev.saveRequest.hpSentThrough);
                        break;
                    case Dfb.KIND_SAVE_DONE:
                        save.OnDone(ev.saveDone.txn, ev.saveDone.committed != 0);
                        break;
                    case Dfb.KIND_LOAD_REQUEST:
                        save.OnLoadRequest(ev.loadRequest.txn, ev.loadRequest.hp, ev.loadRequest.hpMax, ev.loadRequest.worldX, ev.loadRequest.worldZ);
                        break;
                    case Dfb.KIND_LOAD_DONE: // committed means Doom restored its half
                        save.OnLoadDone(ev.saveDone.txn, ev.saveDone.committed != 0);
                        break;
                    case Dfb.KIND_HOLD:
                        save.OnHold(ev.payload0 != 0);
                        break;
                    case Dfb.KIND_NEWGAME_ARRIVED:
                        if (!plainLoad.OnArrived(ev.payload0 != 0))
                            newGame.OnArrived(ev.payload0 != 0);
                        break;
                    case Dfb.KIND_STARTER:
                        plainLoad.OnStarter(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        DoomerfallStartingGun.OnStarter(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_HELLO:
                        Log("hello from UZDoom (seq " + ev.seq + ")");
                        break;
                    case Dfb.KIND_AREA:
                        sync.OnAreaEvent(ev.area.worldContext, ev.area.mapPixelX, ev.area.mapPixelY, ev.area.sentNs);
                        break;
                    case Dfb.KIND_TRANSITION:
                        sync.OnTransitionEvent(ev.transition.action, ev.transition.seq, ev.transition.doorX, ev.transition.doorZ, ev.transition.target);
                        break;
                    case Dfb.KIND_UI_OPEN:
                        string resized = DoomerfallWindow.MatchDoom(ev.uiCommand.screenWidth, ev.uiCommand.screenHeight);
                        if (resized != null)
                            Log(resized);
                        ui.OnOpen(ev.uiCommand.uiId, ev.uiCommand.context);
                        break;
                    case Dfb.KIND_UI_CLOSE:
                        ui.OnClose(ev.uiCommand.uiId);
                        break;
                    case Dfb.KIND_UI_INPUT:
                        DoomerfallInput.Enqueue(ev.uiInput.type, ev.uiInput.a, ev.uiInput.b, ev.uiInput.sentNs);
                        break;
                    case Dfb.KIND_ITEM_TAKE:
                        items.OnTake(ev.itemTake.request, ev.itemTake.id, ev.itemTake.mode);
                        break;
                    case Dfb.KIND_MONSTER_DEATH:
                        monsters.OnDeath(ev.monsterDeath.id, ev.monsterDeath.target, ev.monsterDeath.x, ev.monsterDeath.y, ev.monsterDeath.z);
                        break;
                    case Dfb.KIND_MONSTERS_REQUEST:
                        monsters.OnRequest();
                        break;
                    case Dfb.KIND_PLACE_BEGIN:
                    case Dfb.KIND_PLACE_NAME:
                    case Dfb.KIND_PLACE_PLAN:
                    case Dfb.KIND_PLACE_FACT:
                    case Dfb.KIND_PLACE_END:
                    case Dfb.KIND_PLACE_REQUEST:
                        locations.OnEvent(ref ev);
                        break;
                    case Dfb.KIND_NPCS_REQUEST:
                        npcs.OnRequest();
                        break;
                    case Dfb.KIND_TOWNSPERSON_DEATH:
                        townspeople.OnDeath(ev.townspersonDeath.id, ev.townspersonDeath.worldX, ev.townspersonDeath.worldZ);
                        break;
                    case Dfb.KIND_GUARD_DEATH:
                        guards.OnDeath(ev.guardDeath.id);
                        break;
                    case Dfb.KIND_TOWNSFOLK_REQUEST:
                        townspeople.OnRequest();
                        break;
                    case Dfb.KIND_ITEMS_REQUEST:
                        items.OnRequest();
                        break;
                    case Dfb.KIND_INFO_NAME:
                        info.OnName(ev.infoText.request, ReadText(8));
                        break;
                    case Dfb.KIND_LOOK:
                        info.OnLook(ev.infoRequest.request, ev.infoRequest.target, ev.infoRequest.id, ev.infoRequest.worldX, ev.infoRequest.worldZ);
                        break;
                    case Dfb.KIND_INFO:
                        info.OnRequest(ev.infoRequest.request, ev.infoRequest.target, ev.infoRequest.id, ev.infoRequest.worldX, ev.infoRequest.worldZ);
                        break;
                    case Dfb.KIND_DOOM_ITEM_GUN_STATE:
                        doomItems.OnTakeState(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_DOOM_ITEM_ID:
                        doomItems.OnTakeId(ev.itemTake.request, ev.itemTake.id);
                        break;
                    case Dfb.KIND_DOOM_ITEM_TAKE:
                        doomItems.OnTake(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_HOTKEY:
                    case Dfb.KIND_GUN_STATE:
                    case Dfb.KIND_GUN_STASHED:
                    case Dfb.KIND_GUN_KEPT:
                    case Dfb.KIND_GUN_EQUIPPED:
                        hotkeys.OnEvent(ev.kind, ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_DOOM_ITEM_USED:
                        doomItems.OnUsed(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_DOOM_ITEM_ART:
                        doomItems.OnArt(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_AMMO:
                        ammo.OnReport(ev.doomItem.request, ev.doomItem.status, DoomerfallDoomItems.ClassOf(ev.doomItem));
                        break;
                    case Dfb.KIND_AMMO_READY:
                        ammo.OnReady(DoomerfallDoomItems.ClassOf(ev.doomItem), ev.doomItem.status == 1);
                        break;
                    case Dfb.KIND_AMMO_TAKE:
                        ammo.OnTake(DoomerfallDoomItems.ClassOf(ev.doomItem), (int)ev.doomItem.request, ev.doomItem.status);
                        break;
                    case Dfb.KIND_AMMO_CHANGE:
                        ammo.OnChangeKey();
                        break;
                    case Dfb.KIND_AMMO_UNLOADED:
                        ammo.OnUnloaded(ev.doomItem.request, ev.doomItem.status);
                        break;
                    case Dfb.KIND_AREA_LEVEL_REQUEST:
                        ammo.OnAreaLevelRequest(ev.doomItem.request);
                        break;
                    case Dfb.KIND_DOOR_USE:
                        doors.OnUse(ev.door.id, ev.door.state);
                        break;
                    case Dfb.KIND_LOCKPICK:
                        doors.OnLockpick(ev.door.id, ev.door.state);
                        break;
                    case Dfb.KIND_CLIMB_USES:
                        DoomerfallClimb.OnUses(this, ev.climbUses.uses);
                        break;
                    case Dfb.KIND_NPC_USE:
                        ui.Talk.OnUse(ev.npcUse.request, ev.npcUse.id, ev.npcUse.mode, ev.npcUse.distance);
                        break;
                    default:
                        unknownKinds++; // contract rule 7: skip, never fatal
                        break;
                }
            }
        }

        void FinishFrame(long memoryBefore, int collectionsBefore)
        {
            if (DfbNative.dfb_read_state(session, ref peer, peerSize) == Dfb.GOT)
                stateAge.Add(DfbNative.dfb_now_ns() - peer.publishedNs);

            sync.Tick(ref peer);
            own.dfPhase = sync.Phase;
            own.dfHeartbeat++;
            own.dfFrame = (uint)Time.frameCount;
            own.demoValue = (uint)Time.frameCount;
            hp.Fill(ref own);
            damageBonus.Fill(ref own);
            fallState.Fill(ref own);
            sheet.Publish();
            faces.Publish();
            DfbNative.dfb_publish_state(session, ref own, ownSize);

            long now = DfbNative.dfb_now_ns();
            long age = DfbNative.dfb_peer_state_age_ns(session);
            bool alive = age >= 0 && age < StaleNs;
            if (alive && !peerSeen)
            {
                peerSeen = true;
                Log("UZDoom is live");
            }
            if (peerSeen && alive == peerStale)
            {
                peerStale = !alive;
                Log(alive ? "UZDoom heartbeat resumed" : "UZDoom heartbeat stale (logged only, gameplay unchanged)");
            }
            if (loadingPause == null)
                loadingPause = new DoomerfallLoadingPause(this);
            // Doom does not publish while a hold blocks its main thread (a big dungeon spawn), so a LOADING state stays held
            // well past the 1 s heartbeat limit; only a dead Doom (no state for 60 s) releases it without a fresh phase.
            loadingPause.Tick(age >= 0 && age < 60000000000L && peer.uzPhase == Dfb.UZ_PHASE_LOADING);
            DoomerfallLoadingPauseTest.Tick(this, loadingPause.Held);

            if (alive && now >= nextPingNs)
            {
                nextPingNs = now + PingIntervalNs;
                ev = default(DfbEvent);
                ev.kind = Dfb.KIND_PING;
                ev.tic = (uint)Time.frameCount;
                ev.ping.id = nextPing++;
                ev.ping.sentNs = DfbNative.dfb_now_ns();
                DfbNative.dfb_send(session, ref ev);
            }
            DfbNative.dfb_flush(session);

            // Measures the pump itself. Frames that logged text or saw a GC are not comparable.
            long memoryDelta = GC.GetTotalMemory(false) - memoryBefore;
            if (!textFrame && !peerStateChangedLog && GC.CollectionCount(0) == collectionsBefore)
            {
                measuredFrames++;
                if (memoryDelta > 0) { allocatingFrames++; allocatedBytes += memoryDelta; }
            }
            peerStateChangedLog = false;

            if (now >= nextLogNs)
            {
                nextLogNs = now + LogIntervalNs;
                peerStateChangedLog = true; // the log line below allocates; skip the next measurement too
                DfbNative.dfb_get_stats(session, ref stats);
                Log(string.Format("frame={0} heartbeat={1} uz_tic={2} uz_phase={3} uz_value={4} answered={5} pongs={6} gaps={7} unknown={8} outbox={9} pump_frames={10} pump_alloc_frames={11} pump_alloc_bytes={12}",
                    Time.frameCount, own.dfHeartbeat, peer.uzTic, peer.uzPhase, peer.demoValue, pingsAnswered, pongsReceived,
                    stats.seqGaps, unknownKinds, stats.outboxCount, measuredFrames, allocatingFrames, allocatedBytes));
                Log("latency rtt " + rtt.Summary() + " | df->uz " + oneWayOut.Summary() + " | uz->df " + oneWayIn.Summary() +
                    " | uz state age " + stateAge.Summary());
                sync.LogStatus();
            }
        }

        void OnDestroy()
        {
            SessionActive = false;
            WorldLevel.CurrentPlaceProvider = null;
            WorldLevel.BuildingProvider = null;
            WorldLevel.DangerProvider = null;
            WorldLevel.DungeonProvider = null;
            FormulaHelper.DoomerfallMaterialRoll = null;
            DoomerfallRest.End();
            WorldLevel.ShopProvider = null;
            if (sheet != null) sheet.Dispose();
            if (session != IntPtr.Zero) DfbNative.dfb_close(session);
            session = IntPtr.Zero;
            if (log != null) log.Dispose();
            log = null;
        }
    }
}
