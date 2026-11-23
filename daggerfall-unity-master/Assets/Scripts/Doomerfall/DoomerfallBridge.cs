// Doomerfall: Daggerfall Unity's side of the bridge. Does nothing unless the game is started with
// -dfbridge <session>; without it the native DLL is never loaded and no object is created.
// After startup the per-frame path uses preallocated blittable structs and allocates nothing.
// Only the two-second log line allocates.

using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    [StructLayout(LayoutKind.Sequential)]
    struct DfbEvent
    {
        public uint seq;
        public uint tic;
        public ushort kind;
        public ushort flags;
        public uint reserved;
        public ulong p0, p1, p2, p3, p4, p5; // 48-byte payload
    }

    [StructLayout(LayoutKind.Sequential, Size = 256)]
    struct DfbDfState
    {
        public uint publishSeq;
        public uint dfPhase;
        public ulong dfHeartbeat;
        public long publishedNs;
        public uint dfFrame;
        public uint demoValue;
        public int hpCurrent, hpMax;
        public uint hpApplied, hpFlags;
    }

    [StructLayout(LayoutKind.Sequential, Size = 256)]
    struct DfbUzState
    {
        public uint publishSeq;
        public uint uzPhase;
        public ulong uzHeartbeat;
        public long publishedNs;
        public uint uzTic;
        public uint demoValue;
        public double worldX, worldZ, worldHeight; // Daggerfall world units
        public float yawDegrees;
        public uint worldContext;
        public int mapPixelX, mapPixelY;
        public uint areaSeq;
        public uint pad0;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct DfbStats
    {
        public ulong sent, received, queuedOverflow, seqGaps;
        public uint outboxCount, outboxPeak, ringUsedOut, ringUsedIn, peerPid, peerAttachCount;
    }

    static class DfbNative
    {
        const string Dll = "doomerfall_bridge";

        [DllImport(Dll)] public static extern uint dfb_protocol_version();
        [DllImport(Dll)] public static extern ulong dfb_layout_hash();
        [DllImport(Dll)] public static extern uint dfb_struct_size(int which);
        [DllImport(Dll)] public static extern long dfb_now_ns();
        [DllImport(Dll)] public static extern int dfb_attach([MarshalAs(UnmanagedType.LPStr)] string id, int side, out IntPtr session);
        [DllImport(Dll)] public static extern void dfb_close(IntPtr session);
        [DllImport(Dll)] public static extern int dfb_send(IntPtr session, ref DfbEvent e);
        [DllImport(Dll)] public static extern int dfb_flush(IntPtr session);
        [DllImport(Dll)] public static extern int dfb_receive(IntPtr session, ref DfbEvent e);
        [DllImport(Dll)] public static extern int dfb_publish_state(IntPtr session, ref DfbDfState state, uint size);
        [DllImport(Dll)] public static extern int dfb_read_state(IntPtr session, ref DfbUzState state, uint size);
        [DllImport(Dll)] public static extern int dfb_get_stats(IntPtr session, ref DfbStats stats);
        [DllImport(Dll)] public static extern long dfb_peer_state_age_ns(IntPtr session);
        [DllImport(Dll)] public static extern int dfb_surface_write(IntPtr session, byte[] bgra, uint width, uint height, uint frameId, long capturedNs, long inputNs, int flipY);
    }

    public sealed class DoomerfallBridge : MonoBehaviour
    {
        const uint ProtocolVersion = 4;
        const int SideDf = 1;
        const int Got = 1;
        const ushort KindHello = 1, KindPing = 2, KindPong = 3, KindText = 4, KindArea = 5, KindUiOpen = 6, KindUiClose = 7, KindUiInput = 8, KindHp = 11;
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

        IntPtr session;
        StreamWriter log;
        DfbEvent ev;
        DfbDfState own;
        DfbUzState peer;
        DfbStats stats;
        DoomerfallPositionSync sync;
        DoomerfallUi ui;
        DoomerfallHp hp;
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
                if (DfbNative.dfb_protocol_version() != ProtocolVersion ||
                    DfbNative.dfb_struct_size(0) != Marshal.SizeOf(typeof(DfbEvent)) ||
                    DfbNative.dfb_struct_size(1) != Marshal.SizeOf(typeof(DfbDfState)) ||
                    DfbNative.dfb_struct_size(2) != Marshal.SizeOf(typeof(DfbUzState)) ||
                    DfbNative.dfb_struct_size(3) != Marshal.SizeOf(typeof(DfbStats)))
                {
                    Fail("bridge DLL does not match this build's struct layout");
                    return;
                }
                int rc = DfbNative.dfb_attach(pendingSession, SideDf, out session);
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

            ownSize = (uint)Marshal.SizeOf(typeof(DfbDfState));
            peerSize = (uint)Marshal.SizeOf(typeof(DfbUzState));
            Log(string.Format("attached to session {0}, protocol {1}, layout {2:x16}", pendingSession,
                DfbNative.dfb_protocol_version(), DfbNative.dfb_layout_hash()));

            ev = new DfbEvent { kind = KindHello };
            DfbNative.dfb_send(session, ref ev);
            SendText("hello from Daggerfall Unity");

            sync = gameObject.AddComponent<DoomerfallPositionSync>();
            sync.Init(this, Environment.GetCommandLineArgs());
            hp = new DoomerfallHp(this, sync, Environment.GetCommandLineArgs());
            ui =gameObject.AddComponent<DoomerfallUi>();
            ui.Init(this);
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

        void SendText(string text)
        {
            byte[] bytes = new byte[48];
            Encoding.UTF8.GetBytes(text, 0, Math.Min(text.Length, 48), bytes, 0);
            ev = new DfbEvent
            {
                kind = KindText,
                p0 = BitConverter.ToUInt64(bytes, 0),
                p1 = BitConverter.ToUInt64(bytes, 8),
                p2 = BitConverter.ToUInt64(bytes, 16),
                p3 = BitConverter.ToUInt64(bytes, 24),
                p4 = BitConverter.ToUInt64(bytes, 32),
                p5 = BitConverter.ToUInt64(bytes, 40),
            };
            DfbNative.dfb_send(session, ref ev);
        }

        string ReadText()
        {
            byte[] bytes = new byte[48];
            Buffer.BlockCopy(BitConverter.GetBytes(ev.p0), 0, bytes, 0, 8);
            Buffer.BlockCopy(BitConverter.GetBytes(ev.p1), 0, bytes, 8, 8);
            Buffer.BlockCopy(BitConverter.GetBytes(ev.p2), 0, bytes, 16, 8);
            Buffer.BlockCopy(BitConverter.GetBytes(ev.p3), 0, bytes, 24, 8);
            Buffer.BlockCopy(BitConverter.GetBytes(ev.p4), 0, bytes, 32, 8);
            Buffer.BlockCopy(BitConverter.GetBytes(ev.p5), 0, bytes, 40, 8);
            int length = Array.IndexOf(bytes, (byte)0);
            return Encoding.UTF8.GetString(bytes, 0, length < 0 ? 48 : length);
        }

        void Update()
        {
            if (session == IntPtr.Zero) return;

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
            while (DfbNative.dfb_receive(session, ref ev) == Got)
            {
                long received = DfbNative.dfb_now_ns();
                if (ev.kind == KindText || ev.kind == KindHello) textFrame = true;
                switch (ev.kind)
                {
                    case KindPing:
                        ev.p2 = (ulong)received; // replier_ns
                        ev.kind = KindPong;
                        ev.tic = (uint)Time.frameCount;
                        DfbNative.dfb_send(session, ref ev);
                        pingsAnswered++;
                        break;
                    case KindPong:
                        long sent = (long)ev.p1, replied = (long)ev.p2;
                        rtt.Add(received - sent);
                        oneWayOut.Add(replied - sent);
                        oneWayIn.Add(received - replied);
                        pongsReceived++;
                        break;
                    case KindText:
                    {
                        string text = ReadText();
                        Log("message from UZDoom: \"" + text + "\" (seq " + ev.seq + ")");
                        hp.OnText(text);
                        break;
                    }
                    case KindHp: // payload: event number, type, amount, pad, sent_ns
                        hp.OnEvent((uint)ev.p0, (uint)(ev.p0 >> 32), (int)(uint)ev.p1);
                        break;
                    case KindHello:
                        Log("hello from UZDoom (seq " + ev.seq + ")");
                        break;
                    case KindArea: // payload: context, pixel x, pixel y, sequence, sent_ns
                        sync.OnAreaEvent((uint)ev.p0, (int)(ev.p0 >> 32), (int)(uint)ev.p1, (long)ev.p2);
                        break;
                    case KindUiOpen:
                        ui.OnOpen((uint)ev.p0);
                        break;
                    case KindUiClose:
                        ui.OnClose((uint)ev.p0);
                        break;
                    case KindUiInput: // payload: type, a, b, pad, sent_ns
                        DoomerfallInput.Enqueue((uint)ev.p0, (int)(ev.p0 >> 32), (int)(uint)ev.p1, (long)ev.p2);
                        break;
                    default:
                        unknownKinds++; // contract rule 7: skip, never fatal
                        break;
                }
            }
        }

        void FinishFrame(long memoryBefore, int collectionsBefore)
        {
            if (DfbNative.dfb_read_state(session, ref peer, peerSize) == Got)
                stateAge.Add(DfbNative.dfb_now_ns() - peer.publishedNs);

            sync.Tick(ref peer);
            own.dfPhase = sync.Phase;
            own.dfHeartbeat++;
            own.dfFrame = (uint)Time.frameCount;
            own.demoValue = (uint)Time.frameCount;
            hp.Fill(ref own);
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

            if (alive && now >= nextPingNs)
            {
                nextPingNs = now + PingIntervalNs;
                ev = default(DfbEvent);
                ev.kind = KindPing;
                ev.tic = (uint)Time.frameCount;
                ev.p0 = nextPing++;
                ev.p1 = (ulong)DfbNative.dfb_now_ns();
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
            if (session != IntPtr.Zero) DfbNative.dfb_close(session);
            session = IntPtr.Zero;
            if (log != null) log.Dispose();
            log = null;
        }
    }
}
