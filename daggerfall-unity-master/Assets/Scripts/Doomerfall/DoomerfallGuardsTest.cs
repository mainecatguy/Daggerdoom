// Doomerfall: test only, with -dfguardtest. Once Doom and Daggerfall are both inside an open shop, tavern, or house,
// it calls PlayerEntity.SpawnCityGuards(true), the same call a detected theft makes, then logs Daggerfall's HP and
// its guard copies every two seconds, so a run shows whether Daggerfall's copies act on the player.

using DaggerfallWorkshop.Game.Entity;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallGuardsTest : MonoBehaviour
    {
        const float DelaySeconds = 3f, ReportSeconds = 2f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        float insideSince = -1, nextReport;
        bool spawned;
        int startHealth;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
        }

        void Update()
        {
            if (!GameManager.HasInstance || !sync.InGame)
                return;
            GameManager game = GameManager.Instance;
            if (!spawned)
            {
                DfbUzState peer;
                bridge.ReadPeerState(out peer);
                PlayerEnterExit enter = game.PlayerEnterExit;
                bool ready = peer.worldContext == Dfb.WORLD_INTERIOR && sync.ItemSpace(ref peer) &&
                    (enter.IsPlayerInsideOpenShop || enter.IsPlayerInsideTavern || enter.IsPlayerInsideResidence);
                if (!ready)
                {
                    insideSince = -1;
                    return;
                }
                if (insideSince < 0)
                    insideSince = Time.unscaledTime;
                if (Time.unscaledTime - insideSince < DelaySeconds)
                    return;
                spawned = true;
                startHealth = game.PlayerEntity.CurrentHealth;
                game.PlayerEntity.SpawnCityGuards(true);
                bridge.LogLine(string.Format("guardtest: called SpawnCityGuards(true) inside, open shop {0}, health {1}", enter.IsPlayerInsideOpenShop, startHealth));
                nextReport = Time.unscaledTime + ReportSeconds;
                return;
            }
            if (Time.unscaledTime < nextReport)
                return;
            nextReport = Time.unscaledTime + ReportSeconds;
            int guards = 0, active = 0;
            float nearest = float.MaxValue;
            Vector3 player = game.PlayerObject.transform.position;
            foreach (DaggerfallEntityBehaviour behaviour in FindObjectsOfType<DaggerfallEntityBehaviour>())
            {
                EnemyEntity enemy = behaviour.Entity as EnemyEntity;
                if (enemy == null || enemy.MobileEnemy.ID != (int)MobileTypes.Knight_CityWatch)
                    continue;
                guards++;
                EnemyMotor motor = behaviour.GetComponent<EnemyMotor>();
                EnemyAttack attack = behaviour.GetComponent<EnemyAttack>();
                if ((motor && motor.enabled) || (attack && attack.enabled))
                    active++;
                nearest = Mathf.Min(nearest, Vector3.Distance(player, behaviour.transform.position));
            }
            bridge.LogLine(string.Format("guardtest: health {0} (start {1}), guard copies {2}, with motor or attack enabled {3}, nearest {4:F1} m, DisableAI {5}, top window {6}",
                game.PlayerEntity.CurrentHealth, startHealth, guards, active, guards > 0 ? nearest : 0, game.DisableAI,
                DaggerfallUI.UIManager.TopWindow != null ? DaggerfallUI.UIManager.TopWindow.GetType().Name : "none"));
        }
    }
}
