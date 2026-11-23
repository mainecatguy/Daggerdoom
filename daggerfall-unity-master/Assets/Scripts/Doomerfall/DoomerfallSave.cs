// Doomerfall: Daggerfall's side of the synchronized save. Doom is frozen when the request arrives, and
// the ordered event ring means every earlier hit and heal has already been applied here.

using System;
using System.Collections;
using System.IO;
using System.Text;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public sealed class DoomerfallSave : MonoBehaviour
    {
        const ushort KindSavePrepared = 13;
        const uint StatusOk = 0, StatusRefused = 1, StatusFailed = 2, PathSlot = 4, PhasePlay = 3;
        const float SettleSeconds = 5f, DoneSeconds = 15f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallHp hp;
        bool busy, pausedBySave, testFail;
        uint activeTxn;
        float doneDeadline;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallHp playerHp, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            hp = playerHp;
            int fail = Array.IndexOf(args, "-dfsavetestfail");
            testFail = fail >= 0 && fail + 1 < args.Length && args[fail + 1] == "df_write";
            if (Array.IndexOf(args, "-dfplainsavetest") >= 0)
                StartCoroutine(PlainSaveTest());
        }

        // Test only: a normal Daggerfall save through its own entry point, into the private portable folder.
        IEnumerator PlainSaveTest()
        {
            while (!sync.InGame || sync.Phase != PhasePlay)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            string character = GameManager.Instance.PlayerEntity.Name;
            saves.Save(character, "PlainSaveTest");
            yield return new WaitForSecondsRealtime(2f);
            int key = saves.FindSaveFolderByNames(character, "PlainSaveTest");
            string folder = key >= 0 ? saves.GetSaveFolder(key) : null;
            bridge.LogLine("plain save test: " + (folder == null ? "no save found" : "files " + string.Join(",", Array.ConvertAll(Directory.GetFiles(folder), Path.GetFileName))));
        }

        public void OnRequest(uint txn, uint hpSentThrough)
        {
            if (busy)
            {
                Reply(txn, StatusRefused, 0, 0);
                return;
            }
            string refusal = RefusalReason(hpSentThrough);
            if (refusal != null)
            {
                bridge.LogLine("save " + txn + ": refused, " + refusal);
                Reply(txn, StatusRefused, 0, 0);
                return;
            }
            busy = true;
            activeTxn = txn;
            doneDeadline = float.MaxValue;
            pausedBySave = !GameManager.IsGamePaused;
            if (pausedBySave)
                GameManager.Instance.PauseGame(true);
            StartCoroutine(Run(txn));
        }

        public void OnDone(uint txn, bool committed)
        {
            if (!busy || txn != activeTxn)
                return;
            bridge.LogLine("save " + txn + (committed ? ": Doom committed the bundle" : ": Doom reported failure"));
            StopAllCoroutines();
            Resume();
        }

        void Update()
        {
            if (busy && Time.unscaledTime > doneDeadline)
            {
                bridge.LogLine("save " + activeTxn + ": no result from Doom, resuming");
                Resume();
            }
        }

        void Resume()
        {
            busy = false;
            if (pausedBySave)
                GameManager.Instance.PauseGame(false);
            pausedBySave = false;
        }

        string RefusalReason(uint hpSentThrough)
        {
            if (!GameManager.HasInstance || !sync.InGame || sync.Phase != PhasePlay)
                return "not in play";
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            if (saves.IsSavingPrevented || saves.LoadInProgress)
                return "saving is prevented here";
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (player == null || player.CurrentHealth <= 0)
                return "player is dead";
            if (hp.Applied != hpSentThrough)
                return "HP events are not all applied (" + hp.Applied + " of " + hpSentThrough + ")";
            return null;
        }

        IEnumerator Run(uint txn)
        {
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            float deadline = Time.unscaledTime + SettleSeconds;
            while (!sync.ApplyForSave(ref peer))
            {
                if (Time.unscaledTime > deadline)
                {
                    Fail(txn, "the world did not settle");
                    yield break;
                }
                yield return null;
            }
            // PlayerGPS reads the moved transform on its next update.
            yield return null;
            yield return null;
            while (!sync.PositionSettled)
            {
                if (Time.unscaledTime > deadline)
                {
                    Fail(txn, "the world did not settle");
                    yield break;
                }
                yield return null;
            }

            string folder = ReadStagingFolder();
            if (folder == null)
            {
                Fail(txn, "no staging folder");
                yield break;
            }
            int files = 0;
            long bytes = 0;
            try
            {
                GameManager.Instance.SaveLoadManager.SaveToFolder(folder, "Doomerfall");
                if (testFail)
                    throw new IOException("test failure after writing the files");
                foreach (string file in Directory.GetFiles(folder, "*", SearchOption.AllDirectories))
                {
                    files++;
                    bytes += new FileInfo(file).Length;
                }
            }
            catch (Exception e)
            {
                Fail(txn, e.ToString());
                yield break;
            }
            bridge.LogLine(string.Format("save {0}: wrote {1} files, {2} bytes, hp {3}, position {4},{5}", txn, files, bytes,
                GameManager.Instance.PlayerEntity.CurrentHealth, GameManager.Instance.PlayerGPS.WorldX, GameManager.Instance.PlayerGPS.WorldZ));
            doneDeadline = Time.unscaledTime + DoneSeconds;
            Reply(txn, StatusOk, files, bytes);
        }

        string ReadStagingFolder()
        {
            byte[] data = new byte[4096];
            uint size, version;
            if (DfbNative.dfb_bulk_read(bridge.Session, PathSlot, data, (uint)data.Length, out size, out version) != 1 || size < 2)
                return null;
            string folder = Encoding.UTF8.GetString(data, 0, (int)size - 1);
            return folder.EndsWith(".dfstage", StringComparison.Ordinal) && Directory.Exists(folder) ? folder : null;
        }

        void Fail(uint txn, string why)
        {
            bridge.LogLine("save " + txn + ": failed, " + why);
            Reply(txn, StatusFailed, 0, 0);
            Resume();
        }

        void Reply(uint txn, uint status, int files, long bytes)
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            PlayerGPS gps = GameManager.HasInstance ? GameManager.Instance.PlayerGPS : null;
            DfbEvent e = default(DfbEvent);
            e.kind = KindSavePrepared;
            e.tic = (uint)Time.frameCount;
            e.p0 = txn | (ulong)status << 32;
            if (player != null)
                e.p1 = (uint)player.CurrentHealth | (ulong)(uint)player.MaxHealth << 32;
            e.p2 = hp.Applied | (ulong)(uint)files << 32;
            if (gps != null)
                e.p3 = (uint)gps.WorldX | (ulong)(uint)gps.WorldZ << 32;
            e.p4 = (ulong)bytes;
            bridge.Send(ref e);
        }
    }
}
