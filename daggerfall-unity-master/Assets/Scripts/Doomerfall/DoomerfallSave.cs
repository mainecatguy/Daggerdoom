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
        const ushort KindSavePrepared = 13, KindLoadReady = 16, KindLoadResume = 18;
        const uint StatusOk = 0, StatusRefused = 1, StatusFailed = 2, PathSlot = 4, PhasePlay = 3;
        const float SettleSeconds = 5f, DoneSeconds = 15f, LoadSeconds = 20f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallHp hp;
        bool busy, pausedBySave, testFail, loading, loadRestored;
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
            int load = Array.IndexOf(args, "-dfloadsavetest");
            if (load >= 0 && load + 1 < args.Length)
                StartCoroutine(LoadSaveTest(args[load + 1]));
        }

        // Test only: loads a Daggerfall half taken out of a bundle, through Daggerfall's normal loader.
        IEnumerator LoadSaveTest(string saveName)
        {
            while (!sync.InGame || sync.Phase != PhasePlay)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            saves.EnumerateSaves();
            SaveLoadManager.OnLoad += LogLoaded;
            saves.Load(GameManager.Instance.PlayerEntity.Name, saveName);
        }

        void LogLoaded(SaveData_v1 data)
        {
            SaveLoadManager.OnLoad -= LogLoaded;
            bridge.LogLine(string.Format("load test: loaded health {0}/{1}, position {2},{3}", GameManager.Instance.PlayerEntity.CurrentHealth,
                GameManager.Instance.PlayerEntity.MaxHealth, data.playerData.playerPosition.worldPosX, data.playerData.playerPosition.worldPosZ));
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
                Reply(txn, StatusRefused, 0, 0, KindLoadReady);
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
                Reply(txn, StatusFailed, 0, 0, KindLoadReady);
                yield break;
            }
            bridge.PublishNow();
            bridge.LogLine(string.Format("load {0}: Daggerfall ready, hp {1}/{2}, position {3},{4}", txn, GameManager.Instance.PlayerEntity.CurrentHealth,
                GameManager.Instance.PlayerEntity.MaxHealth, GameManager.Instance.PlayerGPS.WorldX, GameManager.Instance.PlayerGPS.WorldZ));
            Reply(txn, StatusOk, 0, 0, KindLoadReady);
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
            e.kind = KindLoadResume;
            e.tic = (uint)Time.frameCount;
            e.p0 = txn | 1UL << 32;
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

        void Reply(uint txn, uint status, int files, long bytes, ushort kind = KindSavePrepared)
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            PlayerGPS gps = GameManager.HasInstance ? GameManager.Instance.PlayerGPS : null;
            DfbEvent e = default(DfbEvent);
            e.kind = kind;
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
