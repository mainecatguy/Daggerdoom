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

        static DoomerfallUi instance;

        DoomerfallBridge bridge;
        UserInterfaceRenderTarget target;
        IUserInterfaceWindow lastTop;
        RenderTexture scaled;
        uint openId;
        bool waitingForWindow, windowOpen, travelArriving, showingTravelMap;
        float travelWaitUntil;
        uint closeReason;
        int waitFrames, hudFrames, pending, surfaceWidth, surfaceHeight;
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
            StartCoroutine(CaptureLoop());
        }

        void Update()
        {
            bridge.DrainEvents();
            DoomerfallInput.Step();
            if (openId == 0)
                return;

            if (target)
            {
                target.CustomWidth = Screen.width;
                target.CustomHeight = Screen.height;
            }

            IUserInterfaceManager manager = DaggerfallUI.UIManager;
            bool atHud = manager.TopWindow == null || manager.TopWindow is DaggerfallHUD;
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
        }

        public void OnOpen(uint id, uint doomContext)
        {
            if (openId != 0)
                return;
            openId = id;
            closeReason = 0;
            waitFrames = hudFrames = 0;
            showingTravelMap = id == Dfb.UI_TRAVEL_MAP;
            bool creating = id == Dfb.UI_NEW_GAME && DoomerfallNewGame.HoldsNewCharacter;
            if ((id != Dfb.UI_TRAVEL_MAP && id != Dfb.UI_INVENTORY && id != Dfb.UI_MAP && !creating) || !GameManager.HasInstance || !GameManager.Instance.IsReady || !DaggerfallUI.Instance)
            {
                Finish(Dfb.UI_REASON_REFUSED);
                return;
            }

            string message = id == Dfb.UI_INVENTORY ? DaggerfallUIMessages.dfuiOpenInventoryWindow : DaggerfallUIMessages.dfuiOpenTravelMapWindow;
            if (creating)
                message = null; // The wizard is opened below, once input is routed to it.
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
            LogWorldState("before");
            DaggerfallUI.PostMessage(message);
        }

        internal DoomerfallNewGame NewGame { get; set; }

        /// <summary>The wizard is closing because a character was made, not because the player backed out.</summary>
        internal static void MarkResult()
        {
            if (instance && instance.openId == Dfb.UI_NEW_GAME)
                instance.closeReason = Dfb.UI_REASON_RESULT;
        }

        public void OnClose(uint id)
        {
            if (openId == 0 || id != openId)
                return;
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
            waitingForWindow = windowOpen = false;
            if (id == Dfb.UI_NEW_GAME && NewGame)
                NewGame.CreationClosed(reason == Dfb.UI_REASON_RESULT);
            DoomerfallInput.End();
            if (DaggerfallUI.Instance)
                DaggerfallUI.Instance.CustomRenderTarget = null;
            SendState(Dfb.UI_CLOSED, reason, id);
            bridge.LogLine("ui: menu " + id + " closed, reason " + reason);
            if (reason != Dfb.UI_REASON_REFUSED)
                LogWorldState("after");
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

        void SendState(uint state, uint reason, uint id = 0)
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
            GameManager game = GameManager.Instance;
            StreamingWorld world = game.StreamingWorld;
            travelArriving = true;
            travelWaitUntil = Time.realtimeSinceStartup + TravelSettleSeconds;
            closeReason = Dfb.UI_REASON_RESULT;
            // Placement only sets this when a location has a facing to give. Otherwise the player keeps Doom's.
            game.PlayerMouseLook.Yaw = game.PlayerObject.transform.eulerAngles.y;
            bridge.PositionSync.BeginTravelHold(world.MapPixelX, world.MapPixelY);
            LogWorldState("travelled");
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
                if (scaled)
                    Graphics.Blit(source, scaled);
                else if (source.width != surfaceWidth || source.height != surfaceHeight)
                {
                    ChooseSurfaceSize();
                    if (scaled)
                        Graphics.Blit(source, scaled);
                }
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
            DoomerfallInput.End();
            if (scaled)
                scaled.Release();
            if (instance == this)
                instance = null;
        }
    }
}
