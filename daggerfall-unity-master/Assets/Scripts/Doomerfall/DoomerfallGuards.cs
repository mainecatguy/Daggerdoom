// Doomerfall: Daggerfall's side of city guards. Runs only in a bridge session.
//
// Daggerfall still spawns its guards as usual. PlayerEntity.SpawnCityGuard reports each one through Spawned. This
// makes that copy inert (no motor, senses, or attack, on top of the bridge's DisableAI) and tells Doom, which runs a
// hostile bot in its place. Guards spawned in one frame are one group. When Doom reports a guard's bot dead, its
// Daggerfall copy is removed. A guard id is tag (3 bits, value 4) | spawn serial (61).
// Only interior spawns are relayed for now; others are logged and stay inert.

using System.Collections.Generic;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallGuards : MonoBehaviour
    {
        const float DoomPerDaggerfall = 0.75f;

        /// <summary>Set only in a bridge session. PlayerEntity calls it for each guard it spawns.</summary>
        public static System.Action<GameObject> Spawned;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly List<GameObject> pending = new List<GameObject>();
        readonly Dictionary<ulong, GameObject> copies = new Dictionary<ulong, GameObject>();
        readonly Dictionary<ulong, int> corpses = new Dictionary<ulong, int>(); // EnemyDeath's corpse texture, taken at spawn
        // Guard ids end up in saves (a kept corpse is keyed by its guard's id), so the serial starts from the clock: a new
        // session never reuses an id an earlier session saved.
        ulong serial = (ulong)System.DateTime.UtcNow.Ticks;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            Spawned = OnSpawned;
        }

        void OnDestroy()
        {
            Spawned = null;
        }

        void OnSpawned(GameObject guard)
        {
            MakeInert(guard);
            pending.Add(guard);
        }

        internal static void MakeInert(GameObject guard)
        {
            EnemyMotor motor = guard.GetComponent<EnemyMotor>();
            if (motor) motor.enabled = false;
            EnemySenses senses = guard.GetComponent<EnemySenses>();
            if (senses) senses.enabled = false;
            EnemyAttack attack = guard.GetComponent<EnemyAttack>();
            if (attack) attack.enabled = false;
        }

        void LateUpdate()
        {
            if (pending.Count == 0)
                return;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            Transform space = peer.worldContext == Dfb.WORLD_INTERIOR ? sync.ItemSpace(ref peer) : null;
            if (!space)
            {
                bridge.LogLine(string.Format("guards: {0} spawned in context {1}, not relayed (only interiors are), Daggerfall's copies stay inert", pending.Count, peer.worldContext));
                pending.Clear();
                return;
            }
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            for (int i = 0; i < pending.Count; i++)
            {
                GameObject guard = pending[i];
                if (!guard)
                    continue;
                ulong id = ((ulong)Dfb.GUARD_TAG << 61) | (++serial & ((1UL << 61) - 1));
                copies[id] = guard;
                corpses[id] = CorpseTexture(guard);
                Vector3 local = space.InverseTransformPoint(guard.transform.position);
                DfbEvent e = default(DfbEvent);
                e.kind = Dfb.KIND_GUARD_SPAWN;
                e.tic = (uint)Time.frameCount;
                e.guardSpawn.id = id;
                e.guardSpawn.context = peer.worldContext;
                e.guardSpawn.target = peer.spaceTarget;
                e.guardSpawn.x = local.x * units;
                e.guardSpawn.y = local.z * units;
                e.guardSpawn.mobileType = (ushort)MobileTypes.Knight_CityWatch;
                e.guardSpawn.index = (ushort)i;
                e.guardSpawn.count = (ushort)pending.Count;
                bridge.Send(ref e);
                bridge.LogLine(string.Format("guards: sent {0:x16} ({1} of {2}) at doom {3:F1},{4:F1} target {5}, corpse texture {6}", id, i + 1, pending.Count, e.guardSpawn.x, e.guardSpawn.y, peer.spaceTarget, corpses[id]));
            }
            pending.Clear();
        }

        // The corpse texture of a guard's Daggerfall copy, as EnemyDeath picks it (from DaggerfallEnemy.MobileUnit). If the
        // copy has no unit, the city watch's own entry in EnemyBasics.
        static int CorpseTexture(GameObject guard)
        {
            DaggerfallEnemy enemy = guard.GetComponent<DaggerfallEnemy>();
            MobileUnit unit = enemy ? enemy.MobileUnit : null;
            MobileEnemy mobile = unit ? unit.Enemy : CityWatch();
            return mobile.Gender == MobileGender.Female && mobile.FemaleCorpseTexture != 0 ? mobile.FemaleCorpseTexture : mobile.CorpseTexture;
        }

        static MobileEnemy CityWatch()
        {
            foreach (MobileEnemy e in EnemyBasics.Enemies)
                if (e.ID == (int)MobileTypes.Knight_CityWatch)
                    return e;
            return default(MobileEnemy);
        }

        // The corpse image of that guard, taken from its Daggerfall copy when it was sent. A guard this session did not
        // send (none should outlive a load, but in case) lies as the city watch.
        internal void CorpseOf(ulong id, out int archive, out int record)
        {
            int texture;
            if (!corpses.TryGetValue(id, out texture))
            {
                MobileEnemy watch = CityWatch();
                texture = watch.CorpseTexture;
            }
            EnemyBasics.ReverseCorpseTexture(texture, out archive, out record);
        }

        internal void OnDeath(ulong id)
        {
            GameObject guard;
            if (!copies.TryGetValue(id, out guard))
            {
                bridge.LogLine(string.Format("guards: death {0:x16} has no Daggerfall copy here", id));
                return;
            }
            copies.Remove(id);
            corpses.Remove(id);
            if (guard)
                Destroy(guard);
            bridge.LogLine(string.Format("guards: death {0:x16}, removed Daggerfall's copy", id));
        }
    }
}
