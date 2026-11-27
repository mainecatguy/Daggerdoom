// Doomerfall: shows real Daggerfall windows inside the Doom window.
//
// While a menu is open, Daggerfall draws its normal UI into a private render texture, reads it back
// without stalling the GPU, and publishes it to the bridge's shared surface. Doom forwards its mouse
// and keyboard, which DoomerfallInput feeds to Daggerfall's input layer.
//
// Runs before every other script, so injected input is in place when InputManager polls it.
// Only exists in a bridge session.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Utility;
using UnityEngine;
using UnityEngine.Rendering;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    /// <summary>Input forwarded from Doom. Inactive unless a Daggerfall menu is open in Doom.</summary>
    public static class DoomerfallInput
    {
        const int KeyCount = 512;
        const float WheelNotch = 0.1f; // One notch of Unity's "Mouse ScrollWheel" axis.

        struct Item
        {
            public uint type;
            public int a, b;
            public long sentNs;
        }

        static readonly bool[] held = new bool[KeyCount], down = new bool[KeyCount], up = new bool[KeyCount], changed = new bool[KeyCount];
        static readonly Queue<Item> queue = new Queue<Item>();
        static int heldCount;

        public static bool Active { get; private set; }
        public static Vector2 SurfaceMouse { get; private set; }
        public static float Scroll { get; private set; }
        public static char PendingChar { get; private set; }
        public static long LastInputNs { get; private set; }
        public static bool AnyHeld { get { return heldCount > 0; } }

        public static void Begin()
        {
            Clear();
            Active = true;
        }

        public static void End()
        {
            Active = false;
            Clear();
        }

        static void Clear()
        {
            Array.Clear(held, 0, KeyCount);
            Array.Clear(down, 0, KeyCount);
            Array.Clear(up, 0, KeyCount);
            queue.Clear();
            heldCount = 0;
            Scroll = 0;
            PendingChar = (char)0;
            LastInputNs = 0;
        }

        internal static void Enqueue(uint type, int a, int b, long sentNs)
        {
            if (Active)
                queue.Enqueue(new Item { type = type, a = a, b = b, sentNs = sentNs });
        }

        // A press and release in one Doom frame must both be seen, so each key changes at most once per frame.
        internal static void Step()
        {
            if (!Active)
                return;
            Array.Clear(down, 0, KeyCount);
            Array.Clear(up, 0, KeyCount);
            Array.Clear(changed, 0, KeyCount);
            Scroll = 0;
            PendingChar = (char)0;

            while (queue.Count > 0)
            {
                Item item = queue.Peek();
                switch (item.type)
                {
                    case Dfb.UI_INPUT_MOVE:
                        SurfaceMouse = new Vector2(item.a, item.b);
                        break;
                    case Dfb.UI_INPUT_WHEEL:
                        Scroll += item.a * WheelNotch;
                        break;
                    case Dfb.UI_INPUT_CHAR:
                        if (PendingChar != 0)
                            return;
                        PendingChar = (char)item.a;
                        break;
                    case Dfb.UI_INPUT_RELEASE_ALL:
                        for (int i = 0; i < KeyCount; i++)
                        {
                            if (held[i])
                                up[i] = true;
                            held[i] = false;
                        }
                        heldCount = 0;
                        break;
                    case Dfb.UI_INPUT_BUTTON_DOWN:
                    case Dfb.UI_INPUT_BUTTON_UP:
                        if (!SetKey((int)KeyCode.Mouse0 + item.a, item.type == Dfb.UI_INPUT_BUTTON_DOWN))
                            return;
                        break;
                    case Dfb.UI_INPUT_KEY_DOWN:
                    case Dfb.UI_INPUT_KEY_UP:
                        KeyCode key = FromVirtualKey(item.a);
                        if (key != KeyCode.None && !SetKey((int)key, item.type == Dfb.UI_INPUT_KEY_DOWN))
                            return;
                        break;
                }
                LastInputNs = item.sentNs;
                queue.Dequeue();
            }
        }

        static bool SetKey(int key, bool pressed)
        {
            if (key < 0 || key >= KeyCount || held[key] == pressed)
                return true;
            if (changed[key])
                return false;
            changed[key] = true;
            held[key] = pressed;
            heldCount += pressed ? 1 : -1;
            if (pressed)
                down[key] = true;
            else
                up[key] = true;
            return true;
        }

        static bool InRange(KeyCode k) { return (int)k >= 0 && (int)k < KeyCount; }

        public static bool GetKey(KeyCode k) { return InRange(k) && held[(int)k]; }
        public static bool GetKeyDown(KeyCode k) { return InRange(k) && down[(int)k]; }
        public static bool GetKeyUp(KeyCode k) { return InRange(k) && up[(int)k]; }

        /// <summary>The held state from Doom while a menu is open, otherwise Unity's.</summary>
        public static bool Poll(KeyCode k) { return Active ? GetKey(k) : UnityEngine.Input.GetKey(k); }
        public static bool PollDown(KeyCode k) { return Active ? GetKeyDown(k) : UnityEngine.Input.GetKeyDown(k); }
        public static bool PollUp(KeyCode k) { return Active ? GetKeyUp(k) : UnityEngine.Input.GetKeyUp(k); }

        static KeyCode FromVirtualKey(int vk)
        {
            if (vk >= 0x41 && vk <= 0x5A) return KeyCode.A + (vk - 0x41);
            if (vk >= 0x30 && vk <= 0x39) return KeyCode.Alpha0 + (vk - 0x30);
            if (vk >= 0x60 && vk <= 0x69) return KeyCode.Keypad0 + (vk - 0x60);
            if (vk >= 0x70 && vk <= 0x7E) return KeyCode.F1 + (vk - 0x70);
            switch (vk)
            {
                case 0x08: return KeyCode.Backspace;
                case 0x09: return KeyCode.Tab;
                case 0x0D: return KeyCode.Return;
                case 0x1B: return KeyCode.Escape;
                case 0x20: return KeyCode.Space;
                case 0x21: return KeyCode.PageUp;
                case 0x22: return KeyCode.PageDown;
                case 0x23: return KeyCode.End;
                case 0x24: return KeyCode.Home;
                case 0x25: return KeyCode.LeftArrow;
                case 0x26: return KeyCode.UpArrow;
                case 0x27: return KeyCode.RightArrow;
                case 0x28: return KeyCode.DownArrow;
                case 0x2D: return KeyCode.Insert;
                case 0x2E: return KeyCode.Delete;
                case 0x6A: return KeyCode.KeypadMultiply;
                case 0x6B: return KeyCode.KeypadPlus;
                case 0x6D: return KeyCode.KeypadMinus;
                case 0x6E: return KeyCode.KeypadPeriod;
                case 0x6F: return KeyCode.KeypadDivide;
                case 0xA0: return KeyCode.LeftShift;
                case 0xA1: return KeyCode.RightShift;
                case 0xA2: return KeyCode.LeftControl;
                case 0xA3: return KeyCode.RightControl;
                case 0xA4: return KeyCode.LeftAlt;
                case 0xA5: return KeyCode.RightAlt;
                case 0xBA: return KeyCode.Semicolon;
                case 0xBB: return KeyCode.Equals;
                case 0xBC: return KeyCode.Comma;
                case 0xBD: return KeyCode.Minus;
                case 0xBE: return KeyCode.Period;
                case 0xBF: return KeyCode.Slash;
                case 0xC0: return KeyCode.BackQuote;
                case 0xDB: return KeyCode.LeftBracket;
                case 0xDC: return KeyCode.Backslash;
                case 0xDD: return KeyCode.RightBracket;
                case 0xDE: return KeyCode.Quote;
                default: return KeyCode.None;
            }
        }
    }

    [DefaultExecutionOrder(-32000)]
    public sealed class DoomerfallUi : MonoBehaviour
    {
        const int HudFramesToClose = 2; // A window can post the next window as it closes, which appears a frame later.
        const float TravelSettleSeconds = 20f;
        const int OpenWaitFrames = 30;
        const int MaxPendingReadbacks = 3;
        const float AskSettleSeconds = 0.25f, AskRepeatSeconds = 1f;

        static DoomerfallUi instance;

        DoomerfallBridge bridge;
        UserInterfaceRenderTarget target;
        IUserInterfaceWindow lastTop;
        RenderTexture scaled;
        uint openId;
        bool waitingForWindow, windowOpen, travelArriving, showingTravelMap, typing;
        DaggerfallRestWindow restWindow; // DFB_UI_REST: Daggerfall's rest window, kept while popups cover it
        float travelWaitUntil, nextAskAt;
        uint closeReason;
        ulong openGameSeconds;  // Daggerfall's clock when the menu opened, to tell a rest or loiter at the close
        bool traveled;
        int waitFrames, hudFrames, pending, surfaceWidth, surfaceHeight, basisWidth, basisHeight;
        uint frameId;
        byte[] pixels;
        readonly Queue<long> capturedTimes = new Queue<long>(), inputTimes = new Queue<long>();
        Action<AsyncGPUReadbackRequest> onReadback;

        public void Init(DoomerfallBridge owner)
        {
            bridge = owner;
            instance = this;
            onReadback = OnReadback;
            DaggerfallTravelPopUp.OnPostFastTravel += OnPostFastTravel;
            TransportManager.OnTransportModeChanged += OnTransportModeChanged;
            StartCoroutine(CaptureLoop());
        }

        void Update()
        {
            bridge.DrainEvents();
            DoomerfallInput.Step();
            if (openId == 0)
            {
                AskForOwnWindow();
                return;
            }
            nextAskAt = 0;

            if (target)
            {
                target.CustomWidth = Screen.width;
                target.CustomHeight = Screen.height;
            }

            IUserInterfaceManager manager = DaggerfallUI.UIManager;
            bool atHud = manager.TopWindow == null || manager.TopWindow is DaggerfallHUD;
            // Transparent around windows, so Doom can show its view behind small ones. With only the HUD up (a fast
            // travel settling, a fade) the frame stays black, as before.
            if (target)
                target.ClearColor = atHud ? Color.black : Color.clear;
            if (bridge.LogEnabled && manager.TopWindow != lastTop)
            {
                lastTop = manager.TopWindow;
                bridge.LogLine("ui: top window is " + (lastTop == null ? "none" : lastTop.GetType().Name));
            }
            if (waitingForWindow)
            {
                if (!atHud)
                {
                    waitingForWindow = false;
                    windowOpen = true;
                    restWindow = openId == Dfb.UI_REST ? DaggerfallUI.UIManager.TopWindow as DaggerfallRestWindow : null;
                    ChooseSurfaceSize();
                    SendState(Dfb.UI_OPENED, 0);
                    bridge.LogLine(string.Format("ui: menu {0} opened, surface {1}x{2}", openId, surfaceWidth, surfaceHeight));
                }
                else if (++waitFrames > OpenWaitFrames)
                {
                    Finish(Dfb.UI_REASON_REFUSED);
                }
            }
            else if (travelArriving)
            {
                if (GameManager.Instance.StreamingWorld.DoomerfallPositionSettled)
                {
                    FinishTravel();
                    Finish(Dfb.UI_REASON_RESULT);
                }
                else if (Time.realtimeSinceStartup > travelWaitUntil)
                {
                    bridge.LogLine("error: Daggerfall's world did not settle after fast travel");
                    travelArriving = false;
                    bridge.PositionSync.EndTravelHold();
                    Finish(Dfb.UI_REASON_RESULT);
                }
            }
            else if (windowOpen && atHud)
            {
                if (++hudFrames >= HudFramesToClose)
                    Finish(closeReason != 0 ? closeReason : Dfb.UI_REASON_USER);
            }
            else
            {
                hudFrames = 0;
            }

            // Text boxes update after this script, so last frame's is the newest word. While one takes typing,
            // Doom sends it every key unchanged, such as the movement keys it otherwise turns into map panning.
            bool nowTyping = windowOpen && TextBox.LastTypingFrame >= Time.frameCount - 1;
            if (nowTyping != typing)
            {
                typing = nowTyping;
                SendState(typing ? Dfb.UI_TYPING : Dfb.UI_OPENED, 0);
                bridge.LogLine("ui: text entry " + (typing ? "started" : "ended"));
            }
        }

        // Daggerfall can open a window by itself, such as a quest's message or prompt, and pauses behind it. Nobody
        // sees it unless Doom shows it, so ask Doom for a menu until it opens one or the window goes away.
        void AskForOwnWindow()
        {
            DoomerfallPositionSync sync = bridge.PositionSync;
            IUserInterfaceWindow top = DaggerfallUI.Instance ? DaggerfallUI.UIManager.TopWindow : null;
            if (top == null || top is DaggerfallHUD || !GameManager.HasInstance || sync.LoadRunning || !sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY)
            {
                nextAskAt = 0;
                return;
            }
            float now = Time.unscaledTime;
            if (nextAskAt == 0)
                nextAskAt = now + AskSettleSeconds; // A window that closes on its own in a moment needs no menu.
            if (now < nextAskAt)
                return;
            nextAskAt = now + AskRepeatSeconds; // Doom cannot open a menu while going through a door, so ask again.
            var e = new DfbEvent
            {
                kind = Dfb.KIND_UI_ASK,
                tic = (uint)Time.frameCount,
                uiCommand = new DfbUiCommand { uiId = Dfb.UI_DAGGERFALL },
            };
            bridge.Send(ref e);
            bridge.LogLine("ui: Daggerfall opened " + top.GetType().Name + " by itself, asking Doom to show it");
        }

        public void OnOpen(uint id, uint doomContext)
        {
            if (openId != 0)
                return;
            openId = id;
            closeReason = 0;
            openGameSeconds = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds();
            traveled = false;
            waitFrames = hudFrames = 0;
            showingTravelMap = id == Dfb.UI_TRAVEL_MAP;
            bool creating = id == Dfb.UI_NEW_GAME && DoomerfallNewGame.HoldsNewCharacter;
            bool loading = id == Dfb.UI_LOAD_GAME && DoomerfallNewGame.HoldsNewCharacter && PlainLoad;
            if ((id != Dfb.UI_TRAVEL_MAP && id != Dfb.UI_INVENTORY && id != Dfb.UI_MAP && id != Dfb.UI_LOOT && id != Dfb.UI_TALK && id != Dfb.UI_DAGGERFALL && id != Dfb.UI_JOURNAL && id != Dfb.UI_REST && id != Dfb.UI_CHARACTER && id != Dfb.UI_SPELLBOOK && id != Dfb.UI_STATUS && id != Dfb.UI_TRANSPORT && id != Dfb.UI_SKILLS && !creating && !loading) || !GameManager.HasInstance || !GameManager.Instance.IsReady || !DaggerfallUI.Instance)
            {
                Finish(Dfb.UI_REASON_REFUSED);
                return;
            }

            string message = id == Dfb.UI_INVENTORY ? DaggerfallUIMessages.dfuiOpenInventoryWindow : DaggerfallUIMessages.dfuiOpenTravelMapWindow;
            if (creating)
                message = null; // The wizard is opened below, once input is routed to it.
            if (id == Dfb.UI_JOURNAL)
            {
                // Clicking a quest's place opens the travel map. Doom follows that travel only from outdoors, as with K.
                message = DaggerfallUIMessages.dfuiOpenQuestJournalWindow;
                showingTravelMap = doomContext == Dfb.WORLD_EXTERIOR;
            }
            // Daggerfall's own windows, opened as its keys open them; the spellbook keeps Daggerfall's checks (SpellbookRefused).
            if (id == Dfb.UI_CHARACTER)
            {
                // Its Logbook button opens the journal, so travel from there follows the journal's rule.
                message = DaggerfallUIMessages.dfuiOpenCharacterSheetWindow;
                showingTravelMap = doomContext == Dfb.WORLD_EXTERIOR;
            }
            if (id == Dfb.UI_SPELLBOOK)
            {
                message = DaggerfallUIMessages.dfuiOpenSpellBookWindow;
                // Without a spellbook Daggerfall answers on its HUD, which Doom does not show, so Doom shows the same line.
                if (!GameManager.Instance.PlayerEntity.Items.Contains(DaggerfallWorkshop.Game.Items.ItemGroups.MiscItems, (int)DaggerfallWorkshop.Game.Items.MiscItems.Spellbook))
                {
                    DoomerfallInfo.SendText(bridge, 0, TextManager.Instance.GetLocalizedText("noSpellbook"), false, Dfb.KIND_HUD_TEXT);
                    bridge.LogLine("ui: spellbook refused, the player carries no spellbook");
                    Finish(Dfb.UI_REASON_RESULT);
                    return;
                }
            }
            if (id == Dfb.UI_STATUS)
            {
                // Daggerfall's Status key: its location and time box, then its health box (DaggerfallUI.DisplayStatusInfo).
                message = DaggerfallUIMessages.dfuiStatusInfo;
                PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
                uint actual = enter.IsPlayerInsideDungeon ? Dfb.WORLD_DUNGEON : enter.IsPlayerInside ? Dfb.WORLD_INTERIOR : Dfb.WORLD_EXTERIOR;
                bridge.LogLine(string.Format("ui: status in Daggerfall area {0}, Doom area {1}, at {2}", actual, doomContext, DaggerfallUnity.Instance.WorldTime.Now.MinTimeString()));
            }
            if (id == Dfb.UI_TRANSPORT)
            {
                // Daggerfall's own checks (DaggerfallUI, dfuiOpenTransportWindow) on where Doom's player is, since
                // Daggerfall's hidden player waits outside the door Doom used. The window is pushed below.
                if ((doomContext & 0xFF) != Dfb.WORLD_EXTERIOR)
                {
                    DoomerfallInfo.SendText(bridge, 0, TextManager.Instance.GetLocalizedText("cannotChangeTransportationIndoors"), false, Dfb.KIND_HUD_TEXT);
                    bridge.LogLine("ui: transport refused, Doom is in area " + (doomContext & 0xFF));
                    Finish(Dfb.UI_REASON_RESULT);
                    return;
                }
                if ((doomContext & Dfb.TRANSPORT_AIRBORNE) != 0)
                {
                    // Daggerfall says nothing, so the menu closes as answered: a refusal would make Doom print a line.
                    bridge.LogLine("ui: transport refused, Doom's player is not on the ground");
                    Finish(Dfb.UI_REASON_RESULT);
                    return;
                }
            }
            if (id == Dfb.UI_REST)
            {
                // Daggerfall's own rest request, with its own refusals; Doom's context says what it sees around the player.
                message = DaggerfallUIMessages.dfuiOpenRestWindow;
                DoomerfallRest.Opening(doomContext);
            }
            if (id == Dfb.UI_MAP)
            {
                // The map must describe the place Doom is showing, so wait out a door still in progress.
                PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
                uint actual = enter.IsPlayerInsideDungeon ? Dfb.WORLD_DUNGEON : enter.IsPlayerInside ? Dfb.WORLD_INTERIOR : Dfb.WORLD_EXTERIOR;
                if (actual != doomContext)
                {
                    bridge.LogLine(string.Format("ui: map refused, Doom is in area {0} and Daggerfall in {1}", doomContext, actual));
                    Finish(Dfb.UI_REASON_REFUSED);
                    return;
                }

                // Daggerfall has no automap for the wilderness, so its real map there is the travel map.
                PlayerGPS gps = GameManager.Instance.PlayerGPS;
                DaggerfallConnect.Utility.DFPosition pixel = gps.CurrentMapPixel;
                ContentReader.MapSummary summary;
                bool hasLocation = DaggerfallUnity.Instance.ContentReader.HasLocation(pixel.X, pixel.Y, out summary);
                // The exterior automap draws GPS's current location, which trails a map pixel change.
                if (!enter.IsPlayerInside && hasLocation && (!gps.HasCurrentLocation || gps.CurrentLocation.MapTableData.MapId != summary.MapID))
                {
                    bridge.LogLine(string.Format("ui: map refused, location at pixel {0},{1} has not loaded yet", pixel.X, pixel.Y));
                    Finish(Dfb.UI_REASON_REFUSED);
                    return;
                }
                bool hasAutomap = enter.IsPlayerInside || hasLocation;
                showingTravelMap = !hasAutomap;
                if (hasAutomap)
                    message = DaggerfallUIMessages.dfuiOpenAutomap;
                bridge.LogLine(string.Format("ui: map for area {0} at pixel {1},{2} uses {3}", actual, pixel.X, pixel.Y, hasAutomap ? (enter.IsPlayerInside ? "interior automap" : "exterior automap") : "travel map"));
            }

            if (!target)
            {
                var host = new GameObject("DoomerfallUiTarget");
                host.transform.SetParent(DaggerfallUI.Instance.transform, false);
                target = host.AddComponent<UserInterfaceRenderTarget>();
            }
            target.CustomWidth = Screen.width;
            target.CustomHeight = Screen.height;
            DaggerfallUI.Instance.CustomRenderTarget = target;
            DoomerfallInput.Begin();
            waitingForWindow = true;
            if (creating)
            {
                NewGame.BeginCreation();
                return;
            }
            if (loading)
            {
                // Daggerfall's own Load window. A save loaded from it is a plain load (DoomerfallPlainLoad).
                DaggerfallUI.UIManager.PushWindow(new DaggerfallUnitySaveGameWindow(DaggerfallUI.UIManager, DaggerfallUnitySaveGameWindow.Modes.LoadGame, null, true));
                PlainLoad.WindowOpened();
                return;
            }
            LogWorldState("before");
            if (id == Dfb.UI_DAGGERFALL)
            {
                // The window is already there. It may have closed by itself while Doom was opening the menu.
                if (DaggerfallUI.UIManager.TopWindow == null || DaggerfallUI.UIManager.TopWindow is DaggerfallHUD)
                    Finish(Dfb.UI_REASON_RESULT);
                return;
            }
            if (id == Dfb.UI_TRANSPORT)
            {
                DaggerfallUI.UIManager.PushWindow(UIWindowFactory.GetInstance(UIWindowType.Transport, DaggerfallUI.UIManager));
                bridge.LogLine(string.Format("ui: transport menu, owns horse {0} cart {1} ship {2}, riding {3}", GameManager.Instance.TransportManager.HasHorse(),
                    GameManager.Instance.TransportManager.HasCart(), GameManager.Instance.TransportManager.ShipAvailiable(), GameManager.Instance.TransportManager.TransportMode));
                return;
            }
            if (id == Dfb.UI_SKILLS)
            {
                DaggerfallUI.UIManager.PushWindow(new DoomerfallSkillsWindow(DaggerfallUI.UIManager));
                return;
            }
            if (id == Dfb.UI_LOOT)
            {
                // Daggerfall's own activation pushes whatever the container calls for: the loot window, the trade
                // window, or the private property question. Some containers answer with no window at all.
                if (!Items || !Items.OpenWindow())
                    Finish(Dfb.UI_REASON_REFUSED);
                else if (DaggerfallUI.UIManager.TopWindow == null || DaggerfallUI.UIManager.TopWindow is DaggerfallHUD)
                    Finish(Dfb.UI_REASON_RESULT);
                return;
            }
            if (id == Dfb.UI_TALK)
            {
                // Daggerfall's own activation of the NPC pushes its window: talk, or a quest offer or message.
                if (!Talk || !Talk.OpenWindow())
                    Finish(Dfb.UI_REASON_REFUSED);
                else if (DaggerfallUI.UIManager.TopWindow == null || DaggerfallUI.UIManager.TopWindow is DaggerfallHUD)
                    Finish(Dfb.UI_REASON_RESULT);
                return;
            }
            DaggerfallUI.PostMessage(message);
        }

        internal DoomerfallNewGame NewGame { get; set; }
        internal DoomerfallPlainLoad PlainLoad { get; set; }
        internal DoomerfallItems Items { get; set; }
        internal DoomerfallTalk Talk { get; set; }
        internal DoomerfallTownspeople Townspeople { get; set; }
        internal DoomerfallNpcs Npcs { get; set; }

        /// <summary>The wizard is closing because a character was made, or the Load window because a save was chosen,
        /// not because the player backed out.</summary>
        internal static void MarkResult()
        {
            if (instance && (instance.openId == Dfb.UI_NEW_GAME || instance.openId == Dfb.UI_LOAD_GAME))
                instance.closeReason = Dfb.UI_REASON_RESULT;
        }

        /// <summary>The journal's travel map is open while Doom is indoors, where Doom cannot follow a journey.
        /// Says so the way Doom's travel key does, and returns true so the travel map does not start one.</summary>
        public static bool RefuseJournalTravel()
        {
            if (!instance || (instance.openId != Dfb.UI_JOURNAL && instance.openId != Dfb.UI_CHARACTER) || instance.showingTravelMap)
                return false;
            DaggerfallUI.MessageBox("You cannot travel from indoors.");
            instance.bridge.LogLine("ui: travel from the journal refused, Doom is indoors");
            return true;
        }

        /// <summary>Choosing a spell in Daggerfall's spellbook. Casting from Doom is not built yet (backlog
        /// magic-casting-and-self-spells), so in a bridge session every route to the spellbook (its key, the character
        /// sheet, the inventory's spellbook item, the level-up sheet) readies and casts nothing, and says so (owner,
        /// 2026-11-27: the menu first, casting with the casting card).</summary>
        public static bool HoldsSpellChoice()
        {
            if (!instance)
                return false;
            DaggerfallUI.MessageBox("You cannot cast spells yet.");
            instance.bridge.LogLine("ui: spell choice held, casting from Doom is not built yet");
            return true;
        }

        /// <summary>Daggerfall refused its spellbook from inside a Doom menu (the character sheet's Spellbook button) with a
        /// line on its hidden HUD, so the same line shows in the menu.</summary>
        public static void NoSpellbook(string text)
        {
            if (!instance || !instance.windowOpen)
                return;
            DaggerfallUI.MessageBox(text);
            instance.bridge.LogLine("ui: spellbook refused inside the menu, the player carries no spellbook");
        }

        /// <summary>Daggerfall's Load window is showing in Doom (DFB_UI_LOAD_GAME).</summary>
        internal static bool LoadWindowOpen { get { return instance && instance.openId == Dfb.UI_LOAD_GAME; } }

        public void OnClose(uint id)
        {
            if (openId == 0 || id != openId)
                return;
            // The rest key once a rest has started goes to the rest window, so Daggerfall's end of rest and skill check always run.
            if (id == Dfb.UI_REST && restWindow != null && restWindow.DoomerfallRestKey())
            {
                bridge.LogLine("rest: Doom's rest key handled by the rest window");
                return;
            }
            closeReason = Dfb.UI_REASON_DOOM;
            if (waitingForWindow)
                Finish(Dfb.UI_REASON_DOOM);
            else
                DaggerfallUI.Instance.PopToHUD();
        }

        void Finish(uint reason)
        {
            uint id = openId;
            openId = 0;
            waitingForWindow = windowOpen = typing = false;
            restWindow = null;
            if (id == Dfb.UI_NEW_GAME && NewGame)
                NewGame.CreationClosed(reason == Dfb.UI_REASON_RESULT);
            if (id == Dfb.UI_LOAD_GAME && PlainLoad && GameManager.HasInstance && GameManager.Instance.SaveLoadManager.LoadInProgress && reason != Dfb.UI_REASON_RESULT)
            {
                reason = Dfb.UI_REASON_RESULT; // The window closed because a save was chosen; it is loading now.
                PlainLoad.Arm();
            }
            if (id == Dfb.UI_LOOT && Items)
                Items.WindowClosed();
            if (id == Dfb.UI_REST)
                DoomerfallRest.Closed();
            DoomerfallInput.End();
            if (DaggerfallUI.Instance)
                DaggerfallUI.Instance.CustomRenderTarget = null;
            uint flags = reason != Dfb.UI_REASON_REFUSED && TimePassed(id) ? Dfb.UI_CLOSED_TIME_PASSED : 0;
            if (flags != 0)
            {
                // People moved while the clock ran. Their lists go first, so Doom has them when it reads the close.
                if (Townspeople) Townspeople.PublishNow();
                if (Npcs) Npcs.PublishNow();
                bridge.LogLine(string.Format("ui: {0} game minutes passed in menu {1}; sent the people lists before the close",
                    (DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() - openGameSeconds) / 60, id));
            }
            SendState(Dfb.UI_CLOSED, reason, id, flags);
            bridge.LogLine("ui: menu " + id + " closed, reason " + reason);
            if (reason != Dfb.UI_REASON_REFUSED)
                LogWorldState("after");
        }

        // A rest, a loiter or a rented room ran the clock. A journey has its own arrival, and a load its own world.
        bool TimePassed(uint id)
        {
            if (id == Dfb.UI_NEW_GAME || id == Dfb.UI_LOAD_GAME || traveled || !GameManager.HasInstance || GameManager.Instance.SaveLoadManager.LoadInProgress)
                return false;
            return DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() >= openGameSeconds + 60;
        }

        // Evidence that a chosen destination changed nothing: same place, same gold, same game time.
        void LogWorldState(string when)
        {
            if (!bridge.LogEnabled || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return;
            GameManager game = GameManager.Instance;
            bridge.LogLine(string.Format("ui: world {0}: pixel {1},{2} gold {3} game_minutes {4}", when, game.PlayerGPS.CurrentMapPixel.X,
                game.PlayerGPS.CurrentMapPixel.Y, game.PlayerEntity.GoldPieces, DaggerfallUnity.Instance.WorldTime.DaggerfallDateTime.ToClassicDaggerfallTime()));

            var items = new StringBuilder();
            DaggerfallWorkshop.Game.Items.ItemCollection carried = game.PlayerEntity.Items;
            for (int i = 0; i < carried.Count; i++)
            {
                DaggerfallWorkshop.Game.Items.DaggerfallUnityItem item = carried.GetItem(i);
                items.Append(i == 0 ? "" : ", ").Append(item.LongName).Append(item.IsEquipped ? " (equipped)" : "");
            }
            bridge.LogLine(string.Format("ui: inventory {0}: {1} carried, {2} in wagon: {3}", when, carried.Count, game.PlayerEntity.WagonItems.Count, items));
        }

        void SendState(uint state, uint reason, uint id = 0, uint flags = 0)
        {
            var e = new DfbEvent
            {
                kind = Dfb.KIND_UI_STATE,
                tic = (uint)Time.frameCount,
                uiState = new DfbUiState
                {
                    uiId = id != 0 ? id : openId,
                    state = state,
                    reason = reason,
                    surfaceWidth = (uint)surfaceWidth,
                    surfaceHeight = (uint)surfaceHeight,
                    flags = flags,
                },
            };
            bridge.Send(ref e);
        }

        // Daggerfall's own travel has charged, advanced time, and started moving the player. Its placement
        // finishes over the next frames, so Doom stays paused behind the menu until it has settled.
        void OnPostFastTravel()
        {
            if (openId == 0 || !showingTravelMap)
                return;
            BeginArrival("travelled");
        }

        // The transport menu's Ship row: Daggerfall teleports its world to the ship, or back to where the player boarded,
        // with no fast travel. Doom follows it as it follows a fast travel.
        void OnTransportModeChanged(TransportModes newMode, TransportModes previousMode)
        {
            if (openId == Dfb.UI_TRANSPORT && newMode == TransportModes.Ship)
                BeginArrival("boarded or left the ship");
        }

        void BeginArrival(string how)
        {
            GameManager game = GameManager.Instance;
            StreamingWorld world = game.StreamingWorld;
            travelArriving = true;
            traveled = true;
            travelWaitUntil = Time.realtimeSinceStartup + TravelSettleSeconds;
            closeReason = Dfb.UI_REASON_RESULT;
            // Placement only sets this when a location has a facing to give. Otherwise the player keeps Doom's.
            game.PlayerMouseLook.Yaw = game.PlayerObject.transform.eulerAngles.y;
            bridge.PositionSync.BeginTravelHold(world.MapPixelX, world.MapPixelY);
            LogWorldState(how);
        }

        void FinishTravel()
        {
            travelArriving = false;
            GameManager game = GameManager.Instance;
            PlayerGPS gps = game.PlayerGPS;
            StreamingWorld world = game.StreamingWorld;
            SendTravelResult(world.MapPixelX, world.MapPixelY);

            // Placement outside a location's edge can cross into the next map pixel, so use the exact position.
            var arrival = DaggerfallConnect.Arena2.MapsFile.WorldCoordToMapPixel(gps.WorldX, gps.WorldZ);
            bridge.PositionSync.BeginTravelHold(arrival.X, arrival.Y);

            float yaw = Mathf.Repeat(90f - game.PlayerMouseLook.Yaw, 360f);
            var e = new DfbEvent
            {
                kind = Dfb.KIND_TRAVEL,
                tic = (uint)Time.frameCount,
                travel = new DfbTravel
                {
                    worldX = gps.WorldX,
                    worldZ = gps.WorldZ,
                    yawDegrees = yaw,
                    mapPixelX = arrival.X,
                    mapPixelY = arrival.Y,
                },
            };
            bridge.Send(ref e);
            bridge.LogLine(string.Format("travel: arrived at world {0},{1} pixel {2},{3} yaw {4:F1}", gps.WorldX, gps.WorldZ, world.MapPixelX, world.MapPixelY, yaw));
        }

        void SendTravelResult(int x, int y)
        {
            string name = "unknown";
            ContentReader.MapSummary summary;
            DFLocation location;
            ContentReader reader = DaggerfallUnity.Instance.ContentReader;
            if (reader.HasLocation(x, y, out summary) && reader.GetLocation(summary.RegionIndex, summary.MapIndex, out location))
                name = location.Name;
            bridge.LogLine(string.Format("ui: travelled to {0} at map pixel {1},{2}", name, x, y));

            byte[] text = Encoding.UTF8.GetBytes(name);
            var e = new DfbEvent
            {
                kind = Dfb.KIND_UI_RESULT,
                tic = (uint)Time.frameCount,
                uiResult = new DfbUiResult { uiId = Dfb.UI_TRAVEL_MAP, mapPixelX = x, mapPixelY = y },
            };
            e.uiResult.SetName(text, Math.Min(text.Length, 35)); // always leaves the terminator
            bridge.Send(ref e);
        }

        // Keeps the aspect ratio when the Daggerfall window is larger than the shared surface.
        void ChooseSurfaceSize()
        {
            basisWidth = Screen.width;
            basisHeight = Screen.height;
            float scale = Mathf.Min(1f, Mathf.Min((float)Dfb.SURFACE_MAX_W / Screen.width, (float)Dfb.SURFACE_MAX_H / Screen.height));
            surfaceWidth = Mathf.Max(1, Mathf.FloorToInt(Screen.width * scale));
            surfaceHeight = Mathf.Max(1, Mathf.FloorToInt(Screen.height * scale));
            pixels = new byte[surfaceWidth * surfaceHeight * 4];
            if (scaled)
            {
                scaled.Release();
                Destroy(scaled);
                scaled = null;
            }
            if (surfaceWidth != Screen.width || surfaceHeight != Screen.height)
                scaled = new RenderTexture(surfaceWidth, surfaceHeight, 0, RenderTextureFormat.ARGB32);
            bridge.LogLine(string.Format("ui: surface {0}x{1} for a {2}x{3} window", surfaceWidth, surfaceHeight, Screen.width, Screen.height));
        }

        /// <summary>Doom's mouse position in Unity screen pixels, with the origin at the bottom left.</summary>
        public static Vector3 MouseScreenPosition
        {
            get
            {
                DoomerfallUi ui = instance;
                if (!ui || ui.surfaceWidth == 0)
                    return Vector3.zero;
                Vector2 mouse = DoomerfallInput.SurfaceMouse;
                float x = (mouse.x + 0.5f) * Screen.width / ui.surfaceWidth;
                float y = (mouse.y + 0.5f) * Screen.height / ui.surfaceHeight;
                return new Vector3(x, Screen.height - y, 0);
            }
        }

        IEnumerator CaptureLoop()
        {
            var endOfFrame = new WaitForEndOfFrame();
            while (true)
            {
                yield return endOfFrame;
                if (!windowOpen || !target || !target.TargetTexture || pending >= MaxPendingReadbacks)
                    continue;
                RenderTexture source = target.TargetTexture;
                if (source.width != Screen.width || source.height != Screen.height)
                    continue; // Resized this frame; the texture is recreated on the next update.
                if (source.width != basisWidth || source.height != basisHeight)
                    ChooseSurfaceSize(); // The window was resized for Doom's screen (DoomerfallWindow.MatchDoom).
                if (scaled)
                    Graphics.Blit(source, scaled);
                pending++;
                capturedTimes.Enqueue(DfbNative.dfb_now_ns());
                inputTimes.Enqueue(DoomerfallInput.LastInputNs);
                AsyncGPUReadback.Request(scaled ? scaled : source, 0, TextureFormat.BGRA32, onReadback);
            }
        }

        void OnReadback(AsyncGPUReadbackRequest request)
        {
            pending--;
            long capturedNs = capturedTimes.Dequeue(), inputNs = inputTimes.Dequeue();
            if (!windowOpen || request.hasError || request.width != surfaceWidth || request.height != surfaceHeight)
                return;
            request.GetData<byte>().CopyTo(pixels);
            DfbNative.dfb_surface_write(bridge.Session, pixels, (uint)surfaceWidth, (uint)surfaceHeight, ++frameId, capturedNs, inputNs, SystemInfo.graphicsUVStartsAtTop ? 1 : 0);
        }

        void OnDestroy()
        {
            DaggerfallTravelPopUp.OnPostFastTravel -= OnPostFastTravel;
            TransportManager.OnTransportModeChanged -= OnTransportModeChanged;
            DoomerfallInput.End();
            if (scaled)
                scaled.Release();
            if (instance == this)
                instance = null;
        }
    }
}
