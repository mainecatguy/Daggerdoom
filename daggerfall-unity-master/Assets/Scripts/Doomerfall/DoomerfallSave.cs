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
        const float SettleSeconds = 5f, DoneSeconds = 15f, LoadSeconds = 20f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallHp hp;
        bool busy, pausedBySave, testFail, loading, loadRestored;
        uint activeTxn;
        float doneDeadline;

        internal DoomerfallItems Items { get; set; }
        internal DoomerfallMonsters Monsters { get; set; }
        internal DoomerfallLocations Locations { get; set; }
        internal DoomerfallTownspeople Townspeople { get; set; }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallHp playerHp, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            hp = playerHp;
            int fail = Array.IndexOf(args, "-dfsavetestfail");
            testFail = fail >= 0 && fail + 1 < args.Length && args[fail + 1] == "df_write";
            DoomerfallSaveTest.Attach(this, owner, positionSync, args); // Test only: -dfplainsavetest, -dfloadsavetest
        }

        public void OnRequest(uint txn, uint hpSentThrough)
        {
            if (busy)
            {
                Reply(txn, Dfb.SAVE_REFUSED, 0, 0);
                return;
            }
            string refusal = RefusalReason(hpSentThrough);
            if (refusal != null)
            {
                bridge.LogLine("save " + txn + ": refused, " + refusal);
                Reply(txn, Dfb.SAVE_REFUSED, 0, 0);
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

        // Doom is frozen and has checked the bundle. Nothing is destroyed until this half is checked too.
        public void OnLoadRequest(uint txn, int expectHp, int expectMax, int expectX, int expectZ)
        {
            string refusal = null;
            string folder = ReadStagingFolder();
            int health = 0, maxHealth = 0, x = 0, z = 0;
            SaveLoadManager saves = GameManager.HasInstance ? GameManager.Instance.SaveLoadManager : null;
            if (busy || loading)
                refusal = "another save or load is running";
            else if (saves == null || !saves.IsReady() || saves.LoadInProgress)
                refusal = "Daggerfall is not ready";
            else if (folder == null)
                refusal = "no staging folder";
            else if (!saves.CheckFolderForLoad(folder, out health, out maxHealth, out x, out z, out refusal))
                refusal = "bad Daggerfall save: " + refusal;
            else if (health != expectHp || maxHealth != expectMax || x != expectX || z != expectZ)
                refusal = string.Format("the halves do not match: save has hp {0}/{1} at {2},{3}, manifest has hp {4}/{5} at {6},{7}", health, maxHealth, x, z, expectHp, expectMax, expectX, expectZ);
            if (refusal != null)
            {
                bridge.LogLine("load " + txn + ": refused, " + refusal);
                Reply(txn, Dfb.SAVE_REFUSED, 0, 0, Dfb.KIND_LOAD_READY);
                return;
            }
            loading = true;
            sync.LoadRunning = true;
            loadRestored = false;
            activeTxn = txn;
            bridge.LogLine("load " + txn + ": restoring Daggerfall from the bundle");
            StartCoroutine(RunLoad(txn, folder, saves));
        }

        void LoadFinished(SaveData_v1 data)
        {
            loadRestored = true;
        }

        IEnumerator RunLoad(uint txn, string folder, SaveLoadManager saves)
        {
            float deadline = Time.unscaledTime + LoadSeconds;
            SaveLoadManager.OnLoad += LoadFinished;
            GameManager.Instance.DisableAI = true;
            Items.ReadLedger(folder);
            Monsters.ReadLedger(folder);
            Locations.ReadLedger(folder);
            Townspeople.ReadLedger(folder);
            bool started = saves.LoadFromFolder(folder);
            while (started && !loadRestored && Time.unscaledTime < deadline)
                yield return null;
            while (started && loadRestored && !sync.PositionSettled && Time.unscaledTime < deadline)
                yield return null;
            SaveLoadManager.OnLoad -= LoadFinished;

            bool settled = started && loadRestored && sync.PositionSettled;
            GameManager.Instance.PauseGame(true); // Held until Doom has restored its half too.
            if (!settled)
            {
                saves.AbortLoadFromFolder();
                loading = false;
                sync.LoadRunning = false;
                bridge.LogLine("load " + txn + ": failed, Daggerfall's game is no longer valid");
                Reply(txn, Dfb.SAVE_FAILED, 0, 0, Dfb.KIND_LOAD_READY);
                yield break;
            }
            bridge.PublishNow();
            bridge.LogLine(string.Format("load {0}: Daggerfall ready, hp {1}/{2}, position {3},{4}", txn, GameManager.Instance.PlayerEntity.CurrentHealth,
                GameManager.Instance.PlayerEntity.MaxHealth, GameManager.Instance.PlayerGPS.WorldX, GameManager.Instance.PlayerGPS.WorldZ));
            Reply(txn, Dfb.SAVE_OK, 0, 0, Dfb.KIND_LOAD_READY);
        }

        public void OnLoadDone(uint txn, bool restored)
        {
            if (!loading || txn != activeTxn)
                return;
            loading = false;
            sync.LoadRunning = false;
            if (!restored)
            {
                bridge.LogLine("load " + txn + ": Doom could not restore, holding paused");
                return;
            }
            GameManager.Instance.PauseGame(false);
            bridge.LogLine(string.Format("load {0}: both games ready, resuming, hp {1}, paused {2}", txn, GameManager.Instance.PlayerEntity.CurrentHealth, GameManager.IsGamePaused));
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_LOAD_RESUME;
            e.tic = (uint)Time.frameCount;
            e.saveDone.txn = txn;
            e.saveDone.committed = 1;
            bridge.Send(ref e);
        }

        // Doom's title screen: nothing in Daggerfall may advance until a save is loaded.
        public void OnHold(bool hold)
        {
            if (loading || busy)
                return;
            GameManager.Instance.PauseGame(hold);
            bridge.LogLine("hold: Daggerfall " + (hold ? "paused at Doom's title" : "released"));
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
            bridge.LogLine("save " + activeTxn + ": resumed, paused " + GameManager.IsGamePaused + ", time scale " + Time.timeScale);
        }

        string RefusalReason(uint hpSentThrough)
        {
            if (!GameManager.HasInstance || !sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY)
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
                Items.WriteLedger(folder);
                Monsters.WriteLedger(folder);
                Locations.WriteLedger(folder);
                Townspeople.WriteLedger(folder);
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
            bridge.LogLine(string.Format("save {0}: wrote {1} files, {2} bytes, hp {3}, position {4},{5}, Doom items {6}", txn, files, bytes,
                GameManager.Instance.PlayerEntity.CurrentHealth, GameManager.Instance.PlayerGPS.WorldX, GameManager.Instance.PlayerGPS.WorldZ,
                DoomerfallHotkeys.DoomItemList(GameManager.Instance.PlayerEntity.Items)));
            doneDeadline = Time.unscaledTime + DoneSeconds;
            Reply(txn, Dfb.SAVE_OK, files, bytes);
        }

        string ReadStagingFolder()
        {
            byte[] data = new byte[4096];
            uint size, version;
            if (DfbNative.dfb_bulk_read(bridge.Session, Dfb.SAVE_PATH_SLOT, data, (uint)data.Length, out size, out version) != 1 || size < 2)
                return null;
            string folder = Encoding.UTF8.GetString(data, 0, (int)size - 1);
            return folder.EndsWith(".dfstage", StringComparison.Ordinal) && Directory.Exists(folder) ? folder : null;
        }

        void Fail(uint txn, string why)
        {
            bridge.LogLine("save " + txn + ": failed, " + why);
            Reply(txn, Dfb.SAVE_FAILED, 0, 0);
            Resume();
        }

        void Reply(uint txn, uint status, int files, long bytes, ushort kind = Dfb.KIND_SAVE_PREPARED)
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            PlayerGPS gps = GameManager.HasInstance ? GameManager.Instance.PlayerGPS : null;
            DfbEvent e = default(DfbEvent);
            e.kind = kind;
            e.tic = (uint)Time.frameCount;
            e.saveReply.txn = txn;
            e.saveReply.status = status;
            if (player != null)
            {
                e.saveReply.hpCurrent = player.CurrentHealth;
                e.saveReply.hpMax = player.MaxHealth;
            }
            e.saveReply.hpApplied = hp.Applied;
            e.saveReply.fileCount = (uint)files;
            if (gps != null)
            {
                e.saveReply.worldX = gps.WorldX;
                e.saveReply.worldZ = gps.WorldZ;
            }
            e.saveReply.totalBytes = (ulong)bytes;
            bridge.Send(ref e);
        }
    }
}
